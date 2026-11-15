"""The generic approval workflow engine (RFP Section 8)."""
import pytest

from app.core.security import hash_password
from app.models import (
    ApprovalStatus,
    Division,
    Employee,
    EmploymentCategory,
    Role,
    User,
)
from app.services import workflow as workflow_service
from app.services.workflow import NoWorkflowConfiguredError

pytestmark = pytest.mark.integration


def _make_user(db, role_code: str, *, division_id=None, email=None) -> User:
    role = db.query(Role).filter_by(code=role_code).one()
    user = User(
        email=email or f"{role_code}-{db.query(User).count()}@aaranyak.org",
        hashed_password=hash_password("Passw0rd!1"),
        role_id=role.id,
        division_id=division_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_division(db, name="Rhino Research", code="RHN") -> Division:
    div = Division(name=name, code=code)
    db.add(div)
    db.commit()
    db.refresh(div)
    return div


def _make_employee(db, division_id, user=None, full_name="Test Employee") -> Employee:
    emp = Employee(
        employee_code=f"AAR-TST-{db.query(Employee).count() + 1:04d}",
        full_name=full_name,
        division_id=division_id,
        employment_category=EmploymentCategory.regular,
        user_id=user.id if user else None,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def _login(client, user: User) -> dict:
    from app.services import mailer

    r = client.post("/api/auth/login", json={"email": user.email, "password": "Passw0rd!1"})
    body = r.json()
    if body["mfa_required"]:
        code = mailer.OUTBOX[-1]["otp"]
        r = client.post("/api/auth/verify-otp", json={"email": user.email, "code": code})
        body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}


# ------------------------------------------------------------------ seeding
def test_default_workflows_are_seeded_at_startup(db):
    from app.models import RequestType, WorkflowDefinition

    defs = {d.request_type for d in db.query(WorkflowDefinition).all()}
    assert RequestType.leave in defs
    assert RequestType.asset_issue in defs


def test_leave_workflow_has_one_division_head_level(db):
    from app.models import RequestType, WorkflowDefinition

    d = db.query(WorkflowDefinition).filter_by(request_type=RequestType.leave).one()
    assert len(d.levels) == 1
    assert d.levels[0].approver_role_code == "division_head"


# ------------------------------------------------------------ submit/decide
def test_submit_creates_a_pending_request_at_level_one(db):
    from app.models import RequestType

    div = _make_division(db)
    emp = _make_employee(db, div.id)
    req = workflow_service.submit_for_approval(
        db, request_type=RequestType.leave, object_id=1, requested_by_id=emp.id, division_id=div.id, summary="2 days casual"
    )
    db.commit()
    assert req.status == ApprovalStatus.pending
    assert req.current_level_order == 1


def test_submit_with_no_workflow_configured_raises(db):
    from app.models import RequestType, WorkflowDefinition

    div = _make_division(db)
    emp = _make_employee(db, div.id)
    db.query(WorkflowDefinition).filter_by(request_type=RequestType.leave).delete()
    db.commit()
    with pytest.raises(NoWorkflowConfiguredError):
        workflow_service.submit_for_approval(
            db, request_type=RequestType.leave, object_id=1, requested_by_id=emp.id, division_id=div.id
        )


def test_division_head_approves_single_level_request_to_completion(client, db):
    from app.models import RequestType

    div = _make_division(db)
    head_user = _make_user(db, "division_head", division_id=div.id)
    staff_user = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, user=staff_user)

    req = workflow_service.submit_for_approval(
        db, request_type=RequestType.leave, object_id=1, requested_by_id=emp.id, division_id=div.id, summary="Casual leave"
    )
    db.commit()

    headers = _login(client, head_user)
    r = client.post(f"/api/approvals/{req.id}/decide", json={"action": "approve", "remark": "Fine by me"}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "approved"
    assert len(body["steps"]) == 1
    assert body["steps"][0]["remark"] == "Fine by me"


def test_multi_level_workflow_advances_then_completes(client, db):
    from app.models import RequestType

    div = _make_division(db)
    head_user = _make_user(db, "division_head", division_id=div.id)
    hr_user = _make_user(db, "hr_admin")
    staff_user = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, user=staff_user)

    req = workflow_service.submit_for_approval(
        db,
        request_type=RequestType.attendance_regularisation,
        object_id=1,
        requested_by_id=emp.id,
        division_id=div.id,
        summary="Forgot to check out",
    )
    db.commit()
    assert req.current_level_order == 1

    head_headers = _login(client, head_user)
    r1 = client.post(f"/api/approvals/{req.id}/decide", json={"action": "approve"}, headers=head_headers)
    assert r1.status_code == 200
    assert r1.json()["status"] == "pending"
    assert r1.json()["current_level_order"] == 2

    hr_headers = _login(client, hr_user)
    r2 = client.post(f"/api/approvals/{req.id}/decide", json={"action": "approve"}, headers=hr_headers)
    assert r2.status_code == 200
    assert r2.json()["status"] == "approved"
    assert len(r2.json()["steps"]) == 2


