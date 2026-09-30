"""Validate and extract material text before storing the source document."""
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Material
from app.services.text_extraction_service import extract_material_text

def save_material(db: Session, course_id: int, filename: str | None, content: bytes) -> Material:
    filename = (filename or '').replace('\\', '/').rsplit('/', 1)[-1]
    extension = Path(filename).suffix.lower()
    if len(filename) > 255:
        raise HTTPException(400, 'Filename is too long')
    if not content:
        raise HTTPException(400, 'Uploaded file is empty')
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(413, 'Uploaded file exceeds the 5 MiB limit')
    text = extract_material_text(extension, content)
    directory = settings.upload_dir / f'course_{course_id}'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{uuid4().hex}{extension}'
    material = Material(course_id=course_id, filename=filename, file_path=str(path), extracted_text=text)
    try:
        path.write_bytes(content)
        db.add(material)
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    return material
