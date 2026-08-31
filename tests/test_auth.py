"""Unit tests for registration, login, and admin account approval."""

import pytest

from app.exceptions import AuthError
from app.services.auth_service import (
    approve_account_request,
    list_account_requests,
    list_users,
    login_user,
    register_user,
    reject_account_request,
    request_account,
    reset_user_password,
)


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


def test_request_does_not_allow_login_until_approved(db):
    register_user("admin", "adminpass1")
    request_account("newhire", "secret123")

    with pytest.raises(AuthError, match="waiting for admin approval"):
        login_user("newhire", "secret123")

    pending = list_account_requests("admin", status="pending")
    assert len(pending) == 1
    assert pending[0].username == "newhire"

    approve_account_request("admin", pending[0].id)
    logged_in = login_user("newhire", "secret123")
    assert logged_in.username == "newhire"


def test_reject_account_request_blocks_login(db):
    register_user("admin", "adminpass1")
    request_account("newhire", "secret123")
    pending = list_account_requests("admin")
    reject_account_request("admin", pending[0].id)

    with pytest.raises(AuthError, match="Invalid username or password"):
        login_user("newhire", "secret123")


def test_non_admin_cannot_list_users(db):
    register_user("recruiter1", "secret123")
    with pytest.raises(AuthError, match="Admin access required"):
        list_users("recruiter1")


def test_admin_lists_users_without_passwords(db):
    register_user("admin", "adminpass1")
    register_user("recruiter1", "secret123")
    users = list_users("admin")
    assert [row.username for row in users] == ["admin", "recruiter1"]
    assert all(not hasattr(row, "password_hash") for row in users)


def test_admin_resets_password(db):
    register_user("admin", "adminpass1")
    user = register_user("recruiter1", "secret123")
    reset_user_password("admin", user.id, "newsecret1")

    with pytest.raises(AuthError, match="Invalid username or password"):
        login_user("recruiter1", "secret123")
    assert login_user("recruiter1", "newsecret1").username == "recruiter1"


def test_cannot_request_admin_username(db):
    with pytest.raises(AuthError, match="reserved"):
        request_account("admin", "secret123")
