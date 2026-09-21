# RPD-AI Prototype

An experimental web app for preparing a Russian-language draft of a university course working program (РПД). A teacher can create a course, upload plain-text materials, generate a draft, edit it in the browser, and download it as DOCX. A methodist can review a submitted draft and leave feedback.

This is a **prototype, not an approved or production-ready RPD system**. Generated text must be checked by a teacher against the official program template and source materials. See [MVP_STATUS.md](MVP_STATUS.md) for the gap between this prototype and the proposed MVP.

## What works today

- Teacher and methodist accounts, roles, dashboards, and a basic review flow.
- Course creation with a title and free-text description.
- Upload of UTF-8 `.txt` or `.md` course materials; at least one upload is required before generation.
- RPD draft generation through a configured VseGPT-compatible API, with a static template fallback when it is unavailable.
- Browser editing of draft text and DOCX download.

The app does **not** yet collect all planned course metadata, suggest competencies from a catalogue, or verify that a generated RPD is complete and accurate. The DOCX export is editable, but it is not a validated university template.

## Local setup (development only)

Requirements: Python 3.12, Docker with Compose for the included PostgreSQL service, and an optional VseGPT API account for AI generation. Run commands from the repository root inside WSL/Linux.

```bash
docker compose up -d db
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create a local `.env` file (it is ignored by Git). The values below match the **development-only** database credentials in `docker-compose.yml`; change them before any shared deployment.

```dotenv
DATABASE_URL=postgresql+psycopg2://rpd_user:rpd_password@localhost:5432/rpd_ai
VSEGPT_API_KEY=
VSEGPT_MODEL=
VSEGPT_BASE_URL=https://api.vsegpt.ru/v1
```

Start the web app:

```bash
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. An empty API key/model uses a static fallback draft rather than AI generation. The app creates its database tables on startup; there is no migration workflow yet. Startup also seeds demo users with known passwords—**do not expose this configuration to the internet or use it with real student/teacher data**.

## Tests

```bash
python -m pytest
```

Tests use a local SQLite database and mock or bypass external generation. They do not establish RPD content quality, competency relevance, or the planned time-saving target.

## Project boundaries

The proposed MVP is a teacher-facing draft generator with structured course input, competency suggestions from a predefined catalogue, editable output, and a DOCX download. University-system integrations, official approval/signing, multi-user co-editing, and complex approval workflows are out of scope. The current methodist review flow is prototype functionality, not official approval.

Review repository contents before sharing: `.env` is ignored, but some sample files under `uploads/` are currently tracked by Git. Do not commit confidential course material or credentials.
