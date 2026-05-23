from app.auth import hash_password
from app.constants import ROLE_METHODIST, ROLE_TEACHER
from app.database import SessionLocal
from app.models import Course, CourseTeacher, User, UserRole


def seed_demo_data():
    db = SessionLocal()

    try:
        demo_users = [
            {
                "name": "Anna Maria",
                "email": "teacher1@example.com",
                "password": "password123",
                "roles": [ROLE_TEACHER, ROLE_METHODIST],
            },
            {
                "name": "Julia Mazine",
                "email": "julia@example.com",
                "password": "password123",
                "roles": [ROLE_TEACHER],
            },
            {
                "name": "Dmitry Ivanov",
                "email": "dmitry@example.com",
                "password": "password123",
                "roles": [ROLE_METHODIST],
            },
        ]

        created_users: dict[str, User] = {}

        for demo_user in demo_users:
            user = db.query(User).filter(User.email == demo_user["email"]).first()

            if user is None:
                user = User(
                    name=demo_user["name"],
                    email=demo_user["email"],
                    password_hash=hash_password(demo_user["password"]),
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            else:
                user.name = demo_user["name"]
                db.commit()
                db.refresh(user)

            created_users[demo_user["email"]] = user

            existing_roles = {role.role for role in user.roles}

            for role_name in demo_user["roles"]:
                if role_name not in existing_roles:
                    db.add(UserRole(user_id=user.id, role=role_name))

            db.commit()

        main_teacher = created_users["teacher1@example.com"]

        all_courses = db.query(Course).all()

        for course in all_courses:
            existing_assignment = (
                db.query(CourseTeacher)
                .filter(CourseTeacher.course_id == course.id)
                .first()
            )

            if existing_assignment is None:
                db.add(CourseTeacher(course_id=course.id, user_id=main_teacher.id))

        db.commit()

    finally:
        db.close()