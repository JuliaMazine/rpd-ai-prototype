import copy
import json
from io import BytesIO
from unittest.mock import Mock, patch

import pytest
from docx import Document
from pydantic import ValidationError

from app.models import Course, CourseTeacher, Draft, Material, User
from app.services.competency_catalogue_service import load_catalogue
from app.services.competency_generation_service import retrieve_for_generation, update_draft_mappings
from app.services.course_service import CourseInput
from app.services.embedding_service import EmbeddingError
from app.services.llm_service import generate_draft_text
from app.services.rpd_content_service import content_prompt, parse_content, render_content, snapshot


@pytest.fixture
def candidates():
    catalogue = load_catalogue()
    program_id = 'NSU-ММФ-03'
    entries = catalogue.competencies(program_id)
    entry = next(item for item in entries if item['codes'] == ['ОПК-2'])
    return {'results': [entry], 'program_id': program_id, 'program': next(p for p in catalogue.programs() if p['program_id'] == program_id),
            'catalogue_fingerprint': catalogue.fingerprint, 'model_digest': 'test-digest', 'status': 'retrieved', 'warnings': [], 'reviewed': False}


@pytest.fixture
def mapping(candidates):
    return {'competency_id': candidates['results'][0]['id'], 'outcome_kind': 'skills', 'outcome_index': 1}


@pytest.fixture
def mapped_draft(authenticated_client, db_session, teaching_payload, teaching_sources, candidates, mapping):
    user = db_session.query(User).filter_by(email='auth@test.com').one()
    course = Course(title='Анализ данных', description='Подготовка данных', catalogue_program_id=candidates['program_id'])
    db_session.add(course)
    db_session.flush()
    db_session.add(CourseTeacher(course_id=course.id, user_id=user.id))
    teaching_payload['competency_mappings'] = [mapping]
    content = parse_content(json.dumps(teaching_payload), teaching_sources, candidates)
    metadata = snapshot(course, content, teaching_sources)
    metadata['competencies'] = copy.deepcopy(candidates)
    metadata['competencies']['mappings'] = [mapping]
    draft = Draft(course_id=course.id, name='Черновик', status='DRAFT_EDITING', content=render_content(course, content, teaching_sources, candidates), generation_metadata=json.dumps(metadata, ensure_ascii=False))
    db_session.add(draft)
    db_session.commit()
    return draft


def test_program_id_is_validated_and_persisted(authenticated_client, db_session):
    with pytest.raises(ValidationError):
        CourseInput(title='Курс', catalogue_program_id='unknown')
    response = authenticated_client.post('/ui/courses', data={'title': 'Курс', 'catalogue_program_id': 'NSU-ММФ-03'}, follow_redirects=False)
    assert response.status_code == 303
    course = db_session.query(Course).one()
    assert course.catalogue_program_id == 'NSU-ММФ-03'
    assert 'NSU-ММФ-03' in authenticated_client.get('/dashboard').text
    assert authenticated_client.post(f'/ui/courses/{course.id}/edit', data={'title': 'Курс', 'catalogue_program_id': ''}, follow_redirects=False).status_code == 303
    db_session.refresh(course)
    assert course.catalogue_program_id is None


def test_retrieval_is_program_scoped_and_records_provenance(sample_course, candidates):
    sample_course.catalogue_program_id = candidates['program_id']
    with patch('app.services.competency_generation_service.search_competencies', return_value=candidates) as search:
        result = retrieve_for_generation(sample_course)
    assert search.call_args.args == (sample_course, candidates['program_id'])
    assert result['catalogue_fingerprint'] == candidates['catalogue_fingerprint']
    assert result['program']['program_id'] == candidates['program_id']


