#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
import_lessons.py — DakPro Academy
Czyta pliki lekcji .md z folderu content/ i wrzuca je do bazy SQLite.

Pattern jak przy generate_baza_cen_v2.py: plik = zrodlo prawdy, skrypt = generator.
Edytujesz .md -> puszczasz skrypt -> baza zaktualizowana.

Uzycie:
    python import_lessons.py                 # import do dakpro.db (domyslnie)
    python import_lessons.py --db inna.db    # inna baza
    python import_lessons.py --dry-run       # pokaz co by zrobil, nie zapisuj
"""

import argparse
import json
import os
import re
import sqlite3
import sys

# --- KONFIGURACJA ---------------------------------------------------------

CONTENT_DIR = "content"
DEFAULT_DB = "dakpro.db"

# Mapowanie plikow lekcji -> metadane.
# Tu dopisujesz kolejne lekcje gdy je dodasz (cz1 drewno, cz2 staaldek itd.)
LESSONS = [
    {
        "path": "module-1/les-1.1-constructie/cz1-drewno.md",
        "module_slug": "modul-1-konstrukcje",
        "module_title": "Modul 1 — Typy konstrukcji dachow plaskich",
        "module_ord": 1,
        "slug": "konstrukcja-drewniana",
        "lesson_nr": "1.1.1",
        "title_pl": "Konstrukcja drewniana (Houten dakconstructie)",
        "ord": 1,
        # poprawne odpowiedzi quizu (zweryfikowane z sekcji "Odpowiedzi i wyjasnienia")
        "answers": ["C", "A", "B", "B", "B", "B", "B", "B", "C", "B"],
    },
    {
        "path": "module-1/les-1.1-constructie/cz2-staaldek.md",
        "module_slug": "modul-1-konstrukcje",
        "module_title": "Modul 1 — Typy konstrukcji dachow plaskich",
        "module_ord": 1,
        "slug": "konstrukcja-stalowa",
        "lesson_nr": "1.1.2",
        "title_pl": "Konstrukcja stalowa — Staaldek (profielplaten)",
        "ord": 2,
        "answers": ["C", "B", "B", "C", "B", "B", "B", "B", "C", "B"],
    },
    {
        "path": "module-1/les-1.1-constructie/cz3-beton.md",
        "module_slug": "modul-1-konstrukcje",
        "module_title": "Modul 1 — Typy konstrukcji dachow plaskich",
        "module_ord": 1,
        "slug": "konstrukcja-betonowa",
        "lesson_nr": "1.1.3",
        "title_pl": "Konstrukcja betonowa (Betonnen dakconstructie)",
        "ord": 3,
        "answers": ["B", "C", "B", "B", "B", "A", "B", "B", "A", "B"],
    },
]

PASS_THRESHOLD = 0.70  # 70% zaliczenie egzaminu

# --- SCHEMA ---------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS modules (
  id INTEGER PRIMARY KEY, slug TEXT UNIQUE,
  title_pl TEXT, title_nl TEXT, title_en TEXT, ord INTEGER
);
CREATE TABLE IF NOT EXISTS lessons (
  id INTEGER PRIMARY KEY, module_id INTEGER, slug TEXT UNIQUE, lesson_nr TEXT,
  title_pl TEXT, title_nl TEXT, title_en TEXT,
  content_pl TEXT, content_nl TEXT, content_en TEXT, ord INTEGER,
  FOREIGN KEY(module_id) REFERENCES modules(id)
);
CREATE TABLE IF NOT EXISTS exam_questions (
  id INTEGER PRIMARY KEY, lesson_id INTEGER, qnum INTEGER,
  question_pl TEXT, opt_a TEXT, opt_b TEXT, opt_c TEXT, opt_d TEXT,
  correct TEXT, pass_threshold REAL,
  FOREIGN KEY(lesson_id) REFERENCES lessons(id)
);
"""

# --- PARSER QUIZU ---------------------------------------------------------

