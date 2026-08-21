"""User registration and login. Passwords are stored as bcrypt hashes only."""

import re
from dataclasses import dataclass

import bcrypt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import session_scope
from app.db.models import User
from app.exceptions import AuthError

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 72


@dataclass(frozen=True)
class AuthUser:
    id: int
    username: str


def _normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def _validate_credentials(username: str, password: str) -> str:
    normalized = _normalize_username(username)
    if not USERNAME_RE.fullmatch(normalized):
        raise AuthError("Username must be 3–32 characters: letters, numbers, or underscores.")
    if not password or len(password) < MIN_PASSWORD_LEN:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LEN} characters.")
    if len(password.encode("utf-8")) > MAX_PASSWORD_LEN:
        raise AuthError("Password is too long.")
    return normalized


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def register_user(username: str, password: str) -> AuthUser:
    normalized = _validate_credentials(username, password)
    try:
        with session_scope() as session:
            user = User(username=normalized, password_hash=hash_password(password))
            session.add(user)
            session.flush()
            return AuthUser(id=user.id, username=user.username)
    except IntegrityError as exc:
        raise AuthError("That username is already taken.") from exc


def login_user(username: str, password: str) -> AuthUser:
    normalized = _normalize_username(username)
    if not normalized or not password:
        raise AuthError("Enter a username and password.")

    with session_scope() as session:
        user = session.scalar(select(User).where(User.username == normalized))
        if user is None or not verify_password(password, user.password_hash):
            raise AuthError("Invalid username or password.")
        return AuthUser(id=user.id, username=user.username)
