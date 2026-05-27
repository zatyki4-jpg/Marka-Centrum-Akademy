#!/usr/bin/env python3
"""
DakPro Academy — import lekcji .md do SQLite (dakpro.db).

Edytujesz .md -> puszczasz skrypt -> baza zaktualizowana (UPSERT po slug).
Idempotentny: kolejne uruchomienia aktualizują istniejące lekcje, nie duplikują.

Uzycie:
    python import_lessons.py                 # import do dakpro.db
    python import_lessons.py --db inna.db    # inna baza
    python import_lessons.py --dry-run       # pokaz co by zrobil, nie zapisuj
"""

import argparse
import os
import sqlite3
import sys

# --- KONFIGURACJA ---------------------------------------------------------

DEFAULT_DB = "dakpro.db"

# Mapowanie plikow lekcji -> metadane.
# Dopisuj kolejne lekcje na koncu listy gdy je tworzysz.
LESSONS = [
    # === MODUL 1: KONSTRUKCJE I PODLOZA ===

    # Lekcja 1.1 cz.1 - Drewno
    {
        "module": 1,
        "lesson": "1.1",
        "part": 1,
        "slug": "constructie-hout",
        "title_pl": "Lekcja 1.1 cz.1 — Konstrukcja drewniana",
        "title_nl": "Les 1.1 deel 1 — Houten dakconstructie",
        "title_en": "Lesson 1.1 part 1 — Timber roof construction",
        "path_pl": "content/module-1/les-1.1-constructie/cz1-drewno.md",
        "path_nl": None,
        "path_en": None,
    },
    # Lekcja 1.1 cz.2 - Staaldek
    {
        "module": 1,
        "lesson": "1.1",
        "part": 2,
        "slug": "constructie-staaldek",
        "title_pl": "Lekcja 1.1 cz.2 — Konstrukcja stalowa (staaldek)",
        "title_nl": "Les 1.1 deel 2 — Stalen dakconstructie (staaldek)",
        "title_en": "Lesson 1.1 part 2 — Steel deck roof construction",
        "path_pl": "content/module-1/les-1.1-constructie/cz2-staaldek.md",
        "path_nl": None,
        "path_en": None,
    },
    # Lekcja 1.1 cz.3 - Beton
    {
        "module": 1,
        "lesson": "1.1",
        "part": 3,
        "slug": "constructie-beton",
        "title_pl": "Lekcja 1.1 cz.3 — Konstrukcja betonowa",
        "title_nl": "Les 1.1 deel 3 — Betonnen dakconstructie",
        "title_en": "Lesson 1.1 part 3 — Concrete roof construction",
        "path_pl": "content/module-1/les-1.1-constructie/cz3-beton.md",
        "path_nl": None,
        "path_en": None,
    },
    # Lekcja 1.2 - Przygotowanie podloza
    {
        "module": 1,
        "lesson": "1.2",
        "part": 1,
        "slug": "podloze",
        "title_pl": "Lekcja 1.2 — Przygotowanie podłoża pod papę",
        "title_nl": "Les 1.2 — Voorbereiding van de ondergrond",
        "title_en": "Lesson 1.2 — Substrate preparation for bitumen",
        "path_pl": "content/module-1/les-1.2-podloze/podloze.md",
        "path_nl": None,
        "path_en": None,
    },
    # Lekcja 1.3 - Wprowadzenie do papy
    {
        "module": 1,
        "lesson": "1.3",
        "part": 1,
        "slug": "wprowadzenie-papa",
        "title_pl": "Lekcja 1.3 — Wprowadzenie do papy",
        "title_nl": "Les 1.3 — Inleiding tot bitumineuze membranen",
        "title_en": "Lesson 1.3 — Introduction to bitumen membranes",
        "path_pl": "content/module-1/les-1.3-wprowadzenie-papa/wprowadzenie-papa.md",
        "path_nl": None,
        "path_en": None,
    },
    # --- przyszle lekcje dopisujesz tutaj ---
    # Lekcja 1.4 - Dampscherm (TO DO)
    # Lekcja 1.5 - Mocowanie izolacji (TO DO)
    # ...
]

