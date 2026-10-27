# Competency recommendations and assignment: MVP guidelines

## Purpose and current baseline

Guide implementation of competency selection during RPD preparation and methodist review, including a programme-wide course–competency matrix. These are product guidelines, not official NSU regulations. The review flow is prototype validation, not official approval or signing.

The current implementation provides:

- A programme catalogue in `data/competencies_NSU_MMF_FIT.csv`, accessed through `app/services/competency_catalogue_service.py`.
- An optional `Course.catalogue_program_id`, separate from the free-text `educational_program` field.
- Up to five local embedding-based suggestions, using uploaded teaching materials as the main input and the course description/topics as supplementary input. Standalone search can work without uploads; RPD generation currently requires an upload.
- A generation form with suggestions initially checked. Creating the draft accepts the checked entries; replacing unchecked suggestions preserves checked ones. Accepted entries and retrieval details are saved per `Draft` in `generation_metadata`.
- Catalogue-backed competency tables and validated learning-outcome mappings in generated RPDs, browser text editing, DOCX export, and submission, feedback, resubmission, and methodist validation.

The sections below describe the intended behaviour. Full-catalogue selection, structured changes to a saved draft's competency selection, and the programme matrix remain to be implemented. Retrieval currently provides similarity scores, not relevance explanations. Existing text editing does not synchronise changes to competency codes with saved selections.

## 1. Programme catalogue and recommendation rules

Use the course's selected catalogue programme to determine eligible competencies. Offer all programmes available in the repository catalogue; support for other programmes or integration with a university curriculum system is outside this work.

Identify a programme competency by programme ID and catalogue code, retaining its full wording and type. The same code in different programmes is not automatically the same competency. The current search groups identical descriptions using a description hash; that retrieval ID alone is insufficient as a programme assignment key. Preserve the associated programme-specific catalogue entries.

For this workflow, require a catalogue programme before confirming programme-specific selections. The current application also allows searching across all programmes when none is selected; treat those results as exploratory until a programme is chosen. Free-text programme names must not determine membership.

Recommend several relevant entries, retaining the current default of up to five. Display their catalogue codes and full wording; type may be shown as catalogue metadata. Do not filter eligibility, impose quotas, or require a combination of types such as УК, ОПК, ПК, or ПКС. The recommendation count is not a required number of selections.

Rank using the uploaded materials, description, and topics already available. Do not require an existing RPD, curriculum assignment, or separately entered learning outcomes. Favour competencies to which the course makes a meaningful, assessable contribution; a course need not develop every aspect of a competency independently. Similarity scores are ranking signals, not confidence probabilities. A short relevance explanation can be added later; it is not a prerequisite for the MVP selection flow.

## 2. Teacher selects competencies and prepares the RPD

1. Create or edit the course, select its catalogue programme, describe its content/topics, and upload teaching materials for generation.
2. Review the suggested competencies. Select or deselect suggestions and allow adding other entries from the same programme's full catalogue.
3. Create the RPD using the confirmed selection, review and edit the result, then submit it for methodist review.
4. After feedback, revise the RPD and its selection as needed and resubmit through the existing review flow.

Recommendations remain candidates until the teacher saves or generates with the selection. Prechecked suggestions are accepted only by the explicit generation action. Replacing unchecked suggestions must retain checked entries and keep rejected entries excluded during repeated replacements; a failed refresh must preserve the previous selection. Entries added through catalogue browsing must also be retained. Do not silently rerank or substitute entries when saving or generating.

Allow an empty selection while preparing a draft, including the existing explicit option to continue after retrieval failure. Show an empty-selection reminder before submission; do not introduce a mandatory count or competency-type requirement.

Persist selections on the specific RPD draft, with programme identity and a snapshot of catalogue codes and wording. Use only these entries in generated competency tables and learning-outcome mappings. Missing support for a mapping must remain visible as a review placeholder rather than an invented relationship. A missing mapping does not remove a selected competency.

Provide a way to change the saved selection in teacher-editable statuses, using the same catalogue membership checks as generation. Keep structured selections, the RPD competency table, and DOCX output consistent. Free-text edits alone must not silently change matrix assignments; surface discrepancies for correction. Later catalogue or course changes must not rewrite previously saved RPD snapshots.

## 3. Methodist reviews a specific RPD

Show the methodist that RPD's saved programme and selected competencies, with codes and full wording, alongside its content and status. Use the draft's selection, not fresh recommendations or another draft's choices. Distinguish selected entries from suggestions and from their learning-outcome mappings.

The methodist checks programme membership and whether the course's content, learning outcomes, and assessment support the choices. Use the existing actions to return comments or mark the RPD as validated. Comments should identify a concrete correction, such as an unsupported selection or an unclear outcome mapping. Teachers make selection changes through the same revision and resubmission flow.

## 4. Programme course–competency matrix

Provide the methodist with a programme selector listing every available catalogue programme and a matrix for the selected programme:

