# RPD-AI Prototype

An experimental web app for preparing a Russian-language draft of a university course working program (РПД). A teacher can create a course, upload text, PDF, DOCX, Jupyter, or PowerPoint materials, generate a draft, edit it in the browser, and download it as DOCX. A methodist can review a submitted draft and leave feedback.

This is a **prototype, not an approved or production-ready RPD system**. Generated text must be checked by a teacher against the official program template and source materials. See [MVP_STATUS.md](MVP_STATUS.md) for the gap between this prototype and the proposed MVP.

## What works today

- Teacher and methodist accounts, roles, dashboards, and a basic review flow.
- Course creation and editing with a title, description, educational program, semester, workload, credits, assessment format, and topics.
- Upload of UTF-8 `.txt`/`.md`, text-based `.pdf`, Word `.docx`, Jupyter `.ipynb`, and PowerPoint `.pptx` course materials; at least one upload is required before generation.
- Local RPD draft generation through Ollama, with a clearly marked static template fallback when generation fails.
- Five local embedding-based competency suggestions from the repository CSV, reviewed in the generation form.
- RPD generation using course fields, checked competencies, and uploaded material, with catalogue-backed competency tables.
- Browser editing of draft text and DOCX download.

The app does **not** establish that a generated RPD is complete and accurate. The DOCX export is editable, but it is not a validated university template.

## Local setup (development only)

Requirements: Python 3.12, Docker with Compose for PostgreSQL, and Ollama with a downloaded model for local AI generation. Run commands from the repository root inside WSL/Linux.

```bash
docker compose up -d db
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install pytest
```

Create a local `.env` file (it is ignored by Git). The values below match the **development-only** database credentials in `docker-compose.yml`; change them before any shared deployment.

```dotenv
DATABASE_URL=postgresql+psycopg2://rpd_user:rpd_password@localhost:5432/rpd_ai
SESSION_SECRET=replace-with-a-random-secret
SEED_DEMO_DATA=true
SECURE_COOKIES=false
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
OLLAMA_CONTEXT_LENGTH=16384
LLM_TIMEOUT_SECONDS=600
LLM_MAX_TOKENS=4500
MAX_UPLOAD_MB=25
RPD_EXAMPLES_DIR=references/rpd_examples
```

Install [Ollama](https://ollama.com/download) on the machine hosting the app. Start its server (`ollama serve` if it is not already running), then download the model:

```bash
ollama pull qwen3:4b
ollama list
```

Local generation needs no API key. Start the web app:

```bash
python -m app.migrate
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. Without a configured model/provider, a static fallback draft is used instead of AI generation. The app creates its database tables on startup; run `python -m app.migrate` before startup to add course fields (including the catalogue program ID) and draft evidence metadata to an existing database. This additive upgrade is idempotent and preserves existing records; back up any shared database before upgrading. It is a prototype upgrade utility, not a general migration framework. Demo seeding is disabled by default; `SEED_DEMO_DATA=true` enables demo users with known passwords—**do not expose this configuration to the internet or use it with real student/teacher data**.

## Tests

```bash
python -m pytest
```

Tests use an in-memory SQLite database and temporary upload directories and mock or bypass external generation. They do not establish RPD content quality, competency relevance, or the planned time-saving target.

## Project boundaries

The proposed MVP is a teacher-facing draft generator with structured course input, competency suggestions from a predefined catalogue, editable output, and a DOCX download. University-system integrations, official approval/signing, multi-user co-editing, and complex approval workflows are out of scope. The current methodist review flow is prototype functionality, not official approval.

Review repository contents before sharing: `.env` is ignored, but some sample files under `uploads/` are currently tracked by Git. Do not commit confidential course material or credentials.

## Code organization

- `app/routes/`: HTTP handlers for authentication, courses, drafts, and reviews.
- `app/services/`: shared user validation/creation, material storage, generation, seeding, and DOCX export.
- `app/auth.py`: session and role checks, including course ownership and draft read access.
- `app/config.py`: environment settings and absolute project paths; `.env.example` lists supported settings.
- `app/main.py`: app factory and startup lifecycle. Importing it does not create tables or seed users.

Set a random persistent `SESSION_SECRET` (for example, generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"`). If omitted, a random secret is generated on each process start and existing sessions expire after restart. Use `SECURE_COOKIES=true` when serving over HTTPS. `UPLOAD_DIR` can override the default project upload folder. Uploads are limited to 25 MiB by default (configure `MAX_UPLOAD_MB`, an integer from 1 to 100, then restart the app), validated and converted to text before writing, and stored using unique server-generated filenames.

