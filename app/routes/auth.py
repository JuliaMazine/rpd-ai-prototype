from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import (
    get_current_user,
    get_user_roles,
    verify_password,
)
from app.constants import ROLE_LABELS
from app.database import get_db
from app.models import User
from app.services.user_service import create_user, UserValidationError


from app.web import templates


router = APIRouter()


@router.get("/")
def home():
    return RedirectResponse(url="/login", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": None,
            "success": None,
            "email": "",
        },
    )


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email).first()

    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Authorization failed",
                "success": None,
                "email": email,
            },
            status_code=401,
        )

    request.session.clear()
    request.session["user_id"] = user.id

    roles = get_user_roles(user)

    if len(roles) == 1:
        request.session["active_role"] = roles[0]
        return RedirectResponse(url="/dashboard", status_code=303)

    return RedirectResponse(url="/select-role", status_code=303)


@router.post("/register")
async def register(
    request: Request,
    db: Session = Depends(get_db),
):
    form = await request.form()

    name = str(form.get("name", "")).strip()
    email = str(form.get("email", "")).strip()
    password = str(form.get("password", ""))
    roles = form.getlist("roles")

    try:
        new_user = create_user(db, name=name, email=email, password=password, roles=roles)
    except UserValidationError as error:
        return templates.TemplateResponse(
            request=request, name="login.html",
            context={"error": str(error), "success": None, "email": email},
            status_code=400,
        )

    request.session.clear()
    request.session["user_id"] = new_user.id

    if len(roles) == 1:
        request.session["active_role"] = roles[0]
        return RedirectResponse(url="/dashboard", status_code=303)

    return RedirectResponse(url="/select-role", status_code=303)


@router.get("/select-role", response_class=HTMLResponse)
def select_role_page(
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    roles = get_user_roles(user)

    return templates.TemplateResponse(
        request=request,
        name="select_role.html",
        context={
            "user": user,
            "roles": roles,
            "role_labels": ROLE_LABELS,
        },
    )


@router.post("/select-role")
def select_role(
    request: Request,
    role: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    roles = get_user_roles(user)

    if role not in roles:
        raise HTTPException(status_code=403, detail="User does not have this role")

    request.session["active_role"] = role

    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/switch-role")
def switch_role(
    request: Request,
    role: str,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    roles = get_user_roles(user)

    if role not in roles:
        raise HTTPException(status_code=403, detail="User does not have this role")

    request.session["active_role"] = role

    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
