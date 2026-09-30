# MVP status and remaining work

## Goal and success criteria

An AI-assisted system that turns structured teacher-provided course information into an editable RPD draft, suggests relevant competencies from a predefined catalogue, and reduces the average time to a first complete draft by at least 50% in pilot testing.

Success criteria:
1. Structurally complete drafts for selected courses.
2. Correct incorporation of supplied course data.
3. Relevant catalogue-based competency suggestions.
4. Measured 50% time reduction to complete a first RPD draft.

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
| Teacher input form | Implemented: title, description, educational program, semester, workload/credits, assessment format, and topics; validated, persisted, and editable | Confirm required fields and ranges with the selected pilot program. |
| Predefined competency catalogue | Missing | Obtain an approved catalogue, define its data model/import, and make it browsable. |
| Relevant competency suggestions | Missing | Rank/select from the catalogue using course data; show reasons and allow teacher confirmation or correction. The static fallback currently contains hard-coded `ОПК-1` and `ОПК-3`, which are not catalogue-backed suggestions. |
| Generate main RPD sections | Partial: prompt and fallback contain section headings | Map structured inputs and confirmed competencies into the draft, check required sections, and evaluate outputs against a real RPD template. Supplied course metadata is included in prompts and fallback drafts; missing fields and the detailed hour allocation remain placeholders. |
| Complete editable draft | Partial: text can be edited in the browser | Validate completeness and factual consistency; make missing fields visible before export. |
| DOCX export | Implemented at prototype level | Check layout/content against the selected official template with representative courses. |
| Pilot time-saving evidence | Missing | Run a baseline vs. assisted timed study, record corrections and draft quality, and compute average time reduction. |

The app also has role-based login and a methodist feedback/validation flow. These are useful prototype features, but they do not replace the MVP gaps above or constitute official approval.
