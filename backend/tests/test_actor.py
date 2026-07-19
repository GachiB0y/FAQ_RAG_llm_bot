from app.api.v1.actor import resolve_actor_id

BOT = "bot@example.com"


def test_bot_user_with_header_uses_telegram_namespace():
    assert resolve_actor_id(BOT, "u-1", "12345", BOT) == "tg:12345"


def test_web_user_with_header_ignores_header():
    assert resolve_actor_id("web@example.com", "u-1", "12345", BOT) == "u-1"


def test_no_header_returns_user_id():
    assert resolve_actor_id(BOT, "u-1", None, BOT) == "u-1"


def test_empty_header_returns_user_id():
    assert resolve_actor_id(BOT, "u-1", "", BOT) == "u-1"


def test_bot_email_unset_returns_user_id():
    assert resolve_actor_id(BOT, "u-1", "12345", None) == "u-1"