@pytest.mark.parametrize('program_id,status', [(None, 'unavailable'), ('unknown', 'unavailable'), ('NSU-ММФ-03', 'unavailable')])
def test_unavailable_retrieval_is_explicit_and_never_fabricates_results(sample_course, program_id, status):
    sample_course.catalogue_program_id = program_id
    with patch('app.services.competency_generation_service.search_competencies', side_effect=EmbeddingError('Ollama недоступна')) as search:
        result = retrieve_for_generation(sample_course)
    assert result['status'] == status
    assert result['results'] == []
    assert result['warnings']
    if program_id == 'unknown':
        search.assert_not_called()


@pytest.mark.parametrize('change', [{'competency_id': 'invented'}, {'outcome_index': 6}, {'outcome_kind': 'objectives'}])
def test_unknown_competencies_and_outcomes_are_rejected(teaching_payload, teaching_sources, candidates, mapping, change):
    teaching_payload['competency_mappings'] = [{**mapping, **change}]
    with pytest.raises(ValueError):
        parse_content(json.dumps(teaching_payload), teaching_sources, candidates)


def test_duplicate_mappings_rejected_and_empty_selection_allowed(teaching_payload, teaching_sources, candidates, mapping):
    teaching_payload['competency_mappings'] = [mapping, mapping]
    with pytest.raises(ValueError, match='Duplicate'):
        parse_content(json.dumps(teaching_payload), teaching_sources, candidates)
    teaching_payload['competency_mappings'] = []
    assert not parse_content(json.dumps(teaching_payload), teaching_sources, candidates).competency_mappings
    teaching_payload['competency_mappings'] = [mapping]
    with pytest.raises(ValueError, match='Unknown competency'):
        parse_content(json.dumps(teaching_payload), teaching_sources)


def test_generation_receives_candidates_and_saves_mappings(monkeypatch, sample_course, candidates, mapping, teaching_payload, teaching_sources):
    monkeypatch.setenv('LLM_PROVIDER', 'ollama')
    monkeypatch.setenv('OLLAMA_MODEL', 'qwen3:4b')
    teaching_payload['competency_mappings'] = [mapping]
    metadata = {}
    with patch('app.services.competency_generation_service.retrieve_for_generation', return_value=candidates), patch('app.services.llm_service.ollama_service.generate', return_value=(json.dumps(teaching_payload), False)) as generate:
        result = generate_draft_text(sample_course, teaching_sources.full_text, metadata, competencies=candidates)
    assert metadata['status'] == 'validated'
    assert metadata['competencies']['mappings'] == [mapping]
    assert candidates['results'][0]['description'] in result
    assert 'ОПК-2' in result
    assert candidates['results'][0]['id'] in generate.call_args.args[1][1]['content']


def test_retrieval_failure_keeps_generated_teaching_content(monkeypatch, sample_course, teaching_payload, teaching_sources):
    monkeypatch.setenv('LLM_PROVIDER', 'ollama')
    monkeypatch.setenv('OLLAMA_MODEL', 'qwen3:4b')
    sample_course.catalogue_program_id = 'NSU-ММФ-03'
    metadata = {}
    with patch('app.services.competency_generation_service.search_competencies', side_effect=EmbeddingError('Ollama недоступна')), patch('app.services.llm_service.ollama_service.generate', return_value=(json.dumps(teaching_payload), False)):
        result = generate_draft_text(sample_course, teaching_sources.full_text, metadata, competencies=retrieve_for_generation(sample_course))
    assert metadata['status'] == 'validated'
    assert metadata['competencies']['results'] == []
    assert any('Ollama недоступна' in warning for warning in metadata['warnings'])
    assert '[заполнить по утвержденному каталогу]' in result


