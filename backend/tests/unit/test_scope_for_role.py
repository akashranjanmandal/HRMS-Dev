"""Which Scope a role implies — derived from the role code, not stored
redundantly on the user, so it can never drift out of sync with the role
itself."""
import pytest

from app.core.scope import Scope, scope_for_role

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "role_code, expected",
    [
        ("admin", Scope.organisation),
        ("hr_admin", Scope.organisation),
        ("finance", Scope.organisation),
        ("executive", Scope.organisation),
        ("other_authorised", Scope.organisation),
        ("division_head", Scope.division),
        ("project_lead", Scope.project),
        ("coordinator", Scope.project),
        ("project_staff", Scope.own),
        ("field_staff", Scope.own),
    ],
)
def test_scope_for_role(role_code, expected):
    assert scope_for_role(role_code) == expected


def test_unknown_role_defaults_to_the_most_restrictive_scope():
    assert scope_for_role("made_up_role") == Scope.own
