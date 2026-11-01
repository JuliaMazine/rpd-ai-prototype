# RPD-AI Project Notes

## 1. Project idea

RPD-AI is a web application that helps university teachers prepare Рабочие программы дисциплин (RPDs). The system allows teachers to provide structured course information, receive AI-assisted competency suggestions, and generate an editable RPD draft based on an existing template.

## 2. Problem

University teachers spend significant time preparing RPDs (course working programs): they need to select appropriate competencies, fill in numerous required sections, and make sure that the resulting document follows the required structure.

Currently, much of this work is performed manually, which makes RPD preparation tedious and time-consuming. As a result, teachers may submit RPDs late, which in turn complicates the work of the dean’s office and the overall course-documentation process.

**Target users:** university teachers responsible for preparing RPDs.

**Secondary stakeholders:** dean’s office staff who collect and process completed RPDs.

## 3. Goal

By the end of the semester, develop and test an MVP of an AI-assisted RPD generation system that can produce a structurally complete editable RPD draft from structured information provided by a teacher and automatically suggest relevant competencies from an available competency catalogue. A structurally complete draft contains the required RPD sections filled using available course information and can be reviewed and edited by the teacher.

The MVP should demonstrate that using the system can substantially reduce the time required to create the first complete RPD draft compared with preparing it manually.

**Proposed measurable success criteria:**

1. Successfully generate structurally complete RPD drafts for a selected set of test courses.
2. Correctly incorporate the course information supplied by the teacher.
3. Provide relevant competency suggestions from the predefined competency catalogue.
4. Aim to reduce the average time required to obtain a first RPD draft by at least 50% during pilot testing.

## 4. Potential value

**For teachers:**

1. Less time spent on routine document preparation.
2. Assistance with selecting relevant competencies.
3. Less repetitive manual filling of standard RPD sections.
4. A ready draft that can be reviewed and edited instead of writing the document from scratch.

**For the dean’s office / academic administration:**

1. Faster preparation and submission of RPDs.
2. More consistent document structure.
3. Fewer incomplete or incorrectly formatted documents.
4. Reduced effort spent requesting corrections or missing information.

**Value proposition:** for university teachers who need to prepare RPDs, RPD-AI provides an AI-assisted way to generate an editable RPD draft from basic course information and an existing competency catalogue, reducing repetitive manual work compared with preparing the document from scratch.

## 5. Team

| **Team Member**  | **Role(s)**                      |
| ---------------- | -------------------------------- |
| Julia Mazine     | PM, Developer, System Analyst    |
| Anna Latushko    | Developer, System Analyst        |
| Tehreem Kamal    | System Analyst, Data Analyst, QA |
| 1st year student | ?                                |
| 1st year student | ?                                |

## MoSCoW Prioritization

| Priority | Features |
|---|---|
| **Must have** | Course information form; programme competency catalogue and selection; AI competency recommendations; generation using an existing RPD template; draft review and editing; editable document download. |
| **Should have** | DOCX export; brief explanations for competency recommendations. |
| **Could have** | Input examples and help text; additional document formatting polish. |
| **Won’t have** | University system integration; automatic data extraction; support for all programmes; official approval/signing; collaborative editing; version control and complex approval workflows. |

## User Stories

| ID | User story | Acceptance criteria |
|---|---|---|
| US1 | As a teacher, I want to enter course information so that the system can prepare a relevant RPD. | The form accepts course name, programme, semester, workload/credits, assessment format, and description/topics. |
| US2 | As a teacher, I want competency suggestions so that I can select suitable competencies more quickly. | Suggestions come from the selected programme’s catalogue; I can accept, reject, or manually select competencies. |
| US3 | As a teacher, I want to generate an RPD draft so that I spend less time writing it. | The draft follows the agreed template and includes the required sections, entered metadata, and selected competencies. |
| US4 | As a teacher, I want to edit the draft so that I can correct and adapt its content. | Generated sections are editable, and my changes appear in the downloaded document. |
| US5 | As a teacher, I want to download an editable RPD so that I can continue working with it. | The file opens in a compatible document editor and preserves the draft’s content and structure. |
