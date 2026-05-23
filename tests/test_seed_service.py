from unittest.mock import patch

import pytest

from app.auth import verify_password
from app.constants import ROLE_METHODIST, ROLE_TEACHER
from app.models import Course, CourseTeacher, User, UserRole
from app.services.seed_service import seed_demo_data


@pytest.fixture(autouse=True)
def patch_session_local(monkeypatch):
    from tests.conftest import TestSessionLocal

    monkeypatch.setattr(
        "app.services.seed_service.SessionLocal", TestSessionLocal
    )


class TestSeedDemoData:
    def test_creates_demo_users(self, db_session):
        seed_demo_data()

        users = db_session.query(User).all()
        emails = {u.email for u in users}
        assert len(users) == 3
        assert "teacher1@example.com" in emails
        assert "julia@example.com" in emails
        assert "dmitry@example.com" in emails

    def test_creates_users_with_hashed_passwords(self, db_session):
        seed_demo_data()

        user = db_session.query(User).filter(User.email == "teacher1@example.com").first()
        assert user is not None
        assert verify_password("password123", user.password_hash)

    def test_assigns_correct_roles(self, db_session):
        seed_demo_data()

        teacher = db_session.query(User).filter(User.email == "teacher1@example.com").first()
        roles = {role.role for role in teacher.roles}
        assert roles == {ROLE_TEACHER, ROLE_METHODIST}

        julia = db_session.query(User).filter(User.email == "julia@example.com").first()
        julia_roles = {role.role for role in julia.roles}
        assert julia_roles == {ROLE_TEACHER}

        dmitry = db_session.query(User).filter(User.email == "dmitry@example.com").first()
        dmitry_roles = {role.role for role in dmitry.roles}
        assert dmitry_roles == {ROLE_METHODIST}

    def test_is_idempotent(self, db_session):
        seed_demo_data()
        seed_demo_data()

        users = db_session.query(User).all()
        assert len(users) == 3

    def test_assigns_main_teacher_to_existing_courses(self, db_session):
        course = Course(title="Physics", description="Physics course")
        db_session.add(course)
        db_session.commit()

        seed_demo_data()

        teacher = db_session.query(User).filter(User.email == "teacher1@example.com").first()
        assignments = (
            db_session.query(CourseTeacher)
            .filter(CourseTeacher.user_id == teacher.id)
            .all()
        )
        assert len(assignments) == 1
        assert assignments[0].course_id == course.id

    def test_does_not_duplicate_assignments(self, db_session):
        course = Course(title="Math", description="Math course")
        db_session.add(course)
        db_session.commit()

        teacher = User(
            name="Pre-existing Teacher",
            email="teacher1@example.com",
            password_hash="hash",
        )
        db_session.add(teacher)
        db_session.commit()

        db_session.add(
            CourseTeacher(course_id=course.id, user_id=teacher.id)
        )
        db_session.commit()

        seed_demo_data()

        assignments = (
            db_session.query(CourseTeacher)
            .filter(CourseTeacher.course_id == course.id)
            .all()
        )
        assert len(assignments) == 1
