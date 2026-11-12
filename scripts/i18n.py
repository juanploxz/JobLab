"""Compile and verify every gettext catalog of the repository without GNU gettext.

Usage (from the repository root):
    python scripts/i18n.py extract-django  # update locale/en/.../django.po from code and templates
    python scripts/i18n.py compile         # .po -> .mo for Django and every microservice
    python scripts/i18n.py check           # fail if a catalog has untranslated or fuzzy entries

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


DJANGO_PYTHON_DIRS = ("organization", "joblab")
DJANGO_TEMPLATE_DIRS = ("templates", "organization/templates")
DJANGO_KEYWORDS = {
    "_": None,
    "gettext": None,
    "gettext_lazy": None,
    "ngettext": (1, 2),
    "ngettext_lazy": (1, 2),
    "pgettext": ((1, "c"), 2),
}


def _django_messages():
    """Yield (msgid, context) from Django Python files and templates (via ``templatize``)."""
    import io

    from babel.messages.extract import extract_python
    from django.utils.translation.template import templatize

    sources: list[tuple[str, str]] = []
    for folder in DJANGO_PYTHON_DIRS:
        for path in sorted((ROOT / folder).rglob("*.py")):
            if "migrations" in path.parts or "tests" in path.parts:
                continue
            sources.append((str(path), path.read_text(encoding="utf-8")))
    for folder in DJANGO_TEMPLATE_DIRS:
        for path in sorted((ROOT / folder).rglob("*.html")):
            # templatize() targets xgettext; removing indentation makes it tokenizable by Babel.
            code = templatize(path.read_text(encoding="utf-8"))
            sources.append((str(path), "\n".join(line.lstrip() for line in code.splitlines())))
    for _origin, code in sources:
        buffer = io.BytesIO(code.encode("utf-8"))
        for _lineno, _function, message, _comments in extract_python(
            buffer, DJANGO_KEYWORDS, [], {"encoding": "utf-8"}
        ):
            yield message


def extract_django() -> int:
    """Merge every Django msgid into locale/en/LC_MESSAGES/django.po keeping translations."""
    from babel.messages.catalog import Catalog
    from babel.messages.pofile import write_po

    template = Catalog(project="JobLab", charset="utf-8")
    for message in _django_messages():
        if isinstance(message, tuple):
            singular, plural = message[0], message[1]
            if singular:
                template.add((singular, plural))
        elif message:
            template.add(message)

    po_path = ROOT / "locale/en/LC_MESSAGES/django.po"
    po_path.parent.mkdir(parents=True, exist_ok=True)
    if po_path.exists():
        catalog = _read(po_path)
    else:
        catalog = Catalog(locale="en", project="JobLab", charset="utf-8")
    catalog.update(template, no_fuzzy_matching=True)
    catalog.obsolete.clear()
    with po_path.open("wb") as handle:
        write_po(handle, catalog, omit_header=False, sort_output=True, width=0, no_location=True)
    pending = sum(1 for message in catalog if message.id and not message.string)
    print(f"{po_path.relative_to(ROOT)}: {len(catalog)} messages, {pending} untranslated")
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
    commands = {"compile": compile_all, "check": check_all, "extract-django": extract_django}
    sys.exit(commands[command]())