def test_rejection_ends_the_chain(client, db):
    from app.models import RequestType

    div = _make_division(db)
    head_user = _make_user(db, "division_head", division_id=div.id)
    staff_user = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, user=staff_user)

    req = workflow_service.submit_for_approval(
        db, request_type=RequestType.leave, object_id=1, requested_by_id=emp.id, division_id=div.id
    )
    db.commit()

    headers = _login(client, head_user)
    r = client.post(f"/api/approvals/{req.id}/decide", json={"action": "reject", "remark": "Not enough balance"}, headers=headers)
    assert r.json()["status"] == "rejected"


def test_return_for_correction_ends_the_chain_without_approving(client, db):
    from app.models import RequestType

    div = _make_division(db)
    head_user = _make_user(db, "division_head", division_id=div.id)
    staff_user = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, user=staff_user)

    req = workflow_service.submit_for_approval(
        db, request_type=RequestType.leave, object_id=1, requested_by_id=emp.id, division_id=div.id
    )
    db.commit()

    headers = _login(client, head_user)
    r = client.post(
        f"/api/approvals/{req.id}/decide", json={"action": "return_for_correction", "remark": "Attach the medical note"}, headers=headers
    )
    assert r.json()["status"] == "returned"


def test_cannot_decide_an_already_decided_request(client, db):
    from app.models import RequestType

    div = _make_division(db)
    head_user = _make_user(db, "division_head", division_id=div.id)
    staff_user = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, user=staff_user)
    req = workflow_service.submit_for_approval(
        db, request_type=RequestType.leave, object_id=1, requested_by_id=emp.id, division_id=div.id
    )
    db.commit()

    headers = _login(client, head_user)
    client.post(f"/api/approvals/{req.id}/decide", json={"action": "approve"}, headers=headers)
    r2 = client.post(f"/api/approvals/{req.id}/decide", json={"action": "approve"}, headers=headers)
    assert r2.status_code == 400


def test_cannot_approve_own_request(client, db):
    """Segregation of duties (RFP 3.1): a person cannot approve their own
    request — even if, unusually, they also hold the approver role."""
    from app.models import RequestType

    div = _make_division(db)
    head_user = _make_user(db, "division_head", division_id=div.id)
    head_employee = _make_employee(db, div.id, user=head_user, full_name="The Head Themselves")

    req = workflow_service.submit_for_approval(
        db, request_type=RequestType.leave, object_id=1, requested_by_id=head_employee.id, division_id=div.id
    )
    db.commit()

    headers = _login(client, head_user)
    r = client.post(f"/api/approvals/{req.id}/decide", json={"action": "approve"}, headers=headers)
    assert r.status_code == 403