# --- BAZA ------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS lessons (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    module      INTEGER NOT NULL,
    lesson      TEXT    NOT NULL,
    part        INTEGER NOT NULL,
    slug        TEXT    NOT NULL UNIQUE,
    title_pl    TEXT,
    title_nl    TEXT,
    title_en    TEXT,
    content_pl  TEXT,
    content_nl  TEXT,
    content_en  TEXT,
    updated_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_lessons_module ON lessons(module);
CREATE INDEX IF NOT EXISTS idx_lessons_lesson ON lessons(lesson);
"""

UPSERT = """
INSERT INTO lessons (module, lesson, part, slug,
                     title_pl, title_nl, title_en,
                     content_pl, content_nl, content_en, updated_at)
VALUES (:module, :lesson, :part, :slug,
        :title_pl, :title_nl, :title_en,
        :content_pl, :content_nl, :content_en, datetime('now'))
ON CONFLICT(slug) DO UPDATE SET
    module=excluded.module,
    lesson=excluded.lesson,
    part=excluded.part,
    title_pl=excluded.title_pl,
    title_nl=excluded.title_nl,
    title_en=excluded.title_en,
    content_pl=excluded.content_pl,
    content_nl=excluded.content_nl,
    content_en=excluded.content_en,
    updated_at=datetime('now');
"""

# --- POMOCNICZE ------------------------------------------------------------

def read_md(path):
    """Wczytaj plik .md, zwroc tresc lub None jak nie istnieje."""
    if not path:
        return None
    if not os.path.exists(path):
        print(f"  UWAGA: brak pliku {path} (pomijam ten jezyk)")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser(description="Import lekcji .md do SQLite")
    ap.add_argument("--db", default=DEFAULT_DB, help="sciezka do bazy SQLite")
    ap.add_argument("--dry-run", action="store_true", help="nie zapisuj, tylko pokaz")
    args = ap.parse_args()

    print(f"== DakPro Academy — import lekcji ==")
    print(f"Baza: {args.db}  {'(DRY-RUN)' if args.dry_run else ''}\n")

    if not args.dry_run:
        conn = sqlite3.connect(args.db)
        conn.executescript(SCHEMA)
    else:
        conn = None

    imported = 0
    skipped = 0
    for L in LESSONS:
        print(f"-> {L['slug']}  ({L['title_pl']})")
        content_pl = read_md(L["path_pl"])
        content_nl = read_md(L["path_nl"])
        content_en = read_md(L["path_en"])

        if content_pl is None and content_nl is None and content_en is None:
            print("   POMIJAM: brak jakiejkolwiek tresci.\n")
            skipped += 1
            continue

        row = {
            **{k: L[k] for k in ("module", "lesson", "part", "slug",
                                 "title_pl", "title_nl", "title_en")},
            "content_pl": content_pl,
            "content_nl": content_nl,
            "content_en": content_en,
        }

        langs = [name for name, c in
                 (("PL", content_pl), ("NL", content_nl), ("EN", content_en)) if c]
        size = len(content_pl or "") + len(content_nl or "") + len(content_en or "")
        print(f"   jezyki: {', '.join(langs) if langs else 'brak'} | {size} znakow")

        if not args.dry_run:
            conn.execute(UPSERT, row)
            imported += 1
        print()

    if not args.dry_run:
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
        conn.close()
        print(f"OK. Zaimportowano/zaktualizowano: {imported}. Pominieto: {skipped}. W bazie: {total}.")
    else:
        print(f"DRY-RUN zakonczony. Bylo by: import={imported}, skip={skipped}.")


if __name__ == "__main__":
    sys.exit(main())
