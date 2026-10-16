from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.auth import require_draft_reader, verify_password
from app.config import settings
from app.constants import ROLE_METHODIST, ROLE_TEACHER
from app.main import create_app
from app.models import Material, User, UserRole
from app.services.material_service import save_material
from app.services.user_service import create_user, UserValidationError


@pytest.mark.parametrize("seed_demo", [False, True])
def test_database_initialization_happens_on_startup(seed_demo):
    with patch("app.main.Base.metadata.create_all") as create_tables, patch("app.main.seed_demo_data") as seed:
        application = create_app(replace(settings, seed_demo=seed_demo))
        create_tables.assert_not_called()
        seed.assert_not_called()
        with TestClient(application) as client:
            assert client.get("/login").status_code == 200
            create_tables.assert_called_once()
            assert seed.call_count == int(seed_demo)


def test_upload_paths_are_unique_and_stay_in_upload_directory(db_session, sample_course, tmp_path):
    first = save_material(db_session, sample_course.id, "../../lecture.txt", b"first")
    second = save_material(db_session, sample_course.id, "lecture.txt", b"second")
    assert first.filename == "lecture.txt"
    assert first.file_path != second.file_path
    assert Path(first.file_path).is_relative_to(tmp_path)
    assert Path(first.file_path).read_bytes() == b"first"
    assert Path(second.file_path).read_bytes() == b"second"


@pytest.mark.parametrize("content,status", [(b"", 400), (b"\xff", 400)], ids=["empty", "invalid-utf8"])
def test_invalid_uploads_leave_no_files_or_rows(db_session, sample_course, tmp_path, content, status):
    with pytest.raises(HTTPException) as error:
        save_material(db_session, sample_course.id, "lecture.txt", content)
    assert error.value.status_code == status
    assert not list(tmp_path.rglob("*"))
    assert db_session.query(Material).count() == 0


def test_failed_material_commit_cleans_up_file(db_session, sample_course, tmp_path):
    with patch.object(db_session, "commit", side_effect=RuntimeError("commit failed")):
        with pytest.raises(RuntimeError):
            save_material(db_session, sample_course.id, "lecture.txt", b"content")
    assert not list(tmp_path.rglob("*.txt"))
    assert db_session.query(Material).count() == 0


def test_account_creation_preserves_password_and_deduplicates_roles(db_session):
    user = create_user(db_session, name=" Test ", email=" test@example.com ", password=" password123 ", roles=[ROLE_TEACHER, ROLE_TEACHER])
    assert user.name == "Test"
    assert user.email == "test@example.com"
    assert verify_password(" password123 ", user.password_hash)
    assert len(user.roles) == 1


def test_account_creation_rejects_unknown_roles_without_creating_user(db_session):
    with pytest.raises(UserValidationError):
        create_user(db_session, name="Test", email="test@example.com", password="password123", roles=["ADMIN"])
    assert db_session.query(User).count() == 0


def test_draft_reader_rechecks_role_membership(db_session, sample_teacher, sample_draft):
    request = Request({"type": "http", "session": {"user_id": sample_teacher.id, "active_role": ROLE_METHODIST}})
    with pytest.raises(HTTPException) as error:
        require_draft_reader(request, db_session, sample_draft.id)
    assert error.value.status_code == 403


def test_draft_reader_allows_real_methodist(db_session, sample_methodist, sample_draft):
    request = Request({"type": "http", "session": {"user_id": sample_methodist.id, "active_role": ROLE_METHODIST}})
    assert require_draft_reader(request, db_session, sample_draft.id).id == sample_draft.id


def test_upload_above_old_limit_is_accepted(db_session, sample_course):
    content = b"a" * (5 * 1024 * 1024 + 1)
    material = save_material(db_session, sample_course.id, "large.txt", content)
    assert len(material.extracted_text) == len(content)


def test_upload_boundary_is_enforced(db_session, sample_course, tmp_path, monkeypatch):
    from dataclasses import replace
    from app.config import settings
    monkeypatch.setattr("app.services.material_service.settings", replace(settings, upload_dir=tmp_path, max_upload_bytes=1024 * 1024))
    material = save_material(db_session, sample_course.id, "at-limit.txt", b"a" * (1024 * 1024))
    assert len(material.extracted_text) == 1024 * 1024
    with pytest.raises(HTTPException) as error:
        save_material(db_session, sample_course.id, "over-limit.txt", b"a" * (1024 * 1024 + 1))
    assert error.value.status_code == 413
    assert "1 МиБ" in error.value.detail
    assert db_session.query(Material).count() == 1


def test_upload_limit_is_configurable(monkeypatch):
    from app.config import Settings
    monkeypatch.setenv("MAX_UPLOAD_MB", "40")
    assert Settings().max_upload_bytes == 40 * 1024 * 1024


@pytest.mark.parametrize("value", ["0", "101", "invalid"])
def test_invalid_upload_limit_is_rejected(monkeypatch, value):
    from app.config import Settings
    monkeypatch.setenv("MAX_UPLOAD_MB", value)
    with pytest.raises(ValueError):
        Settings()
