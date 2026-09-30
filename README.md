# RPD-AI Prototype

An experimental web app for preparing a Russian-language draft of a university course working program (РПД). A teacher can create a course, upload text, PDF, or DOCX materials, generate a draft, edit it in the browser, and download it as DOCX. A methodist can review a submitted draft and leave feedback.

This is a **prototype, not an approved or production-ready RPD system**. Generated text must be checked by a teacher against the official program template and source materials. See [MVP_STATUS.md](MVP_STATUS.md) for the gap between this prototype and the proposed MVP.

## What works today

- Teacher and methodist accounts, roles, dashboards, and a basic review flow.
- Course creation and editing with a title, description, educational program, semester, workload, credits, assessment format, and topics.
- Upload of UTF-8 `.txt`/`.md`, text-based `.pdf`, and Word `.docx` course materials; at least one upload is required before generation.
- RPD draft generation through a configured VseGPT-compatible API, with a static template fallback when it is unavailable.
- Browser editing of draft text and DOCX download.

The app does **not** yet suggest competencies from a catalogue or verify that a generated RPD is complete and accurate. The DOCX export is editable, but it is not a validated university template.

## Local setup (development only)

Requirements: Python 3.12, Docker with Compose for the included PostgreSQL service, and an optional VseGPT API account for AI generation. Run commands from the repository root inside WSL/Linux.

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
VSEGPT_API_KEY=
VSEGPT_MODEL=
VSEGPT_BASE_URL=https://api.vsegpt.ru/v1
```

Start the web app:

```bash
python -m app.migrate
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. An empty API key/model uses a static fallback draft rather than AI generation. The app creates its database tables on startup; run `python -m app.migrate` before startup to add the course metadata columns to an existing database. This additive upgrade is idempotent and preserves existing records; back up any shared database before upgrading. It is a prototype upgrade utility, not a general migration framework. Demo seeding is disabled by default; `SEED_DEMO_DATA=true` enables demo users with known passwords—**do not expose this configuration to the internet or use it with real student/teacher data**.

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

Set a random persistent `SESSION_SECRET` (for example, generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"`). If omitted, a random secret is generated on each process start and existing sessions expire after restart. Use `SECURE_COOKIES=true` when serving over HTTPS. `UPLOAD_DIR` can override the default project upload folder. Uploads are limited to 5 MiB, validated and converted to text before writing, and stored using unique server-generated filenames.

The existing prototype account policy still allows self-registration as a teacher or methodist and user management by any signed-in user. An administrator role and restricted registration require a separate access-policy change.

Course metadata is optional so older courses remain usable. Semester accepts integers 1–20, workload 1–10,000 academic hours, and credits a positive value up to 100 with at most two decimal places. Assessment choices are exam, pass, and graded pass. Both AI prompts and fallback drafts use these fields. Missing values remain marked for confirmation; hours are not automatically inferred from credits. Changing course details affects future drafts, not previously saved drafts.

The interface, field hints, review status labels, and draft generation use Russian. The topics field asks what students will study and accepts one topic per line.

PDF extraction reads the document text layer; image-only scans require OCR before upload. Password-protected PDFs and unreadable documents are rejected. DOCX extraction includes paragraphs and tables in document order; images, headers, footers, and text boxes are not extracted. Save older `.doc` files as `.docx` before uploading. Extracted text feeds the existing draft-generation flow; original files are retained.
