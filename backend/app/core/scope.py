"""Scope: which rows a user's permissions reach (RFP 3.1 — "reach is
layered: whole organisation, one division, own or assigned projects, own
records only"). This is independent of *what* a permission lets someone do
— ``require_perm`` answers "can they approve leave at all"; these helpers
answer "can they approve *this employee's* leave".

A ``Scope`` lives on ``User`` (added alongside the employee master in
checklist 2.5, since scope is meaningless without employee/division rows
to scope over) and is set once per login: a Division Head's scope is
``division`` with their ``division_id`` filled in; a Project Lead's scope
is ``project`` with their assigned project ids; HR/Admin/Finance/Executive
use ``organisation``, which always passes.

An unassigned scoped user (a Division Head with no division yet) sees
nothing, never everything — the RFP's own example for Department Head-like
roles, carried over from the AVFU build's ``department_scope_ids``.
"""
from enum import Enum


class Scope(str, Enum):
    organisation = "organisation"
    division = "division"
    project = "project"
    own = "own"


def scope_allows_division(scope: Scope, *, user_division_id: int | None, target_division_id: int) -> bool:
    """Can a user with this scope act on something in ``target_division_id``?"""
    if scope == Scope.organisation:
        return True
    if scope == Scope.division:
        return user_division_id is not None and user_division_id == target_division_id
    return False  # 'project' and 'own' scope never grant division-wide reach


def scope_allows_project(scope: Scope, *, user_project_ids: set[int], target_project_id: int) -> bool:
    """Can a user with this scope act on something in ``target_project_id``?"""
    if scope == Scope.organisation:
        return True
    if scope == Scope.project:
        return target_project_id in user_project_ids
    return False  # 'division' scope is checked via scope_allows_division instead
