"""Teacher-owned course competency search; suggestions are not accepted automatically."""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_course_teacher, require_role, get_user_roles
from app.database import get_db
from app.models import Course
from app.services.competency_catalogue_service import CatalogueError, load_catalogue
from app.services.competency_search_service import search_competencies
from app.services.embedding_service import EmbeddingError
from app.web import templates

router = APIRouter()


def owned_course(request, course_id, db):
    require_course_teacher(request, db, course_id)
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(404, "Дисциплина не найдена.")
    return course


def search_page(request, course, program_id=None, run_search=False):
    context = {"course": course, "programs": [], "program_id": program_id, "search": None, "error": None}
    status = 200
    try:
        catalogue = load_catalogue()
        context["programs"] = catalogue.programs()
        if run_search:
            context["search"] = search_competencies(course, program_id, catalogue=catalogue)
    except ValueError as error:
        context["error"], status = str(error), 422
    except (CatalogueError, EmbeddingError) as error:
        context["error"], status = str(error), 503
    return templates.TemplateResponse(request=request, name="competencies.html", context=context, status_code=status)


@router.get("/courses/{course_id}/competencies")
def competencies_page(request: Request, course_id: int, db: Session = Depends(get_db)):
    course = owned_course(request, course_id, db)
    return search_page(request, course, course.catalogue_program_id)


@router.post("/ui/courses/{course_id}/competencies/search")
def ui_search_competencies(request: Request, course_id: int, program_id: str = Form(default="", max_length=100), db: Session = Depends(get_db)):
    return search_page(request, owned_course(request, course_id, db), program_id.strip() or None, run_search=True)


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    program_id: str | None = Field(default=None, max_length=100)


@router.post("/api/courses/{course_id}/competencies/search")
def api_search_competencies(request: Request, course_id: int, data: SearchInput, db: Session = Depends(get_db)):
    course = owned_course(request, course_id, db)
    try:
        return search_competencies(course, (data.program_id or "").strip() or course.catalogue_program_id)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except (CatalogueError, EmbeddingError) as error:
        raise HTTPException(503, str(error)) from None


@router.get("/api/courses/{course_id}/competency-catalogue")
def generation_catalogue(request: Request, course_id: int, db: Session = Depends(get_db)):
    from app.services.competency_selection_service import catalogue_entries
    from app.services.competency_generation_service import preview_token
    course = owned_course(request, course_id, db)
    try:
        catalogue = load_catalogue()
        entries = catalogue_entries(catalogue, course.catalogue_program_id)
        snapshot = {"program_id": course.catalogue_program_id,
                    "program": next(p for p in catalogue.programs() if p["program_id"] == course.catalogue_program_id),
                    "catalogue_fingerprint": catalogue.fingerprint, "results": [], "warnings": [], "mappings": []}
        return {"entries": entries, "token": preview_token(course, snapshot)}
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except CatalogueError as error:
        raise HTTPException(503, str(error)) from None


@router.get("/programmes/competency-matrix")
def competency_matrix(request: Request, program_id: str = "", unassigned_only: bool = False, db: Session = Depends(get_db)):
    from app.constants import ROLE_METHODIST
    from app.services.competency_matrix_service import programme_matrix
    user = require_role(request, db, ROLE_METHODIST)
    try:
        catalogue = load_catalogue()
        programs = catalogue.programs()
        course_counts = dict(db.query(Course.catalogue_program_id, func.count(Course.id))
                             .group_by(Course.catalogue_program_id).all())
        # Start with a programme containing courses; explicit empty programmes remain selectable.
        program_id = program_id or max(programs, key=lambda p: course_counts.get(p['program_id'], 0))['program_id']
        matrix = programme_matrix(db, catalogue, program_id, unassigned_only)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except CatalogueError as error:
        raise HTTPException(503, str(error)) from None
    return templates.TemplateResponse(request=request, name="competency_matrix.html", context={
        "user": user, "user_roles": get_user_roles(user), "active_role": ROLE_METHODIST,
        "programs": programs, "program_id": program_id, "unassigned_only": unassigned_only,
        "course_counts": course_counts, "courses_without_program": course_counts.get(None, 0), **matrix})