| Element | Behaviour |
|---|---|
| Rows | All competencies in the programme, with code and access to full wording; type is optional display metadata. |
| Columns | All courses associated with that catalogue programme, including courses with no RPD or selection yet. |
| Cells | Checked when the course's eligible matrix-source RPD has that competency selected; otherwise blank. |
| Course link | Opens the eligible RPD supplying the column's selections, showing its status; indicate when no eligible RPD exists. |
| **Unassigned competencies only** | Shows exactly the rows with no checked cells. |

A course can have multiple drafts. Only RPDs currently submitted for review, resubmitted for review, or validated are eligible to supply matrix assignments: `DRAFT_SUBMITTED_FOR_REVIEW`, `DRAFT_RESUBMITTED_FOR_REVIEW`, and `RPD_VALIDATED`. Exclude drafts in `DRAFT_EDITING` and `DRAFT_FEEDBACK_GIVEN`; their selections are still being prepared or corrected.

Use the newest eligible RPD (by creation time, then ID) as the single source for each course. A newer unsubmitted draft must not replace an older eligible RPD in the matrix. If a source RPD is returned for correction, fall back to the newest remaining eligible RPD; if none exists, leave the column unchecked and label it as having no eligible RPD. Show which RPD and status supply each column. Do not combine selections across historical drafts or imply that assignments awaiting review are validated. Reviewing a specific RPD must always show that RPD's own selection.

Build rows from the complete programme catalogue and columns from courses, then populate cells from eligible RPD selections. Include programmes with no courses and competencies that have never been recommended or selected. Distinguish a course without an eligible RPD or recorded selection data from one whose eligible RPD has an explicitly empty selection, although none produces checked cells.

Use the source draft's saved programme when validating its selections against the column's programme. If the course programme has changed, flag an incompatible draft for reselection rather than carrying its codes into the new programme. Courses without a catalogue programme cannot be assigned to a programme matrix by their free-text name.

Recompute the source RPD and cells on the next load after submission, resubmission, return for correction, or validation. Creating or editing an unsubmitted draft must not affect matrix assignments or the unassigned filter; its revised selection takes effect only when it becomes the eligible source RPD. Removing a competency's final eligible assignment must make it appear under the unassigned filter. No separate matrices by review status, achievement scores, or curriculum stages are required.

An unassigned row means no represented course's eligible source RPD currently has that competency selected. Choices in unsubmitted or returned drafts do not count as assignments for this view. It is a planning signal, not proof of a programme deficiency; a checked cell does not establish student achievement. The methodist can request relevant revisions, but the system must not automatically assign competencies merely to fill gaps.

## 5. Implementation boundaries

Extend the existing catalogue service, course/draft models, and basic review flow. A separate programme database, independently maintained matrix dataset, or complex approval workflow is unnecessary for this scope.

- Keep recommended candidates separate from accepted selections. Existing draft metadata already stores accepted entries and catalogue provenance; reuse it or add structured assignment storage linked to the draft without creating conflicting sources of truth.
- Validate programme membership and prevent duplicate programme/code selections on every save, including manual catalogue additions. Preserve exact catalogue wording and the saved snapshot when the catalogue later changes.
- When the programme changes, require a new programme-compatible selection for subsequent saves/generation. Preserve old RPDs as historical records and flag mismatches in the matrix.
- Reuse the signed-preview checks for recommendation acceptance so changed course inputs, materials, or catalogue data require a refreshed preview. Manual catalogue additions also require server-side catalogue validation.
- Keep course selection separate from competency-to-learning-outcome mappings. The matrix records the former; it must not infer assignments by parsing RPD prose or by counting mappings.
- Apply existing teacher ownership and editable-status checks to selection changes, and methodist role checks to programme-wide matrix access.

## 6. Acceptance checks

These checks cover the intended functionality, including additions beyond the current baseline:

1. A teacher obtains several catalogue-based suggestions for a new course without an existing RPD or curriculum assignment. Selecting a programme confines candidates and saved choices to that programme, with no type restrictions or quotas.
2. The teacher can choose from suggestions or the full programme catalogue, preserve choices during replacement, save them, and reopen the same selection. Saving rejects duplicate or out-of-programme entries.
3. Generated RPD and DOCX competency entries match the saved selection and catalogue snapshot. Unsupported mappings remain flagged; empty selections remain possible and visible.
4. The methodist sees the exact submitted RPD's selection, returns comments or validates it, and can review a teacher's resubmission.
5. Every available programme has a matrix containing its complete catalogue and associated course list, including empty programmes and courses without eligible RPDs. Each course uses only its newest submitted, resubmitted, or validated RPD. A newer unsubmitted draft does not displace an older eligible RPD.
6. The unassigned filter returns exactly rows with no assignments from eligible source RPDs. Creating or editing unsubmitted drafts changes neither cells nor filtering. Submission, resubmission, and return for correction update source selection and assignments, including removal of a final eligible assignment and fallback to an older eligible RPD where available.
7. Older RPDs retain their own selections after new drafts, programme changes, or catalogue updates. Incompatible or missing selection data is identified without inventing assignments.
