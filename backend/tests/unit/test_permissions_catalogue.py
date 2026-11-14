"""The permission catalogue and default roles are plain data — checked here
without touching the database, so a typo in a role's permission list or a
duplicate code fails fast."""
import pytest

from app.core.permissions import DEFAULT_ROLES, MODULES, PERMISSIONS, permission_code

pytestmark = pytest.mark.unit

ACTIONS = ("view", "create", "edit", "delete", "approve", "export", "admin")


def test_permission_codes_are_unique():
    codes = [p[0] for p in PERMISSIONS]
    assert len(codes) == len(set(codes))


def test_every_permission_has_a_known_action_suffix():
    for code, _group, _desc in PERMISSIONS:
        action = code.split(":")[-1]
        assert action in ACTIONS, f"{code} has an unrecognised action '{action}'"


def test_permission_code_builder_matches_catalogue():
    # permission_code("employee", "view") must be a real, registered code —
    # "view" is the one action every module declares.
    all_codes = {p[0] for p in PERMISSIONS}
    for module in MODULES:
        code = permission_code(module, "view")
        assert code in all_codes, f"{code} missing from PERMISSIONS"


def test_ten_rfp_roles_are_defined():
    codes = [r[0] for r in DEFAULT_ROLES]
    assert len(codes) == 10
    assert len(codes) == len(set(codes))


def test_role_permission_codes_all_exist_in_the_catalogue():
    all_codes = {p[0] for p in PERMISSIONS}
    for role in DEFAULT_ROLES:
        code, perms = role[0], role[3]
        unknown = set(perms) - all_codes
        assert not unknown, f"Role '{code}' references unknown permissions: {unknown}"


def test_system_administrator_has_every_permission():
    all_codes = {p[0] for p in PERMISSIONS}
    admin = next(r for r in DEFAULT_ROLES if r[0] == "admin")
    assert set(admin[3]) == all_codes


def test_field_staff_cannot_approve_or_administer_anything():
    field_staff = next(r for r in DEFAULT_ROLES if r[0] == "field_staff")
    forbidden_actions = {"approve", "admin", "delete"}
    for code in field_staff[3]:
        action = code.split(":")[-1]
        assert action not in forbidden_actions, f"field_staff holds '{code}'"


def test_other_authorised_role_is_view_only():
    """Auditors / donors: view-only access when granted (RFP role #10)."""
    other = next(r for r in DEFAULT_ROLES if r[0] == "other_authorised")
    for code in other[3]:
        assert code.split(":")[-1] == "view", f"other_authorised holds non-view permission '{code}'"


def test_segregation_of_duties_hr_cannot_manage_roles():
    """HR/Admin (role #2) is distinct from System Administrator (#1); only
    the System Administrator manages roles themselves."""
    hr = next(r for r in DEFAULT_ROLES if r[0] == "hr_admin")
    assert "role:admin" not in hr[3]


def test_confidential_employee_data_has_its_own_permission():
    """Restricted bank/statutory fields are gated by a permission distinct
    from ordinary employee:view, so viewing a record and seeing its
    confidential fields are two separate grants."""
    all_codes = {p[0] for p in PERMISSIONS}
    assert "employee_confidential:view" in all_codes


def test_confidential_employee_permission_held_only_by_hr_finance_admin():
    holders = {r[0] for r in DEFAULT_ROLES if "employee_confidential:view" in r[3]}
    assert holders == {"admin", "hr_admin", "finance"}
