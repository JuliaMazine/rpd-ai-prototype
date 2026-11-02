`qwen3:14b` is now selected in `.env`, `.env.example`, and the setup instructions, per the user's decision. Generation still uses a 16K context, a 4500-token output cap, disabled thinking, the same content validator, and the same template fallback. Restart an already-running application to reload `.env`.

The changes focus on measured costs:

- Keep the generator loaded for 900 seconds after a request using the native `keep_alive` field. `OLLAMA_KEEP_ALIVE_SECONDS` accepts 0–3600 seconds. This reduces cold starts between editing/regeneration requests; it does not increase token generation throughput or guarantee residency under memory pressure. [Ollama chat API](https://docs.ollama.com/api/chat)
- Request compact JSON and serialize the prompt's schema compactly. Indentation is not useful content; the rendered RPD keeps its normal formatting. The model can still change wording and detail between runs, so the observed reduction is not attributable solely to whitespace.
- Describe the existing no-fixed-quantities rule beside `dataset.description`, identify the offending task and field in numerical validation errors, and discourage repeated source IDs. These instructions do not relax validation or guarantee semantic accuracy.
- For errors confined to `assessment_tasks`, request only a corrected assignment array. Merge that array into the original response and run the complete content, evidence, and competency validation again. Every other section is retained, even if a legacy transport returns a full response. Unrelated errors retain the full-response correction path, and there is still only one correction attempt. Unexpected extra fields are rejected.
- Record the model and per-attempt usage counters in `generation_metadata.generation`; the comparison script also records them. These diagnostics stay outside the document. Timings use nanoseconds, as specified by [Ollama usage metrics](https://docs.ollama.com/api/usage).

Measurements on Ollama 0.13.0, RTX 4070 Ti SUPER, Q4_K_M, 16K context, using the three synthetic Russian cases without reference examples or selected competencies:

| Case | Before output/repair changes | Final implementation |
| --- | --- | --- |
| Data analysis | 27.18 s, one attempt | 23.42 s, one attempt |
| Missing data | 25.97 s, one attempt | 25.67 s, two attempts |
| Linear algebra | 23.41 s, one attempt | 20.92 s, one attempt |
| Sum | 76.56 s | 70.01 s |

All three final cases validated. The approximately 9% lower total is an observation from one run per version, not a general speed guarantee. Content varied between runs. Both first cases included comparable cold loading (about 1.5 seconds), with subsequent loads around 0.06 seconds. Baseline output decoding took approximately 22–25 seconds, compared with 0.6–1.1 seconds of prompt evaluation. This made output tokens and correction rewrites better initial targets than reducing the context or cutting source material.

The intermediate experiments matter: compact formatting alone accelerated two cases but the mathematical case invented matrix dimensions and failed twice, falling back after 46.85 seconds. After clarifying that rule, the mathematical case validated, but the missing-data response omitted a topic's assignment. A full rewrite took 21.29 seconds, giving 41.72 seconds total for that case. With assignment-only repair, a comparable missing-assignment error required a 7.30-second correction (360 output tokens) instead of regenerating the full document (1007 output tokens in the preceding run). The final case completed in 25.67 seconds. Those runs are not byte-for-byte identical inputs to the repair prompt, so the timing difference is illustrative rather than an isolated causal benchmark.

[Before summary](speed/before/summary.json) and [after summary](speed/after/summary.json) retain source hashes, model digests, input hashes, timings, counts, warnings, and runtime memory information. Each directory contains the exact inputs, response schema, rendered drafts, and full validated metadata. Compare [full-response correction](speed/full-repair.json) with [assignment-only correction](speed/partial-repair.json). Full local request/response artifacts are retained under `.cache/rpd-comparison/profile-14b-*`. Raw partial replies are not standalone RPDs; inspect the merged `metadata.json` and `draft.txt` for the completed result.

The final runtime remained entirely on GPU at approximately 12.17 GB. No source-input budget, output cap, context setting, quantization, or server-wide performance setting was reduced to obtain these results. Models still make subject errors and may repeat citations; teacher review is still necessary.

Further options were considered against the measurements:

- Preventing more structural errors can avoid the remaining correction passes. This needs broader cases and teacher review rather than judging quality by a three-case pass count.
- Flash Attention may improve attention memory use and throughput depending on the backend. The installed server had no explicit performance overrides, but that does not establish whether Flash Attention was already active automatically. Available service logs did not establish activation. No Ollama service settings were changed. A separate controlled server benchmark would be needed before claiming a gain. [Ollama FAQ](https://docs.ollama.com/faq#how-can-i-enable-flash-attention), [installed-version implementation](https://github.com/ollama/ollama/blob/v0.13.0/llm/server.go#L180)
- Streaming could show progress sooner but would not reduce decode time; partial output must not be saved as a validated RPD.
- A smaller context could reduce memory use but risks truncating longer real inputs. The existing budget is retained. Quantizing the KV cache can affect precision, so it was not enabled as an unmeasured shortcut. [Ollama cache guidance](https://docs.ollama.com/faq#how-can-i-set-the-quantization-type-for-the-kv-cache)

Validation: 99 generation, content, competency, and review tests passed. Tests cover timing counter filtering, timing isolation across attempts, bounded keep-alive configuration, scoped numerical feedback, retaining untouched sections during partial repair, full correction for unrelated errors, and rejecting extra administrative fields. The three final real 14B cases also passed, including a live assignment-only repair.
