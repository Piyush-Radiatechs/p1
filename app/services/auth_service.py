"""User registration and login. Passwords are stored as bcrypt hashes only."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import session_scope
from app.db.models import AccountRequest, Search, User
from app.exceptions import AuthError

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 72
ADMIN_USERNAME = "admin"


@dataclass(frozen=True)
class AuthUser:
    id: int
    username: str


@dataclass(frozen=True)
class UserSummary:
    id: int
    username: str
    created_at: datetime | None
    search_count: int


@dataclass(frozen=True)
class AccountRequestSummary:
    id: int
    username: str
    status: str
    created_at: datetime | None
    reviewed_at: datetime | None
    reviewed_by: str | None


def is_admin(username: str | None) -> bool:
    return _normalize_username(username or "") == ADMIN_USERNAME


def _require_admin(admin_username: str) -> str:
    if not is_admin(admin_username):
        raise AuthError("Admin access required.")
    return ADMIN_USERNAME


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
    """Create an approved user immediately. Used by tests and admin approval."""
    normalized = _validate_credentials(username, password)
    return _insert_user(normalized, hash_password(password))


def _insert_user(normalized: str, password_hash: str) -> AuthUser:
    try:
        with session_scope() as session:
            user = User(username=normalized, password_hash=password_hash)
            session.add(user)
            session.flush()
            return AuthUser(id=user.id, username=user.username)
    except IntegrityError as exc:
        raise AuthError("That username is already taken.") from exc


def request_account(username: str, password: str) -> None:
    """Store a pending signup. The user cannot log in until an admin approves it."""
    normalized = _validate_credentials(username, password)
    if normalized == ADMIN_USERNAME:
        raise AuthError("That username is reserved.")

    with session_scope() as session:
        existing_user = session.scalar(select(User).where(User.username == normalized))
        if existing_user is not None:
            raise AuthError("That username is already taken.")

        pending = session.scalar(
            select(AccountRequest).where(
                AccountRequest.username == normalized,
                AccountRequest.status == "pending",
            )
        )
        if pending is not None:
            raise AuthError("A request for this username is already waiting for admin approval.")

        session.add(
            AccountRequest(
                username=normalized,
                password_hash=hash_password(password),
                status="pending",
            )
        )


def login_user(username: str, password: str) -> AuthUser:
    normalized = _normalize_username(username)
    if not normalized or not password:
        raise AuthError("Enter a username and password.")

    with session_scope() as session:
        user = session.scalar(select(User).where(User.username == normalized))
        if user is not None:
            if not verify_password(password, user.password_hash):
                raise AuthError("Invalid username or password.")
            return AuthUser(id=user.id, username=user.username)

        pending = session.scalar(
            select(AccountRequest).where(
                AccountRequest.username == normalized,
                AccountRequest.status == "pending",
            )
        )
        if pending is not None:
            raise AuthError("This account is waiting for admin approval.")

        raise AuthError("Invalid username or password.")


def list_users(admin_username: str) -> list[UserSummary]:
    _require_admin(admin_username)
    with session_scope() as session:
        search_counts = dict(
            session.execute(
                select(Search.user_id, func.count(Search.id)).group_by(Search.user_id)
            ).all()
        )
        users = session.scalars(select(User).order_by(User.created_at.asc(), User.id.asc())).all()
        return [
            UserSummary(
                id=user.id,
                username=user.username,
                created_at=user.created_at,
                search_count=int(search_counts.get(user.id, 0)),
            )
            for user in users
        ]


def reset_user_password(admin_username: str, user_id: int, new_password: str) -> str:
    _require_admin(admin_username)
    if not new_password or len(new_password) < MIN_PASSWORD_LEN:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LEN} characters.")
    if len(new_password.encode("utf-8")) > MAX_PASSWORD_LEN:
        raise AuthError("Password is too long.")

    with session_scope() as session:
        user = session.get(User, user_id)
        if user is None:
            raise AuthError("User not found.")
        user.password_hash = hash_password(new_password)
        return user.username


def list_account_requests(
    admin_username: str,
    *,
    status: str | None = "pending",
) -> list[AccountRequestSummary]:
    _require_admin(admin_username)
    with session_scope() as session:
        stmt = select(AccountRequest).order_by(AccountRequest.created_at.desc())
        if status:
            stmt = stmt.where(AccountRequest.status == status)
        rows = session.scalars(stmt).all()
        return [
            AccountRequestSummary(
                id=row.id,
                username=row.username,
                status=row.status,
                created_at=row.created_at,
                reviewed_at=row.reviewed_at,
                reviewed_by=row.reviewed_by,
            )
            for row in rows
        ]


def approve_account_request(admin_username: str, request_id: int) -> AuthUser:
    admin = _require_admin(admin_username)
    with session_scope() as session:
        request = session.get(AccountRequest, request_id)
        if request is None:
            raise AuthError("Account request not found.")
        if request.status != "pending":
            raise AuthError("This request has already been reviewed.")

        existing = session.scalar(select(User).where(User.username == request.username))
        if existing is not None:
            raise AuthError("That username is already taken.")

        user = User(username=request.username, password_hash=request.password_hash)
        session.add(user)
        request.status = "approved"
        request.reviewed_at = datetime.now(timezone.utc)
        request.reviewed_by = admin
        session.flush()
        return AuthUser(id=user.id, username=user.username)


def reject_account_request(admin_username: str, request_id: int) -> str:
    admin = _require_admin(admin_username)
    with session_scope() as session:
        request = session.get(AccountRequest, request_id)
        if request is None:
            raise AuthError("Account request not found.")
        if request.status != "pending":
            raise AuthError("This request has already been reviewed.")
        request.status = "rejected"
        request.reviewed_at = datetime.now(timezone.utc)
        request.reviewed_by = admin
        return request.username
