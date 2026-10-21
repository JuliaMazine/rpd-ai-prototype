"""Program-scoped competency candidates and validated learning-outcome mappings."""
from app.services.competency_catalogue_service import CatalogueError, load_catalogue
from app.services.competency_search_service import search_competencies
from app.services.embedding_service import EmbeddingError

MAPPING_HEADING = "Соотнесение результатов обучения с компетенциями образовательной программы:"


def retrieve_for_generation(course, program_id=None):
    program_id = program_id or course.catalogue_program_id
    snapshot = {"program_id": program_id, "results": [], "mappings": [], "warnings": [], "reviewed": False}
    if not program_id:
        snapshot.update(status="missing_program", warnings=["Выберите программу из каталога в настройках дисциплины. Компетенции не назначены."])
        return snapshot
    try:
        catalogue = load_catalogue()
        program = next((item for item in catalogue.programs() if item["program_id"] == program_id), None)
        if program is None:
            raise ValueError("Выбранная программа отсутствует в каталоге.")
        result = search_competencies(course, program_id, catalogue=catalogue)
        snapshot.update(result, program=program, status="retrieved")
    except (CatalogueError, EmbeddingError, ValueError) as error:
        snapshot.update(status="unavailable", warnings=[f"Компетенции не подобраны: {error} Повторите подбор или продолжите без компетенций."])
    return snapshot


def validate_mappings(content, competencies):
    allowed = {entry["id"] for entry in competencies.get("results", [])}
    seen = set()
    for mapping in getattr(content, "competency_mappings", []):
        if mapping.competency_id not in allowed:
            raise ValueError("Unknown competency_id; use only supplied candidates")
        if mapping.outcome_index > len(getattr(content, mapping.outcome_kind)):
            raise ValueError("Competency mapping refers to an unknown learning outcome")
        key = (mapping.competency_id, mapping.outcome_kind, mapping.outcome_index)
        if key in seen:
            raise ValueError("Duplicate competency mapping")
        seen.add(key)


def mapping_text(content, competencies):
    from app.services.rpd_content_service import knowledge_outcome, skill_outcome, table
    validate_mappings(content, competencies)
    if not competencies.get("results"):
        return MAPPING_HEADING + " [заполнить по утвержденному каталогу]."
    entries = {entry["id"]: entry for entry in competencies["results"]}
    rows = []
    for mapping in getattr(content, "competency_mappings", []):
        entry = entries[mapping.competency_id]
        outcome = getattr(content, mapping.outcome_kind)[mapping.outcome_index - 1]
        formatter = knowledge_outcome if mapping.outcome_kind == "knowledge" else skill_outcome
        rows.append([" / ".join(entry["codes"]), entry["description"], formatter(outcome)])
    mapped_ids = {mapping.competency_id for mapping in getattr(content, "competency_mappings", [])}
    for entry in competencies["results"]:
        if entry["id"] not in mapped_ids:
            rows.append([" / ".join(entry["codes"]), entry["description"], "[соответствие требует проверки]"])
    return MAPPING_HEADING + "\n" + table(["Код компетенции", "Формулировка из каталога", "Результат обучения"], rows)


def review_context(draft):
    import json
    from app.services.rpd_content_service import TeachingContent, knowledge_outcome, skill_outcome
    try:
        metadata = json.loads(draft.generation_metadata or "{}")
    except (ValueError, TypeError):
        return None
    candidates = metadata.get("competencies", {})
    if not candidates.get("results") or not metadata.get("teaching_content"):
        return None
    content = TeachingContent.model_validate(metadata["teaching_content"])
    outcomes = []
    for kind, formatter in [("knowledge", knowledge_outcome), ("skills", skill_outcome)]:
        for index, value in enumerate(getattr(content, kind), 1):
            outcomes.append({"key": f"{kind}:{index}", "text": formatter(value)})
    selected = {f"{item.outcome_kind}:{item.outcome_index}:{item.competency_id}" for item in content.competency_mappings}
    return {"snapshot": candidates, "outcomes": outcomes, "selected": selected, "edited": metadata.get("edited", False)}


