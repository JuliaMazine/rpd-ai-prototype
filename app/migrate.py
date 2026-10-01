"""Run `python -m app.migrate` before starting an existing database."""
from sqlalchemy import inspect, text

from app.database import Base, engine
from app.models import Course

COURSE_METADATA_COLUMNS = (
    "educational_program", "semester", "total_hours", "credits", "assessment_format", "topics",
)

def upgrade_course_metadata(connection):
    existing = {item["name"] for item in inspect(connection).get_columns("courses")}
    for name in COURSE_METADATA_COLUMNS:
        if name not in existing:
            column_type = Course.__table__.c[name].type.compile(dialect=connection.dialect)
            connection.execute(text(f"ALTER TABLE courses ADD COLUMN {name} {column_type}"))

def main():
    with engine.begin() as connection:
        Base.metadata.create_all(bind=connection)
        upgrade_course_metadata(connection)
    print("Course metadata schema is up to date.")

if __name__ == "__main__":
    main()