The existing prototype account policy still allows self-registration as a teacher or methodist and user management by any signed-in user. An administrator role and restricted registration require a separate access-policy change.

Course metadata is optional so older courses remain usable. Semester accepts integers 1–20, total workload 1–10,000 academic hours, contact and independent work 0–10,000 hours each, and credits a positive value up to 100 with at most two decimal places. Total workload must be explicitly confirmed; existing hours keep their value but remain unconfirmed. Contact and independent hours cannot exceed a confirmed total when summed. Assessment choices are exam, pass, and graded pass. Both AI prompts and fallback drafts use these fields. Missing values remain marked for confirmation; hours are not automatically inferred from credits. Changing course details affects future drafts, not previously saved drafts.

The interface, field hints, review status labels, and draft generation use Russian. The topics field asks what students will study and accepts one topic per line.

PDF extraction reads the document text layer; image-only scans require OCR before upload. Password-protected PDFs and unreadable documents are rejected. DOCX extraction includes paragraphs and tables in document order; images, headers, footers, and text boxes are not extracted. Save older `.doc` files as `.docx` before uploading. Extracted text feeds the existing draft-generation flow; original files are retained.

## Local generation with Ollama

Local generation uses Ollama's native `/api/chat` endpoint and needs no API key. It runs on the machine hosting the app; models must be downloaded there. Initial model loading and CPU generation may take several minutes. This setup disables thinking output and reserves a 16K context window for the prompt and answer. Set the timeout (1–3600 seconds), output limit (1–32768 tokens), and context length (512–131072 tokens) for the model and available memory. The current materials prompt is limited to 16,000 characters. Increase context if longer prompts or answers require it; this increases memory use.

Use `LLM_PROVIDER=template` to disable AI requests. Keep `LLM_PROVIDER=ollama` explicitly set in `.env`; the legacy code default when this variable is omitted is still VseGPT. If the server is unavailable, the model is missing, the request times out, or the response is empty, the app returns a clearly marked template draft. Responses cut short by the output limit also produce a marked template fallback. No automatic switch to a paid service occurs.

Jupyter notebook extraction validates the notebook and reads Markdown, raw text, and code cell sources in cell order without executing them. Saved outputs, attachments, and images are excluded. PowerPoint extraction reads slide text, grouped shapes, and tables in slide order. Images, charts, and speaker notes are excluded. Save older `.ppt` presentations as `.pptx` before uploading. The same configurable upload limit applies to these formats.

The displayed upload limit and rejection message follow `MAX_UPLOAD_MB`. Compressed Word/PowerPoint documents and PDF content streams have a separate 100 MiB expansion limit. Larger uploads do not increase the generation prompt budget: materials are still capped at 16,000 characters per request.


RPD generation now requests structured teaching content and validates goals, learning outcomes, topic explanations, practical work, and assessment proposals before rendering the document. Administrative facts, workload, assessment format, and competency tables are rendered by the app. Every uploaded material gets part of the 16,000-character input budget, with excerpts spread over longer files. The model writes syllabus descriptions linked to selected excerpt IDs; the app retrieves exact source text for review. The saved draft keeps the excerpts, filenames, page/slide/cell locations, extracted-text offsets, and SHA-256 fingerprints. Source evidence is available in a collapsed section below the draft and stays outside the RPD text and DOCX. Automatic coverage diagnostics remain in saved generation metadata; they are not displayed as reviewer remarks. The document follows the supplied examples with a title page, full section headings, and tables for learning outcomes, workload, syllabus, and independent work. Editing a draft marks its evidence as belonging to the original generated version.

Exercise instructions and expected deliverables are built by the app from task types and a named method. Every syllabus topic has an assessment task; prediction evaluation requires true targets and predictions. Each exercise uses one proposed teaching dataset, which the teacher must prepare; model-written numerical answers and free-form exercise steps are rejected. Reasonable teaching additions are allowed; missing source support becomes a review note rather than a generation failure. Structurally invalid responses receive one correction attempt, then a marked template fallback if validation still fails.

