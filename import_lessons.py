#!/usr/bin/env python3
"""
DakPro Academy — import lekcji .md do bazy apki (backend/database.demo.db).

Wpisuje 5 lekcji jako nowy etap "rf-s0" Constructie en ondergrond
w kursie Bitumineuze dakbedekking (kurs-roofing-nl).

Parsuje quizy z .md (sekcja "# QUIZ") i wpisuje do tabeli quiz_questions.

Idempotentny: UPSERT po id, kolejne uruchomienia tylko aktualizuja.

Uzycie:
    python3 import_lessons.py                    # import do backend/database.demo.db
    python3 import_lessons.py --db inna.db       # inna baza
    python3 import_lessons.py --dry-run          # pokaz co by zrobil
"""

import argparse
import os
import re
import sqlite3
import sys

# --- KONFIGURACJA ---------------------------------------------------------

DEFAULT_DB = "backend/database.demo.db"
COURSE_ID = "kurs-roofing-nl"
STAGE_ID = "rf-s0"
STAGE_TITLE = "Constructie en ondergrond"
STAGE_POSITION = 0  # PRZED rf-s1 (position=1)

# Mapowanie plikow .md -> dane lekcji w apce
LESSONS = [
    {
        "id": "rf-s0-l1",
        "position": 1,
        "title": "Constructie 1.1 cz.1 — Houten dakconstructie",
        "path": "content/module-1/les-1.1-constructie/cz1-drewno.md",
        "duration_min": 35,
        "is_free_preview": 1,  # PIERWSZA lekcja jako free preview = marketing
    },
    {
        "id": "rf-s0-l2",
        "position": 2,
        "title": "Constructie 1.1 cz.2 — Staaldek (Joris Ide profielplaten)",
        "path": "content/module-1/les-1.1-constructie/cz2-staaldek.md",
        "duration_min": 40,
        "is_free_preview": 0,
    },
    {
        "id": "rf-s0-l3",
        "position": 3,
        "title": "Constructie 1.1 cz.3 — Betonnen dakconstructie",
        "path": "content/module-1/les-1.1-constructie/cz3-beton.md",
        "duration_min": 30,
        "is_free_preview": 0,
    },
    {
        "id": "rf-s0-l4",
        "position": 4,
        "title": "Voorbereiding van de ondergrond (sucho, czysto, spadek, primer)",
        "path": "content/module-1/les-1.2-podloze/podloze.md",
        "duration_min": 30,
        "is_free_preview": 0,
    },
    {
        "id": "rf-s0-l5",
        "position": 5,
        "title": "Inleiding tot bitumineuze membranen (SBS / APP / DUO / wortelwerend)",
        "path": "content/module-1/les-1.3-wprowadzenie-papa/wprowadzenie-papa.md",
        "duration_min": 45,
        "is_free_preview": 0,
    },
    {
        "id": "rf-s0-l6",
        "position": 6,
        "title": "Dampscherm (paroizolacja) V3/P3 primer drukschotels",
        "path": "content/module-1/les-1.4-dampscherm/Lekcja_1.4_Dampscherm_v2.md",
        "duration_min": 35,
        "is_free_preview": 0,
    },
]

# --- PARSER QUIZU --------------------------------------------------------

