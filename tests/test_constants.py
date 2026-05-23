from app.constants import (
    REVIEWABLE_STATUSES,
    ROLE_LABELS,
    ROLE_METHODIST,
    ROLE_TEACHER,
    STATUS_DRAFT_EDITING,
    STATUS_FEEDBACK_GIVEN,
    STATUS_RESUBMITTED_FOR_REVIEW,
    STATUS_RPD_VALIDATED,
    STATUS_SUBMITTED_FOR_REVIEW,
    TEACHER_EDITABLE_STATUSES,
    STATUS_LABELS,
)


class TestRoleConstants:
    def test_teacher_role_string(self):
        assert ROLE_TEACHER == "USER_TEACHER"

    def test_methodist_role_string(self):
        assert ROLE_METHODIST == "USER_METHODIST"

    def test_role_labels_contains_both_roles(self):
        assert ROLE_TEACHER in ROLE_LABELS
        assert ROLE_METHODIST in ROLE_LABELS
        assert ROLE_LABELS[ROLE_TEACHER] == "Teacher"
        assert ROLE_LABELS[ROLE_METHODIST] == "Methodist"


class TestStatusConstants:
    def test_all_statuses_have_labels(self):
        statuses = [
            STATUS_DRAFT_EDITING,
            STATUS_SUBMITTED_FOR_REVIEW,
            STATUS_FEEDBACK_GIVEN,
            STATUS_RESUBMITTED_FOR_REVIEW,
            STATUS_RPD_VALIDATED,
        ]
        for status in statuses:
            assert status in STATUS_LABELS

    def test_reviewable_statuses(self):
        assert STATUS_SUBMITTED_FOR_REVIEW in REVIEWABLE_STATUSES
        assert STATUS_RESUBMITTED_FOR_REVIEW in REVIEWABLE_STATUSES
        assert STATUS_DRAFT_EDITING not in REVIEWABLE_STATUSES
        assert STATUS_FEEDBACK_GIVEN not in REVIEWABLE_STATUSES
        assert STATUS_RPD_VALIDATED not in REVIEWABLE_STATUSES

    def test_teacher_editable_statuses(self):
        assert STATUS_DRAFT_EDITING in TEACHER_EDITABLE_STATUSES
        assert STATUS_FEEDBACK_GIVEN in TEACHER_EDITABLE_STATUSES
        assert STATUS_SUBMITTED_FOR_REVIEW not in TEACHER_EDITABLE_STATUSES
        assert STATUS_RESUBMITTED_FOR_REVIEW not in TEACHER_EDITABLE_STATUSES
        assert STATUS_RPD_VALIDATED not in TEACHER_EDITABLE_STATUSES
