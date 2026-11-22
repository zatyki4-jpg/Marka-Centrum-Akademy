#!/usr/bin/env python3
"""Prepare a separate MCA UI release; never changes lessons, data or live containers.

Default is a read-only check. --apply requires a new --output directory.
This patch targets the self-hosted TanStack application, not the legacy app
on this repository's main branch. Run it from the deployed source directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Source differs: expected one occurrence of ' + repr(old[:70]))
    return source.replace(old, new, 1)


def prepare(root):
    header_path = 'src/components/SiteHeader.tsx'
    panel_path = 'src/routes/_authenticated/panel.tsx'
    header = (root / header_path).read_text()
    panel = (root / panel_path).read_text()
    logo = json.loads((root / 'src/assets/mca-logo.png.asset.json').read_text())['url']
    if not re.fullmatch(r'/__l5e/[A-Za-z0-9_./-]+', logo):
        raise ValueError('Unexpected logo asset path')
    header = once(header, 'HardHat, LogOut,', 'LogOut,')
    old = '''          <span className="flex size-9 items-center justify-center rounded-lg surface-hero">
            <HardHat className="size-5" />
          </span>'''
    new = '''          <img
            src="%s"
            alt="MCA"
            width={56}
            height={56}
            className="size-14 shrink-0 rounded-lg object-cover"
          />''' % logo
    header = once(header, old, new)
    header = once(header, 'flex h-16 max-w-6xl items-center justify-between gap-4 px-4',
                  'flex min-h-20 max-w-6xl items-center justify-between gap-3 px-4 py-2')
    header = once(header, '<Link to="/" className="flex items-center gap-2.5">',
                  '<Link to="/" className="flex min-w-0 items-center gap-2.5">')
    header = once(header, '''        <div className="flex items-center gap-2 md:hidden">
          <LanguageSwitcher />''', '''        <div className="flex shrink-0 items-center gap-2 md:hidden">''')
    header = once(header, '''          <nav className="flex flex-col gap-4">
            {nav}''', '''          <nav className="flex flex-col gap-4">
            <LanguageSwitcher className="flex-wrap border-b border-border pb-3" />
            {nav}''')
    panel = once(panel, '''        <div className="mt-6 flex flex-wrap gap-2">''', '''        <div className="mt-6 flex flex-wrap gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link to="/katalog"><BookOpen className="size-4" /> {t("nav.catalog")}</Link>
          </Button>''')
    return {header_path: header, panel_path: panel}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    changes = prepare(root)
    report = {'changes': {p: {'before': hashlib.sha256((root / p).read_bytes()).hexdigest(),
                             'after': hashlib.sha256(s.encode()).hexdigest()}
                          for p, s in changes.items()}}
    if args.apply:
        if args.output is None:
            parser.error('--apply requires a new --output directory')
        out = args.output.resolve()
        if out.exists() or root == out or root in out.parents:
            parser.error('Output must be a new directory outside the source tree')
        os.umask(0o077)
        shutil.copytree(root, out, ignore=shutil.ignore_patterns('node_modules', '.output', '.git'))
        out.chmod(0o700)
        for p, content in changes.items():
            (out / p).write_text(content)
        (out / 'UI-CHANGE-REPORT.json').write_text(json.dumps(report, indent=2) + '\n')
        report['prepared_directory'] = str(out)
    report['live_containers_changed'] = False
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