def test_review_edit_and_docx_use_saved_catalogue_entries(authenticated_client, db_session, mapped_draft, candidates, mapping):
    draft = mapped_draft
    with patch('app.services.competency_catalogue_service.load_catalogue', side_effect=AssertionError('Review must use snapshot')):
        page = authenticated_client.get(f'/drafts/{draft.id}/view')
        assert page.status_code == 200
        assert 'Компетенции и результаты обучения' in page.text
        assert candidates['results'][0]['description'] in page.text
        # Add a different learning-outcome link; preserve an unrelated manual edit.
        draft.content += '\nПримечание преподавателя.'
        db_session.commit()
        selection = f"knowledge:1:{mapping['competency_id']}"
        response = authenticated_client.post(f'/ui/drafts/{draft.id}/competencies', data={'mapping': selection}, follow_redirects=False)
        assert response.status_code == 303
        db_session.refresh(draft)
        metadata = json.loads(draft.generation_metadata)
        assert metadata['competencies']['reviewed'] is True
        assert metadata['competencies']['model_digest'] == 'test-digest'
        assert 'Примечание преподавателя.' in draft.content
        assert metadata['teaching_content']['competency_mappings'][0]['outcome_kind'] == 'knowledge'
        exported = authenticated_client.get(f'/drafts/{draft.id}/download-docx')
        document = Document(BytesIO(exported.content))
        cells = [cell.text for table in document.tables for row in table.rows for cell in row.cells]
        assert 'ОПК-2' in cells
        assert candidates['results'][0]['description'] in cells
        response = authenticated_client.post(f'/ui/drafts/{draft.id}/competencies', data={}, follow_redirects=False)
        assert response.status_code == 303
        db_session.refresh(draft)
        assert 'ОПК-2' in draft.content
        assert '[соответствие требует проверки]' in draft.content
        assert json.loads(draft.generation_metadata)['competencies']['mappings'] == []


def test_mapping_edits_check_ownership_status_and_ids(authenticated_client, db_session, mapped_draft, sample_draft):
    assert authenticated_client.post(f'/ui/drafts/{sample_draft.id}/competencies', data={}).status_code == 403
    original = mapped_draft.content
    assert authenticated_client.post(f'/ui/drafts/{mapped_draft.id}/competencies', data={'mapping': 'skills:1:invented'}).status_code == 422
    db_session.refresh(mapped_draft)
    assert mapped_draft.content == original
    mapped_draft.status = 'DRAFT_SUBMITTED_FOR_REVIEW'
    db_session.commit()
    assert authenticated_client.post(f'/ui/drafts/{mapped_draft.id}/competencies', data={}).status_code == 400


def test_manual_mapping_changes_are_not_overwritten(authenticated_client, db_session, mapped_draft):
    mapped_draft.content = mapped_draft.content.replace('ОПК-2', 'Изменено преподавателем')
    db_session.commit()
    response = authenticated_client.post(f'/ui/drafts/{mapped_draft.id}/competencies', data={})
    assert response.status_code == 422
    db_session.refresh(mapped_draft)
    assert 'Изменено преподавателем' in mapped_draft.content


def test_free_text_edit_requires_review_again(authenticated_client, db_session, mapped_draft):
    metadata = json.loads(mapped_draft.generation_metadata)
    metadata['competencies']['reviewed'] = True
    mapped_draft.generation_metadata = json.dumps(metadata)
    db_session.commit()
    authenticated_client.post(f'/ui/drafts/{mapped_draft.id}/edit', data={'content': mapped_draft.content + '\nИзменения.'})
    db_session.refresh(mapped_draft)
    assert json.loads(mapped_draft.generation_metadata)['competencies']['reviewed'] is False


