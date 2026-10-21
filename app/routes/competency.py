"""Teacher-owned course competency search; suggestions are not accepted automatically."""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth import require_course_teacher
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
    return search_page(request, owned_course(request, course_id, db))


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
        return search_competencies(course, (data.program_id or "").strip() or None)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except (CatalogueError, EmbeddingError) as error:
        raise HTTPException(503, str(error)) from None
