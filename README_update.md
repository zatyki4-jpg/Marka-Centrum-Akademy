# DakPro Academy — Update Modul 1 (les 1.2 + 1.3)

Toevoeging van **2 nieuwe lessen** aan de cursus Bitumineuze dakbedekking:

- **Les 1.2** — Voorbereiding van de ondergrond (Przygotowanie podłoża)
- **Les 1.3** — Inleiding tot bitumineuze membranen (Wprowadzenie do papy)

## Wat zit erin

```
content/
  module-1/
    les-1.2-podloze/
      podloze.md                # PL — 4 filary + primer
    les-1.3-wprowadzenie-papa/
      wprowadzenie-papa.md      # PL — SBS/APP/DUO/wortelwerend + narzedzia
import_lessons.py               # bijgewerkt: nu 5 lessen in LESSONS-lijst
```

## Hoe deployen

### Optie 1: GitHub Codespaces (aanbevolen)

```bash
# In je Codespace, in de root van Marka-Centrum-Akademy repo:

# 1. Upload deze bestanden (sleep ze in de file explorer of git pull)
# 2. Bekijk wat het script gaat doen:
python3 import_lessons.py --dry-run

# 3. Voer het import uit:
python3 import_lessons.py

# 4. Commit en push:
git add content/ import_lessons.py
git commit -m "Add les 1.2 podloze + les 1.3 wprowadzenie do papy"
git push
```

### Optie 2: Lokaal

Pak de ZIP uit, kopieer naar je repo-folder, voer `python3 import_lessons.py` uit, dan git push.

## Verificatie

Na het importeren zou `dakpro.db` moeten bevatten:

- Les 1.1 cz.1 — drewno (al aanwezig)
- Les 1.1 cz.2 — staaldek (al aanwezig)
- Les 1.1 cz.3 — beton (al aanwezig)
- **Les 1.2 — podloze** (NIEUW)
- **Les 1.3 — wprowadzenie-papa** (NIEUW)

Check met:
```bash
sqlite3 dakpro.db "SELECT lesson, part, slug, length(content_pl) FROM lessons ORDER BY lesson, part;"
```

## Idempotent

Het script gebruikt `ON CONFLICT(slug) DO UPDATE` — meermaals draaien doet geen kwaad,
het werkt bestaande lessen bij in plaats van duplicaten te maken.

## Volgende stappen

- **Les 1.4** — Dampscherm (TO DO)
- **Les 1.5** — Bevestiging van isolatie (TO DO)
- NL + EN vertalingen voor alle bestaande lessen (kolommen content_nl / content_en zijn nog NULL)
