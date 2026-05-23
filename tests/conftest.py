import os
from io import BytesIO

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["VSEGPT_API_KEY"] = ""
os.environ["VSEGPT_MODEL"] = ""

from app.database import Base, get_db
from app.main import app
from app.models import Course, CourseTeacher, Draft, Material, User, UserRole


TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test.db")
TEST_DB_URL = f"sqlite:///{TEST_DB_PATH}"

TEST_ENGINE = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)
TestSessionLocal = sessionmaker(
    bind=TEST_ENGINE,
    autocommit=False,
    autoflush=False,
)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture(autouse=True)
def override_dependencies():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def db_session():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def sample_user(db_session):
    user = User(name="Test Teacher", email="teacher@test.com", password_hash="hash")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_teacher(db_session, sample_user):
    db_session.add(UserRole(user_id=sample_user.id, role="USER_TEACHER"))
    db_session.commit()
    return sample_user


@pytest.fixture
def sample_methodist(db_session):
    user = User(
        name="Test Methodist", email="methodist@test.com", password_hash="hash"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserRole(user_id=user.id, role="USER_METHODIST"))
    db_session.commit()
    return user


@pytest.fixture
def sample_course(db_session, sample_teacher):
    course = Course(title="Test Course", description="A test course description")
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)
    db_session.add(CourseTeacher(course_id=course.id, user_id=sample_teacher.id))
    db_session.commit()
    return course


@pytest.fixture
def sample_material(db_session, sample_course):
    material = Material(
        course_id=sample_course.id,
        filename="test_material.txt",
        file_path="/tmp/test_material.txt",
        extracted_text="Sample course material content for testing.",
    )
    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)
    return material


@pytest.fixture
def sample_draft(db_session, sample_course):
    draft = Draft(
        course_id=sample_course.id,
        name="RPD Draft v1 - Test Course",
        content="\n\n".join(
            [
                "1. Цели освоения дисциплины",
                "Основная цель освоения дисциплины — формирование знаний.",
                "2. Содержание дисциплины",
                "Раздел 1. Введение в дисциплину. Объем: 2 ч.",
                "• тема 1",
                "• тема 2",
            ]
        ),
        feedback=None,
        status="DRAFT_EDITING",
    )
    db_session.add(draft)
    db_session.commit()
    db_session.refresh(draft)
    return draft


@pytest.fixture
def sample_submitted_draft(db_session, sample_course):
    draft = Draft(
        course_id=sample_course.id,
        name="RPD Draft v2 - Test Course",
        content="Draft content for review.",
        feedback=None,
        status="DRAFT_SUBMITTED_FOR_REVIEW",
    )
    db_session.add(draft)
    db_session.commit()
    db_session.refresh(draft)
    return draft


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture
def authenticated_client(client, db_session):
    from app.auth import hash_password

    user = User(
        name="Auth User",
        email="auth@test.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserRole(user_id=user.id, role="USER_TEACHER"))
    db_session.commit()

    client.post(
        "/login",
        data={"email": "auth@test.com", "password": "password123"},
    )
    yield client


@pytest.fixture
def methodist_client(client, db_session):
    from app.auth import hash_password

    user = User(
        name="Methodist User",
        email="methodist-auth@test.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserRole(user_id=user.id, role="USER_METHODIST"))
    db_session.commit()

    client.post(
        "/login",
        data={"email": "methodist-auth@test.com", "password": "password123"},
    )
    yield client