def parse_quiz(content):
    """
    Parsuje sekcje "# QUIZ" z markdown.
    Format:
        # QUIZ ...
        **1. Pytanie?**
        A) opcja a
        B) opcja b
        C) opcja c
        D) opcja d
        **Poprawna: X**

    Zwraca: list[dict] z pytaniami {question, opt_a, opt_b, opt_c, opt_d, correct_index}
    """
    if not content:
        return []

    # Wytnij wszystko od naglowka QUIZ w gore
    # Akceptuje: "# QUIZ", "## QUIZ", "### QUIZ", "## 🧪 QUIZ — sprawdz sie" itd.
    m = re.search(r'^#{1,3}\s+.*QUIZ\b.*$', content, re.MULTILINE | re.IGNORECASE)
    if not m:
        return []
    quiz_section_start = m.end()
    quiz_section = content[quiz_section_start:]

    # Wytnij sekcje "Odpowiedzi i wyjasnienia" osobno (przyda sie nizej)
    # Pytania konczy sie tam gdzie zaczynaja sie odpowiedzi
    answers_match = re.search(
        r'^#{2,4}\s+.*(?:Odpowiedzi|Poprawne odpowiedzi|Klucz)\b.*$',
        quiz_section,
        re.MULTILINE | re.IGNORECASE
    )
    answers_section = ""
    if answers_match:
        answers_section = quiz_section[answers_match.end():]
        # Pytania = wszystko PRZED sekcja odpowiedzi
        quiz_section = quiz_section[:answers_match.start()]

    # Wytnij od "**Koniec lekcji" w dol (zeby nie lapac smieci po quizie)
    end_m = re.search(r'\*\*Koniec lekcji', quiz_section)
    if end_m:
        quiz_section = quiz_section[:end_m.start()]
    # To samo dla sekcji odpowiedzi
    end_m2 = re.search(r'^#{1,3}\s+', answers_section, re.MULTILINE)
    if end_m2:
        answers_section = answers_section[:end_m2.start()]

    questions = []

    # FORMAT A: pytanie + opcje + "**Poprawna: X**" wszystko razem (lekcje 1.2, 1.3)
    pattern_inline = re.compile(
        r'\*\*(\d+)\.\s+(.+?)\*\*\s*\n+'           # numer + tekst pytania
        r'(.*?)'                                    # opcje (cokolwiek)
        r'\*\*Poprawna:\s*([A-D])\*\*',             # poprawna odpowiedz
        re.DOTALL
    )

    # FORMAT B: pytanie + opcje (bez "Poprawna"), odpowiedzi w osobnej sekcji (lekcje 1.1)
    # Najpierw zbieramy pytania, potem dopisujemy odpowiedz z sekcji
    pattern_question_only = re.compile(
        r'\*\*(\d+)\.\s+(.+?)\*\*\s*\n+'           # numer + tekst pytania
        r'((?:\s*-?\s*[A-D]\)[^\n]+\n+)+)',         # 4 opcje A-D (z myslnikiem lub bez)
        re.MULTILINE
    )

    # Sprawdz czy mamy format A (sa "Poprawna: X" w sekcji pytan)
    has_inline_answers = bool(re.search(r'\*\*Poprawna:\s*[A-D]\*\*', quiz_section))

    if has_inline_answers:
        # FORMAT A - dziala jak wczesniej
        for m in pattern_inline.finditer(quiz_section):
            qnum = int(m.group(1))
            qtext = m.group(2).strip()
            options_block = m.group(3)
            correct_letter = m.group(4).strip()

            opts = parse_options(options_block)
            if opts is None:
                print(f"   ! Pytanie {qnum} - brak wszystkich opcji A-D, pomijam")
                continue

            questions.append({
                "position": qnum,
                "question": qtext,
                "option_a": opts['A'],
                "option_b": opts['B'],
                "option_c": opts['C'],
                "option_d": opts['D'],
                "correct_index": ord(correct_letter) - ord('A'),
            })
    else:
        # FORMAT B - pytania osobno, odpowiedzi w sekcji "Odpowiedzi i wyjasnienia"
        # Wyciagamy odpowiedzi z answers_section: "**N. X — ...**"
        answer_map = {}
        for am in re.finditer(
            r'\*\*(\d+)\.\s+([A-D])\s*[—\-–]',  # **1. C —  lub  **1. C -  lub  **1. C –
            answers_section
        ):
            anum = int(am.group(1))
            aletter = am.group(2)
            answer_map[anum] = aletter

        # Teraz parsuj pytania z sekcji quizu
        for m in pattern_question_only.finditer(quiz_section):
            qnum = int(m.group(1))
            qtext = m.group(2).strip()
            options_block = m.group(3)

            opts = parse_options(options_block)
            if opts is None:
                print(f"   ! Pytanie {qnum} - brak wszystkich opcji A-D, pomijam")
                continue

            correct_letter = answer_map.get(qnum)
            if not correct_letter:
                print(f"   ! Pytanie {qnum} - brak odpowiedzi w sekcji 'Odpowiedzi', pomijam")
                continue

            questions.append({
                "position": qnum,
                "question": qtext,
                "option_a": opts['A'],
                "option_b": opts['B'],
                "option_c": opts['C'],
                "option_d": opts['D'],
                "correct_index": ord(correct_letter) - ord('A'),
            })

    return questions


def parse_options(options_block):
    """
    Parsuje blok opcji A-D, akceptuje formaty:
        A) tekst
        - A) tekst
        -A) tekst
    Zwraca dict {A: ..., B: ..., C: ..., D: ...} lub None jak czego\u015b brak.
    """
    opts = {}
    for line in options_block.split('\n'):
        line = line.strip()
        # Usun "-" lub "*" na poczatku (formatowanie listy markdown)
        line = re.sub(r'^[\-\*]\s*', '', line)
        opt_m = re.match(r'^([A-D])\)\s*(.+)$', line)
        if opt_m:
            opts[opt_m.group(1)] = opt_m.group(2).strip()
    if not all(k in opts for k in ['A', 'B', 'C', 'D']):
        return None
    return opts


# --- BAZA ------------------------------------------------------------------

UPSERT_STAGE = """
INSERT INTO stages (id, course_id, title, position)
VALUES (?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    course_id=excluded.course_id,
    title=excluded.title,
    position=excluded.position;
"""

UPSERT_LESSON = """
INSERT INTO lessons (id, stage_id, title, type, content, duration_min, position, is_free_preview)
VALUES (?, ?, ?, 'text', ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    stage_id=excluded.stage_id,
    title=excluded.title,
    type=excluded.type,
    content=excluded.content,
    duration_min=excluded.duration_min,
    position=excluded.position,
    is_free_preview=excluded.is_free_preview;
"""

