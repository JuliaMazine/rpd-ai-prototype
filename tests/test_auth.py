import pytest
from fastapi import HTTPException
from starlette.datastructures import MutableHeaders
from starlette.requests import Request

from app.auth import (
    get_active_role,
    get_current_user,
    get_user_roles,
    hash_password,
    require_course_teacher,
    require_draft_teacher,
    require_login,
    require_role,
    user_is_course_teacher,
    verify_password,
)
from app.constants import ROLE_METHODIST, ROLE_TEACHER
from app.models import Draft, UserRole


class TestPasswordHashing:
    def test_hash_and_verify_success(self):
        password = "my_secure_password"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_hash_and_verify_failure(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_hash_produces_different_outputs(self):
        password = "same_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2

    def test_hash_empty_password(self):
        hashed = hash_password("")
        assert verify_password("", hashed) is True


class TestGetUserRoles:
    def test_user_with_multiple_roles(self, db_session, sample_user):
        db_session.add(UserRole(user_id=sample_user.id, role="USER_TEACHER"))
        db_session.add(UserRole(user_id=sample_user.id, role="USER_METHODIST"))
        db_session.commit()

        roles = get_user_roles(sample_user)
        assert set(roles) == {"USER_TEACHER", "USER_METHODIST"}

    def test_user_with_single_role(self, db_session, sample_user):
        db_session.add(UserRole(user_id=sample_user.id, role="USER_TEACHER"))
        db_session.commit()

        roles = get_user_roles(sample_user)
        assert roles == ["USER_TEACHER"]

    def test_user_with_no_roles(self, sample_user):
        roles = get_user_roles(sample_user)
        assert roles == []


class TestGetCurrentUser:
    def test_returns_user_when_session_exists(self, db_session, sample_user):
        scope = {
            "type": "http",
            "session": {"user_id": sample_user.id},
        }
        request = Request(scope)
        user = get_current_user(request, db_session)
        assert user is not None
        assert user.id == sample_user.id

    def test_returns_none_when_no_session(self, db_session):
        scope = {"type": "http", "session": {}}
        request = Request(scope)
        user = get_current_user(request, db_session)
        assert user is None

    def test_returns_none_for_invalid_user_id(self, db_session):
        scope = {"type": "http", "session": {"user_id": 99999}}
        request = Request(scope)
        user = get_current_user(request, db_session)
        assert user is None


class TestRequireLogin:
    def test_raises_401_when_not_logged_in(self, db_session):
        scope = {"type": "http", "session": {}}
        request = Request(scope)
        with pytest.raises(HTTPException) as exc:
            require_login(request, db_session)
        assert exc.value.status_code == 401

    def test_returns_user_when_logged_in(self, db_session, sample_user):
        scope = {"type": "http", "session": {"user_id": sample_user.id}}
        request = Request(scope)
        user = require_login(request, db_session)
        assert user.id == sample_user.id


class TestGetActiveRole:
    def test_returns_role_from_session(self):
        scope = {"type": "http", "session": {"active_role": "USER_TEACHER"}}
        request = Request(scope)
        assert get_active_role(request) == "USER_TEACHER"

    def test_returns_none_when_no_role(self):
        scope = {"type": "http", "session": {}}
        request = Request(scope)
        assert get_active_role(request) is None


class TestRequireRole:
    def test_raises_401_when_not_logged_in(self, db_session):
        scope = {"type": "http", "session": {}}
        request = Request(scope)
        with pytest.raises(HTTPException) as exc:
            require_role(request, db_session, "USER_TEACHER")
        assert exc.value.status_code == 401

    def test_raises_403_when_inactive_role_mismatch(self, db_session, sample_teacher):
        scope = {
            "type": "http",
            "session": {"user_id": sample_teacher.id, "active_role": "USER_METHODIST"},
        }
        request = Request(scope)
        with pytest.raises(HTTPException) as exc:
            require_role(request, db_session, "USER_TEACHER")
        assert exc.value.status_code == 403

    def test_succeeds_when_role_matches(self, db_session, sample_teacher):
        scope = {
            "type": "http",
            "session": {"user_id": sample_teacher.id, "active_role": "USER_TEACHER"},
        }
        request = Request(scope)
        user = require_role(request, db_session, "USER_TEACHER")
        assert user.id == sample_teacher.id


class TestUserIsCourseTeacher:
    def test_teacher_assigned_to_course(self, db_session, sample_teacher, sample_course):
        result = user_is_course_teacher(sample_teacher.id, sample_course.id, db_session)
        assert result is True

    def test_teacher_not_assigned(self, db_session):
        from app.models import User

        other = User(name="Other", email="other@test.com", password_hash="hash")
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)

        result = user_is_course_teacher(other.id, 1, db_session)
        assert result is False


class TestRequireCourseTeacher:
    def test_succeeds_for_assigned_teacher(self, db_session, sample_teacher, sample_course):
        scope = {
            "type": "http",
            "session": {"user_id": sample_teacher.id, "active_role": "USER_TEACHER"},
        }
        request = Request(scope)
        user = require_course_teacher(request, db_session, sample_course.id)
        assert user.id == sample_teacher.id

    def test_raises_403_for_unassigned_teacher(self, db_session):
        from app.models import User

        other = User(name="Other", email="other@test.com", password_hash="hash")
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)
        db_session.add(UserRole(user_id=other.id, role="USER_TEACHER"))
        db_session.commit()

        scope = {
            "type": "http",
            "session": {"user_id": other.id, "active_role": "USER_TEACHER"},
        }
        request = Request(scope)
        with pytest.raises(HTTPException) as exc:
            require_course_teacher(request, db_session, 999)
        assert exc.value.status_code == 403


class TestRequireDraftTeacher:
    def test_succeeds_for_own_draft(self, db_session, sample_teacher, sample_draft):
        scope = {
            "type": "http",
            "session": {"user_id": sample_teacher.id, "active_role": "USER_TEACHER"},
        }
        request = Request(scope)
        user, draft = require_draft_teacher(request, db_session, sample_draft.id)
        assert user.id == sample_teacher.id
        assert draft.id == sample_draft.id

    def test_raises_404_for_nonexistent_draft(self, db_session, sample_teacher):
        scope = {
            "type": "http",
            "session": {"user_id": sample_teacher.id, "active_role": "USER_TEACHER"},
        }
        request = Request(scope)
        with pytest.raises(HTTPException) as exc:
            require_draft_teacher(request, db_session, 99999)
        assert exc.value.status_code == 404
