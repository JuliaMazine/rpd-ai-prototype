import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import require_role
from app.constants import (
    REVIEWABLE_STATUSES,
    ROLE_METHODIST,
    STATUS_FEEDBACK_GIVEN,
    STATUS_RPD_VALIDATED,
)
from app.database import get_db
from app.models import Draft
from app.services.document_view_service import document_blocks
from app.services.competency_selection_service import selection_context


from app.web import templates


router = APIRouter()


@router.get("/drafts/{draft_id}/feedback", response_class=HTMLResponse)
def feedback_page(
    request: Request,
    draft_id: int,
    db: Session = Depends(get_db),
):
    require_role(request, db, ROLE_METHODIST)

    draft = db.query(Draft).filter(Draft.id == draft_id).first()

    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    if draft.status not in REVIEWABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Feedback cannot be given in status {draft.status}",
        )

    try:
        review = json.loads(draft.generation_metadata or "{}")
    except (ValueError, TypeError):
        review = {}

    return templates.TemplateResponse(
        request=request,
        name="review_workspace.html",
        context={
            "draft": draft,
            "selection": selection_context(draft),
            "generation_review": review,
            "document_blocks": document_blocks(draft.content),
        },
    )


@router.post("/ui/drafts/{draft_id}/feedback")
def ui_save_feedback(
    request: Request,
    draft_id: int,
    feedback: str = Form(default=""),
    decision: str = Form(default="save"),
    db: Session = Depends(get_db),
):
    require_role(request, db, ROLE_METHODIST)

    draft = db.query(Draft).filter(Draft.id == draft_id).first()

    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    if draft.status not in REVIEWABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Feedback cannot be written in status {draft.status}",
        )

    if decision not in {"save", "return"}:
        raise HTTPException(422, "Unknown review decision")
    if decision == "return" and not feedback.strip():
        raise HTTPException(422, "Напишите замечания перед возвратом преподавателю.")

    draft.feedback = feedback
    if decision == "return":
        draft.status = STATUS_FEEDBACK_GIVEN

    db.commit()

    if decision == "return":
        return RedirectResponse(url="/dashboard#review-inbox", status_code=303)

    return RedirectResponse(
        url=f"/drafts/{draft.id}/view?saved=1#decision",
        status_code=303,
    )


@router.post("/ui/drafts/{draft_id}/mark-feedback-given")
def ui_mark_feedback_given(
    request: Request,
    draft_id: int,
    db: Session = Depends(get_db),
):
    require_role(request, db, ROLE_METHODIST)

    draft = db.query(Draft).filter(Draft.id == draft_id).first()

    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    if draft.status not in REVIEWABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition. Current status is {draft.status}.",
        )

    if not draft.feedback or not draft.feedback.strip():
        raise HTTPException(
            status_code=400,
            detail="Cannot mark feedback as given before writing feedback.",
        )

    draft.status = STATUS_FEEDBACK_GIVEN

    db.commit()

    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/ui/drafts/{draft_id}/validate")
def ui_validate_rpd(
    request: Request,
    draft_id: int,
    db: Session = Depends(get_db),
):
    require_role(request, db, ROLE_METHODIST)

    draft = db.query(Draft).filter(Draft.id == draft_id).first()

    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    if draft.status not in REVIEWABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Draft cannot be validated in status {draft.status}",
        )

    draft.status = STATUS_RPD_VALIDATED

    db.commit()

    return RedirectResponse(url="/dashboard", status_code=303)
