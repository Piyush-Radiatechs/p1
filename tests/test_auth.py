"""Unit tests for registration and login."""

import pytest

from app.exceptions import AuthError
from app.services.auth_service import login_user, register_user


def test_register_and_login(db):
    created = register_user("Recruiter1", "secret123")
    assert created.username == "recruiter1"

    logged_in = login_user("recruiter1", "secret123")
    assert logged_in.id == created.id
    assert logged_in.username == "recruiter1"


def test_login_rejects_wrong_password(db):
    register_user("recruiter1", "secret123")
    with pytest.raises(AuthError, match="Invalid username or password"):
        login_user("recruiter1", "wrong-password")


def test_duplicate_username(db):
    register_user("recruiter1", "secret123")
    with pytest.raises(AuthError, match="already taken"):
        register_user("Recruiter1", "otherpass")


def test_username_validation(db):
    with pytest.raises(AuthError, match="Username"):
        register_user("ab", "secret123")
    with pytest.raises(AuthError, match="Password"):
        register_user("recruiter1", "short")
