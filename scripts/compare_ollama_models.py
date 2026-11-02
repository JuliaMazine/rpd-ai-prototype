"""Run real RPD generation with identical inputs and retain reviewable artifacts.

Run from the repository root: .venv/bin/python scripts/compare_ollama_models.py
This does not connect to the application database or edit .env.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx

from app.config import GenerationSettings
from app.models import Course
from app.services import ollama_service
from app.services.llm_service import generate_draft_text


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=["qwen3:4b", "qwen3:14b"])
    parser.add_argument("--cases", type=Path, default=ROOT / "scripts/fixtures/rpd_comparison.json")
    parser.add_argument("--output", type=Path, default=ROOT / ".cache/rpd-comparison" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--max-tokens", type=int, default=4500)
    parser.add_argument("--context-length", type=int, default=16384)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output directory already exists; choose a new path to preserve prior results.")
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    limits = {
        "LLM_PROVIDER": "ollama", "LLM_TIMEOUT_SECONDS": str(args.timeout),
        "LLM_MAX_TOKENS": str(args.max_tokens), "OLLAMA_CONTEXT_LENGTH": str(args.context_length),
        "RPD_EXAMPLES_DIR": "",
    }
    try:
        with patch.dict(os.environ, limits):
            config = GenerationSettings.from_environment()
    except ValueError as error:
        parser.error(str(error))
    with httpx.Client(timeout=10) as client:
        response = client.get(f"{config.base_url}/api/tags")
        response.raise_for_status()
        installed = {item["name"]: item for item in response.json()["models"]}
    missing = [model for model in args.models if model not in installed]
    if missing:
        parser.error("Download missing models first: " + ", ".join(missing))
    args.output.mkdir(parents=True)
    write_json(args.output / "inputs.json", cases)
    from app.services.rpd_content_service import TeachingContent
    write_json(args.output / "response-schema.json", TeachingContent.model_json_schema())
    summary = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "input_sha256": sha256(args.cases.read_bytes()).hexdigest(),
        "source_sha256": {
            str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest()
            for path in sorted((ROOT / "app").rglob("*.py"))
        },
        "settings": {"timeout": args.timeout, "max_tokens": args.max_tokens, "context_length": args.context_length, "temperature": 0.15, "think": False},
        "models": {model: installed[model] for model in args.models},
        "results": [],
        "limitations": "One run per case; structural validation and warnings are diagnostics, not a semantic quality score. Review saved drafts and source evidence manually. Timing includes cold loading and correction attempts.",
    }
    real_generate = ollama_service.generate
    for model_index, model in enumerate(args.models):
        for case in cases:
            output = args.output / f"model-{model_index + 1}" / case["id"]
            output.mkdir(parents=True)
            attempts = []

            def record_attempt(*positional, **keywords):
                start = perf_counter()
                attempt = {"number": len(attempts) + 1}
                attempts.append(attempt)
                write_json(output / f"request-{attempt['number']}.json", positional[1])
                try:
                    raw, truncated = real_generate(*positional, **keywords)
                    (output / f"response-{attempt['number']}.txt").write_text(raw, encoding="utf-8")
                    attempt.update(truncated=truncated, response_chars=len(raw))
                    attempt["metrics"] = dict(keywords.get("metrics", {}))
                    return raw, truncated
                except Exception as error:
                    attempt["error_type"] = type(error).__name__
                    raise
                finally:
                    attempt["seconds"] = round(perf_counter() - start, 2)

            environment = {**limits, "OLLAMA_MODEL": model}
            metadata = {}
            print(f"Generating {model}: {case['id']}", flush=True)
            start = perf_counter()
            with patch.dict(os.environ, environment), patch.object(ollama_service, "generate", side_effect=record_attempt):
                draft = generate_draft_text(Course(**case["course"]), case["materials"], metadata)
            (output / "draft.txt").write_text(draft, encoding="utf-8")
            write_json(output / "metadata.json", metadata)
            content = metadata.get("teaching_content", {})
            row = {
                "model": model, "case": case["id"], "status": metadata.get("status"),
                "seconds": round(perf_counter() - start, 2), "attempts": attempts,
                "topics": len(content.get("topics", [])), "evidence_references": len(metadata.get("evidence", [])),
                "warnings": metadata.get("warnings", []),
                "artifacts": str(output.relative_to(args.output)),
            }
            try:
                response = httpx.get(f"{config.base_url}/api/ps", timeout=10)
                response.raise_for_status()
                row["runtime_models"] = response.json().get("models", [])
            except (httpx.HTTPError, ValueError):
                row["runtime_models"] = None
            summary["results"].append(row)
            write_json(args.output / "summary.json", summary)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    print(f"Review results in {args.output}", flush=True)
    return 0 if all(row["status"] == "validated" for row in summary["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