def update_draft_mappings(draft, selections):
    """Change only the mapping block, retaining free-text edits elsewhere in the RPD."""
    import json
    from app.services.rpd_content_service import TeachingContent, CompetencyMapping
    metadata = json.loads(draft.generation_metadata or "{}")
    competencies = metadata.get("competencies", {})
    if not competencies.get("results") or not metadata.get("teaching_content"):
        raise ValueError("В этом черновике нет сохраненных кандидатов. Создайте новый черновик.")
    content = TeachingContent.model_validate(metadata["teaching_content"])
    previous = mapping_text(content, competencies)
    if draft.content.count(previous) != 1:
        raise ValueError("Таблица компетенций изменена вручную. Сохраните правки в тексте или создайте новый черновик для автоматического редактирования связей.")
    mappings = []
    for selection in selections:
        try:
            kind, index, identifier = selection.split(":", 2)
            mappings.append(CompetencyMapping(outcome_kind=kind, outcome_index=int(index), competency_id=identifier))
        except (ValueError, TypeError) as error:
            raise ValueError("Некорректная связь компетенции с результатом обучения.") from error
    if len(mappings) > 60:
        raise ValueError("Слишком много связей компетенций.")
    content.competency_mappings = mappings
    updated = mapping_text(content, competencies)
    # Do not reintroduce outcomes removed or rewritten in the free-text editor.
    from app.services.rpd_content_service import knowledge_outcome, skill_outcome
    outside_mapping = draft.content.replace(previous, "", 1)
    for mapping in mappings:
        formatter = knowledge_outcome if mapping.outcome_kind == "knowledge" else skill_outcome
        text = formatter(getattr(content, mapping.outcome_kind)[mapping.outcome_index - 1])
        if text not in outside_mapping:
            raise ValueError("Результат обучения изменен вручную. Обновите соответствие в тексте черновика.")
    draft.content = draft.content.replace(previous, updated, 1)
    metadata["teaching_content"] = content.model_dump()
    competencies["mappings"] = [item.model_dump() for item in mappings]
    competencies["reviewed"] = True
    draft.generation_metadata = json.dumps(metadata, ensure_ascii=False)


def course_search_fingerprint(course, program_id):
    import json
    from hashlib import sha256
    return sha256(json.dumps([course.id, course.title, course.description, course.topics, program_id], ensure_ascii=False).encode()).hexdigest()


def preview_token(course, competencies):
    from itsdangerous import URLSafeTimedSerializer
    from app.config import settings
    return URLSafeTimedSerializer(settings.session_secret, salt="generation-competencies-v1").dumps({
        "course_fingerprint": course_search_fingerprint(course, competencies["program_id"]),
        "competencies": competencies,
    })


def accept_preview(course, program_id, token, selected_ids):
    """Verify exactly what the teacher saw; never rerun ranking on Generate."""
    from itsdangerous import URLSafeTimedSerializer, BadData
    from app.config import settings
    try:
        payload = URLSafeTimedSerializer(settings.session_secret, salt="generation-competencies-v1").loads(token, max_age=3600)
    except BadData as error:
        raise ValueError("Подбор устарел. Обновите предложения компетенций перед генерацией.") from error
    if payload["course_fingerprint"] != course_search_fingerprint(course, program_id):
        raise ValueError("Сведения о дисциплине или программе изменились. Обновите предложения компетенций.")
    competencies = payload["competencies"]
    if competencies["catalogue_fingerprint"] != load_catalogue().fingerprint:
        raise ValueError("Каталог изменился. Обновите предложения компетенций.")
    allowed = {entry["id"] for entry in competencies["results"]}
    if not set(selected_ids) <= allowed:
        raise ValueError("Выбрана компетенция, которой нет среди предложений.")
    competencies["suggested_results"] = competencies["results"]
    competencies["results"] = [entry for entry in competencies["results"] if entry["id"] in set(selected_ids)]
    competencies.update(status="accepted", accepted=True)
    if not competencies["results"]:
        competencies["warnings"].append("Преподаватель снял выбор всех компетенций. Соответствия нужно заполнить вручную.")
    return competencies