def test_division_head_cannot_decide_outside_their_division(client, db):
    from app.models import RequestType

    div_a = _make_division(db, "Rhino Research", "RHN")
    div_b = _make_division(db, "Elephant Research", "ELE")
    head_a = _make_user(db, "division_head", division_id=div_a.id)
    staff_b_user = _make_user(db, "field_staff")
    emp_b = _make_employee(db, div_b.id, user=staff_b_user)

    req = workflow_service.submit_for_approval(
        db, request_type=RequestType.leave, object_id=1, requested_by_id=emp_b.id, division_id=div_b.id
    )
    db.commit()

    headers = _login(client, head_a)
    r = client.post(f"/api/approvals/{req.id}/decide", json={"action": "approve"}, headers=headers)
    assert r.status_code == 403


def test_unrelated_role_cannot_decide(client, db):
    from app.models import RequestType

    div = _make_division(db)
    staff_user = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, user=staff_user)
    req = workflow_service.submit_for_approval(
        db, request_type=RequestType.leave, object_id=1, requested_by_id=emp.id, division_id=div.id
    )
    db.commit()

    other_field_staff = _make_user(db, "field_staff", email="irrelevant@aaranyak.org")
    headers = _login(client, other_field_staff)
    r = client.post(f"/api/approvals/{req.id}/decide", json={"action": "approve"}, headers=headers)
    assert r.status_code == 403


def test_approving_creates_an_on_screen_notification_for_requester(client, db):
    from app.models import Notification, RequestType

    div = _make_division(db)
    head_user = _make_user(db, "division_head", division_id=div.id)
    staff_user = _make_user(db, "field_staff")
    emp = _make_employee(db, div.id, user=staff_user)
    req = workflow_service.submit_for_approval(
        db, request_type=RequestType.leave, object_id=1, requested_by_id=emp.id, division_id=div.id, summary="My leave"
    )
    db.commit()

    headers = _login(client, head_user)
    client.post(f"/api/approvals/{req.id}/decide", json={"action": "approve"}, headers=headers)

    notes = db.query(Notification).filter_by(user_id=staff_user.id).all()
    assert any("approved" in n.message for n in notes)


def test_submitting_notifies_the_approver(db):
    from app.models import Notification, RequestType

    div = _make_division(db)
    head_user = _make_user(db, "division_head", division_id=div.id)
    emp = _make_employee(db, div.id)
    workflow_service.submit_for_approval(
        db, request_type=RequestType.leave, object_id=1, requested_by_id=emp.id, division_id=div.id, summary="New leave"
    )
    db.commit()

    notes = db.query(Notification).filter_by(user_id=head_user.id).all()
    assert len(notes) == 1
    assert "New leave" in notes[0].message


# --------------------------------------------------------- Approvals Center
def test_pending_counts_scoped_to_division(client, db):
    from app.models import RequestType

    div_a = _make_division(db, "Rhino Research", "RHN")
    div_b = _make_division(db, "Elephant Research", "ELE")
    head_a = _make_user(db, "division_head", division_id=div_a.id)
    emp_a = _make_employee(db, div_a.id)
    emp_b = _make_employee(db, div_b.id)

    workflow_service.submit_for_approval(db, request_type=RequestType.leave, object_id=1, requested_by_id=emp_a.id, division_id=div_a.id)
    workflow_service.submit_for_approval(db, request_type=RequestType.leave, object_id=2, requested_by_id=emp_b.id, division_id=div_b.id)
    db.commit()

    headers = _login(client, head_a)
    r = client.get("/api/approvals/counts", headers=headers)
    assert r.status_code == 200
    counts = {c["request_type"]: c["pending_count"] for c in r.json()}
    assert counts.get("leave") == 1


