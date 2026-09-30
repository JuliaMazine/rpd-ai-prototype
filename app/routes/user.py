from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import require_login
from app.constants import ROLE_LABELS, ROLE_METHODIST, ROLE_TEACHER
from app.database import get_db
from app.models import User
from app.services.user_service import create_user, UserValidationError


from app.web import templates


router = APIRouter()


@router.get("/admin/users", response_class=HTMLResponse)
def users_page(
    request: Request,
    db: Session = Depends(get_db),
):
    current_user = require_login(request, db)

    users = db.query(User).order_by(User.id).all()

    return templates.TemplateResponse(
        request=request,
        name="users.html",
        context={
            "current_user": current_user,
            "users": users,
            "role_labels": ROLE_LABELS,
            "role_teacher": ROLE_TEACHER,
            "role_methodist": ROLE_METHODIST,
            "error": None,
            "success": None,
        },
    )


@router.post("/admin/users")
async def create_user_from_admin(
    request: Request,
    db: Session = Depends(get_db),
):
    current_user = require_login(request, db)

    form = await request.form()

    name = str(form.get("name", "")).strip()
    email = str(form.get("email", "")).strip()
    password = str(form.get("password", ""))
    roles = form.getlist("roles")

    users = db.query(User).order_by(User.id).all()

    context = {
        "current_user": current_user,
        "users": users,
        "role_labels": ROLE_LABELS,
        "role_teacher": ROLE_TEACHER,
        "role_methodist": ROLE_METHODIST,
        "success": None,
    }

    try:
        create_user(db, name=name, email=email, password=password, roles=roles)
    except UserValidationError as error:
        context["error"] = str(error)
        return templates.TemplateResponse(
            request=request, name="users.html", context=context, status_code=400,
        )

    return RedirectResponse(url="/admin/users", status_code=303)
