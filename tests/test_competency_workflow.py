"""SCRUM-13: selections, historical snapshots and review-driven matrix assignments."""
import copy
import json
from datetime import datetime
from io import BytesIO
from unittest.mock import patch

import pytest
from docx import Document

from app.constants import (STATUS_DRAFT_EDITING, STATUS_FEEDBACK_GIVEN,
                           STATUS_SUBMITTED_FOR_REVIEW, STATUS_RESUBMITTED_FOR_REVIEW,
                           STATUS_RPD_VALIDATED)
from app.models import Course, CourseTeacher, Draft, Material, User
from app.services.competency_catalogue_service import load_catalogue
from app.services.competency_generation_service import accept_preview, mapping_text, preview_token
from app.services.competency_matrix_service import programme_matrix
from app.services.competency_selection_service import catalogue_entries, selection_keys, update_draft_selection

PROGRAM = 'NSU-ММФ-03'


@pytest.fixture
def catalogue():
    return load_catalogue()


@pytest.fixture
def owned_course(authenticated_client, db_session):
    user = db_session.query(User).filter_by(email='auth@test.com').one()
    course = Course(title='Новый курс', catalogue_program_id=PROGRAM)
    db_session.add(course)
    db_session.flush()
    db_session.add(CourseTeacher(course_id=course.id, user_id=user.id))
    db_session.add(Material(course_id=course.id, filename='lecture.txt', file_path='/missing', extracted_text='Учебные материалы'))
    db_session.commit()
    return course


def snapshot(catalogue, entries=None, program=PROGRAM):
    return {'program_id': program, 'program': next(p for p in catalogue.programs() if p['program_id'] == program),
            'results': entries or [], 'warnings': [], 'catalogue_fingerprint': catalogue.fingerprint}


def make_draft(db, course, competencies, status=STATUS_DRAFT_EDITING, created_at=None):
    metadata = {'competencies': copy.deepcopy(competencies)} if competencies is not None else {}
    draft = Draft(course=course, name='Test RPD', status=status,
                  content='РАБОЧАЯ ПРОГРАММА ДИСЦИПЛИНЫ\nOther teacher text\n\n' + mapping_text(None, competencies or {}) + '\n\n4. Трудоемкость\nTeacher hours',
                  generation_metadata=json.dumps(metadata, ensure_ascii=False), created_at=created_at or datetime(2026, 1, 1))
    db.add(draft)
    db.flush()
    return draft


def test_manual_catalogue_selection_without_embeddings(authenticated_client, owned_course, db_session, catalogue):
    response = authenticated_client.get(f'/api/courses/{owned_course.id}/competency-catalogue')
    assert response.status_code == 200
    result = response.json()
    assert len(result['entries']) == len([r for r in catalogue.rows if r['program_id'] == PROGRAM])
    codes = [entry['codes'][0] for entry in result['entries'][:7]]
    with patch('app.services.competency_generation_service.search_competencies', side_effect=AssertionError('No reranking')), patch.dict('os.environ', LLM_PROVIDER='template'):
        response = authenticated_client.post(f'/ui/courses/{owned_course.id}/generate-draft', data={
            'catalogue_token': result['token'], 'manual_codes': codes}, follow_redirects=False)
    assert response.status_code == 303
    draft = db_session.query(Draft).one()
    stored = json.loads(draft.generation_metadata)['competencies']
    assert selection_keys(stored) == {(PROGRAM, code) for code in codes}
    assert all(code in draft.content for code in codes)


def test_manual_selection_rejects_duplicate_outside_program_and_stale_preview(owned_course, catalogue):
    entries = catalogue_entries(catalogue, PROGRAM)
    empty = snapshot(catalogue)
    token = preview_token(owned_course, empty)
    code = entries[0]['codes'][0]
    for codes in [[code, code], ['invented']]:
        with pytest.raises(ValueError):
            accept_preview(owned_course, PROGRAM, token, [], codes)
    owned_course.topics = 'Changed inputs'
    with pytest.raises(ValueError, match='изменились'):
        accept_preview(owned_course, PROGRAM, token, [], [code])


def test_exploratory_results_cannot_be_confirmed(owned_course, catalogue):
    preview = snapshot(catalogue)
    preview['program_id'] = None
    token = preview_token(owned_course, preview)
    with pytest.raises(ValueError, match='Выберите программу'):
        accept_preview(owned_course, None, token, [])