def test_preview_and_generation_use_only_accepted_selection(authenticated_client, db_session, mapped_draft, candidates):
    course = mapped_draft.course
    extra = next(e for e in load_catalogue().competencies(candidates['program_id']) if e['id'] != candidates['results'][0]['id'])
    candidates['results'].append(extra)
    db_session.add(Material(course_id=course.id, filename='lecture.txt', file_path='/missing', extracted_text='Материал для генерации'))
    db_session.commit()
    with patch('app.routes.course.retrieve_for_generation', return_value=candidates):
        preview = authenticated_client.post(f'/api/courses/{course.id}/generation-competencies', json={'program_id': candidates['program_id']})
    assert preview.status_code == 200
    token = preview.json()['token']
    accepted_id = candidates['results'][0]['id']
    with patch('app.routes.course.generate_draft_text', return_value='РПД') as generate, patch('app.services.competency_generation_service.search_competencies', side_effect=AssertionError('Must not rerank during generation')):
        response = authenticated_client.post(f'/ui/courses/{course.id}/generate-draft', data={'catalogue_program_id': candidates['program_id'], 'competency_token': token, 'competency_ids': accepted_id}, follow_redirects=False)
        assert response.status_code == 303
        passed = generate.call_args.kwargs['competencies']
        assert passed['accepted'] is True
        assert [item['id'] for item in passed['results']] == [accepted_id]
        assert len(passed['suggested_results']) == 2
        assert generate.call_args.args[1].endswith('Материал для генерации')
    # Unchecking every suggestion is an explicit empty acceptance.
    with patch('app.routes.course.generate_draft_text', return_value='РПД') as generate:
        response = authenticated_client.post(f'/ui/courses/{course.id}/generate-draft', data={'catalogue_program_id': candidates['program_id'], 'competency_token': token}, follow_redirects=False)
        assert response.status_code == 303
        assert generate.call_args.kwargs['competencies']['results'] == []


@pytest.mark.parametrize('change', ['forged', 'description', 'program', 'unknown_id', 'expired', 'catalogue'])
def test_generation_rejects_changed_or_invalid_previews(authenticated_client, db_session, mapped_draft, candidates, change):
    from app.services.competency_generation_service import preview_token
    course = mapped_draft.course
    db_session.add(Material(course_id=course.id, filename='lecture.txt', file_path='/missing', extracted_text='Материал'))
    db_session.commit()
    token = preview_token(course, candidates)
    program_id = candidates['program_id']
    selected_id = candidates['results'][0]['id']
    if change == 'forged':
        token = 'forged'
    elif change == 'description':
        course.description = 'Измененное описание'
        db_session.commit()
    elif change == 'program':
        program_id = 'NSU-ММФ-10'
    elif change == 'unknown_id':
        selected_id = 'invented'
    elif change == 'catalogue':
        altered = {**candidates, 'catalogue_fingerprint': 'previous-catalogue'}
        token = preview_token(course, altered)
    with patch('app.routes.course.generate_draft_text') as generate:
        if change == 'expired':
            from itsdangerous import SignatureExpired
            with patch('itsdangerous.URLSafeTimedSerializer.loads', side_effect=SignatureExpired('expired')):
                response = authenticated_client.post(f'/ui/courses/{course.id}/generate-draft', data={'catalogue_program_id': program_id, 'competency_token': token, 'competency_ids': selected_id})
        else:
            response = authenticated_client.post(f'/ui/courses/{course.id}/generate-draft', data={'catalogue_program_id': program_id, 'competency_token': token, 'competency_ids': selected_id})
    assert response.status_code == 422
    generate.assert_not_called()


def test_preview_checks_ownership_and_generation_requires_acceptance(authenticated_client, db_session, mapped_draft, sample_course):
    assert authenticated_client.post(f'/api/courses/{sample_course.id}/generation-competencies', json={'program_id': 'NSU-ММФ-03'}).status_code == 403
    course = mapped_draft.course
    db_session.add(Material(course_id=course.id, filename='lecture.txt', file_path='/missing', extracted_text='Материал'))
    db_session.commit()
    with patch('app.routes.course.generate_draft_text', return_value='РПД') as generate:
        assert authenticated_client.post(f'/ui/courses/{course.id}/generate-draft').status_code == 422
        generate.assert_not_called()
        response = authenticated_client.post(f'/ui/courses/{course.id}/generate-draft', data={'skip_competencies': 'true'}, follow_redirects=False)
        assert response.status_code == 303
        assert generate.call_args.kwargs['competencies']['status'] == 'skipped'


