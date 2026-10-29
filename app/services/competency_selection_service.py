"""Draft selections and matrix assignments use programme/code pairs, never retrieval IDs."""
import copy
import json

from app.services.competency_catalogue_service import COLUMNS, load_catalogue
from app.services.competency_generation_service import mapping_text


def catalogue_entries(catalogue, program_id):
    if not program_id:
        raise ValueError("Выберите программу из каталога в сведениях о дисциплине.")
    if program_id not in {p['program_id'] for p in catalogue.programs()}:
        raise ValueError("Программа отсутствует в каталоге.")
    from hashlib import sha256
    return [{"id": sha256((program_id + ':' + row['competence_code']).encode()).hexdigest(),
             "codes": [row['competence_code']], "description": row['competence_description'],
             "programs": [{key: row[key] for key in COLUMNS[:-1]}]}
            for row in catalogue.rows if row['program_id'] == program_id]


def selection_keys(snapshot):
    """Read only the saved programme-specific associations, including legacy snapshots."""
    program_id = snapshot.get('program_id')
    keys = []
    for entry in snapshot.get('results', []):
        associations = entry.get('programs', [])
        if not associations or any(row.get('program_id') != program_id for row in associations):
            raise ValueError("Сохраненный выбор не соответствует программе. Выберите компетенции заново.")
        keys.extend((row['program_id'], row['competence_code']) for row in associations)
    if len(keys) != len(set(keys)):
        raise ValueError("Компетенции не должны повторяться.")
    return set(keys)


def validate_selection(snapshot, catalogue):
    entries = catalogue_entries(catalogue, snapshot.get('program_id'))
    allowed = {(snapshot['program_id'], entry['codes'][0]) for entry in entries}
    if not selection_keys(snapshot) <= allowed:
        raise ValueError("Выбрана компетенция вне программы.")


def add_catalogue_entries(snapshot, codes, catalogue):
    if len(codes) != len(set(codes)):
        raise ValueError("Компетенции не должны повторяться.")
    entries = {entry['codes'][0]: entry for entry in catalogue_entries(catalogue, snapshot.get('program_id'))}
    if not set(codes) <= entries.keys():
        raise ValueError("Выбрана компетенция вне программы.")
    snapshot['results'].extend(copy.deepcopy(entries[code]) for code in codes)
    validate_selection(snapshot, catalogue)
    return snapshot


def draft_metadata(draft):
    try:
        metadata = json.loads(draft.generation_metadata or '{}')
        return metadata if isinstance(metadata, dict) else {}
    except (ValueError, TypeError):
        return {}


def saved_content(metadata):
    from app.services.rpd_content_service import TeachingContent
    return TeachingContent.model_validate(metadata['teaching_content']) if metadata.get('teaching_content') else None


def selection_context(draft):
    metadata = draft_metadata(draft)
    snapshot = metadata.get('competencies')
    context = {'snapshot': snapshot, 'warnings': [], 'empty': not snapshot or not snapshot.get('results')}
    if snapshot is None:
        context['warnings'].append('В этом РПД нет сохраненных сведений о выборе компетенций.')
        return context
    if snapshot.get('program_id') != draft.course.catalogue_program_id:
        context['warnings'].append('Программа дисциплины изменилась. Для дальнейших изменений выберите компетенции текущей программы.')
    try:
        expected = mapping_text(saved_content(metadata), snapshot)
        context["expected_block"] = expected
        if draft.content.count(expected) != 1:
            context['warnings'].append('Таблица компетенций в тексте отличается от сохраненного выбора. Исправьте таблицу перед изменением выбора. Матрица использует сохраненный выбор.')
    except (ValueError, TypeError, KeyError):
        context['warnings'].append('Не удалось проверить соответствие таблицы сохраненному выбору.')
    return context


def selection_editor(draft):
    catalogue = load_catalogue()
    entries = catalogue_entries(catalogue, draft.course.catalogue_program_id)
    snapshot = draft_metadata(draft).get('competencies', {})
    try:
        keys = selection_keys(snapshot) if snapshot.get('program_id') == draft.course.catalogue_program_id else set()
    except (ValueError, KeyError):
        keys = set()
    return {'entries': entries, 'selected_codes': {code for _, code in keys},
            'program_id': draft.course.catalogue_program_id, 'catalogue_fingerprint': catalogue.fingerprint}


def update_draft_selection(draft, codes, program_id, fingerprint, replace_table=False):
    """Replace only an intact competency block, preserving all other teacher edits."""
    catalogue = load_catalogue()
    if fingerprint != catalogue.fingerprint or program_id != draft.course.catalogue_program_id:
        raise ValueError('Программа или каталог изменились. Откройте выбор компетенций заново.')
    metadata = draft_metadata(draft)
    previous = metadata.get('competencies', {})
    content = saved_content(metadata)
    block = mapping_text(content, previous)
    if draft.content.count(block) != 1 and replace_table:
        import re
        from app.services.competency_generation_service import MAPPING_HEADING
        # Replace only a uniquely delimited competency block with explicit teacher consent.
        pattern = re.escape(MAPPING_HEADING) + r".*?(?=\n4\. )"
        blocks = list(re.finditer(pattern, draft.content, re.DOTALL))
        if len(blocks) == 1:
            block = blocks[0].group().rstrip()
    if draft.content.count(block) != 1:
        raise ValueError('Таблица компетенций изменена вручную. Восстановите таблицу по сохраненному выбору перед изменением компетенций.')
    snapshot = {'program_id': program_id, 'results': [], 'warnings': [], 'mappings': [],
                'status': 'accepted', 'accepted': True, 'reviewed': False,
                'catalogue_fingerprint': fingerprint,
                'program': next((p for p in catalogue.programs() if p['program_id'] == program_id), None)}
    add_catalogue_entries(snapshot, codes, catalogue)
    # Keep snapshots and mappings for unchanged programme/code selections.
    previous_by_key = {}
    if previous.get('program_id') == program_id:
        for entry in previous.get('results', []):
            if len(entry.get('programs', [])) == 1:
                row = entry['programs'][0]
                previous_by_key[(row['program_id'], row['competence_code'])] = entry
    snapshot['results'] = [copy.deepcopy(previous_by_key.get((program_id, entry['codes'][0]), entry)) for entry in snapshot['results']]
    if content:
        allowed = {entry['id'] for entry in snapshot['results']}
        content.competency_mappings = [m for m in content.competency_mappings if m.competency_id in allowed]
        snapshot['mappings'] = [m.model_dump() for m in content.competency_mappings]
        metadata['teaching_content'] = content.model_dump()
    replacement = mapping_text(content, snapshot)
    draft.content = draft.content.replace(block, replacement, 1)
    metadata['competencies'] = snapshot
    draft.generation_metadata = json.dumps(metadata, ensure_ascii=False)
