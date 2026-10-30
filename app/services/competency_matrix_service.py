"""Build a live programme matrix from the newest eligible draft per course."""
from sqlalchemy.orm import selectinload

from app.constants import REVIEWABLE_STATUSES, STATUS_RPD_VALIDATED
from app.models import Course
from app.services.competency_selection_service import catalogue_entries, draft_metadata, selection_keys


def programme_matrix(db, catalogue, program_id, unassigned_only=False):
    entries = catalogue_entries(catalogue, program_id)
    courses = (db.query(Course).filter(Course.catalogue_program_id == program_id)
               .options(selectinload(Course.drafts)).order_by(Course.title, Course.id).all())
    allowed = {(program_id, entry['codes'][0]) for entry in entries}
    columns = []
    for course in courses:
        eligible = [d for d in course.drafts if d.status in [*REVIEWABLE_STATUSES, STATUS_RPD_VALIDATED]]
        source = max(eligible, key=lambda d: (d.created_at, d.id)) if eligible else None
        column = {'course': course, 'draft': source, 'keys': set(), 'state': 'no_draft'}
        if source:
            snapshot = draft_metadata(source).get('competencies')
            column['state'] = 'missing'
            if isinstance(snapshot, dict) and isinstance(snapshot.get('results'), list):
                try:
                    keys = selection_keys(snapshot)
                    if snapshot.get('program_id') != program_id or not keys <= allowed:
                        raise ValueError('Incompatible programme')
                    column.update(keys=keys, state='selected' if keys else 'empty')
                except (ValueError, KeyError, TypeError):
                    column['state'] = 'incompatible'
        columns.append(column)
    rows = []
    assigned_count = 0
    for entry in entries:
        cells = [(program_id, entry['codes'][0]) in column['keys'] for column in columns]
        assigned_count += bool(any(cells))
        if not unassigned_only or not any(cells):
            rows.append({'entry': entry, 'cells': cells, 'assigned': any(cells)})
    return {'columns': columns, 'rows': rows, 'stats': {
        'competencies': len(entries), 'assigned': assigned_count,
        'unassigned': len(entries) - assigned_count, 'courses': len(columns),
        'submitted': sum(column['draft'] is not None for column in columns),
    }}
