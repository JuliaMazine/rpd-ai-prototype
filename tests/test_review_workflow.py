"""Review decisions must save the exact notes being returned, in one transaction."""
import pytest

from app.models import Draft


@pytest.mark.parametrize('status', ['DRAFT_SUBMITTED_FOR_REVIEW', 'DRAFT_RESUBMITTED_FOR_REVIEW'])
def test_return_saves_current_comments(methodist_client, sample_course, db_session, status):
    draft = Draft(course_id=sample_course.id, name='Review', content='Text', status=status, feedback='Older saved notes')
    db_session.add(draft)
    db_session.commit()
    response = methodist_client.post(f'/ui/drafts/{draft.id}/feedback', data={'feedback': 'Correct section 3.', 'decision': 'return'}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == '/dashboard#review-inbox'
    db_session.refresh(draft)
    assert draft.feedback == 'Correct section 3.'
    assert draft.status == 'DRAFT_FEEDBACK_GIVEN'


@pytest.mark.parametrize('feedback', ['', '   '])
def test_blank_return_keeps_saved_notes_and_status(methodist_client, sample_draft, db_session, feedback):
    sample_draft.status = 'DRAFT_SUBMITTED_FOR_REVIEW'
    sample_draft.feedback = 'Saved notes'
    db_session.commit()
    response = methodist_client.post(f'/ui/drafts/{sample_draft.id}/feedback', data={'feedback': feedback, 'decision': 'return'})
    assert response.status_code == 422
    db_session.refresh(sample_draft)
    assert sample_draft.feedback == 'Saved notes'
    assert sample_draft.status == 'DRAFT_SUBMITTED_FOR_REVIEW'


def test_save_does_not_return_draft(methodist_client, sample_draft, db_session):
    sample_draft.status = 'DRAFT_SUBMITTED_FOR_REVIEW'
    db_session.commit()
    response = methodist_client.post(f'/ui/drafts/{sample_draft.id}/feedback', data={'feedback': 'Work in progress', 'decision': 'save'})
    assert response.status_code == 200
    assert 'Замечания сохранены' in response.text
    db_session.refresh(sample_draft)
    assert sample_draft.status == 'DRAFT_SUBMITTED_FOR_REVIEW'
    assert sample_draft.feedback == 'Work in progress'


def test_teacher_cannot_return_draft(authenticated_client, sample_draft, db_session):
    sample_draft.status = 'DRAFT_SUBMITTED_FOR_REVIEW'
    db_session.commit()
    response = authenticated_client.post(f'/ui/drafts/{sample_draft.id}/feedback', data={'feedback': 'Notes', 'decision': 'return'})
    assert response.status_code == 403
    db_session.refresh(sample_draft)
    assert sample_draft.status == 'DRAFT_SUBMITTED_FOR_REVIEW'


def test_completed_review_cannot_be_returned(methodist_client, sample_draft, db_session):
    sample_draft.status = 'RPD_VALIDATED'
    db_session.commit()
    response = methodist_client.post(f'/ui/drafts/{sample_draft.id}/feedback', data={'feedback': 'Notes', 'decision': 'return'})
    assert response.status_code == 400
    db_session.refresh(sample_draft)
    assert sample_draft.status == 'RPD_VALIDATED'
