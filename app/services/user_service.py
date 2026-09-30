"""Shared account validation and atomic creation for both account forms."""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.constants import ROLE_METHODIST, ROLE_TEACHER
from app.models import User, UserRole

class UserValidationError(ValueError):
    pass

def create_user(db: Session, *, name: str, email: str, password: str, roles: list[str]) -> User:
    name, email = name.strip(), email.strip()
    for invalid, message in (
        (not name, 'Name is required.'),
        (not email, 'Email is required.'),
        (not password, 'Password is required.'),
        (len(password) < 8, 'Password must be at least 8 characters.'),
        (not roles, 'Please select at least one role.'),
        (bool(set(roles) - {ROLE_TEACHER, ROLE_METHODIST}), 'Invalid role selected'),
    ):
        if invalid:
            raise UserValidationError(message)
    if db.query(User).filter(User.email == email).first() is not None:
        raise UserValidationError('A user with this email already exists.')
    user = User(name=name, email=email, password_hash=hash_password(password))
    user.roles = [UserRole(role=role) for role in dict.fromkeys(roles)]
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise UserValidationError('A user with this email already exists.') from None
    db.refresh(user)
    return user
