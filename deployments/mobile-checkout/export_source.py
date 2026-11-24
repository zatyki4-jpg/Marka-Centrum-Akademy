#!/usr/bin/env python3
"""Export only the deployed checkout navigation source to the existing private MCA repository."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
spec = importlib.util.spec_from_file_location("checkout_ops", HERE.parent / "checkout-120/release.py")
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)
root, *_ = ops.inspect_current("mca-course-test")
allowed = [Path("src/routes/kurs.$slug.tsx"), Path("src/components/CourseCheckout.tsx"),
           Path("src/components/PlayCourseCheckout.tsx"), Path("src/lib/mca-purchase-surface.ts")]
allowed += [p.relative_to(root) for p in (root / "src/routes").glob("lekcja.*.tsx")]
allowed += [p.relative_to(root) for p in (root / "src/routes").glob("panel.kurs.*.tsx")]
ops.require(len(allowed) <= 12, "Unexpected route inventory")
for relative in allowed:
    source = root / relative
    ops.require(source.is_file() and not source.is_symlink(), "Missing expected source: " + str(relative))
    target = HERE / "source" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
paths = [str((HERE / "source" / p).relative_to(REPO)) for p in allowed]
subprocess.run(["git", "add", "--", *paths], cwd=REPO, check=True)
if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO).returncode != 0:
    staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=REPO, text=True).splitlines()
    ops.require(set(staged) <= set(paths), "Unrelated staged changes")
    subprocess.run(["git", "commit", "-m", "Snapshot deployed MCA checkout navigation before mobile fix"], cwd=REPO, check=True)
    subprocess.run(["git", "push", "origin", "HEAD:refs/heads/mca-mobile-checkout-20261124"], cwd=REPO, check=True)
print("EXPORTED_CHECKOUT_SOURCE", *paths, sep="\n")
