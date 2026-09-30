from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import get_active_role, get_current_user, get_user_roles
from app.constants import (
    REVIEWABLE_STATUSES,
    ROLE_LABELS,
    ROLE_METHODIST,
    ROLE_TEACHER,
)
from app.database import get_db
from app.models import Course, CourseTeacher, Draft
from app.services.course_service import ASSESSMENT_LABELS


from app.web import templates


router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    active_role = get_active_role(request)
    user_roles = get_user_roles(user)

    if active_role is None:
        if len(user_roles) == 1:
            request.session["active_role"] = user_roles[0]
            active_role = user_roles[0]
        else:
            return RedirectResponse(url="/select-role", status_code=303)

    if active_role not in user_roles:
        request.session.pop("active_role", None)
        return RedirectResponse(url="/select-role", status_code=303)

    if active_role == ROLE_TEACHER:
        courses = (
            db.query(Course)
            .join(CourseTeacher, CourseTeacher.course_id == Course.id)
            .filter(CourseTeacher.user_id == user.id)
            .order_by(Course.id)
            .all()
        )
    else:
        courses = []

    inbox_drafts = []

    if active_role == ROLE_METHODIST:
        inbox_drafts = (
            db.query(Draft)
            .filter(Draft.status.in_(REVIEWABLE_STATUSES))
            .order_by(Draft.created_at.desc())
            .all()
        )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user": user,
            "active_role": active_role,
            "user_roles": user_roles,
            "role_labels": ROLE_LABELS,
            "role_teacher": ROLE_TEACHER,
            "role_methodist": ROLE_METHODIST,
            "courses": courses,
            "assessment_labels": ASSESSMENT_LABELS,
            "inbox_drafts": inbox_drafts,
        },
    )
