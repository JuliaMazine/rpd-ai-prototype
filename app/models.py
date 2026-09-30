from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    roles = relationship("UserRole", back_populates="user")
    taught_courses = relationship("CourseTeacher", back_populates="user")


class UserRole(Base):
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(100), nullable=False)

    user = relationship("User", back_populates="roles")


class CourseTeacher(Base):
    __tablename__ = "course_teachers"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    course = relationship("Course", back_populates="teachers")
    user = relationship("User", back_populates="taught_courses")


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    educational_program = Column(String(255), nullable=True)
    semester = Column(Integer, nullable=True)
    total_hours = Column(Integer, nullable=True)
    credits = Column(Numeric(5, 2), nullable=True)
    assessment_format = Column(String(50), nullable=True)
    topics = Column(Text, nullable=True)

    materials = relationship("Material", back_populates="course")
    drafts = relationship("Draft", back_populates="course")
    teachers = relationship("CourseTeacher", back_populates="course")


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)

    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    extracted_text = Column(Text, nullable=True)

    course = relationship("Course", back_populates="materials")


class Draft(Base):
    __tablename__ = "drafts"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)

    name = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    feedback = Column(Text, nullable=True)
    status = Column(String(100), nullable=False, default="DRAFT_EDITING")
    document_url = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    course = relationship("Course", back_populates="drafts")