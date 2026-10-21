"""Capture current templates with synthetic data and real local search results.

Run from the repo root with .venv/bin/python docs/week-2026-10-19/capture_screenshots.py.
Use --reuse-search to render from the saved example-search.json without Ollama.
No application database or user uploads are read or changed.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DATABASE_URL', 'sqlite://')
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.models import Course, Draft, Material
from app.services.competency_generation_service import retrieve_for_generation
from app.services.rpd_content_service import parse_content, render_content, snapshot
from app.services.rpd_evidence_service import source_context
from app.services.document_view_service import document_blocks
from app.constants import STATUS_LABELS

HERE = Path(__file__).resolve().parent
OUT = Path('/tmp/rpd-week-2026-10-19')
OUT.mkdir(exist_ok=True)
(HERE / 'images').mkdir(exist_ok=True)
course = Course(id=1, title='Математическое моделирование',
    description='Построение и анализ математических моделей физических процессов.',
    topics='Построение моделей\nЧисленные методы\nАнализ устойчивости',
    educational_program='Прикладная математика и информатика', catalogue_program_id='NSU-ММФ-03',
    semester=4, total_hours=108, contact_hours=36, independent_hours=72,
    workload_confirmed=True, credits=3, assessment_format='exam')
source = ('Математическая модель описывает изучаемый процесс с помощью математических объектов. '
          'Построение модели включает выбор переменных, допущений и уравнений. '
          'При анализе модели исследуются существование решения, устойчивость и зависимость от параметров. '
          'Численные методы позволяют приближенно решать уравнения модели. '
          'Результат расчета проверяется сравнением с исходными предположениями и доступными данными.')
course.materials = [Material(id=1, filename='lecture.pdf', file_path='/synthetic/lecture.pdf', extracted_text='Страница 1:\n' + source)]
if '--reuse-search' in sys.argv:
    search = json.loads((HERE / 'example-search.json').read_text())
else:
    search = retrieve_for_generation(course)
    if search['status'] != 'retrieved':
        raise RuntimeError(search['warnings'])
    (HERE / 'example-search.json').write_text(json.dumps(search, ensure_ascii=False, indent=2) + '\n')

env = Environment(loader=FileSystemLoader(ROOT / 'app/templates'), autoescape=select_autoescape())
env.globals['status_labels'] = STATUS_LABELS
css = (ROOT / 'app/static/styles.css').read_text()
form = env.get_template('generation_form.html').render(course=course)
# The mocked browser transport replays the recorded real model result only for this illustration.
transport = '<script>window.fetch = async()=>({ok:true,json:async()=>(' + json.dumps({'token':'illustration-not-for-submission', 'results':search['results'], 'material_sources':search['material_sources']}, ensure_ascii=False) + ')});</script>'
form_html = ('<!doctype html><html lang="ru"><meta charset="utf-8"><style>' + css +
    '\nbody{padding:28px; margin:0}main{max-width:980px;margin:auto}h1{font-size:25px}' +
    '</style><main><div class="card"><h1>Создание черновика РПД</h1><h2>' + course.title +
    '</h2><p>Загруженные материалы: lecture.pdf</p>' + form + '</div></main>' + transport +
    '<script>' + (ROOT / 'app/static/generation.js').read_text() + '</script><script>setTimeout(()=>document.querySelectorAll(\'[name=competency_ids]\').forEach((item,index)=>{item.checked=index<2}),100);</script></html>')
(OUT / 'generation.html').write_text(form_html)

accepted = {**search, 'results':search['results'][:2], 'accepted':True}
payload = {
    'objectives':['Применять математические модели для описания изучаемых процессов.',
                  'Обосновывать выбор переменных и допущений математической модели.',
                  'Сравнивать результаты вычислений с исходными предположениями.'],
    'knowledge':['Знать этапы построения математической модели.',
                 'Знать основные требования к проверке математической модели.',
                 'Знать подходы к исследованию устойчивости решений.'],
    'skills':['Выбирать переменные и допущения для описания процесса.',
              'Применять численные методы для исследования модели.',
              'Объяснять ограничения результатов математического моделирования.'],
    'topics':[{'title':'Построение математической модели',
               'summary':'Выбор переменных, допущений и уравнений для описания изучаемого процесса.',
               'claims':[{'evidence':{'excerpt_id':'S1E1'}}]},
              {'title':'Анализ модели и проверка результатов',
               'summary':'Исследование устойчивости решений и зависимости от параметров. Сравнение расчета с исходными предположениями.',
               'claims':[{'evidence':{'excerpt_id':'S1E1'}}]}],
    'assessment_tasks':[{'topic_index':i, 'dataset':{'kind':'study_case','description':'Учебное описание физического процесса с заданными исходными условиями и допущениями.'},
                         'method':'математическое моделирование', 'exercise_type':'apply_method'} for i in (1,2)],
    'assessment_criteria':['Обоснованность выбранных переменных и допущений модели.',
                           'Корректность применения выбранного метода исследования.',
                           'Полнота объяснения ограничений полученных результатов.'],
    'competency_mappings':[{'competency_id':entry['id'],'outcome_kind':'skills','outcome_index':i} for i,entry in enumerate(accepted['results'],1)],
}
sources = source_context('[Источник: lecture.pdf]\nСтраница 1:\n' + source)[1]
content = parse_content(json.dumps(payload, ensure_ascii=False), sources, accepted)
text = render_content(course, content, sources, accepted)
# Show only the RPD competency section as a document illustration.
section = text[text.index('3. Перечень'):text.index('4. Трудоемкость')].strip()
metadata = snapshot(course, content, sources)
metadata['status'] = 'validated'
draft = Draft(id=1, name='Черновик РПД — Математическое моделирование', course=course, status='DRAFT_EDITING', content=text)
# Reuse the application's document-block rendering without surrounding application panels.
full = env.get_template('draft_view.html').render(draft=draft, active_role='USER_TEACHER', generation_review={}, document_blocks=document_blocks(section))
article = full[full.index('<article class="rpd-document">'):full.index('</article>')+len('</article>')]
page = '<!doctype html><html lang="ru"><meta charset="utf-8"><head><style>' + css + '</style></head><body><div class="card">' + article + '</div></body></html>'
page = page.replace('<link rel="stylesheet" href="/static/styles.css">', '<style>' + css + '</style>')
page = page.replace('</head>', '<style>.rpd-document{font:18px/1.5 Georgia,serif}.rpd-table{border-collapse:collapse;width:100%}.rpd-table td,.rpd-table th{border:1px solid #888;padding:12px;text-align:left}.card{max-width:1000px;margin:18px auto}body{margin:24px}.rpd-table th{background:#eef5ee}</style></head>')
(OUT / 'draft.html').write_text(page)

for name, filename, height in [('generation','01-generation-suggestions.png',900),('draft','02-rpd-competencies.png',1020)]:
    result = subprocess.run(['google-chrome','--headless','--disable-gpu','--no-sandbox',
        '--disable-dev-shm-usage','--user-data-dir='+str(OUT / ('chrome-'+name)),
        '--window-size=1100,'+str(height),'--virtual-time-budget=2500',
        '--screenshot='+str(HERE / 'images' / filename),'--dump-dom', (OUT / (name+'.html')).as_uri()],
        capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr[-1500:])
    (OUT / (name+'-dom.html')).write_text(result.stdout)
    print(HERE / 'images' / filename)
