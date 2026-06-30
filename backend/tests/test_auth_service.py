import pytest
from app.services.auth_service import AuthService


def test_password_hashing():
    auth = AuthService(jwt_secret="test", jwt_expire_minutes=60)
    password = "mysecretpassword"
    hashed = auth.hash_password(password)

    assert hashed != password
    assert auth.verify_password(password, hashed) is True
    assert auth.verify_password("wrongpassword", hashed) is False


def test_jwt_token_creation():
    auth = AuthService(jwt_secret="test-secret", jwt_expire_minutes=60)
    token = auth.create_access_token(user_id="user-123", role="admin")

    assert token is not None
    payload = auth.decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "admin"
