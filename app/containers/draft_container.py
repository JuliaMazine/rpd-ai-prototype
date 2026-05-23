from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import (
    get_active_role,
    require_draft_teacher,
    require_login,
    user_is_course_teacher,
)
from app.constants import (
    ROLE_METHODIST,
    ROLE_TEACHER,
    STATUS_DRAFT_EDITING,
    STATUS_FEEDBACK_GIVEN,
    STATUS_RESUBMITTED_FOR_REVIEW,
    STATUS_SUBMITTED_FOR_REVIEW,
    TEACHER_EDITABLE_STATUSES,
)
from app.database import get_db
from app.models import Draft
from app.services.docx_service import (
    build_draft_docx,
    clean_filename,
    encode_docx_filename,
)


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/drafts/{draft_id}/view", response_class=HTMLResponse)
def view_draft_page(
    request: Request,
    draft_id: int,
    db: Session = Depends(get_db),
):
    user = require_login(request, db)

    draft = db.query(Draft).filter(Draft.id == draft_id).first()

    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    active_role = get_active_role(request)

    if active_role == ROLE_TEACHER:
        if not user_is_course_teacher(user.id, draft.course_id, db):
            raise HTTPException(status_code=403, detail="Access denied")

    elif active_role != ROLE_METHODIST:
        raise HTTPException(status_code=403, detail="Access denied")

    return templates.TemplateResponse(
        request=request,
        name="draft_view.html",
        context={
            "draft": draft,
            "active_role": active_role,
        },
    )


@router.get("/drafts/{draft_id}/download-docx")
def download_draft_docx(
    request: Request,
    draft_id: int,
    db: Session = Depends(get_db),
):
    user = require_login(request, db)

    draft = db.query(Draft).filter(Draft.id == draft_id).first()

    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    active_role = get_active_role(request)

    if active_role == ROLE_TEACHER:
        if not user_is_course_teacher(user.id, draft.course_id, db):
            raise HTTPException(status_code=403, detail="Access denied")

    elif active_role != ROLE_METHODIST:
        raise HTTPException(status_code=403, detail="Access denied")

    docx_file = build_draft_docx(draft)

    filename = clean_filename(f"{draft.name}.docx")
    encoded_filename = encode_docx_filename(filename)

    return StreamingResponse(
        docx_file,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        },
    )


@router.get("/drafts/{draft_id}/edit", response_class=HTMLResponse)
def edit_draft_page(
    request: Request,
    draft_id: int,
    db: Session = Depends(get_db),
):
    _, draft = require_draft_teacher(request, db, draft_id)

    return templates.TemplateResponse(
        request=request,
        name="draft_edit.html",
        context={
            "draft": draft,
        },
    )


@router.post("/ui/drafts/{draft_id}/edit")
def ui_save_draft_edit(
    request: Request,
    draft_id: int,
    content: str = Form(...),
    db: Session = Depends(get_db),
):
    _, draft = require_draft_teacher(request, db, draft_id)

    if draft.status not in TEACHER_EDITABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Draft cannot be edited in status {draft.status}",
        )

    draft.content = content

    db.commit()

    return RedirectResponse(
        url=f"/drafts/{draft.id}/edit",
        status_code=303,
    )


@router.post("/ui/drafts/{draft_id}/submit-review")
def ui_submit_review(
    request: Request,
    draft_id: int,
    db: Session = Depends(get_db),
):
    _, draft = require_draft_teacher(request, db, draft_id)

    if draft.status != STATUS_DRAFT_EDITING:
        raise HTTPException(
            status_code=400,
            detail=f"Draft cannot be submitted in status {draft.status}",
        )

    draft.status = STATUS_SUBMITTED_FOR_REVIEW

    db.commit()

    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/ui/drafts/{draft_id}/resubmit-review")
def ui_resubmit_review(
    request: Request,
    draft_id: int,
    db: Session = Depends(get_db),
):
    _, draft = require_draft_teacher(request, db, draft_id)

    if draft.status != STATUS_FEEDBACK_GIVEN:
        raise HTTPException(
            status_code=400,
            detail=f"Draft cannot be resubmitted in status {draft.status}",
        )

    draft.status = STATUS_RESUBMITTED_FOR_REVIEW

    draft.feedback = None

    db.commit()

    return RedirectResponse(url="/dashboard", status_code=303)