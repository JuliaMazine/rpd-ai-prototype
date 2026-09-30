from fastapi import HTTPException, Request
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.constants import ROLE_TEACHER, ROLE_METHODIST
from app.models import CourseTeacher, Draft, User


password_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def get_user_roles(user: User) -> list[str]:
    return [role.role for role in user.roles]


def get_current_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")

    if not user_id:
        return None

    return db.query(User).filter(User.id == user_id).first()


def require_login(request: Request, db: Session) -> User:
    user = get_current_user(request, db)

    if user is None:
        raise HTTPException(status_code=401, detail="Login required")

    return user


def get_active_role(request: Request) -> str | None:
    return request.session.get("active_role")


def require_role(request: Request, db: Session, required_role: str) -> User:
    user = require_login(request, db)
    active_role = get_active_role(request)

    if active_role != required_role:
        raise HTTPException(
            status_code=403,
            detail=f"This action requires role {required_role}",
        )

    user_roles = get_user_roles(user)

    if required_role not in user_roles:
        raise HTTPException(
            status_code=403,
            detail="User does not have this role",
        )

    return user


def user_is_course_teacher(user_id: int, course_id: int, db: Session) -> bool:
    assignment = (
        db.query(CourseTeacher)
        .filter(
            CourseTeacher.user_id == user_id,
            CourseTeacher.course_id == course_id,
        )
        .first()
    )

    return assignment is not None


def require_course_teacher(
    request: Request,
    db: Session,
    course_id: int,
) -> User:
    user = require_role(request, db, ROLE_TEACHER)

    if not user_is_course_teacher(user.id, course_id, db):
        raise HTTPException(
            status_code=403,
            detail="Teacher is not assigned to this course",
        )

    return user


def require_draft_teacher(
    request: Request,
    db: Session,
    draft_id: int,
) -> tuple[User, Draft]:
    user = require_role(request, db, ROLE_TEACHER)

    draft = db.query(Draft).filter(Draft.id == draft_id).first()

    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    if not user_is_course_teacher(user.id, draft.course_id, db):
        raise HTTPException(
            status_code=403,
            detail="Teacher is not assigned to this draft's course",
        )

    return user, draft

def require_draft_reader(request: Request, db: Session, draft_id: int) -> Draft:
    """Readers must have their active role and teachers must own the course."""
    role = get_active_role(request)
    if role == ROLE_TEACHER:
        _, draft = require_draft_teacher(request, db, draft_id)
        return draft
    if role == ROLE_METHODIST:
        require_role(request, db, ROLE_METHODIST)
        draft = db.get(Draft, draft_id)
        if draft is None:
            raise HTTPException(404, "Draft not found")
        return draft
    require_login(request, db)
    raise HTTPException(403, "Access denied")
