from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Course, CourseTeacher, Draft, Material, User, UserRole


@pytest.fixture
def session_client(client, db_session):
    """Client authenticated as a teacher, with db_session available for setup."""
    from app.auth import hash_password

    user = User(
        name="Test Teacher",
        email="test_teacher@test.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserRole(user_id=user.id, role="USER_TEACHER"))
    db_session.commit()

    client.post(
        "/login",
        data={"email": "test_teacher@test.com", "password": "password123"},
    )
    return client, db_session, user


@pytest.fixture
def methodist_session_client(client, db_session):
    """Client authenticated as a methodist, with db_session available for setup."""
    from app.auth import hash_password

    user = User(
        name="Test Methodist",
        email="test_methodist@test.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserRole(user_id=user.id, role="USER_METHODIST"))
    db_session.commit()

    client.post(
        "/login",
        data={"email": "test_methodist@test.com", "password": "password123"},
    )
    return client, db_session, user


class TestAuthRoutes:
    def test_root_redirects_to_login(self, client):
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_login_page_returns_html(self, client):
        response = client.get("/login")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_logout_clears_session(self, client, db_session):
        from app.auth import hash_password

        user = User(
            name="Logout User",
            email="logout@test.com",
            password_hash=hash_password("password123"),
        )
        db_session.add(user)
        db_session.commit()
        db_session.add(UserRole(user_id=user.id, role="USER_TEACHER"))
        db_session.commit()

        client.post(
            "/login",
            data={"email": "logout@test.com", "password": "password123"},
        )
        response = client.get("/logout", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_register_creates_user_and_redirects(self, client, db_session):
        response = client.post(
            "/register",
            data={
                "name": "New User",
                "email": "new@test.com",
                "password": "password123",
                "roles": ["USER_TEACHER"],
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/dashboard" in response.headers["location"]

        user = db_session.query(User).filter(User.email == "new@test.com").first()
        assert user is not None
        assert user.name == "New User"

    def test_register_validates_password_length(self, client):
        response = client.post(
            "/register",
            data={
                "name": "Test",
                "email": "test@test.com",
                "password": "short",
                "roles": ["USER_TEACHER"],
            },
        )
        assert response.status_code == 400

    def test_register_rejects_duplicate_email(self, client, db_session):
        user = User(name="Existing", email="existing@test.com", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/register",
            data={
                "name": "Duplicate",
                "email": "existing@test.com",
                "password": "password123",
                "roles": ["USER_TEACHER"],
            },
        )
        assert response.status_code == 400

    def test_login_success(self, client, db_session):
        from app.auth import hash_password

        user = User(
            name="Login User",
            email="login@test.com",
            password_hash=hash_password("password123"),
        )
        db_session.add(user)
        db_session.commit()
        db_session.add(UserRole(user_id=user.id, role="USER_TEACHER"))
        db_session.commit()

        response = client.post(
            "/login",
            data={"email": "login@test.com", "password": "password123"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_login_failure(self, client, db_session):
        from app.auth import hash_password

        user = User(
            name="Fail User",
            email="fail@test.com",
            password_hash=hash_password("correct_password"),
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/login",
            data={"email": "fail@test.com", "password": "wrong_password"},
        )
        assert response.status_code == 401


class TestCourseRoutes:
    def test_create_course(self, session_client):
        client, db_session, user = session_client
        response = client.post(
            "/ui/courses",
            data={"title": "New Course", "description": "A new course"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        course = db_session.query(Course).filter(Course.title == "New Course").first()
        assert course is not None
        assert course.description == "A new course"

    def test_create_course_creates_teacher_assignment(self, session_client):
        client, db_session, user = session_client
        client.post(
            "/ui/courses",
            data={"title": "Assigned Course", "description": ""},
            follow_redirects=False,
        )
        course = (
            db_session.query(Course)
            .filter(Course.title == "Assigned Course")
            .first()
        )
        assignment = (
            db_session.query(CourseTeacher)
            .filter(
                CourseTeacher.course_id == course.id,
                CourseTeacher.user_id == user.id,
            )
            .first()
        )
        assert assignment is not None

    def test_upload_material(self, session_client):
        client, db_session, user = session_client
        course = Course(title="Upload Course", description="")
        db_session.add(course)
        db_session.commit()
        db_session.add(CourseTeacher(course_id=course.id, user_id=user.id))
        db_session.commit()

        response = client.post(
            f"/ui/courses/{course.id}/materials",
            files={"file": ("lecture.txt", b"Course material content", "text/plain")},
            follow_redirects=False,
        )
        assert response.status_code == 303

        material = (
            db_session.query(Material)
            .filter(Material.course_id == course.id)
            .first()
        )
        assert material is not None
        assert material.filename == "lecture.txt"
        assert material.extracted_text == "Course material content"

    def test_upload_material_rejects_invalid_extension(self, session_client):
        client, db_session, user = session_client
        course = Course(title="Ext Course", description="")
        db_session.add(course)
        db_session.commit()
        db_session.add(CourseTeacher(course_id=course.id, user_id=user.id))
        db_session.commit()

        response = client.post(
            f"/ui/courses/{course.id}/materials",
            files={"file": ("image.png", b"fake_png", "image/png")},
        )
        assert response.status_code == 400

    def test_generate_draft(self, session_client):
        client, db_session, user = session_client
        course = Course(title="Draft Course", description="")
        db_session.add(course)
        db_session.commit()
        db_session.add(CourseTeacher(course_id=course.id, user_id=user.id))
        db_session.commit()

        material = Material(
            course_id=course.id,
            filename="test.txt",
            file_path="/tmp/test.txt",
            extracted_text="Material content for draft.",
        )
        db_session.add(material)
        db_session.commit()

        with patch(
            "app.routes.course.generate_draft_text",
            return_value="Generated draft content.",
        ):
            response = client.post(
                f"/ui/courses/{course.id}/generate-draft",
                follow_redirects=False,
            )
            assert response.status_code == 303

        db_session.expire_all()
        draft = (
            db_session.query(Draft)
            .filter(Draft.course_id == course.id)
            .first()
        )
        assert draft is not None
        assert draft.content == "Generated draft content."
        assert draft.status == "DRAFT_EDITING"

    def test_generate_draft_fails_without_materials(self, session_client):
        client, db_session, user = session_client
        course = Course(title="Empty Course", description="")
        db_session.add(course)
        db_session.commit()
        db_session.add(CourseTeacher(course_id=course.id, user_id=user.id))
        db_session.commit()

        response = client.post(
            f"/ui/courses/{course.id}/generate-draft",
        )
        assert response.status_code == 400


class TestDraftRoutes:
    def test_view_draft(self, session_client):
        client, db_session, user = session_client
        course = Course(title="View Draft Course", description="")
        db_session.add(course)
        db_session.commit()
        db_session.add(CourseTeacher(course_id=course.id, user_id=user.id))
        db_session.commit()

        draft = Draft(
            course_id=course.id,
            name="Test Draft",
            content="Draft content here.",
            status="DRAFT_EDITING",
        )
        db_session.add(draft)
        db_session.commit()

        response = client.get(f"/drafts/{draft.id}/view")
        assert response.status_code == 200

    def test_edit_draft_page(self, session_client):
        client, db_session, user = session_client
        course = Course(title="Edit Draft Course", description="")
        db_session.add(course)
        db_session.commit()
        db_session.add(CourseTeacher(course_id=course.id, user_id=user.id))
        db_session.commit()

        draft = Draft(
            course_id=course.id,
            name="Editable Draft",
            content="Original content.",
            status="DRAFT_EDITING",
        )
        db_session.add(draft)
        db_session.commit()

        response = client.get(f"/drafts/{draft.id}/edit")
        assert response.status_code == 200

    def test_save_draft_edit(self, session_client):
        client, db_session, user = session_client
        course = Course(title="Save Draft Course", description="")
        db_session.add(course)
        db_session.commit()
        db_session.add(CourseTeacher(course_id=course.id, user_id=user.id))
        db_session.commit()

        draft = Draft(
            course_id=course.id,
            name="Save Draft",
            content="Old content.",
            status="DRAFT_EDITING",
        )
        db_session.add(draft)
        db_session.commit()

        response = client.post(
            f"/ui/drafts/{draft.id}/edit",
            data={"content": "Updated draft content"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_submit_for_review(self, session_client):
        client, db_session, user = session_client
        course = Course(title="Submit Draft Course", description="")
        db_session.add(course)
        db_session.commit()
        db_session.add(CourseTeacher(course_id=course.id, user_id=user.id))
        db_session.commit()

        draft = Draft(
            course_id=course.id,
            name="Submit Draft",
            content="Content to review.",
            status="DRAFT_EDITING",
        )
        db_session.add(draft)
        db_session.commit()

        response = client.post(
            f"/ui/drafts/{draft.id}/submit-review",
            follow_redirects=False,
        )
        assert response.status_code == 303

        db_session.expire_all()
        updated = db_session.query(Draft).filter(Draft.id == draft.id).first()
        assert updated.status == "DRAFT_SUBMITTED_FOR_REVIEW"

    def test_download_docx(self, session_client):
        client, db_session, user = session_client
        course = Course(title="Download Course", description="")
        db_session.add(course)
        db_session.commit()
        db_session.add(CourseTeacher(course_id=course.id, user_id=user.id))
        db_session.commit()

        draft = Draft(
            course_id=course.id,
            name="Downloadable Draft",
            content="Content for docx.",
            status="DRAFT_EDITING",
        )
        db_session.add(draft)
        db_session.commit()

        response = client.get(f"/drafts/{draft.id}/download-docx")
        assert response.status_code == 200
        assert (
            response.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )


class TestReviewRoutes:
    def test_feedback_page(self, methodist_session_client):
        client, db_session, user = methodist_session_client
        course = Course(title="Feedback Course", description="")
        db_session.add(course)
        db_session.commit()

        draft = Draft(
            course_id=course.id,
            name="Feedback Draft",
            content="Content for feedback.",
            status="DRAFT_SUBMITTED_FOR_REVIEW",
        )
        db_session.add(draft)
        db_session.commit()

        response = client.get(f"/drafts/{draft.id}/feedback")
        assert response.status_code == 200

    def test_save_feedback(self, methodist_session_client):
        client, db_session, user = methodist_session_client
        course = Course(title="Save Feedback Course", description="")
        db_session.add(course)
        db_session.commit()

        draft = Draft(
            course_id=course.id,
            name="Save Feedback Draft",
            content="Content.",
            status="DRAFT_SUBMITTED_FOR_REVIEW",
        )
        db_session.add(draft)
        db_session.commit()

        response = client.post(
            f"/ui/drafts/{draft.id}/feedback",
            data={"feedback": "Improve section 2."},
            follow_redirects=False,
        )
        assert response.status_code == 303

        db_session.expire_all()
        updated = db_session.query(Draft).filter(Draft.id == draft.id).first()
        assert updated.feedback == "Improve section 2."

    def test_mark_feedback_given(self, methodist_session_client):
        client, db_session, user = methodist_session_client
        course = Course(title="Mark Feedback Course", description="")
        db_session.add(course)
        db_session.commit()

        draft = Draft(
            course_id=course.id,
            name="Mark Feedback Draft",
            content="Content.",
            status="DRAFT_SUBMITTED_FOR_REVIEW",
            feedback="Review notes.",
        )
        db_session.add(draft)
        db_session.commit()

        response = client.post(
            f"/ui/drafts/{draft.id}/mark-feedback-given",
            follow_redirects=False,
        )
        assert response.status_code == 303

        db_session.expire_all()
        updated = db_session.query(Draft).filter(Draft.id == draft.id).first()
        assert updated.status == "DRAFT_FEEDBACK_GIVEN"

    def test_mark_feedback_given_fails_without_feedback_text(
        self, methodist_session_client
    ):
        client, db_session, user = methodist_session_client
        course = Course(title="No Feedback Course", description="")
        db_session.add(course)
        db_session.commit()

        draft = Draft(
            course_id=course.id,
            name="No Feedback Draft",
            content="Content.",
            status="DRAFT_SUBMITTED_FOR_REVIEW",
        )
        db_session.add(draft)
        db_session.commit()

        response = client.post(
            f"/ui/drafts/{draft.id}/mark-feedback-given",
        )
        assert response.status_code == 400

    def test_validate_rpd(self, methodist_session_client):
        client, db_session, user = methodist_session_client
        course = Course(title="Validate Course", description="")
        db_session.add(course)
        db_session.commit()

        draft = Draft(
            course_id=course.id,
            name="Validate Draft",
            content="Content to validate.",
            status="DRAFT_SUBMITTED_FOR_REVIEW",
        )
        db_session.add(draft)
        db_session.commit()

        response = client.post(
            f"/ui/drafts/{draft.id}/validate",
            follow_redirects=False,
        )
        assert response.status_code == 303

        db_session.expire_all()
        updated = db_session.query(Draft).filter(Draft.id == draft.id).first()
        assert updated.status == "RPD_VALIDATED"


class TestDashboardRoutes:
    def test_dashboard_requires_login(self, client):
        response = client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_dashboard_shows_teacher_courses(self, session_client):
        client, db_session, user = session_client
        course = Course(title="Dashboard Course", description="")
        db_session.add(course)
        db_session.commit()
        db_session.add(CourseTeacher(course_id=course.id, user_id=user.id))
        db_session.commit()

        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "Dashboard Course" in response.text

    def test_dashboard_shows_methodist_inbox(self, methodist_session_client):
        client, db_session, user = methodist_session_client
        course = Course(title="Methodist Course", description="")
        db_session.add(course)
        db_session.commit()

        draft = Draft(
            course_id=course.id,
            name="Draft for Methodist",
            content="Content.",
            status="DRAFT_SUBMITTED_FOR_REVIEW",
        )
        db_session.add(draft)
        db_session.commit()

        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "Draft for Methodist" in response.text


class TestUserRoutes:
    def test_users_page_requires_login(self, client):
        response = client.get("/admin/users", follow_redirects=False)
        assert response.status_code == 401

    def test_users_page_lists_users(self, session_client):
        client, db_session, user = session_client
        response = client.get("/admin/users")
        assert response.status_code == 200
        assert "Test Teacher" in response.text

    def test_create_user_from_admin(self, session_client):
        client, db_session, user = session_client
        response = client.post(
            "/admin/users",
            data={
                "name": "Admin Created",
                "email": "admin_created@test.com",
                "password": "password123",
                "roles": ["USER_METHODIST"],
            },
        )
        assert response.status_code == 200

        user = (
            db_session.query(User)
            .filter(User.email == "admin_created@test.com")
            .first()
        )
        assert user is not None
