"""Render actual repository templates with synthetic data for the autumn report.

Run from the repo root: .venv/bin/python docs/autumn-2026/capture_screenshots.py
Writes HTML into /tmp/rpd-autumn-report.
No application database, model server, or private uploads are used.
"""
import json
import ast
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SEED_DEMO_DATA"] = "false"

from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.constants import ROLE_LABELS, STATUS_LABELS
from app.localization import translate
from app.models import Course
from app.services.course_service import ASSESSMENT_LABELS
from app.services.competency_catalogue_service import load_catalogue
from app.services.document_view_service import document_blocks
from app.services.rpd_content_service import parse_content, render_content, snapshot
from app.services.rpd_evidence_service import source_context

OUT = Path('/tmp/rpd-autumn-report')
OUT.mkdir(exist_ok=True)
(Path(__file__).parent / 'images').mkdir(exist_ok=True)
env = Environment(loader=FileSystemLoader(ROOT / 'app/templates'), autoescape=select_autoescape())
course = Course(id=1, title='Анализ данных', description='Подготовка данных и оценка качества классификации.',
    educational_program='Прикладная математика и информатика', semester=4, total_hours=108,
    contact_hours=54, independent_hours=54, workload_confirmed=True, credits=3,
    assessment_format='exam', topics='Предобработка данных\nМетрики классификации')
user = NS(name='Демонстрационный преподаватель', email='teacher@example.invalid')
ctx = dict(user=user, active_role='USER_TEACHER', user_roles=['USER_TEACHER'],
    role_labels=ROLE_LABELS, status_labels=STATUS_LABELS, role_teacher='USER_TEACHER',
    role_methodist='USER_METHODIST', courses=[course], inbox_drafts=[],
    generation_label='Локальная модель: qwen3:4b',
    generation_hint='Генерация выполняется локально. На CPU это может занять несколько минут.',
    max_upload_mb=25, assessment_labels=ASSESSMENT_LABELS, t=translate)

def save(name, html, css, script=''):
    html = html.replace('<link rel="stylesheet" href="/static/styles.css">', '<style>' + css + '</style>')
    # Set encoding explicitly for file:// rendering; expand/scroll only where requested.
    html = html.replace('<head>', '<head><meta charset="utf-8">', 1)
    html = html.replace('</body>', '<script>' + script + '</script></body>')
    (OUT / (name + '.html')).write_text(html, encoding='utf-8')

old = subprocess.check_output(['git', 'show', '163f265:app/templates/dashboard.html'], cwd=ROOT).decode()
old_css = subprocess.check_output(['git', 'show', '163f265:app/static/styles.css'], cwd=ROOT).decode()
old_ctx = {**ctx, 'role_labels': {'USER_TEACHER': 'Teacher', 'USER_METHODIST': 'Methodist'}}
save('01-baseline-dashboard', env.from_string(old).render(**old_ctx), old_css)

# Additional baseline screens: retain the original templates and workflow states.
baseline_course = NS(id=1, title=course.title, description=course.description,
    materials=[NS(filename='lecture.txt'), NS(filename='practice.md')], drafts=[])
baseline_source = subprocess.check_output(
    ['git', 'show', '163f265:app/services/llm_service.py'], cwd=ROOT).decode()
template_function = next(node for node in ast.parse(baseline_source).body
    if isinstance(node, ast.FunctionDef) and node.name == 'build_template_draft')
namespace = {'Course': Course}
exec(compile(ast.Module(body=[template_function], type_ignores=[]), '<baseline-template>', 'exec'), namespace)
baseline_text = namespace['build_template_draft'](baseline_course,
    'Предобработка данных. Заполнение пропусков. Оценка качества классификации.')
baseline_draft = NS(id=1, name='RPD Draft v1 — Анализ данных', course=baseline_course,
    content=baseline_text, status='DRAFT_EDITING', feedback=None)
baseline_course.drafts = [baseline_draft]
save('07-baseline-course-workflow', env.from_string(old).render(**{**old_ctx, 'courses':[baseline_course]}), old_css)
def old_template(name):
    return env.from_string(subprocess.check_output(
        ['git', 'show', '163f265:app/templates/' + name], cwd=ROOT).decode())
save('08-baseline-draft-editor', old_template('draft_edit.html').render(**old_ctx, draft=baseline_draft), old_css)
baseline_draft.status = 'DRAFT_SUBMITTED_FOR_REVIEW'
baseline_draft.feedback = 'Уточните общую трудоемкость и распределение часов по темам.'
methodist_ctx = {**old_ctx, 'active_role':'USER_METHODIST', 'user_roles':['USER_METHODIST'],
    'user':NS(name='Методист', email='methodist@example.invalid'), 'courses':[], 'inbox_drafts':[baseline_draft]}
save('09-baseline-methodist-inbox', env.from_string(old).render(**methodist_ctx), old_css)
save('10-baseline-feedback', old_template('feedback.html').render(**methodist_ctx, draft=baseline_draft), old_css)
css = (ROOT / 'app/static/styles.css').read_text()
save('02-current-course-form', env.get_template('dashboard.html').render(**ctx), css,
     "document.querySelector('form[action=\"/ui/courses\"]').parentElement.scrollIntoView();")

# Same valid teaching fixture used by the test suite; deterministic, not a model run.
from tests.conftest import teaching_payload, SOURCE_TEXT
payload = teaching_payload.__wrapped__()
payload['assessment_tasks'] = [
    {'topic_index': 1, 'method': 'заполнение пропущенных значений',
     'dataset': {'kind': 'feature_table', 'description': 'Учебная таблица признаков с пропущенными значениями для подготовки к анализу.'},
     'exercise_type': 'prepare_data'},
    {'topic_index': 2, 'method': 'метрики классификации',
     'dataset': {'kind': 'classification_predictions', 'description': 'Учебная таблица с истинными метками классов и предсказаниями классификатора.'},
     'exercise_type': 'evaluate_predictions'},
]
_, sources = source_context('[Источник: lecture-demo.pdf]\nСтраница 1:\n' + SOURCE_TEXT)
content = parse_content(json.dumps(payload, ensure_ascii=False), sources)
review = snapshot(course, content, sources)
draft = NS(id=1, name='Демонстрационный черновик РПД', course=course, status='DRAFT_EDITING', feedback=None)
html = env.get_template('draft_view.html').render(**ctx, draft=draft, generation_review=review,
    document_blocks=document_blocks(render_content(course, content, sources)))
save('04-current-source-evidence', html, css, "document.querySelector('details').open = true;")

# The full, teacher-edited export illustration has its own maintained source.
subprocess.run([sys.executable, str(ROOT / 'docs/rpd-preview/build_example.py')], check=True, cwd=ROOT)
catalogue = load_catalogue()
save('06-working-tree-competency-search', env.get_template('competencies.html').render(
    course=course, programs=catalogue.programs(), program_id=None, search=None, error=None), css)
print('Rendered eight actual UI template views into', OUT)
