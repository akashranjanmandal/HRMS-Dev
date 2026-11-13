"""Scope: 'which rows can this user act on', a separate axis from
permissions ('can they do this at all'). RFP 3.1: whole organisation, one
division, own/assigned projects, own records only. Pure logic — no
database, no HTTP."""
import pytest

from app.core.scope import Scope, scope_allows_division, scope_allows_project

pytestmark = pytest.mark.unit


class TestDivisionScope:
    def test_organisation_scope_allows_any_division(self):
        assert scope_allows_division(Scope.organisation, user_division_id=None, target_division_id=7)

    def test_division_scope_allows_only_own_division(self):
        assert scope_allows_division(Scope.division, user_division_id=3, target_division_id=3)
        assert not scope_allows_division(Scope.division, user_division_id=3, target_division_id=4)

    def test_division_scope_with_no_division_assigned_allows_nothing(self):
        # An unassigned Division Head sees nothing, never everything.
        assert not scope_allows_division(Scope.division, user_division_id=None, target_division_id=3)

    def test_own_scope_never_allows_a_division_level_action(self):
        assert not scope_allows_division(Scope.own, user_division_id=3, target_division_id=3)


class TestProjectScope:
    def test_organisation_scope_allows_any_project(self):
        assert scope_allows_project(Scope.organisation, user_project_ids=set(), target_project_id=9)

    def test_project_scope_allows_only_assigned_projects(self):
        assert scope_allows_project(Scope.project, user_project_ids={1, 2}, target_project_id=2)
        assert not scope_allows_project(Scope.project, user_project_ids={1, 2}, target_project_id=3)

    def test_project_scope_with_no_projects_assigned_allows_nothing(self):
        assert not scope_allows_project(Scope.project, user_project_ids=set(), target_project_id=1)

    def test_division_scope_does_not_grant_project_access_by_itself(self):
        # Division scope is checked via scope_allows_division on the
        # project's own division_id, not through this helper.
        assert not scope_allows_project(Scope.division, user_project_ids=set(), target_project_id=1)