def test_edit_selection_preserves_teacher_text_and_docx(authenticated_client, owned_course, db_session, catalogue):
    entries = catalogue_entries(catalogue, PROGRAM)
    draft = make_draft(db_session, owned_course, snapshot(catalogue, entries[:1]))
    db_session.commit()
    response = authenticated_client.post(f'/ui/drafts/{draft.id}/competency-selection', data={
        'program_id': PROGRAM, 'catalogue_fingerprint': catalogue.fingerprint,
        'competency_codes': [entries[1]['codes'][0]]}, follow_redirects=False)
    assert response.status_code == 303
    db_session.refresh(draft)
    assert 'Other teacher text' in draft.content and 'Teacher hours' in draft.content
    assert entries[1]['description'] in draft.content
    assert entries[0]['description'] not in draft.content
    stored = json.loads(draft.generation_metadata)['competencies']
    assert selection_keys(stored) == {(PROGRAM, entries[1]['codes'][0])}
    download = authenticated_client.get(f'/drafts/{draft.id}/download-docx')
    document = Document(BytesIO(download.content))
    text = '\n'.join(cell.text for table in document.tables for row in table.rows for cell in row.cells)
    assert entries[1]['description'] in text and entries[0]['description'] not in text
    assert entries[1]['description'] in authenticated_client.get(f'/drafts/{draft.id}/edit').text


def test_text_discrepancy_does_not_change_assignments(authenticated_client, owned_course, db_session, catalogue):
    entries = catalogue_entries(catalogue, PROGRAM)
    draft = make_draft(db_session, owned_course, snapshot(catalogue, entries[:1]))
    draft.content = draft.content.replace(entries[0]['description'], 'Manual rewrite')
    db_session.commit()
    assert 'отличается от сохраненного выбора' in authenticated_client.get(f'/drafts/{draft.id}/view').text
    response = authenticated_client.post(f'/ui/drafts/{draft.id}/competency-selection', data={
        'program_id': PROGRAM, 'catalogue_fingerprint': catalogue.fingerprint, 'competency_codes': entries[1]['codes'][0]})
    assert response.status_code == 422
    db_session.refresh(draft)
    assert selection_keys(json.loads(draft.generation_metadata)['competencies']) == {(PROGRAM, entries[0]['codes'][0])}


def test_selection_permissions(authenticated_client, methodist_client, sample_draft, owned_course, db_session, catalogue):
    authenticated_client.post('/login', data={'email': 'auth@test.com', 'password': 'password123'})
    data = {'program_id': PROGRAM, 'catalogue_fingerprint': catalogue.fingerprint}
    assert authenticated_client.post(f'/ui/drafts/{sample_draft.id}/competency-selection', data=data).status_code == 403
    draft = make_draft(db_session, owned_course, snapshot(catalogue), STATUS_SUBMITTED_FOR_REVIEW)
    db_session.commit()
    # Clients share a cookie jar through the client fixture; log the teacher back in.
    authenticated_client.post('/login', data={'email': 'auth@test.com', 'password': 'password123'})
    assert authenticated_client.post(f'/ui/drafts/{draft.id}/competency-selection', data=data).status_code == 400


def test_matrix_source_order_fallback_and_final_assignment(db_session, sample_course, catalogue):
    sample_course.catalogue_program_id = PROGRAM
    entries = catalogue_entries(catalogue, PROGRAM)
    older = make_draft(db_session, sample_course, snapshot(catalogue, entries[:1]), STATUS_RPD_VALIDATED)
    newer = make_draft(db_session, sample_course, snapshot(catalogue, entries[1:2]), STATUS_SUBMITTED_FOR_REVIEW)
    editing = make_draft(db_session, sample_course, snapshot(catalogue, entries[2:3]), created_at=datetime(2026, 2, 1))
    # Same creation time resolves by ID; a newer editing draft is excluded.
    matrix = programme_matrix(db_session, catalogue, PROGRAM)
    assert matrix['columns'][0]['draft'].id == newer.id
    assert matrix['columns'][0]['keys'] == {(PROGRAM, entries[1]['codes'][0])}
    assert len(programme_matrix(db_session, catalogue, PROGRAM, True)['rows']) == len(entries) - 1
    newer.status = STATUS_FEEDBACK_GIVEN
    assert programme_matrix(db_session, catalogue, PROGRAM)['columns'][0]['draft'].id == older.id
    older.status = STATUS_FEEDBACK_GIVEN
    assert programme_matrix(db_session, catalogue, PROGRAM)['columns'][0]['state'] == 'no_draft'
    assert len(programme_matrix(db_session, catalogue, PROGRAM, True)['rows']) == len(entries)
    editing.status = STATUS_RESUBMITTED_FOR_REVIEW
    assert programme_matrix(db_session, catalogue, PROGRAM)['columns'][0]['draft'].id == editing.id
    assert json.loads(older.generation_metadata)['competencies']['results'] == entries[:1]


