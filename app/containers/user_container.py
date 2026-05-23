from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import hash_password, require_login
from app.constants import ROLE_LABELS, ROLE_METHODIST, ROLE_TEACHER
from app.database import get_db
from app.models import User, UserRole


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


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
    password = str(form.get("password", "")).strip()
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

    if not name:
        context["error"] = "Name is required."
        return templates.TemplateResponse(
            request=request,
            name="users.html",
            context=context,
            status_code=400,
        )

    if not email:
        context["error"] = "Email is required."
        return templates.TemplateResponse(
            request=request,
            name="users.html",
            context=context,
            status_code=400,
        )

    if not password:
        context["error"] = "Password is required."
        return templates.TemplateResponse(
            request=request,
            name="users.html",
            context=context,
            status_code=400,
        )

    if len(password) < 8:
        context["error"] = "Password must be at least 8 characters."
        return templates.TemplateResponse(
            request=request,
            name="users.html",
            context=context,
            status_code=400,
        )

    if not roles:
        context["error"] = "Please select at least one role."
        return templates.TemplateResponse(
            request=request,
            name="users.html",
            context=context,
            status_code=400,
        )

    allowed_roles = {ROLE_TEACHER, ROLE_METHODIST}

    for role in roles:
        if role not in allowed_roles:
            raise HTTPException(status_code=400, detail="Invalid role selected")

    existing_user = db.query(User).filter(User.email == email).first()

    if existing_user is not None:
        context["error"] = "A user with this email already exists."
        return templates.TemplateResponse(
            request=request,
            name="users.html",
            context=context,
            status_code=400,
        )

    new_user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    for role in roles:
        db.add(UserRole(user_id=new_user.id, role=role))

    db.commit()

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
            "success": f"User {new_user.name} was created successfully.",
        },
    )