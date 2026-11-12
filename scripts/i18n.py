"""Compile and verify every gettext catalog of the repository without GNU gettext.

Usage (from the repository root):
    python scripts/i18n.py compile   # .po -> .mo for Django and every microservice
    python scripts/i18n.py check     # fail if a catalog has untranslated or fuzzy entries

Django's ``compilemessages`` needs the GNU ``msgfmt`` binary, which is rarely
installed on Windows. Babel produces equivalent .mo files in pure Python.
"""

from __future__ import annotations

import sys
from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

ROOT = Path(__file__).resolve().parents[1]
CATALOG_GLOBS = (
    "locale/*/LC_MESSAGES/*.po",
    "services/*/*/translations/*/LC_MESSAGES/*.po",
)


def catalogs() -> list[Path]:
    found: list[Path] = []
    for pattern in CATALOG_GLOBS:
        found.extend(sorted(ROOT.glob(pattern)))
    return found


def _read(path: Path):
    with path.open("rb") as handle:
        locale = path.parents[1].name
        return read_po(handle, locale=locale)


def compile_all() -> int:
    for po_path in catalogs():
        catalog = _read(po_path)
        mo_path = po_path.with_suffix(".mo")
        with mo_path.open("wb") as handle:
            write_mo(handle, catalog, use_fuzzy=False)
        print(f"compiled {po_path.relative_to(ROOT)} ({len(catalog)} messages)")
    return 0


def check_all() -> int:
    problems = 0
    for po_path in catalogs():
        for message in _read(po_path):
            if not message.id:
                continue
            translated = message.string
            empty = not translated or (
                isinstance(translated, tuple) and not all(translated)
            )
            if empty or message.fuzzy:
                problems += 1
                print(f"{po_path.relative_to(ROOT)}: untranslated {message.id!r}")
    print("all catalogs complete" if not problems else f"{problems} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "compile"
    sys.exit({"compile": compile_all, "check": check_all}[command]())
