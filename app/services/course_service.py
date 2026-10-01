"""Course form validation shared by creation and editing."""
from decimal import Decimal
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field, ValidationError, field_validator

ASSESSMENT_LABELS = {
    "exam": "Экзамен",
    "pass": "Зачет",
    "graded_pass": "Дифференцированный зачет",
}

class CourseInput(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=10000)
    educational_program: str | None = Field(default=None, max_length=255)
    semester: int | None = Field(default=None, ge=1, le=20)
    total_hours: int | None = Field(default=None, ge=1, le=10000)
    credits: Decimal | None = Field(default=None, gt=0, le=100, max_digits=5, decimal_places=2, allow_inf_nan=False)
    assessment_format: Literal["exam", "pass", "graded_pass"] | None = None
    topics: str | None = Field(default=None, max_length=16000)

    @field_validator("*", mode="before")
    @classmethod
    def normalize_blanks(cls, value, info):
        if isinstance(value, str):
            value = value.strip()
            if not value and info.field_name not in {"title", "description"}:
                return None
        return value

async def course_form(request: Request) -> CourseInput:
    form = await request.form()
    values = {name: form[name] for name in CourseInput.model_fields if name in form}
    try:
        return CourseInput.model_validate(values)
    except ValidationError as error:
        raise HTTPException(422, [
            {"field": item["loc"][0], "message": "Проверьте значение поля: оно должно соответствовать допустимому типу и диапазону."}
            for item in error.errors()
        ]) from None
