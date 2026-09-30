from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import require_course_teacher, require_role
from app.constants import ROLE_TEACHER, STATUS_DRAFT_EDITING
from app.database import get_db
from app.models import Course, CourseTeacher, Draft
from app.config import settings
from app.services.material_service import save_material
from app.services.llm_service import generate_draft_text


router = APIRouter()


@router.post("/ui/courses")
def ui_create_course(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    user = require_role(request, db, ROLE_TEACHER)

    title = title.strip()
    if not title or len(title) > 255:
        raise HTTPException(400, "Course title must contain 1 to 255 characters")
    course = Course(title=title, description=description.strip())

    db.add(course)
    db.flush()

    db.add(CourseTeacher(course_id=course.id, user_id=user.id))
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


@router.post("/ui/courses/{course_id}/generate-draft")
def ui_generate_draft(
    request: Request,
    course_id: int,
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

    materials_text = "\n\n".join(
        material.extracted_text or "" for material in course.materials
    )

    draft_content = generate_draft_text(course, materials_text)

    draft_number = len(course.drafts) + 1

    draft = Draft(
        course_id=course.id,
        name=f"RPD Draft v{draft_number} - {course.title}",
        content=draft_content,
        feedback=None,
        status=STATUS_DRAFT_EDITING,
        document_url=None,
    )

    db.add(draft)
    db.commit()

    return RedirectResponse(url="/dashboard", status_code=303)