def test_approvals_list_filterable_by_request_type(client, db):
    from app.models import RequestType

    div = _make_division(db)
    head_user = _make_user(db, "division_head", division_id=div.id)
    emp = _make_employee(db, div.id)
    workflow_service.submit_for_approval(db, request_type=RequestType.leave, object_id=1, requested_by_id=emp.id, division_id=div.id)
    workflow_service.submit_for_approval(db, request_type=RequestType.asset_issue, object_id=1, requested_by_id=emp.id, division_id=div.id)
    db.commit()

    headers = _login(client, head_user)
    r = client.get("/api/approvals", params={"request_type": "leave"}, headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["request_type"] == "leave"


def test_unauthenticated_cannot_list_approvals(client):
    assert client.get("/api/approvals").status_code == 401


# -------------------------------------------------------- workflow admin API
def test_admin_can_reconfigure_a_workflow(client, db):
    admin_user = _make_user(db, "admin")
    headers = _login(client, admin_user)
    r = client.put(
        "/api/workflows/leave",
        json={
            "name": "Leave approval (two levels)",
            "levels": [
                {"label": "Division Head", "approver_kind": "role", "approver_role_code": "division_head"},
                {"label": "HR", "approver_kind": "role", "approver_role_code": "hr_admin"},
            ],
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["levels"]) == 2


def test_reconfigured_workflow_is_used_for_new_submissions(client, db):
    from app.models import RequestType

    admin_user = _make_user(db, "admin")
    headers = _login(client, admin_user)
    client.put(
        "/api/workflows/leave",
        json={
            "name": "Leave approval (two levels)",
            "levels": [
                {"label": "Division Head", "approver_kind": "role", "approver_role_code": "division_head"},
                {"label": "HR", "approver_kind": "role", "approver_role_code": "hr_admin"},
            ],
        },
        headers=headers,
    )

    div = _make_division(db)
    emp = _make_employee(db, div.id)
    req = workflow_service.submit_for_approval(
        db, request_type=RequestType.leave, object_id=1, requested_by_id=emp.id, division_id=div.id
    )
    db.commit()
    assert req.current_level_order == 1

    head_user = _make_user(db, "division_head", division_id=div.id)
    head_headers = _login(client, head_user)
    r1 = client.post(f"/api/approvals/{req.id}/decide", json={"action": "approve"}, headers=head_headers)
    assert r1.json()["status"] == "pending"
    assert r1.json()["current_level_order"] == 2


def test_operational_roles_without_workflow_admin_cannot_reconfigure(client, db):
    """hr_admin holds workflow:admin (Phase 2's own design: HR has full
    operational HR authority short of role management) — the role that
    genuinely has none of it is a self-service one."""
    staff_user = _make_user(db, "field_staff")
    headers = _login(client, staff_user)
    r = client.put(
        "/api/workflows/leave",
        json={"name": "x", "levels": [{"approver_kind": "role", "approver_role_code": "division_head"}]},
        headers=headers,
    )
    assert r.status_code == 403


def test_hr_admin_can_also_reconfigure_workflows(client, db):
    hr_user = _make_user(db, "hr_admin")
    headers = _login(client, hr_user)
    r = client.put(
        "/api/workflows/leave",
        json={"name": "x", "levels": [{"approver_kind": "role", "approver_role_code": "division_head"}]},
        headers=headers,
    )
    assert r.status_code == 200


def test_workflow_with_specific_user_level(client, db):
    from app.models import RequestType

    admin_user = _make_user(db, "admin")
    headers = _login(client, admin_user)
    named_approver = _make_user(db, "executive", email="director@aaranyak.org")
    client.put(
        "/api/workflows/asset_issue",
        json={
            "name": "Asset issue (director sign-off)",
            "levels": [{"label": "Executive Director", "approver_kind": "specific_user", "approver_user_id": named_approver.id}],
        },
        headers=headers,
    )

    div = _make_division(db)
    emp = _make_employee(db, div.id)
    req = workflow_service.submit_for_approval(
        db, request_type=RequestType.asset_issue, object_id=1, requested_by_id=emp.id, division_id=div.id
    )
    db.commit()

    approver_headers = _login(client, named_approver)
    r = client.post(f"/api/approvals/{req.id}/decide", json={"action": "approve"}, headers=approver_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
