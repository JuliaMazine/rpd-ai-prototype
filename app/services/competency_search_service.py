"""Retrieve five distinct catalogue competencies using local cosine similarity."""
import json
import sqlite3
from hashlib import sha256
from threading import Lock

from app.services.competency_catalogue_service import load_catalogue
from app.services.embedding_service import EmbeddingCache, EmbeddingError, EmbeddingSettings, OllamaEmbeddings

_index_lock = Lock()
TOP_K = 5


def search_materials(course):
    return sorted(
        [item for item in course.materials if (item.extracted_text or "").strip()],
        key=lambda item: (item.id or 0, item.filename),
    )


def material_sources(course):
    return [{"id": item.id, "filename": item.filename,
             "text_sha256": sha256(item.extracted_text.encode()).hexdigest()}
            for item in search_materials(course)]


def course_query(course):
    from app.services.rpd_evidence_service import source_context
    parts = []
    materials = search_materials(course)
    if materials:
        texts = "\n\n".join("[Источник: " + item.filename.replace("\n", " ").replace("\r", " ") + "]\n" + item.extracted_text for item in materials)
        context, _ = source_context(texts, budget=12000)
        parts.append("Содержание загруженных учебных материалов (основа подбора):\n" + context)
    if (course.description or "").strip():
        parts.append("Описание дисциплины: " + course.description.strip()[:2000])
    if (course.topics or "").strip():
        parts.append("Темы дисциплины:\n" + course.topics.strip()[:2000])
    if not parts:
        raise ValueError("Загрузите учебные материалы или добавьте описание или темы дисциплины, прежде чем подбирать компетенции.")
    return "\n\n".join(parts)


def search_competencies(course, program_id=None, *, catalogue=None, config=None, exclude_ids=(), limit=TOP_K):
    query = course_query(course)
    catalogue = catalogue or load_catalogue()
    excluded = set(exclude_ids)
    entries = [entry for entry in catalogue.competencies(program_id) if entry["id"] not in excluded]
    config = config or EmbeddingSettings.from_environment()
    if config.model.lower().startswith("qwen3-embedding"):
        query = "Instruct: Given uploaded university teaching materials and supplementary course information, retrieve educational competencies supported by the teaching content.\nQuery: " + query
    with OllamaEmbeddings(config) as encoder:
        digest = encoder.model_digest()
        query_vector = encoder.embed([query])[0]
        dimensions = len(query_vector)
        namespace = sha256(json.dumps(["competency-description-v1", config.base_url, config.model, digest], ensure_ascii=False).encode()).hexdigest()
        try:
            with _index_lock, EmbeddingCache(config.cache_path, namespace) as cache:
                vectors = {entry["id"]: cache.get(entry["description"], dimensions) for entry in entries}
                missing = [entry for entry in entries if vectors[entry["id"]] is None]
                for offset in range(0, len(missing), 16):
                    batch = missing[offset:offset + 16]
                    texts = [entry["description"] for entry in batch]
                    batch_vectors = encoder.embed(texts)
                    if any(len(vector) != dimensions for vector in batch_vectors):
                        raise EmbeddingError("Размерность векторов запроса и каталога не совпадает. Проверьте модель поиска.")
                    cache.put(texts, batch_vectors)
                    vectors.update({entry["id"]: vector for entry, vector in zip(batch, batch_vectors, strict=True)})
        except (sqlite3.Error, OSError) as error:
            raise EmbeddingError("Не удалось сохранить локальный индекс компетенций. Проверьте доступ к каталогу кэша.") from error
    ranked = []
    for entry in entries:
        score = sum(a * b for a, b in zip(query_vector, vectors[entry["id"]], strict=True))
        ranked.append({**entry, "score": max(-1.0, min(1.0, score))})
    ranked.sort(key=lambda entry: (-entry["score"], entry["id"]))
    return {"results": ranked[:limit], "catalogue_fingerprint": catalogue.fingerprint, "model": config.model,
            "model_digest": digest, "program_id": program_id, "candidates": len(entries),
            "material_sources": material_sources(course), "input_source": "uploaded_materials" if search_materials(course) else "course_fields"}
