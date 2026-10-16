"""Bounded style excerpts from local reference RPDs, separate from course facts."""
import logging
import re
from functools import lru_cache
from pathlib import Path

from app.services.text_extraction_service import extract_material_text
from app.config import PROJECT_DIR

logger = logging.getLogger(__name__)

def reference_examples(directory: str) -> str:
    if not directory:
        return ""
    folder = Path(directory).expanduser()
    if not folder.is_absolute():
        folder = PROJECT_DIR / folder
    if not folder.is_dir():
        logger.warning("RPD example directory is unavailable")
        return ""
    files = [path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in {".docx", ".pdf", ".txt", ".md"} and path.stat().st_size <= 5 * 1024 * 1024]
    files.sort(key=lambda path: ("пример" not in path.stem.lower(), "бак" not in path.stem.lower(), path.name))
    selected = tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in files[:2])
    return cached_examples(selected)

@lru_cache(maxsize=8)
def cached_examples(files):
    examples = []
    for filename, _, _ in files:
        path = Path(filename)
        try:
            text = extract_material_text(path.suffix.lower(), path.read_bytes())
        except Exception:
            logger.warning("An RPD style example could not be read")
            continue
        excerpts = []
        for section, title in ((1, "Цели"), (3, "Результаты обучения"), (5, "Содержание")):
            match = re.search(rf"(?m)^\s*{section}\.\s+[^\n]*\n", text)
            if not match:
                continue
            body = text[match.end():]
            end = re.search(rf"(?m)^\s*{section + 1}\.\s+", body)
            if end:
                body = body[:end.start()]
            # Competency catalogues are deliberately out of this feature's scope.
            lines = [line for line in body.splitlines() if not re.search(r"(?:ОПК|УК|ПК)[-–]\d", line)]
            body = "\n".join(lines).strip()[:800]
            if body:
                excerpts.append(title + ":\n" + body)
        if excerpts:
            examples.append("Образец структуры: " + path.name + "\n" + "\n\n".join(excerpts))
    return "\n\n".join(examples)[:5500]