Coverage warnings flag missing deep-learning/NLP material and unmatched teacher topics, plus ambiguous workload hours. These are keyword checks, not a complete syllabus audit. Exact excerpts establish source provenance; teachers still need to verify source quality, topic relevance, proposed outcomes, and exercise suitability.

Set `RPD_EXAMPLES_DIR` to a local folder of `.docx`, `.pdf`, `.txt`, or `.md` reference programs to guide style and detail. Up to two examples (files containing `пример` are prioritized) contribute short excerpts from sections 1, 3, and 5. They are explicitly separate from teaching sources and must not supply the new course's topics, workload, bibliography, or competency codes. Two owner-supplied examples are included in `references/rpd_examples`; set `RPD_EXAMPLES_DIR=references/rpd_examples` to use them, or choose another local folder. Relative paths resolve against the repository root. Changes to the selected files refresh the cached excerpts.

## Optional external provider

VseGPT remains supported for older installations. To use it instead of Ollama, set `LLM_PROVIDER=vsegpt` and supply `VSEGPT_API_KEY`, `VSEGPT_MODEL`, and `VSEGPT_BASE_URL` (default: `https://api.vsegpt.ru/v1`). It is an external, potentially paid service; Ollama does not require these settings. The app never automatically switches from Ollama to VseGPT.


## Competency search (SCRUM-5)

Download the separate local embedding model once:

```bash
ollama pull qwen3-embedding:0.6b
```

For standalone catalogue inspection, open **Проверить подбор компетенций → Открыть поиск по каталогу** on a course card. Search embeds sampled excerpts from uploaded materials, supplemented by the saved description and topics, and returns the five most similar competency descriptions from `data/competencies_NSU_MMF_FIT.csv`. The saved catalogue program is used by default; the standalone search also allows changing the filter; otherwise identical descriptions are grouped with their original program-specific codes. Without uploaded material, search falls back to the description and topics and makes no requests to VseGPT or a paid embedding API.

The default model is `qwen3-embedding:0.6b`, served by Ollama at `OLLAMA_BASE_URL`. Override it with `OLLAMA_EMBEDDING_MODEL`. `EMBEDDING_TIMEOUT_SECONDS` controls each local request (1–600, default 120). Ollama uses available GPU acceleration. The first search builds document vectors in batches; subsequent searches reuse the SQLite cache at `COMPETENCY_EMBEDDING_CACHE` (default `.cache/competency_embeddings.sqlite3`, ignored by Git). Changes to a competency description, model digest, or server invalidate the corresponding cached vectors. Query vectors are not persisted. The ranking uses cosine similarity, which is not a confidence probability. Missing models, server errors, and invalid vectors produce an actionable error rather than fabricated results.

Authenticated teacher-only endpoints:

- `GET /courses/{id}/competencies` — search page.
- `POST /ui/courses/{id}/competencies/search` — form with optional `program_id`.
- `POST /api/courses/{id}/competencies/search` — JSON `{}` or `{"program_id": "NSU-ММФ-10"}`; returns ranked results, source catalogue fingerprint, and model digest.

Standalone search only returns suggestions. SCRUM-8 integrates acceptance into the generation form as described below. Existing databases need `python -m app.migrate` to add the nullable `catalogue_program_id` course field.

## RPD generation with accepted competencies (SCRUM-8)

In **Создание черновика**, suggestions load automatically using the program saved in course settings. There is no second program selector. With no saved catalogue program, search covers all programs for exploration; confirming a competency selection requires choosing a catalogue program in the course settings. The form loads up to five local suggestions from `data/competencies_NSU_MMF_FIT.csv`, with every suggestion initially checked. Uncheck unsuitable entries and click **Создать черновик РПД**; this action accepts the checked entries for that draft. No separate acceptance screen is required. **Заменить невыбранные** keeps checked suggestions and replaces unchecked ones with the next-ranked candidates. Rejected entries stay excluded during repeated replacements; when alternatives run out, the form keeps the checked entries and explains why fewer than five remain. A failed refresh preserves the previous selection. Change the program in course settings when needed. Uploaded text is the main search input: excerpts are sampled across files with a 12,000-character budget; description and topics add up to 2,000 characters each.

