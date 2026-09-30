from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text
from starlette.requests import Request

from app.auth import hash_password
from app.constants import ROLE_TEACHER
from app.migrate import upgrade_course_metadata
from app.models import Course, CourseTeacher, User, UserRole
from app.services.course_service import CourseInput
from app.services.llm_service import build_rpd_prompt, build_template_draft

@pytest.fixture
def teacher_client(client, db_session):
    user = User(name="Teacher", email="fields@example.com", password_hash=hash_password("password123"))
    user.roles = [UserRole(role=ROLE_TEACHER)]
    db_session.add(user)
    db_session.commit()
    client.post("/login", data={"email": user.email, "password": "password123"})
    return client, user

def test_create_persist_display_and_edit_metadata(teacher_client, db_session):
    client, user = teacher_client
    fields = {"title": "Физика", "educational_program": "Прикладная физика", "semester": "2", "total_hours": "144", "credits": "4.5", "assessment_format": "exam", "topics": "Механика\nОптика"}
    response = client.post("/ui/courses", data=fields, follow_redirects=False)
    assert response.status_code == 303
    db_session.expire_all()
    course = db_session.query(Course).one()
    assert course.educational_program == fields["educational_program"]
    assert course.semester == 2
    assert course.total_hours == 144
    assert course.credits == Decimal("4.50")
    assert course.assessment_format == "exam"
    assert course.topics == fields["topics"]
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Прикладная физика" in response.text
    assert "Оптика" in response.text
    fields.update(semester="3", total_hours="180", credits="5", assessment_format="pass")
    response = client.post(f"/ui/courses/{course.id}/edit", data=fields, follow_redirects=False)
    assert response.status_code == 303
    db_session.refresh(course)
    assert course.semester == 3
    assert course.total_hours == 180
    assert course.credits == Decimal("5")
    assert course.assessment_format == "pass"

@pytest.mark.parametrize("field,value", [("semester", "0"), ("semester", "2.5"), ("total_hours", "-1"), ("credits", "NaN"), ("credits", "0"), ("credits", "3.333"), ("assessment_format", "unknown"), ("educational_program", "x" * 256)], ids=["semester-zero", "semester-fraction", "hours-negative", "credits-nan", "credits-zero", "credits-precision", "assessment", "program-length"])
def test_invalid_metadata_is_not_saved(teacher_client, db_session, field, value):
    client, user = teacher_client
    response = client.post("/ui/courses", data={"title": "Course", field: value})
    assert response.status_code == 422
    assert db_session.query(Course).count() == 0

def test_blanks_remain_optional():
    data = CourseInput.model_validate({"title": " Course ", "semester": "", "total_hours": "", "credits": "", "assessment_format": "", "topics": " "})
    assert data.title == "Course"
    assert data.semester is None
    assert data.credits is None
    assert data.topics is None

def test_other_teacher_cannot_edit_course(teacher_client, db_session, sample_course):
    client, user = teacher_client
    response = client.post(f"/ui/courses/{sample_course.id}/edit", data={"title": "Stolen"})
    assert response.status_code == 403
    db_session.refresh(sample_course)
    assert sample_course.title == "Test Course"

def test_metadata_reaches_prompt_and_fallback(sample_course):
    sample_course.educational_program = "Прикладная физика"
    sample_course.semester = 5
    sample_course.total_hours = 144
    sample_course.credits = Decimal("4.5")
    sample_course.assessment_format = "graded_pass"
    sample_course.topics = "Термодинамика\nОптика"
    for result in (build_rpd_prompt(sample_course, "materials"), build_template_draft(sample_course, "materials")):
        for value in ("Прикладная физика", "Семестр: 5", "144", "4.5", "Дифференцированный зачет", "Термодинамика", "Оптика"):
            assert value in result
    result = build_template_draft(sample_course, "materials")
    assert "108" not in result
    assert "экзамена" not in result

def test_missing_metadata_does_not_invent_workload(sample_course):
    result = build_template_draft(sample_course, "materials")
    assert "уточняется" in result
    assert "108" not in result
    assert "3 зачетные единицы" not in result

def test_existing_database_upgrade_preserves_courses_and_is_idempotent():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE courses (id INTEGER PRIMARY KEY, title VARCHAR(255) NOT NULL, description TEXT)"))
        connection.execute(text("INSERT INTO courses (title, description) VALUES ('Physics', 'Existing course')"))
        upgrade_course_metadata(connection)
        upgrade_course_metadata(connection)
        columns = {item["name"] for item in inspect(connection).get_columns("courses")}
        assert {"educational_program", "semester", "total_hours", "credits", "assessment_format", "topics"} <= columns
        row = connection.execute(text("SELECT title, semester FROM courses")).one()
        assert row.title == "Physics"
        assert row.semester is None


def test_russian_form_labels_and_validation(teacher_client):
    client, user = teacher_client
    response = client.get("/dashboard")
    assert '<html lang="ru">' in response.text
    assert "Что будут изучать студенты?" in response.text
    assert "Перечислите основные темы" in response.text
    assert "Преподаватель" in response.text
    assert "Educational program" not in response.text
    assert 'action="/language"' not in response.text
    response = client.post("/ui/courses", data={"title": "Курс", "semester": "0"})
    assert response.status_code == 422
    assert "Проверьте значение поля" in response.json()["detail"][0]["message"]


def test_russian_login_failure_message(client):
    response = client.post("/login", data={"email": "unknown@example.com", "password": "password123"})
    assert response.status_code == 401
    assert "Неверная электронная почта или пароль" in response.text


def test_russian_draft_status_in_docx(sample_draft):
    from docx import Document
    from app.services.docx_service import build_draft_docx
    document = Document(build_draft_docx(sample_draft))
    assert any("Редактирование" in paragraph.text for paragraph in document.paragraphs)
