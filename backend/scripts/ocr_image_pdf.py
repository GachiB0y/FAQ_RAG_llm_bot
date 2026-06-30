#!/usr/bin/env python3
"""
OCR для картинок-PDF (где текст «отрисован», а не закодирован).

Рендерит каждую страницу PDF в PNG через PyMuPDF и шлёт в vision-LLM
(локальная llama3.2-vision через Ollama по умолчанию, либо vision-модель
через OpenRouter если задана OCR_PROVIDER=openrouter).

Результат сохраняется как .txt рядом с исходным PDF (или в OCR_OUTPUT).

Запуск:
    docker exec faq_rag_llm_bot-backend-1 python -u scripts/ocr_image_pdf.py
"""

import base64
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, "/app")

import fitz  # PyMuPDF
import httpx

# --- настройки ---
OCR_INPUT = Path(
    os.environ.get("OCR_INPUT", "/tmp/corpus/кратко-о-процессе-вступления.pdf")
)
OCR_OUTPUT = Path(
    os.environ.get("OCR_OUTPUT", str(OCR_INPUT.with_suffix(".txt")))
)
OCR_PROVIDER = os.environ.get("OCR_PROVIDER", "tesseract")  # tesseract | ollama | openrouter
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OCR_MODEL", "llama3.2-vision:11b")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get(
    "OCR_OR_MODEL", "google/gemma-4-31b-it:free"
)
PAGE_DPI = int(os.environ.get("OCR_DPI", "200"))  # 200 — хороший баланс
OCR_PROMPT = (
    "Это страница из русскоязычного документа Федерации Практической Стрельбы. "
    "Извлеки весь видимый текст в порядке чтения. Сохрани структуру: заголовки, "
    "пункты списка, абзацы. Не добавляй ничего от себя. Если страница не содержит "
    "читаемого текста — напиши '(пустая страница)'. Верни только текст, без "
    "комментариев и без markdown-обёрток."
)


def render_pdf_pages(pdf_path: Path, dpi: int) -> list[bytes]:
    """Возвращает список PNG-байтов — по одному на страницу."""
    pngs = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            pngs.append(pix.tobytes("png"))
    return pngs


def ocr_with_ollama(png_bytes: bytes) -> str:
    b64 = base64.b64encode(png_bytes).decode("ascii")
    r = httpx.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": OCR_PROMPT,
                    "images": [b64],
                }
            ],
            "stream": False,
            "options": {"temperature": 0},
        },
        timeout=600.0,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


def ocr_with_tesseract(png_bytes: bytes) -> str:
    """Tesseract OCR — локально, бесплатно, надёжно для отрендеренного текста."""
    import pytesseract
    from PIL import Image

    image = Image.open(io.BytesIO(png_bytes))
    return pytesseract.image_to_string(image, lang="rus+eng")


def ocr_with_openrouter(png_bytes: bytes) -> str:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY не задан")
    b64 = base64.b64encode(png_bytes).decode("ascii")
    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/faq-rag-llm-bot",
            "X-Title": "FAQ RAG OCR",
        },
        json={
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": OCR_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
            "max_tokens": 4096,
            "temperature": 0,
        },
        timeout=120.0,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def main() -> None:
    if not OCR_INPUT.exists():
        raise FileNotFoundError(f"Не найден файл: {OCR_INPUT}")

    print(f">> OCR target: {OCR_INPUT.name}")
    print(f">> Provider:   {OCR_PROVIDER}")
    print(f">> Model:      {OLLAMA_MODEL if OCR_PROVIDER == 'ollama' else OPENROUTER_MODEL}")
    print(f">> DPI:        {PAGE_DPI}")

    pages = render_pdf_pages(OCR_INPUT, PAGE_DPI)
    print(f">> Страниц:    {len(pages)}")

    ocr_fns = {
        "tesseract": ocr_with_tesseract,
        "ollama": ocr_with_ollama,
        "openrouter": ocr_with_openrouter,
    }
    if OCR_PROVIDER not in ocr_fns:
        raise ValueError(f"OCR_PROVIDER должен быть {list(ocr_fns)}, не {OCR_PROVIDER}")
    ocr_fn = ocr_fns[OCR_PROVIDER]

    texts = []
    for i, png in enumerate(pages, 1):
        print(f"   [{i}/{len(pages)}] OCR…", flush=True)
        text = ocr_fn(png).strip()
        texts.append(f"[Page {i}]\n{text}")
        print(f"      {len(text)} символов")

    full_text = "\n\n".join(texts)
    OCR_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OCR_OUTPUT.write_text(full_text, encoding="utf-8")
    print(f"\n>> Сохранено: {OCR_OUTPUT}  ({OCR_OUTPUT.stat().st_size} байт)")
    print("\n--- первые 500 символов на проверку ---")
    print(full_text[:500])


if __name__ == "__main__":
    main()