Generation sends the course fields, only the accepted competency IDs/codes/descriptions, and bounded excerpts of uploaded materials to the configured generator (normally local Ollama). The model proposes learning-outcome mappings using only the accepted IDs. The app rejects invented IDs, invalid outcome references, and duplicate mappings, and renders exact catalogue codes and descriptions into the RPD and DOCX. Accepted competencies without a supported mapping remain in the table with a review placeholder and a warning; the app does not fabricate a relationship.

The preview is signed and valid for one hour. Generation validates it against the course description/topics, saved program, uploaded extracted-text fingerprints, and current catalogue fingerprint; it does not silently rerun ranking when Generate is clicked. The draft saves the original suggestions, accepted entries, program information, catalogue fingerprint, embedding model/digest, and mappings in `generation_metadata`. Subsequent catalogue changes do not rewrite saved drafts. Competency mappings are part of section 3 of the draft. Teachers correct mappings through the ordinary draft text editor. Structured selection changes are available separately in the draft editor, as described below.

If retrieval fails, the form offers a retry or an explicit checkbox to continue without competencies. Unchecking all suggestions also permits generation with a review warning and a competency placeholder. Unconfirmed search results are never automatically sent to generation. Generator failures retain the existing marked template fallback.

`POST /api/courses/{id}/generation-competencies` accepts JSON `{}` to use the saved course program (or optional `{"program_id": "NSU-ММФ-03"}` to override it) and returns a signed preview plus results. To replace unchecked suggestions, send the previous `token` and `selected_ids` for the checked entries; exclusions are kept in the signed preview. `POST /ui/courses/{id}/generate-draft` accepts `catalogue_program_id`, `competency_token`, repeated checked `competency_ids`, and optional `skip_competencies`. All endpoints require the assigned teacher. `POST /ui/drafts/{id}/competencies` updates learning-outcome mappings within editable drafts using saved accepted entries.

Local checks with `qwen3-embedding:0.6b` covered machine learning, mathematical modeling, and foreign-language examples. These are smoke checks, not a teacher-rated relevance benchmark or evidence of the time-saving target.

## Competency selection and programme matrix (SCRUM-13)

Choose a catalogue programme in course settings before confirming competencies. In the generation form, teachers can accept suggestions and add entries from the programme's full catalogue, with no required count or type quotas. The full catalogue remains usable if embedding retrieval fails. Catalogue additions use a signed preview tied to the same course inputs, materials, and catalogue fingerprint as suggestions. Replacing unchecked suggestions preserves manually selected catalogue entries. Empty selections remain allowed; submission and resubmission display a reminder and a button to continue without competencies.

The draft editor offers **Изменить выбор компетенций** in editing and returned-for-correction statuses. Saving validates programme/code membership and duplicates, updates only the competency table, retains existing supported mappings, and gives new entries a mapping placeholder. Unchanged entries keep their saved wording. Other teacher text remains intact, and DOCX uses the updated draft text. Manually changed competency tables show a discrepancy warning; teachers can explicitly replace that table when saving the selection. If the table boundaries have also been removed, repair those boundaries in the text editor first. Older drafts without a recognisable competency block require a new draft for structured selection editing.

The methodist dashboard links to **Матрица компетенций программы** (`/programmes/competency-matrix`). Every repository programme is available. Rows include the complete programme catalogue and columns include all associated courses. Each column uses only its newest submitted, resubmitted, or validated RPD, ordered by creation time then ID. Editing and returned drafts are excluded; returning a draft falls back to the next eligible version. The source RPD and its status are linked in the column. Missing records, explicitly empty selections, and programme mismatches have distinct labels. **Только неназначенные компетенции** filters rows with no eligible assignments. The view is recomputed on each load and never infers assignments from RPD prose or learning-outcome mappings.

The RPD view shows that draft's saved programme and selection for teacher and methodist review. Course or catalogue changes do not rewrite historical snapshots. Selections reuse `generation_metadata`; SCRUM-13 requires no additional database migration.
