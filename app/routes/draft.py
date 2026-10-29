import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.auth import (
    get_active_role,
    require_draft_teacher,
    require_draft_reader,
)
from app.constants import (
    STATUS_DRAFT_EDITING,
    STATUS_FEEDBACK_GIVEN,
    STATUS_RESUBMITTED_FOR_REVIEW,
    STATUS_SUBMITTED_FOR_REVIEW,
    TEACHER_EDITABLE_STATUSES,
)
from app.database import get_db
from app.services.document_view_service import document_blocks
from app.services.docx_service import (
    build_draft_docx,
    clean_filename,
    encode_docx_filename,
)


from app.web import templates
from app.services.competency_generation_service import update_draft_mappings
from app.services.competency_selection_service import selection_context, selection_editor, update_draft_selection
from app.services.competency_catalogue_service import CatalogueError


router = APIRouter()


@router.get("/drafts/{draft_id}/view", response_class=HTMLResponse)
def view_draft_page(
    request: Request,
    draft_id: int,
    db: Session = Depends(get_db),
):
    draft = require_draft_reader(request, db, draft_id)
    active_role = get_active_role(request)
    try:
        review = json.loads(draft.generation_metadata or "{}")
    except (ValueError, TypeError):
        review = {}

    return templates.TemplateResponse(
        request=request,
        name="draft_view.html",
        context={
            "draft": draft,
            "active_role": active_role,
            "generation_review": review,
            "selection": selection_context(draft),
            "document_blocks": document_blocks(draft.content),
        },
    )


@router.get("/drafts/{draft_id}/download-docx")
def download_draft_docx(
    request: Request,
    draft_id: int,
    db: Session = Depends(get_db),
):
    draft = require_draft_reader(request, db, draft_id)

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

    editor, editor_error = None, None
    try:
        editor = selection_editor(draft)
    except (ValueError, CatalogueError) as error:
        editor_error = str(error)
    return templates.TemplateResponse(
        request=request,
        name="draft_edit.html",
        context={
            "draft": draft,
            "selection": selection_context(draft),
            "editor": editor,
            "editor_error": editor_error,
        },
    )


@router.post("/ui/drafts/{draft_id}/competencies")
async def ui_update_competencies(request: Request, draft_id: int, db: Session = Depends(get_db)):
    _, draft = require_draft_teacher(request, db, draft_id)
    if draft.status not in TEACHER_EDITABLE_STATUSES:
        raise HTTPException(400, "Черновик в этом статусе нельзя редактировать.")
    form = await request.form()
    try:
        update_draft_mappings(draft, form.getlist("mapping"))
    except (ValueError, TypeError, KeyError) as error:
        raise HTTPException(422, str(error)) from None
    db.commit()
    return RedirectResponse(url=f"/drafts/{draft.id}/view", status_code=303)


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
    if draft.generation_metadata:
        try:
            review = json.loads(draft.generation_metadata)
            review["edited"] = True
            if review.get("competencies"):
                review["competencies"]["reviewed"] = False
            draft.generation_metadata = json.dumps(review, ensure_ascii=False)
        except (ValueError, TypeError):
            pass

    db.commit()

    return RedirectResponse(
        url=f"/drafts/{draft.id}/edit",
        status_code=303,
    )


@router.post("/ui/drafts/{draft_id}/submit-review")
def ui_submit_review(
    request: Request,
    draft_id: int,
    confirm_empty: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    _, draft = require_draft_teacher(request, db, draft_id)

    if draft.status != STATUS_DRAFT_EDITING:
        raise HTTPException(
            status_code=400,
            detail=f"Draft cannot be submitted in status {draft.status}",
        )

    if selection_context(draft)['empty'] and not confirm_empty:
        return templates.TemplateResponse(request=request, name="confirm_empty_selection.html", context={"draft": draft, "action": request.url.path})

    draft.status = STATUS_SUBMITTED_FOR_REVIEW

    db.commit()

    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/ui/drafts/{draft_id}/resubmit-review")
def ui_resubmit_review(
    request: Request,
    draft_id: int,
    confirm_empty: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    _, draft = require_draft_teacher(request, db, draft_id)

    if draft.status != STATUS_FEEDBACK_GIVEN:
        raise HTTPException(
            status_code=400,
            detail=f"Draft cannot be resubmitted in status {draft.status}",
        )

    if selection_context(draft)['empty'] and not confirm_empty:
        return templates.TemplateResponse(request=request, name="confirm_empty_selection.html", context={"draft": draft, "action": request.url.path})

    draft.status = STATUS_RESUBMITTED_FOR_REVIEW

    draft.feedback = None

    db.commit()

    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/ui/drafts/{draft_id}/competency-selection")
async def ui_update_selection(request: Request, draft_id: int, db: Session = Depends(get_db)):
    _, draft = require_draft_teacher(request, db, draft_id)
    if draft.status not in TEACHER_EDITABLE_STATUSES:
        raise HTTPException(400, "Черновик в этом статусе нельзя редактировать.")
    form = await request.form()
    try:
        update_draft_selection(draft, form.getlist('competency_codes'), form.get('program_id'), form.get('catalogue_fingerprint'), form.get('replace_table') == 'true')
    except (ValueError, TypeError, KeyError, CatalogueError) as error:
        raise HTTPException(422, str(error)) from None
    db.commit()
    return RedirectResponse(url=f"/drafts/{draft.id}/edit", status_code=303)
