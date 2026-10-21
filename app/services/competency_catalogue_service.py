"""Read the repository catalogue without inventing or rewriting competencies."""
import csv
from dataclasses import dataclass
from hashlib import sha256
from io import StringIO
from pathlib import Path

from app.config import PROJECT_DIR

CATALOGUE_PATH = PROJECT_DIR / "data" / "competencies_NSU_MMF_FIT.csv"
COLUMNS = ("program_id", "faculty", "education_level", "direction_code", "direction_name", "profile", "competence_type", "competence_code", "competence_description")


class CatalogueError(Exception):
    pass


@dataclass(frozen=True)
class Catalogue:
    fingerprint: str
    rows: tuple[dict, ...]

    def programs(self):
        programs = {}
        for row in self.rows:
            programs.setdefault(row["program_id"], {key: row[key] for key in COLUMNS[:6]})
        return sorted(programs.values(), key=lambda row: (row["faculty"], row["education_level"], row["direction_code"], row["profile"], row["program_id"]))

    def competencies(self, program_id=None):
        if program_id and program_id not in {row["program_id"] for row in self.rows}:
            raise ValueError("Образовательная программа не найдена в каталоге.")
        grouped = {}
        for row in self.rows:
            if program_id and row["program_id"] != program_id:
                continue
            normalized = " ".join(row["competence_description"].split())
            identifier = sha256(normalized.encode()).hexdigest()
            if identifier not in grouped:
                grouped[identifier] = {"id": identifier, "description": row["competence_description"], "codes": [], "programs": []}
            entry = grouped[identifier]
            if row["competence_code"] not in entry["codes"]:
                entry["codes"].append(row["competence_code"])
            entry["programs"].append({key: row[key] for key in COLUMNS[:-1]})
        return list(grouped.values())


def load_catalogue(path: Path | None = None):
    try:
        content = (path or CATALOGUE_PATH).read_bytes()
        reader = csv.DictReader(StringIO(content.decode("utf-8-sig")))
        if not set(COLUMNS) <= set(reader.fieldnames or []):
            raise ValueError("Missing catalogue columns")
        rows = []
        seen = set()
        for row in reader:
            entry = {key: (row.get(key) or "").strip() for key in COLUMNS}
            if not all(entry.values()):
                raise ValueError("Empty catalogue fields")
            key = (entry["program_id"], entry["competence_code"])
            if key in seen:
                raise ValueError("Duplicate program/competency code")
            seen.add(key)
            rows.append(entry)
        if not rows:
            raise ValueError("Empty catalogue")
    except (OSError, UnicodeError, ValueError, csv.Error) as error:
        raise CatalogueError("Каталог компетенций недоступен или содержит некорректные данные.") from error
    return Catalogue(sha256(content).hexdigest(), tuple(rows))
