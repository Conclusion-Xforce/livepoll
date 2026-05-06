import os

import bcrypt
from itsdangerous import URLSafeTimedSerializer

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
serializer = URLSafeTimedSerializer(SECRET_KEY)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_admin_token(session_id: str) -> str:
    return serializer.dumps({"session_id": session_id})


def verify_admin_token(token: str, max_age: int = 86400) -> str | None:
    try:
        data = serializer.loads(token, max_age=max_age)
        return data.get("session_id")
    except Exception:
        return None
