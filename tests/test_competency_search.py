import csv
from unittest.mock import Mock, patch

import httpx
import pytest

from app.models import Course, CourseTeacher, User
from app.services.competency_catalogue_service import COLUMNS, Catalogue, CatalogueError, load_catalogue
from app.services.competency_search_service import search_competencies
from app.services.embedding_service import EmbeddingError, EmbeddingSettings, OllamaEmbeddings, unit_vector


def catalogue_row(index, program="P1", description=None):
    return dict(zip(COLUMNS, [program, "ФИТ", "Магистратура", "09.04.01", "Информатика", "Искусственный интеллект", "ПК", f"ПК-{index}", description or f"Компетенция по анализу данных {index}"], strict=True))


@pytest.fixture
def catalogue():
    rows = [catalogue_row(index) for index in range(1, 8)]
    rows.append(catalogue_row(10, "P2", rows[0]["competence_description"]))
    return Catalogue("catalogue-hash", tuple(rows))


@pytest.fixture
def embedding_config(tmp_path):
    return EmbeddingSettings("qwen3-embedding:0.6b", "http://localhost:11434", 10, tmp_path / "embeddings.sqlite3")


@pytest.fixture
def fake_encoder(monkeypatch):
    state = {"calls": [], "digest": "model-v1"}
    class Encoder:
        def __init__(self, config):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def model_digest(self):
            return state["digest"]
        def embed(self, texts):
            state["calls"].append(list(texts))
            vectors = []
            for text in texts:
                if text.startswith("Instruct:"):
                    vectors.append([1.0, 0.0] if "химия" not in text else [0.0, 1.0])
                else:
                    index = int(text.rsplit(" ", 1)[1])
                    vectors.append(unit_vector([8 - index, index]))
            return vectors
    monkeypatch.setattr("app.services.competency_search_service.OllamaEmbeddings", Encoder)
    return state


def test_real_catalogue_has_programs_and_groups_repeated_descriptions():
    catalogue = load_catalogue()
    assert len(catalogue.programs()) == 22
    competencies = catalogue.competencies()
    assert len(competencies) < len(catalogue.rows)
    assert len({entry["description"] for entry in competencies}) == len(competencies)
    assert all(entry["codes"] and entry["programs"] for entry in competencies)


def test_csv_bom_and_code_variants_are_preserved(tmp_path):
    path = tmp_path / "catalogue.csv"
    rows = [catalogue_row(1), catalogue_row(9, "P2", catalogue_row(1)["competence_description"])]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    entry = load_catalogue(path).competencies()[0]
    assert entry["codes"] == ["ПК-1", "ПК-9"]
    assert {row["program_id"] for row in entry["programs"]} == {"P1", "P2"}
    path.write_text("wrong,columns\nhello,world", encoding="utf-8")
    with pytest.raises(CatalogueError):
        load_catalogue(path)


def test_returns_five_distinct_competencies_sorted_by_cosine(catalogue, embedding_config, fake_encoder):
    course = Course(title="Course", description="Машинное обучение", topics="Предобработка данных")
    result = search_competencies(course, catalogue=catalogue, config=embedding_config)
    hits = result["results"]
    assert len(hits) == 5
    assert [entry["description"] for entry in hits] == [catalogue_row(index)["competence_description"] for index in range(1, 6)]
    assert [entry["score"] for entry in hits] == sorted([entry["score"] for entry in hits], reverse=True)
    assert hits[0]["codes"] == ["ПК-1", "ПК-10"]
    assert result["catalogue_fingerprint"] == "catalogue-hash"
    query = fake_encoder["calls"][0][0]
    assert "Машинное обучение" in query and "Предобработка данных" in query
    assert "Instruct:" in query


def test_program_filter_preserves_correct_codes(catalogue, embedding_config, fake_encoder):
    result = search_competencies(Course(description="Анализ данных"), "P2", catalogue=catalogue, config=embedding_config)
    assert len(result["results"]) == 1
    assert result["results"][0]["codes"] == ["ПК-10"]
    assert result["results"][0]["programs"][0]["program_id"] == "P2"
    fake_encoder["calls"].clear()
    with pytest.raises(ValueError, match="не найдена"):
        search_competencies(Course(description="Анализ"), "NO-PROGRAM", catalogue=catalogue, config=embedding_config)
    assert not fake_encoder["calls"]


def test_warm_search_reuses_document_vectors_but_reembeds_query(catalogue, embedding_config, fake_encoder):
    course = Course(description="Анализ", topics="Статистика")
    search_competencies(course, catalogue=catalogue, config=embedding_config)
    fake_encoder["calls"].clear()
    course.topics = "химия"
    result = search_competencies(course, catalogue=catalogue, config=embedding_config)
    assert len(fake_encoder["calls"]) == 1
    assert result["results"][0]["description"] == catalogue_row(7)["competence_description"]
    fake_encoder["calls"].clear()
    fake_encoder["digest"] = "model-v2"
    search_competencies(course, catalogue=catalogue, config=embedding_config)
    assert len(fake_encoder["calls"]) == 2