def parse_quiz(md):
    """Wyciaga pytania quizu (treof + warianty A-D). Obsluguje oba formaty:
    **N. tre**+opcje w osobnych liniach ORAZ **N.** tre+opcje w jednej linii."""
    m = re.search(r"#+\s*[^\n]*QUIZ[^\n]*\n(.*?)\n#+\s*Odpowiedzi", md, re.S | re.I)
    block = m.group(1) if m else ""
    questions = []
    chunks = re.split(r"\n(?=\*\*\d+[\.\)])", block)
    for ch in chunks:
        ch = ch.strip()
        qm = re.match(r"\*\*(\d+)[\.\)]\s*(.*?)\*\*\s*(.*?)(?:\n|$)", ch, re.S)
        if not qm:
            continue
        qnum = int(qm.group(1))
        qtext = (qm.group(2) + " " + qm.group(3)).strip()
        qtext = re.split(r"\s*-?\s*[A-D]\)", qtext)[0]
        qtext = re.sub(r"\s+", " ", qtext).strip()
        opts = {}
        for om in re.finditer(r"([A-D])\)\s*(.+?)(?=\s+[A-D]\)|\n|$)", ch):
            if om.group(1) not in opts:
                opts[om.group(1)] = om.group(2).strip()
        if qtext and opts:
            questions.append({"num": qnum, "question": qtext, "options": opts})
    return questions

# --- IMPORT ---------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONTENT_DIR)

    if args.dry_run:
        print("== DRY RUN — nic nie zapisuje ==\n")
        con = None
    else:
        con = sqlite3.connect(args.db)
        con.executescript(SCHEMA)

    total_q = 0
    for L in LESSONS:
        fp = os.path.join(base, L["path"])
        if not os.path.exists(fp):
            print(f"!! BRAK PLIKU: {fp} — pomijam")
            continue
        with open(fp, encoding="utf-8") as f:
            md = f.read()
        qs = parse_quiz(md)
        for q in qs:
            idx = q["num"] - 1
            q["correct"] = L["answers"][idx] if idx < len(L["answers"]) else None
        print(f"{L['slug']:24} {len(md):6} znakow, {len(qs)} pytan -> {[q['correct'] for q in qs]}")
        total_q += len(qs)

        if args.dry_run:
            continue

        # modul (upsert)
        con.execute(
            "INSERT OR IGNORE INTO modules (slug, title_pl, ord) VALUES (?,?,?)",
            (L["module_slug"], L["module_title"], L["module_ord"]),
        )
        mod_id = con.execute(
            "SELECT id FROM modules WHERE slug=?", (L["module_slug"],)
        ).fetchone()[0]

        # lekcja (upsert, content_nl/en nietkniete jezeli juz sa)
        con.execute(
            """INSERT INTO lessons (module_id, slug, lesson_nr, title_pl, content_pl, ord)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(slug) DO UPDATE SET
                 module_id=excluded.module_id, lesson_nr=excluded.lesson_nr,
                 title_pl=excluded.title_pl, content_pl=excluded.content_pl,
                 ord=excluded.ord""",
            (mod_id, L["slug"], L["lesson_nr"], L["title_pl"], md, L["ord"]),
        )
        les_id = con.execute(
            "SELECT id FROM lessons WHERE slug=?", (L["slug"],)
        ).fetchone()[0]

        # pytania — czyscimy stare dla tej lekcji i wstawiamy od nowa
        con.execute("DELETE FROM exam_questions WHERE lesson_id=?", (les_id,))
        for q in qs:
            o = q["options"]
            con.execute(
                """INSERT INTO exam_questions
                   (lesson_id, qnum, question_pl, opt_a, opt_b, opt_c, opt_d, correct, pass_threshold)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (les_id, q["num"], q["question"],
                 o.get("A"), o.get("B"), o.get("C"), o.get("D"),
                 q["correct"], PASS_THRESHOLD),
            )

    if not args.dry_run:
        con.commit()
        nl = con.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
        nq = con.execute("SELECT COUNT(*) FROM exam_questions").fetchone()[0]
        con.close()
        print(f"\nOK -> {args.db}: {nl} lekcje, {nq} pytan egzaminacyjnych")
    else:
        print(f"\nDRY RUN: razem {total_q} pytan w {len(LESSONS)} lekcjach")


if __name__ == "__main__":
    main()