def test_matrix_empty_missing_mismatch_and_empty_programmes(db_session, catalogue):
    entries = catalogue_entries(catalogue, PROGRAM)
    for index, selection in enumerate([None, snapshot(catalogue), snapshot(catalogue, entries[:1], 'NSU-ММФ-10')]):
        course = Course(title=str(index), catalogue_program_id=PROGRAM)
        db_session.add(course)
        make_draft(db_session, course, selection, STATUS_SUBMITTED_FOR_REVIEW)
    db_session.add(Course(title='No draft', catalogue_program_id=PROGRAM))
    db_session.flush()
    matrix = programme_matrix(db_session, catalogue, PROGRAM)
    assert [c['state'] for c in matrix['columns']] == ['missing', 'empty', 'incompatible', 'no_draft']
    assert not any(any(row['cells']) for row in matrix['rows'])
    empty = programme_matrix(db_session, catalogue, 'NSU-ММФ-10')
    assert empty['columns'] == [] and empty['rows']


def test_matrix_access_and_empty_submission_reminder(authenticated_client, owned_course, db_session, catalogue):
    assert authenticated_client.get('/programmes/competency-matrix').status_code == 403
    draft = make_draft(db_session, owned_course, snapshot(catalogue))
    db_session.commit()
    response = authenticated_client.post(f'/ui/drafts/{draft.id}/submit-review')
    assert 'Отправить без компетенций' in response.text
    db_session.refresh(draft)
    assert draft.status == STATUS_DRAFT_EDITING
    response = authenticated_client.post(f'/ui/drafts/{draft.id}/submit-review', data={'confirm_empty': 'true'}, follow_redirects=False)
    assert response.status_code == 303
    db_session.refresh(draft)
    assert draft.status == STATUS_SUBMITTED_FOR_REVIEW


def test_methodist_matrix_and_saved_selection(methodist_client, sample_course, db_session, catalogue):
    sample_course.catalogue_program_id = PROGRAM
    entry = catalogue_entries(catalogue, PROGRAM)[0]
    draft = make_draft(db_session, sample_course, snapshot(catalogue, [entry]), STATUS_SUBMITTED_FOR_REVIEW)
    db_session.commit()
    response = methodist_client.get('/programmes/competency-matrix', params={'program_id': PROGRAM})
    assert response.status_code == 200 and f'/drafts/{draft.id}/view' in response.text
    assert '✓' in response.text
    view = methodist_client.get(f'/drafts/{draft.id}/view')
    assert 'Сохраненный выбор компетенций этого РПД' in view.text and entry['description'] in view.text


def test_explicit_table_replacement_preserves_surrounding_text(authenticated_client, owned_course, db_session, catalogue):
    entries = catalogue_entries(catalogue, PROGRAM)
    draft = make_draft(db_session, owned_course, snapshot(catalogue, entries[:1]))
    draft.content = draft.content.replace(entries[0]['description'], 'Teacher table rewrite')
    db_session.commit()
    response = authenticated_client.post(f'/ui/drafts/{draft.id}/competency-selection', data={
        'program_id': PROGRAM, 'catalogue_fingerprint': catalogue.fingerprint,
        'competency_codes': entries[1]['codes'][0], 'replace_table': 'true'}, follow_redirects=False)
    assert response.status_code == 303
    db_session.refresh(draft)
    assert entries[1]['description'] in draft.content and 'Teacher table rewrite' not in draft.content
    assert 'Other teacher text' in draft.content and 'Teacher hours' in draft.content


def test_selection_edit_preserves_original_wording_when_catalogue_changes(owned_course, db_session, catalogue, monkeypatch):
    from app.services.competency_catalogue_service import Catalogue
    entry = catalogue_entries(catalogue, PROGRAM)[0]
    draft = make_draft(db_session, owned_course, snapshot(catalogue, [entry]))
    rows = tuple({**row, 'competence_description': 'Updated wording'}
                 if row['program_id'] == PROGRAM and row['competence_code'] == entry['codes'][0] else row
                 for row in catalogue.rows)
    changed = Catalogue('new-fingerprint', rows)
    monkeypatch.setattr('app.services.competency_selection_service.load_catalogue', lambda: changed)
    update_draft_selection(draft, entry['codes'], PROGRAM, changed.fingerprint)
    assert entry['description'] in draft.content and 'Updated wording' not in draft.content
    assert json.loads(draft.generation_metadata)['competencies']['results'] == [entry]


