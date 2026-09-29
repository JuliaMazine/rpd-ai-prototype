# MVP status and remaining work

Assessment date: 2026-09-22. Based on `PMP notes.docx` and a source-code review of this repository. This is an implementation assessment, **not** a user-test or production-readiness claim.

## Goal and success criteria

The notes propose an AI-assisted system that turns structured teacher-provided course information into an editable RPD draft, suggests relevant competencies from a predefined catalogue, and reduces the average time to a first complete draft by at least 50% in pilot testing.

None of the four proposed success criteria has yet been demonstrated with pilot evidence: structurally complete drafts for selected courses, correct incorporation of supplied course data, relevant catalogue-based competency suggestions, and a measured 50% time reduction.

## MVP Scope

| IN | OUT |
| --- | --- |
| Simple interface/form for entering basic course information | Integration with university information systems |
| Input of course metadata such as course name, educational program, semester, workload/credits, assessment format, and short course description/topics | Automatic extraction of all course information from external systems |
| Access to a predefined catalogue/list of competencies | Support for every university/faculty/program |
| AI-based suggestion of relevant competencies based on the provided course information | Automatic official approval or electronic signing of an RPD |
| Generation of the main required sections of an RPD using an existing RPD structure/template | Multi-user collaborative editing |
| Generation of a structurally complete editable RPD draft | Version-control and complex approval workflows |
| Ability for the teacher to review and edit the generated result | |
| Export/download of the generated RPD in a practical document format, preferably DOCX | |

## Scope check

| MVP item | Current state | Remaining work |
| --- | --- | --- |
| Teacher input form | Partial: title and free-text description only | Add educational program, semester, workload/credits, assessment format, topics, and validation; persist these fields. |
| Predefined competency catalogue | Missing | Obtain an approved catalogue, define its data model/import, and make it browsable. |
| Relevant competency suggestions | Missing | Rank/select from the catalogue using course data; show reasons and allow teacher confirmation or correction. The static fallback currently contains hard-coded `ОПК-1` and `ОПК-3`, which are not catalogue-backed suggestions. |
| Generate main RPD sections | Partial: prompt and fallback contain section headings | Map structured inputs and confirmed competencies into the draft, check required sections, and evaluate outputs against a real RPD template. Some fallback fields are placeholders or fixed values. |
| Complete editable draft | Partial: text can be edited in the browser | Validate completeness and factual consistency; make missing fields visible before export. |
| DOCX export | Implemented at prototype level | Check layout/content against the selected official template with representative courses. |
| Pilot time-saving evidence | Missing | Run a baseline vs. assisted timed study, record corrections and draft quality, and compute average time reduction. |

The app also has role-based login and a methodist feedback/validation flow. These are useful prototype features, but they do not replace the MVP gaps above or constitute official approval.

## Recommended sequence

1. **Agree on inputs and examples.** Obtain one approved RPD template, the competency catalogue, and 3–5 representative courses with expected metadata and sections. Define what “structurally complete” means.
2. **Finish structured intake.** Extend the course model and form; validate credits, hours, semester, assessment, and program information. Add a migration approach for existing databases.
3. **Build competency suggestions.** Import the catalogue, implement relevance ranking, let the teacher accept/edit suggestions, and carry only confirmed competencies into generation.
4. **Make draft quality measurable.** Populate the official structure from known data, flag missing inputs instead of inventing facts, verify section presence and consistency, and test DOCX output with the example courses.
5. **Run the pilot.** Time manual and assisted first-draft creation on comparable courses, capture teacher corrections and relevance ratings, then report whether the 50% target was met.

Before testing with real users or confidential materials, replace the hard-coded session secret and seeded known-password accounts, review upload handling and data retention, and keep API keys and course materials out of Git.

## Effort estimate

This is a functional prototype, but the core differentiator—catalogue-based competency suggestions—and the evidence for the goal are still absent. A rough planning range is **2–4 developer-weeks** for structured intake, catalogue matching, generation/validation, and focused tests, **plus 1–2 calendar weeks** to organize and run a small pilot. This assumes the official template, catalogue, representative courses, and API access are supplied promptly. It is not a completion percentage or a deadline commitment; missing source materials or stricter institutional formatting can expand the work substantially.

## Verification limits

The assessment is based on code and documentation review. The automated test suite was not run in this environment, and no live model output, DOCX file, or pilot session was evaluated.
