"""Course form validation shared by creation and editing."""
from decimal import Decimal
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

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
    contact_hours: int | None = Field(default=None, ge=0, le=10000)
    independent_hours: int | None = Field(default=None, ge=0, le=10000)
    workload_confirmed: bool = False
    credits: Decimal | None = Field(default=None, gt=0, le=100, max_digits=5, decimal_places=2, allow_inf_nan=False)
    assessment_format: Literal["exam", "pass", "graded_pass"] | None = None
    topics: str | None = Field(default=None, max_length=16000)

    @field_validator("*", mode="before")
    @classmethod
    def normalize_blanks(cls, value, info):
        if isinstance(value, str):
            value = value.strip()
            if info.field_name == "workload_confirmed" and not value:
                return False
            if not value and info.field_name not in {"title", "description"}:
                return None
        return value

    @model_validator(mode="after")
    def check_workload(self):
        if self.workload_confirmed and self.total_hours is None:
            raise ValueError("Confirmed total workload needs a total hours value")
        if self.total_hours is not None and self.workload_confirmed:
            parts = (self.contact_hours or 0) + (self.independent_hours or 0)
            if parts > self.total_hours:
                raise ValueError("Contact and independent hours exceed total workload")
        return self

async def course_form(request: Request) -> CourseInput:
    form = await request.form()
    values = {name: form[name] for name in CourseInput.model_fields if name in form}
    try:
        return CourseInput.model_validate(values)
    except ValidationError as error:
        raise HTTPException(422, [
            {"field": item["loc"][0] if item["loc"] else "workload", "message": "Проверьте значение поля: оно должно соответствовать допустимому типу и диапазону."}
            for item in error.errors()
        ]) from None
