SCRUM-11 — Upgrade model and improve generation quality

Work is on `SCRUM-11-upgrade-model-generation-quality`. The configured generation model is now `qwen3:14b`, selected by the user after comparison with `qwen3:4b`. Ollama lists the download at approximately 9.3 GB: <https://ollama.com/library/qwen3/tags>. The local RTX 4070 Ti SUPER has 16 GB VRAM. The completed comparison used approximately 12.17 GB entirely on GPU at the app's 16K context. The `unit0000` Qwen2.5 weights use Hugging Face/Transformers and are not installed in Ollama.

Download, verification, generation, and content review are complete. Both models passed all three initial comparison cases. 14B required no corrections in that run, though the content review did not establish a consistent semantic quality improvement. `.env`, `.env.example`, and setup instructions now select `qwen3:14b`. The app keeps the model loaded for 900 seconds between requests and collects per-attempt usage counters. [Speed measurements and implementation notes](speed.md) describe the subsequent optimizations. A blanket quality improvement is not established by this small evaluation.

| Initial model comparison | 4B | 14B |
| --- | --- | --- |
| Data analysis | Validated, 10.89 s, one attempt | Validated, 28.25 s, one attempt |
| Missing data | Validated, 21.33 s, two attempts | Validated, 26.29 s, one attempt |
| Linear algebra | Validated, 9.68 s, one attempt | Validated, 22.43 s, one attempt |
| Runtime model/context memory | 5.39 GB, entirely GPU | 12.17 GB, entirely GPU |

The [final summary](final/summary.json) records model digests and source hashes. [Identical inputs](final/inputs.json), [response schema](final/response-schema.json), rendered drafts, and complete evidence metadata are retained in `final/model-1/` (4B) and `final/model-2/` (14B). For example, compare the linear algebra drafts for [4B](final/model-1/linear-algebra/draft.txt) and [14B](final/model-2/linear-algebra/draft.txt). Raw requests and responses also remain in `.cache/rpd-comparison/final-4b-vs-14b/`.

Manual review found mixed results:

- 14B avoided 4B's oversimplified MCAR/MAR/MNAR definitions in the missing-data case, but its proposed diagnostic exercise still suggested identifying mechanisms from an observed table. It also added unnamed parametric imputation methods absent from the input.
- 14B used `study_case` for one linear algebra task; 4B used feature tables for all of them. Both retained awkward table/feature wording for mathematical exercises. 14B grouped the requested linear-mapping material into another topic, so topic counts alone do not measure coverage.
- 14B supplied features and a target for its model-fitting exercise, but proposed comparing linear and logistic regression on a binary target without explaining the methodological choice. It added normality of residuals as an unqualified prerequisite and described binary targets as necessary for logistic regression. Those additions are not supported by the supplied excerpt and need correction or qualification.
- Both models still require subject review. Valid excerpt IDs and fewer retries do not establish factual accuracy or adequate teaching design. This was one run per model/case, without teacher ratings, repeated sampling, real uploaded lecture documents, or accepted competency mappings.

The comparison script uses three synthetic Russian course cases: introductory data analysis, missing-data handling, and linear algebra. It calls `generate_draft_text` with the normal structured-output transport, validation, one correction attempt, template fallback, and rendering. It does not read or write application records. The cases deliberately omit competency selection so generation quality is examined independently of ranking; this is not a competency-mapping benchmark. Reference examples are disabled for repeatability.

Exploratory 4B results on 2026-11-02:

| Version | Data analysis | Missing data | Linear algebra |
| --- | --- | --- | --- |
| Original prompt/schema | Validated, first attempt, 19.38 s | Validated, first attempt, 8.66 s | Template after two invalid answers, 15.81 s |
| Revised prompt/schema guidance | Validated, first attempt, 10.40 s | Validated, first attempt, 10.64 s | Validated, first attempt, 10.26 s |

These are single exploratory runs, not a controlled quality or speed benchmark. The first run includes cold loading. The missing-data fixture's assessment value was corrected from unsupported `credit` to `pass` between runs. The schema guidance wording was also refined after the recorded run. The initial model comparison above used identical inputs and code for both models at the time it was recorded; speed changes came later. Summary records are in [baseline-4b.json](baseline-4b.json) and [schema-guidance-4b.json](schema-guidance-4b.json); original inputs, raw answers, and full draft/evidence artifacts remain locally in `.cache/rpd-comparison/baseline-4b/` and `.cache/rpd-comparison/schema-guidance-4b/`.

A verification run preceding the speed changes also validated all three cases: 11.74 s for data analysis, 22.37 s for missing data (one correction), and 10.25 s for linear algebra. The runtime API reported approximately 5.39 GB of model/context memory, fully on GPU at 16K context. [current-baseline-4b.json](current-baseline-4b.json) records this run, including application source hashes; full local artifacts are in `.cache/rpd-comparison/current-baseline-4b/`. Different retry behavior between runs reinforces the need for more than a structural pass count.

The original 4B answer copied the prompt's missing-data example into a linear algebra topic. A model-fitting task supplied only predictions instead of training features. The revised prompt removes that subject-specific example, explains task/data compatibility and mathematical study cases, and preserves source limitations. JSON schema field descriptions explain the same choices beside the constrained values. Validation errors now identify the offending task and valid correction options.

Semantic problems remain despite structural validation. In the revised exploratory run, 4B described mathematical exercises as feature tables with target variables, overstated the need for regularization, and used vague methods in some exercises. Valid source IDs establish that excerpts exist, not that the response correctly uses them. A larger model must be reviewed for those same issues before promotion.

The successful download/comparison command wrote:

- `.cache/rpd-comparison/pull-14b.log`: resumable Ollama download progress.
- `.cache/rpd-comparison/comparison.log`: completed comparison progress.
- `.cache/rpd-comparison/final-4b-vs-14b/summary.json`: final comparison results.

To reproduce after the download:

```bash
.venv/bin/python scripts/compare_ollama_models.py --models qwen3:4b qwen3:14b
```

Every run gets a fresh output directory. `--output` can choose another directory; existing results are never overwritten. The script checks model availability before generation, records model digests, source/input hashes, requests, the response schema, each answer and attempt timing, validation status, review warnings, and runtime model memory information. It returns a nonzero status if any case falls back to a template. Output length, timeout, and context can be set with `--max-tokens`, `--timeout`, and `--context-length`; defaults match the app's current local generation defaults. The script never promotes a model automatically.

Review both sets of `draft.txt` and `metadata.json` files against the recorded `inputs.json`. Check subject accuracy, source-to-topic relevance, task inputs sufficient for the named method, coverage and sequence, clear Russian outcomes, and unsupported guarantees. Compare cold-load and retry costs separately from the content review. Restart an already-running app to load changes from `.env`.

Initial validation: 87 generation, content, and competency tests passed outside the sandbox. The subsequent speed implementation passed 99 generation, content, competency, and review tests; see [speed notes](speed.md). The sandboxed HTTP route tests stalled and were stopped before the successful rerun.
