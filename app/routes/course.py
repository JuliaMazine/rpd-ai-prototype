import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import require_course_teacher, require_role
from app.constants import ROLE_TEACHER, STATUS_DRAFT_EDITING
from app.database import get_db
from app.models import Course, CourseTeacher, Draft
from app.config import settings
from app.services.material_service import save_material, generation_materials
from app.services.llm_service import generate_draft_text
from app.services.course_service import CourseInput, course_form
from app.services.competency_generation_service import retrieve_for_generation, preview_token, accept_preview, refresh_preview
from app.services.competency_catalogue_service import CatalogueError
from pydantic import BaseModel, Field


router = APIRouter()


@router.post("/ui/courses")
def ui_create_course(
    request: Request,
    data: CourseInput = Depends(course_form),
    db: Session = Depends(get_db),
):
    user = require_role(request, db, ROLE_TEACHER)

    course = Course(**data.model_dump())

    db.add(course)
    db.flush()

    db.add(CourseTeacher(course_id=course.id, user_id=user.id))
    db.commit()

    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/ui/courses/{course_id}/edit")
def ui_edit_course(
    request: Request,
    course_id: int,
    data: CourseInput = Depends(course_form),
    db: Session = Depends(get_db),
):
    require_course_teacher(request, db, course_id)
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(404, "Course not found")
    for name, value in data.model_dump().items():
        setattr(course, name, value)
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/ui/courses/{course_id}/materials")
async def ui_upload_material(
    request: Request,
    course_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    require_course_teacher(request, db, course_id)

    course = db.query(Course).filter(Course.id == course_id).first()

    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    try:
        file_bytes = await file.read(settings.max_upload_bytes + 1)
        save_material(db, course_id, file.filename, file_bytes)
    finally:
        await file.close()

    return RedirectResponse(url="/dashboard", status_code=303)


async def generation_program(request: Request):
    form = await request.form()
    return ("catalogue_program_id" in form, form.get("catalogue_program_id"))


class GenerationPreviewInput(BaseModel):
    program_id: str | None = Field(default=None, max_length=100)
    token: str = Field(default="", max_length=100000)
    selected_ids: list[str] = Field(default_factory=list, max_length=5)


@router.post("/api/courses/{course_id}/generation-competencies")
def generation_competencies(request: Request, course_id: int, data: GenerationPreviewInput, db: Session = Depends(get_db)):
    require_course_teacher(request, db, course_id)
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(404, "Дисциплина не найдена.")
    try:
        result = refresh_preview(course, data.program_id or course.catalogue_program_id, data.token, data.selected_ids) if data.token else retrieve_for_generation(course, data.program_id)
    except (ValueError, CatalogueError) as error:
        raise HTTPException(422, str(error)) from None
    if result["status"] != "retrieved":
        raise HTTPException(503, " ".join(result["warnings"]))
    return {"token": preview_token(course, result), "results": result["results"], "material_sources": result.get("material_sources", []), "exhausted": result.get("exhausted", False)}


@router.post("/ui/courses/{course_id}/generate-draft")
def ui_generate_draft(
    request: Request,
    course_id: int,
    program_selection: tuple = Depends(generation_program),
    competency_token: str = Form(default="", max_length=100000),
    competency_ids: list[str] = Form(default=[]),
    skip_competencies: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    require_course_teacher(request, db, course_id)

    course = db.query(Course).filter(Course.id == course_id).first()

    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    if not course.materials:
        raise HTTPException(
            status_code=400,
            detail="Cannot generate draft: course has no uploaded materials",
        )

    program_provided, catalogue_program_id = program_selection
    if catalogue_program_id is not None and (not isinstance(catalogue_program_id, str) or len(catalogue_program_id) > 100):
        raise HTTPException(422, "Некорректная программа.")
    program_id = (catalogue_program_id.strip() or None) if program_provided else course.catalogue_program_id
    competencies = {"program_id": program_id, "results": [], "mappings": [], "warnings": [], "status": "not_selected", "reviewed": False}
    if skip_competencies:
        competencies.update(status="skipped", warnings=["Преподаватель продолжил без подбора компетенций. Заполните соответствия вручную."])
    elif program_id or competency_token:
        if not competency_token:
            raise HTTPException(422, "Дождитесь предложений компетенций или выберите генерацию без компетенций.")
        try:
            competencies = accept_preview(course, program_id, competency_token, competency_ids)
        except (ValueError, CatalogueError) as error:
            raise HTTPException(422, str(error)) from None
    else:
        if competency_ids or competency_token:
            raise HTTPException(422, "Выберите программу для компетенций.")
        competencies["warnings"].append("Программа из каталога не выбрана. Компетенции нужно заполнить вручную.")
    if program_provided:
        try:
            CourseInput(title=course.title, catalogue_program_id=program_id)
        except ValueError:
            raise HTTPException(422, "Выбранная программа отсутствует в каталоге.") from None
        course.catalogue_program_id = program_id
    materials_text = generation_materials(course.materials)
    metadata = {}
    draft_content = generate_draft_text(course, materials_text, metadata=metadata, competencies=competencies)

    draft_number = len(course.drafts) + 1

    draft = Draft(
        course_id=course.id,
        name=f"Черновик РПД v{draft_number} — {course.title}",
        content=draft_content,
        generation_metadata=json.dumps(metadata, ensure_ascii=False),
        feedback=None,
        status=STATUS_DRAFT_EDITING,
        document_url=None,
    )

    db.add(draft)
    db.commit()

    return RedirectResponse(url="/dashboard", status_code=303)