def test_only_changed_description_gets_reembedded(catalogue, embedding_config, fake_encoder):
    course = Course(description="Анализ")
    search_competencies(course, catalogue=catalogue, config=embedding_config)
    rows = [dict(row) for row in catalogue.rows]
    rows[2]["competence_description"] = "Новое описание компетенции 3"
    fake_encoder["calls"].clear()
    search_competencies(course, catalogue=Catalogue("changed", tuple(rows)), config=embedding_config)
    assert fake_encoder["calls"][1] == ["Новое описание компетенции 3"]


def test_empty_description_and_topics_do_not_call_embedding_model(fake_encoder, catalogue, embedding_config):
    with pytest.raises(ValueError, match="описание или темы"):
        search_competencies(Course(title="Only title", description=" ", topics=""), catalogue=catalogue, config=embedding_config)
    assert not fake_encoder["calls"]


@pytest.mark.parametrize("vector", [[], [0, 0], [float("nan"), 1], [float("inf"), 1], [True, 1], ["value", 1]])
def test_invalid_embedding_vectors_are_rejected(vector):
    with pytest.raises(ValueError):
        unit_vector(vector)


def test_embedding_transport_is_native_local_and_rejects_bad_payload(embedding_config):
    response = Mock()
    response.json.return_value = {"embeddings": [[3, 4]]}
    with patch("app.services.embedding_service.httpx.Client") as client:
        mock = client.return_value
        mock.request.return_value = response
        with OllamaEmbeddings(embedding_config) as encoder:
            assert encoder.embed(["Данные"]) == [[0.6, 0.8]]
            request = mock.request.call_args
            assert request.args[:2] == ("POST", "http://localhost:11434/api/embed")
            assert request.kwargs["json"]["truncate"] is False
            assert request.kwargs["json"]["model"] == embedding_config.model
            response.json.return_value = {"embeddings": []}
            with pytest.raises(EmbeddingError, match="некорректные векторы"):
                encoder.embed(["Данные"])


def test_missing_model_is_actionable(embedding_config):
    response = Mock()
    response.json.return_value = {"models": []}
    with patch("app.services.embedding_service.httpx.Client") as client:
        client.return_value.request.return_value = response
        with OllamaEmbeddings(embedding_config) as encoder:
            with pytest.raises(EmbeddingError, match="не установлена"):
                encoder.model_digest()


def test_offline_model_does_not_return_fabricated_results(embedding_config):
    with patch("app.services.embedding_service.httpx.Client") as client:
        client.return_value.request.side_effect = httpx.ConnectError("offline")
        with OllamaEmbeddings(embedding_config) as encoder:
            with pytest.raises(EmbeddingError, match="подключиться"):
                encoder.model_digest()


@pytest.fixture
def owned_course(authenticated_client, db_session):
    user = db_session.query(User).filter_by(email="auth@test.com").one()
    course = Course(title="Машинное обучение", description="Классификация", topics="Метрики качества")
    db_session.add(course)
    db_session.flush()
    db_session.add(CourseTeacher(course_id=course.id, user_id=user.id))
    db_session.commit()
    return course


def test_course_search_page_and_api_use_owned_course(authenticated_client, owned_course, monkeypatch):
    from app.routes import competency
    hits = {"results": [{"id": "item-id", "codes": ["ПК-1"], "description": "Анализ данных <script>bad</script>", "programs": [], "score": 0.8}], "candidates": 78}
    search = Mock(return_value=hits)
    monkeypatch.setattr(competency, "search_competencies", search)
    page = authenticated_client.get(f"/courses/{owned_course.id}/competencies")
    assert page.status_code == 200
    assert "Найти пять компетенций" in page.text
    search.assert_not_called()
    page = authenticated_client.post(f"/ui/courses/{owned_course.id}/competencies/search", data={"program_id": "NSU-ММФ-10"})
    assert page.status_code == 200
    assert "&lt;script&gt;bad&lt;/script&gt;" in page.text
    assert search.call_args.args[1] == "NSU-ММФ-10"
    api = authenticated_client.post(f"/api/courses/{owned_course.id}/competencies/search", json={})
    assert api.status_code == 200
    assert api.json()["results"][0]["codes"] == ["ПК-1"]


def test_other_teacher_cannot_search_course(authenticated_client, sample_course, monkeypatch):
    search = Mock()
    monkeypatch.setattr("app.routes.competency.search_competencies", search)
    for method, path in [("get", f"/courses/{sample_course.id}/competencies"), ("post", f"/api/courses/{sample_course.id}/competencies/search")]:
        response = getattr(authenticated_client, method)(path, **({"json": {}} if method == "post" else {}))
        assert response.status_code == 403
    search.assert_not_called()


def test_search_failure_is_visible_and_can_be_retried(authenticated_client, owned_course, monkeypatch):
    monkeypatch.setattr("app.routes.competency.search_competencies", Mock(side_effect=EmbeddingError("Не удалось подключиться к Ollama.")))
    page = authenticated_client.post(f"/ui/courses/{owned_course.id}/competencies/search", data={})
    assert page.status_code == 503
    assert "Не удалось подключиться" in page.text
    assert "Найти пять компетенций" in page.text
    api = authenticated_client.post(f"/api/courses/{owned_course.id}/competencies/search", json={})
    assert api.status_code == 503
