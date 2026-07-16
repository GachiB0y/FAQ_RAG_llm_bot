import logging
import re

logger = logging.getLogger(__name__)

# Явные атаки (RU+EN) → block. Компилируются один раз.
_BLOCK_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(the\s+)?above",
    r"forget\s+(all\s+)?(your\s+)?instructions",
    r"забудь\s+(все\s+)?(предыдущие\s+|свои\s+)?инструкц",
    r"игнорируй\s+(все\s+)?(предыдущие\s+)?инструкц",
    r"system\s+prompt",
    r"систем(ный|ную)\s+промпт",
    r"твой\s+(системный\s+)?промпт",
    r"act\s+as\s+(an?\s+)?(unrestricted|dan|jailbroken)",
    r"\bdan\b.*(mode|режим)",
    r"ты\s+теперь\s+\w+",
    r"веди\s+себя\s+как",
    r"pretend\s+(you|to\s+be)",
    r"без\s+(всяких\s+)?ограничен",
]

# Подозрительные триггеры → unsure (уходит в LLM-стадию, если она включена).
_SUSPICIOUS_PATTERNS = [
    r"инструкц",
    r"instruction",
    r"prompt",
    r"промпт",
    r"правила\s+(работы|поведения)",
]


class InjectionGuard:
    """Двухступенчатый фильтр. Stage 1 — правила (block/unsure/clean).
    Stage 2 — LLM (только на unsure), опционален; сбой/отсутствие → fail-open (clean)."""

    def __init__(self, classifier=None):
        self.classifier = classifier  # async (text)->bool | None
        self._block = [re.compile(p, re.IGNORECASE) for p in _BLOCK_PATTERNS]
        self._suspicious = [re.compile(p, re.IGNORECASE) for p in _SUSPICIOUS_PATTERNS]

    def classify_rules(self, text: str) -> str:
        for pat in self._block:
            if pat.search(text):
                return "block"
        for pat in self._suspicious:
            if pat.search(text):
                return "unsure"
        return "clean"

    async def is_injection(self, text: str) -> bool:
        verdict = self.classify_rules(text)
        if verdict == "block":
            return True
        if verdict == "clean":
            return False
        # unsure → Stage 2
        if self.classifier is None:
            return False
        try:
            return bool(await self.classifier(text))
        except Exception as exc:
            logger.warning("injection LLM-classifier failed → fail-open (clean): %s", exc)
            return False
