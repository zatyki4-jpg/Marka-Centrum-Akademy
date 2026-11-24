#!/usr/bin/env python3
"""Build and atomically switch the deployed MCA checkout navigation only."""
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.request

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("checkout_ops", HERE.parent / "checkout-120/release.py")
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)
APP = "mca-course-test"


def environment_fingerprint():
    info = json.loads(ops.run("docker", "inspect", APP, capture=True))[0]
    return hashlib.sha256(json.dumps(sorted(info["Config"]["Env"])).encode()).hexdigest()


def replace_once(path, before, after):
    original = path.read_text()
    ops.require(original.count(before) == 1, "Unexpected checkout source: " + path.name)
    path.write_text(original.replace(before, after, 1))


def deploy():
    ops.require(os.geteuid() == 0, "Use the existing Academy server root session")
    root, project, service, directory, files, envfiles, previous = ops.inspect_current(APP)
    component = HERE / "LessonPurchaseOptions.tsx"
    ops.require(component.is_file(), "Checkout component missing")
    active_component = root / "src/components/LessonPurchaseOptions.tsx"
    if active_component.is_file() and active_component.read_bytes() == component.read_bytes():
        print("MOBILE_CHECKOUT_ALREADY_ACTIVE")
        return
    ops.require(directory.is_relative_to(root), "Compose directory outside release")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = Path(tempfile.mkdtemp(prefix="mobile-checkout-" + stamp + "-", dir=ops.RELEASES))
    target.chmod(0o700)
    shutil.copytree(root, target, dirs_exist_ok=True, symlinks=True,
                    ignore=shutil.ignore_patterns("node_modules", ".git", ".output", ".tanstack", ".vinxi", "dist"))
    course_path = target / "src/routes/kurs.$slug.tsx"
    course_source = course_path.read_text()
    aside_tags = re.findall(r"<aside\b[^>]*>", course_source)
    ops.require(len(aside_tags) == 1, "Unexpected course checkout panel count")
    aside = aside_tags[0]
    if 'className="' in aside:
        next_aside = aside.replace('className="', 'className="order-first lg:order-last ', 1)
    else:
        ops.require("className" not in aside, "Unexpected checkout panel classes")
        next_aside = aside.replace("<aside", '<aside className="order-first lg:order-last"', 1)
    replace_once(course_path, aside, next_aside)
    lesson = target / "src/routes/lekcja.$lessonId.tsx"
    original = lesson.read_text()
    heading = '<h1 className="text-2xl font-bold">{t("lesson.notFound")}</h1>'
    ops.require(original.count(heading) == 1, "Unexpected missing-lesson layout")
    ops.require("LessonPurchaseOptions" not in original, "Partial checkout patch found")
    lesson.write_text('import { LessonPurchaseOptions } from "@/components/LessonPurchaseOptions";\n'
                      + original.replace(heading, heading + "\n          <LessonPurchaseOptions />", 1))
    shutil.copyfile(component, target / "src/components/LessonPurchaseOptions.tsx")
    target_dir = ops.local_copy(root, target, directory)
    next_files = [ops.local_copy(root, target, p) for p in files]
    next_envs = [ops.local_copy(root, target, p) for p in envfiles]
    override = target_dir / "mobile-checkout.compose.json"
    override.write_text(json.dumps({"services": {service: {
        "build": {"context": str(target)}, "image": "mca-mobile-checkout:" + target.name,
    }}}))
    command = ops.compose(project, target_dir, [*next_files, override], next_envs)
    old_config = json.loads(ops.run(*previous, "config", "--format", "json", capture=True))
    new_config = json.loads(ops.run(*command, "config", "--format", "json", capture=True))
    ops.require(old_config["services"][service].get("environment") == new_config["services"][service].get("environment"),
                "Runtime configuration changed")
    fingerprint = environment_fingerprint()
    rollback = previous + ["up", "-d", "--no-build", "--no-deps", "--wait", service]
    (target / "mobile-checkout-rollback.json").write_text(json.dumps(rollback))
    ops.run(*command, "build", service)
    try:
        ops.run(*command, "up", "-d", "--no-build", "--no-deps", "--wait", service)
        ops.require(environment_fingerprint() == fingerprint, "Running environment changed")
        for path in ["/", "/kurs/bitumiczne-dachy-plaskie", "/kurs/renowacja-dachow-plaskich", "/privacy"]:
            with urllib.request.urlopen("https://www.markacentrumacademy.eu" + path, timeout=25) as response:
                ops.require(response.status == 200, "HTTP check failed")
        print("MOBILE_CHECKOUT_ACTIVE", target)
        print("RUNTIME_UNCHANGED HTTP_SMOKE_OK")
    except BaseException:
        ops.run(*rollback)
        raise


if __name__ == "__main__":
    os.umask(0o077)
    try:
        with (ops.PRIVATE / "checkout-release.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            deploy()
    except Exception as error:
        if isinstance(error, ValueError):
            print(str(error), file=sys.stderr)
        print("MOBILE_CHECKOUT_STOPPED", type(error).__name__, file=sys.stderr)
        sys.exit(1)
