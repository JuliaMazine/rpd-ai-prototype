# RPD-AI Prototype

Prepare a Russian-language university course working program (РПД) from teaching materials, with local AI generation, editable drafts, competency selection, and DOCX export.

A teacher creates a course, uploads materials, reviews catalogue suggestions, and generates a draft. A methodist can return it with feedback or mark it validated and inspect competency coverage across a programme.

**Prototype:** generated content needs teacher review against the official programme template and source materials. Content completeness, DOCX compliance, competency relevance, and the proposed 50% time saving still need pilot evaluation. See [MVP status](MVP_STATUS.md).

## Watch the demo

[Two-minute walkthrough with English captions](artifacts/app-overview-demo/rpd-app-overview-2min.mp4) covers course materials, an existing draft, review, the programme matrix, and Word export. [Chapters and sample DOCX](artifacts/app-overview-demo/README.md).

For a live presentation, follow the same sequence:

1. Open a teacher course and inspect its details and uploaded materials.
2. Review selected competencies and open a saved draft.
3. Edit and save the draft, then submit it for review.
4. Switch to the methodist role; inspect the RPD and leave feedback or validate it.
5. Open the programme competency matrix, then export the RPD as DOCX.

The recording uses synthetic data and a previously generated draft. Fresh local generation can take several minutes; prepare a draft before presenting.

## What works

- Course details: programme, semester, confirmed workload, credits, assessment, and topics.
- Teaching materials: TXT/Markdown, text-based PDF, DOCX, Jupyter, and PowerPoint.
- Local competency search with Ollama embeddings, teacher selection, and a full programme catalogue.
- Local RPD generation with Ollama, source excerpts for review, and a marked template fallback.
- Browser editing, DOCX export, teacher/methodist review, and a programme competency matrix.
- Russian interface and generated documents.

## Run locally

Use Python 3.12, Docker Compose, and Ollama on Linux/WSL. From the repository root:

```bash
docker compose up -d db
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

In `.env`, set a persistent random `SESSION_SECRET`. For an isolated local demo, set `SEED_DEMO_DATA=true`. Keep the development database credentials local.

With the Ollama server running, download both models and start the app:

```bash
ollama pull qwen3:14b
ollama pull qwen3-embedding:0.6b
python -m app.migrate
python -m uvicorn app.main:app --reload --host 127.0.0.1
```

Open <http://127.0.0.1:8000>. With demo seeding enabled on a fresh database, sign in as `teacher1@example.com` / `password123` to access both roles. Seeding creates accounts; create a course and upload materials to begin. Use this configuration only for local synthetic data.

Set `LLM_PROVIDER=template` to try draft creation without AI generation. Competency embedding search still requires Ollama; the full catalogue remains available without it.

See the [development and workflow reference](docs/development.md) for configuration, upload limits, database upgrades, generation evidence, competency selection, and review behavior.

## Verify

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests use SQLite and temporary uploads, with external generation mocked or bypassed. They do not measure model quality.

## Repository map

| Path | Contents |
| --- | --- |
| `app/` | FastAPI routes, services, Jinja templates, and static UI assets |
| `tests/` | Automated tests |
| `data/` | Programme competency catalogue |
| `scripts/` | Local model comparison tools and fixtures |
| `docs/` | Development reference, model comparisons, and project reports |
| `artifacts/` | Demo recordings and exported sample documents |
| `references/` | Example RPDs used for style guidance |
| `uploads/` | Local runtime materials; new files are ignored by Git |

Some legacy sample uploads are already tracked. Review them before sharing the repository. Keep confidential materials and credentials out of commits. [Known risks](RISK_MAP.md) and [MVP gaps](MVP_STATUS.md) describe the prototype’s remaining limits.