UPSERT_QUIZ_LESSON = """
INSERT INTO lessons (id, stage_id, title, type, content, duration_min, position, is_free_preview)
VALUES (?, ?, ?, 'quiz', NULL, ?, ?, 0)
ON CONFLICT(id) DO UPDATE SET
    stage_id=excluded.stage_id,
    title=excluded.title,
    type=excluded.type,
    duration_min=excluded.duration_min,
    position=excluded.position;
"""

UPSERT_QUESTION = """
INSERT INTO quiz_questions (id, lesson_id, question, option_a, option_b, option_c, option_d, correct_index, position)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    lesson_id=excluded.lesson_id,
    question=excluded.question,
    option_a=excluded.option_a,
    option_b=excluded.option_b,
    option_c=excluded.option_c,
    option_d=excluded.option_d,
    correct_index=excluded.correct_index,
    position=excluded.position;
"""

# --- POMOCNICZE ------------------------------------------------------------

def read_md(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser(description="Import lekcji .md do bazy apki")
    ap.add_argument("--db", default=DEFAULT_DB, help="sciezka do bazy SQLite")
    ap.add_argument("--dry-run", action="store_true", help="nie zapisuj, tylko pokaz")
    args = ap.parse_args()

    print(f"== DakPro Academy — import do apki ==")
    print(f"Baza: {args.db}  {'(DRY-RUN)' if args.dry_run else ''}")
    print(f"Kurs: {COURSE_ID}")
    print(f"Etap: {STAGE_ID} \"{STAGE_TITLE}\" (position={STAGE_POSITION})\n")

    if not os.path.exists(args.db):
        print(f"BLAD: baza {args.db} nie istnieje!")
        return 1

    if not args.dry_run:
        conn = sqlite3.connect(args.db)
        # Weryfikacja: kurs musi istniec
        course = conn.execute("SELECT id, title FROM courses WHERE id=?", (COURSE_ID,)).fetchone()
        if not course:
            print(f"BLAD: kurs {COURSE_ID} nie istnieje w bazie!")
            conn.close()
            return 1
        print(f"Kurs znaleziony: {course[1]}")

        # Stage
        conn.execute(UPSERT_STAGE, (STAGE_ID, COURSE_ID, STAGE_TITLE, STAGE_POSITION))
        print(f"-> Stage {STAGE_ID} zapisany\n")
    else:
        conn = None
        print(f"(DRY-RUN: nie tworze stage'a)\n")

    total_lessons = 0
    total_questions = 0
    quiz_lesson_position_offset = len(LESSONS)  # quizy ida po wszystkich lekcjach

    for L in LESSONS:
        print(f"-> {L['id']}  ({L['title']})")
        content = read_md(L["path"])
        if content is None:
            print(f"   ! brak pliku {L['path']}, pomijam\n")
            continue

        # Parsuj quiz
        questions = parse_quiz(content)
        print(f"   tresc: {len(content)} znakow | quiz: {len(questions)} pytan")

        if not args.dry_run:
            # Lekcja tekstowa
            conn.execute(UPSERT_LESSON, (
                L["id"], STAGE_ID, L["title"], content,
                L["duration_min"], L["position"], L["is_free_preview"]
            ))
            total_lessons += 1

            # Jesli sa pytania - tworz osobna lekcje quiz tussentoets
            if questions:
                quiz_lesson_id = f"{L['id']}-q1"
                quiz_lesson_title = f"Tussentoets — {L['title'].split('—')[-1].strip() if '—' in L['title'] else L['title']}"
                quiz_lesson_position = quiz_lesson_position_offset + L["position"]

                conn.execute(UPSERT_QUIZ_LESSON, (
                    quiz_lesson_id, STAGE_ID, quiz_lesson_title,
                    10, quiz_lesson_position
                ))

                # Wstaw pytania
                for q in questions:
                    qid = f"{quiz_lesson_id}-{q['position']:02d}"
                    conn.execute(UPSERT_QUESTION, (
                        qid, quiz_lesson_id,
                        q["question"], q["option_a"], q["option_b"],
                        q["option_c"], q["option_d"], q["correct_index"],
                        q["position"]
                    ))
                    total_questions += 1
                print(f"   -> quiz lesson: {quiz_lesson_id} ({len(questions)} pytan)")

        print()

    if not args.dry_run:
        conn.commit()
        # Weryfikacja
        n_lessons = conn.execute(
            "SELECT COUNT(*) FROM lessons WHERE stage_id=?", (STAGE_ID,)
        ).fetchone()[0]
        n_quiz_lessons = conn.execute(
            "SELECT COUNT(*) FROM lessons WHERE stage_id=? AND type='quiz'", (STAGE_ID,)
        ).fetchone()[0]
        n_questions = conn.execute(
            """SELECT COUNT(*) FROM quiz_questions q
               JOIN lessons l ON q.lesson_id = l.id
               WHERE l.stage_id=?""", (STAGE_ID,)
        ).fetchone()[0]
        conn.close()
        print(f"OK. W etapie {STAGE_ID}: lekcji={n_lessons} (w tym quizow={n_quiz_lessons}), pytan={n_questions}")
    else:
        print(f"DRY-RUN: byloby {total_lessons} lekcji + {total_questions} pytan")

    return 0


if __name__ == "__main__":
    sys.exit(main())