def test_stale_editor_and_changed_programme_require_new_selection(owned_course, db_session, catalogue):
    entry = catalogue_entries(catalogue, PROGRAM)[0]
    draft = make_draft(db_session, owned_course, snapshot(catalogue, [entry]))
    old_content = draft.content
    with pytest.raises(ValueError, match='изменились'):
        update_draft_selection(draft, entry['codes'], PROGRAM, 'old-fingerprint')
    owned_course.catalogue_program_id = 'NSU-ММФ-10'
    with pytest.raises(ValueError, match='изменились'):
        update_draft_selection(draft, entry['codes'], PROGRAM, catalogue.fingerprint)
    assert draft.content == old_content
    matrix = programme_matrix(db_session, catalogue, 'NSU-ММФ-10')
    assert not any(any(row['cells']) for row in matrix['rows'])


def test_selection_edit_retains_existing_mappings_and_flags_new_entries(owned_course, db_session, catalogue, teaching_payload, teaching_sources):
    from app.services.rpd_content_service import parse_content, render_content
    entries = catalogue_entries(catalogue, PROGRAM)
    selection = snapshot(catalogue, entries[:1])
    teaching_payload['competency_mappings'] = [{'competency_id': entries[0]['id'], 'outcome_kind': 'skills', 'outcome_index': 1}]
    content = parse_content(json.dumps(teaching_payload), teaching_sources, selection)
    draft = make_draft(db_session, owned_course, selection)
    draft.content = render_content(owned_course, content, teaching_sources, selection)
    draft.generation_metadata = json.dumps({'competencies': selection, 'teaching_content': content.model_dump()}, ensure_ascii=False)
    update_draft_selection(draft, [e['codes'][0] for e in entries[:2]], PROGRAM, catalogue.fingerprint)
    saved = json.loads(draft.generation_metadata)
    assert saved['teaching_content']['competency_mappings'] == teaching_payload['competency_mappings']
    assert entries[1]['description'] in draft.content and '[соответствие требует проверки]' in draft.content
    update_draft_selection(draft, [entries[1]['codes'][0]], PROGRAM, catalogue.fingerprint)
    assert json.loads(draft.generation_metadata)['teaching_content']['competency_mappings'] == []


def test_matrix_defaults_to_programme_with_courses_but_allows_empty_programme(methodist_client, sample_course, db_session, catalogue):
    sample_course.catalogue_program_id = PROGRAM
    entry = catalogue_entries(catalogue, PROGRAM)[0]
    draft = make_draft(db_session, sample_course, snapshot(catalogue, [entry]), STATUS_SUBMITTED_FOR_REVIEW)
    db_session.commit()
    response = methodist_client.get('/programmes/competency-matrix')
    assert response.status_code == 200
    assert response.context['program_id'] == PROGRAM
    assert response.context['stats']['courses'] == 1
    assert f'/drafts/{draft.id}/view' in response.text
    empty = methodist_client.get('/programmes/competency-matrix', params={'program_id': 'NSU-ММФ-10'})
    assert empty.status_code == 200
    assert empty.context['program_id'] == 'NSU-ММФ-10'
    assert empty.context['stats']['courses'] == 0
    assert 'В этой программе пока нет дисциплин' in empty.text
    assert 'Изменить сведения о дисциплине' in empty.text


def test_matrix_summary_stays_programme_wide_when_filtered(db_session, sample_course, catalogue):
    sample_course.catalogue_program_id = PROGRAM
    entry = catalogue_entries(catalogue, PROGRAM)[0]
    make_draft(db_session, sample_course, snapshot(catalogue, [entry]), STATUS_SUBMITTED_FOR_REVIEW)
    full = programme_matrix(db_session, catalogue, PROGRAM)
    filtered = programme_matrix(db_session, catalogue, PROGRAM, True)
    assert full['stats'] == filtered['stats']
    assert filtered['stats']['assigned'] == 1
    assert filtered['stats']['unassigned'] == len(filtered['rows'])
    assert full['stats']['submitted'] == full['stats']['courses'] == 1
    assert not any(row['assigned'] for row in filtered['rows'])
