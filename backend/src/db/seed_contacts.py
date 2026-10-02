"""Load config/department_contacts.yaml into department_contacts (T022).

Usage (from backend/):  python -m src.db.seed_contacts
Safe to re-run: contacts are upserted by name.
"""

import sys
from pathlib import Path

import psycopg
import yaml

from src.config import BACKEND_DIR, ConfigError, get_settings
from src.models.enums import ContactCampus

CONTACTS_FILE = BACKEND_DIR / "config" / "department_contacts.yaml"


def load_contacts(path: Path = CONTACTS_FILE) -> list[dict]:
    data = yaml.safe_load(path.read_text()) or {}
    contacts = data.get("contacts") or []
    seen: set[str] = set()
    for i, c in enumerate(contacts, start=1):
        for field in ("name", "contact_method"):
            if not str(c.get(field) or "").strip():
                raise ValueError(f"contact #{i} in {path.name} is missing {field!r}")
        if c["name"] in seen:
            raise ValueError(f"duplicate contact name {c['name']!r} in {path.name}")
        seen.add(c["name"])
        if c.get("campus") is not None:
            ContactCampus(c["campus"])  # raises on an unknown campus value
        c["topics"] = [str(t).strip().lower() for t in c.get("topics") or []]
    return contacts


def seed(conn: psycopg.Connection, contacts: list[dict]) -> int:
    for c in contacts:
        conn.execute(
            """
            INSERT INTO department_contacts (name, topics, contact_method, campus)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE
               SET topics = EXCLUDED.topics,
                   contact_method = EXCLUDED.contact_method,
                   campus = EXCLUDED.campus
            """,
            (c["name"], c["topics"], c["contact_method"], c.get("campus")),
        )
    return len(contacts)


def main() -> int:
    try:
        settings = get_settings()
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 1
    contacts = load_contacts()
    with psycopg.connect(settings.database_url) as conn:
        count = seed(conn, contacts)
    print(f"seeded {count} department contacts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
