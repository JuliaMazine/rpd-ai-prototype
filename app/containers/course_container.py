from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import require_course_teacher, require_role
from app.constants import ROLE_TEACHER, STATUS_DRAFT_EDITING
from app.database import get_db
from app.models import Course, CourseTeacher, Draft, Material
from app.services.llm_service import generate_draft_text


router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/ui/courses")
def ui_create_course(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    user = require_role(request, db, ROLE_TEACHER)

    course = Course(title=title, description=description)

    db.add(course)
    db.commit()
    db.refresh(course)

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

    allowed_extensions = [".txt", ".md"]
    file_extension = Path(file.filename).suffix.lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Only .txt and .md are supported in the prototype.",
        )

    course_upload_dir = UPLOAD_DIR / f"course_{course_id}"
    course_upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = course_upload_dir / file.filename

    file_bytes = await file.read()

    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    file_path.write_bytes(file_bytes)

    try:
        extracted_text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Could not read file as UTF-8 text",
        )

    material = Material(
        course_id=course_id,
        filename=file.filename,
        file_path=str(file_path),
        extracted_text=extracted_text,
    )

    db.add(material)
    db.commit()

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