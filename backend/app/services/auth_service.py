from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext


class AuthService:
    def __init__(self, jwt_secret: str, jwt_expire_minutes: int = 60):
        self.jwt_secret = jwt_secret
        self.jwt_expire_minutes = jwt_expire_minutes
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.algorithm = "HS256"

    def hash_password(self, password: str) -> str:
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)

    def create_access_token(
        self,
        user_id: str,
        role: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        expire = datetime.now(timezone.utc) + (
            expires_delta or timedelta(minutes=self.jwt_expire_minutes)
        )
        to_encode = {
            "sub": user_id,
            "role": role,
            "exp": expire,
            "type": "access"
        }
        return jwt.encode(to_encode, self.jwt_secret, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(days=7)
        to_encode = {
            "sub": user_id,
            "exp": expire,
            "type": "refresh"
        }
        return jwt.encode(to_encode, self.jwt_secret, algorithm=self.algorithm)

    def decode_token(self, token: str) -> Optional[dict]:
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.algorithm])
            return payload
        except JWTError:
            return None