def test_prompt_includes_course_fields_and_only_selected_competencies(sample_course, candidates):
    sample_course.semester = 4
    sample_course.total_hours = 108
    sample_course.contact_hours = 36
    sample_course.independent_hours = 72
    sample_course.credits = 3
    sample_course.assessment_format = 'pass'
    prompt, _ = content_prompt(sample_course, 'Текст загруженного материала', candidates)
    for text in ['Семестр: 4', '108', 'Контактные часы: 36', '72', 'Зачетные единицы: 3', 'Зачет', 'Текст загруженного материала', candidates['results'][0]['description']]:
        assert text in prompt
    empty_prompt, _ = content_prompt(sample_course, 'Материалы', {**candidates, 'results': []})
    assert candidates['results'][0]['description'] not in empty_prompt


def test_saved_course_program_can_be_cleared_in_generation(authenticated_client, db_session, mapped_draft):
    course = mapped_draft.course
    db_session.add(Material(course_id=course.id, filename='lecture.txt', file_path='/missing', extracted_text='Материал'))
    db_session.commit()
    with patch('app.routes.course.generate_draft_text', return_value='РПД'):
        response = authenticated_client.post(f'/ui/courses/{course.id}/generate-draft', data={'catalogue_program_id': ''}, follow_redirects=False)
    assert response.status_code == 303
    db_session.refresh(course)
    assert course.catalogue_program_id is None


def test_template_fallback_preserves_accepted_competencies(monkeypatch, sample_course, candidates):
    monkeypatch.setenv('LLM_PROVIDER', 'template')
    metadata = {}
    result = generate_draft_text(sample_course, 'Материал', metadata, competencies=candidates)
    assert metadata['status'] == 'template'
    assert candidates['results'][0]['description'] in result
    assert '[соответствие требует проверки]' in result
    assert 'каталог компетенций пока не подключен' not in result


def test_preview_defaults_to_saved_program_and_form_has_no_duplicate_selector(authenticated_client, db_session, mapped_draft, candidates):
    import re
    course = mapped_draft.course
    with patch('app.services.competency_generation_service.search_competencies', return_value=candidates) as search:
        response = authenticated_client.post(f'/api/courses/{course.id}/generation-competencies', json={})
    assert response.status_code == 200
    assert search.call_args.args[1] == course.catalogue_program_id
    db_session.add(Material(course_id=course.id, filename='text.txt', file_path='/missing', extracted_text='Материалы'))
    db_session.commit()
    page = authenticated_client.get('/dashboard')
    form = re.search(r'<form[^>]+class="generation-form"[\s\S]+?</form>', page.text).group()
    assert '<select' not in form
    assert course.catalogue_program_id in form


@pytest.mark.parametrize('change', ['add', 'edit', 'remove'])
def test_material_changes_invalidate_preview(mapped_draft, candidates, change):
    from app.services.competency_generation_service import preview_token, accept_preview
    course = mapped_draft.course
    material = Material(filename='lecture.txt', file_path='/missing', extracted_text='Исходные учебные материалы')
    course.materials.append(material)
    token = preview_token(course, candidates)
    if change == 'add':
        course.materials.append(Material(filename='new.txt', file_path='/new', extracted_text='Дополнительные материалы'))
    elif change == 'edit':
        material.extracted_text = 'Измененные учебные материалы'
    else:
        course.materials.remove(material)
    with pytest.raises(ValueError, match='материалах'):
        accept_preview(course, candidates['program_id'], token, [])


def test_preview_without_saved_program_searches_whole_catalogue(sample_course, candidates):
    with patch('app.services.competency_generation_service.search_competencies', return_value={**candidates, 'program_id': None}) as search:
        result = retrieve_for_generation(sample_course)
    assert search.call_args.args[1] is None
    assert result['status'] == 'retrieved'
