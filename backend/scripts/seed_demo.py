"""Run once against a dev database to create demo logins and sample
records for manual testing:

    ./venv/bin/python scripts/seed_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.services.demo_seed import seed_demo_data


def main() -> None:
    with SessionLocal() as db:
        created = seed_demo_data(db)
    print(f"Divisions: {', '.join(created['divisions'])}")
    print(f"Leave types created: {', '.join(created['leave_types']) or '(already present)'}")
    print("\nDemo logins (password is the same for all):")
    for u in created["users"]:
        print(f"  {u['email']:<28} {u['role']:<18} {u['password']}")


if __name__ == "__main__":
    main()
