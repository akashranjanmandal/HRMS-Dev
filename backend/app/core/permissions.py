"""Permission catalogue and default roles. Filled in by checklist item 2.2."""

PERMISSIONS: list[tuple[str, str, str]] = []  # (code, group, description)
DEFAULT_ROLES: list[tuple[str, str, str, list[str], bool, bool]] = []  # (code, name, description, permissions, is_system, is_hidden)
