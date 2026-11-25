#!/usr/bin/env python3
"""Add a mobile access section to the existing Academy release, preserving runtime and lessons."""
import datetime, fcntl, hashlib, importlib.util, json, os, shutil, subprocess, sys, tempfile, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("play_setup", HERE.parent / "google-play/setup.py")
play = importlib.util.module_from_spec(spec)
spec.loader.exec_module(play)
pay = play.pay
APP = "mca-course-test"
MARKER = "mobile-app-section.sha256"

def environment_fingerprint():
    data = json.loads(pay.run("docker", "inspect", APP, capture=True))[0]
    env = sorted(data["Config"]["Env"])
    return hashlib.sha256(json.dumps(env).encode()).hexdigest()

def source_fingerprint(root):
    h = hashlib.sha256()
    for folder in ["src", "public", "supabase"]:
        base = root / folder
        if not base.exists(): continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and not path.is_symlink() and path.relative_to(root).as_posix() not in ["src/routes/index.tsx", "src/components/MobileAppSection.tsx"]:
                h.update(path.relative_to(root).as_posix().encode())
                h.update(path.read_bytes())
    return h.hexdigest()

def main():
    pay.require(os.geteuid() == 0 and pay.PRIVATE.is_dir(), "Use the existing Academy root terminal")
    os.umask(0o077)
    with (pay.PRIVATE / "checkout-release.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        root, project, service, directory, files, envfiles, old = pay.inspect_current(APP)
        source = HERE.parent / "mobile-app/MobileAppSection.tsx"
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if (root / MARKER).is_file() and (root / MARKER).read_text().strip() == digest:
            print("MOBILE_SECTION_ALREADY_ACTIVE", flush=True); return
        pay.require(directory.is_relative_to(root), "Unexpected Compose directory")
        route = root / "src/routes/index.tsx"
        original = route.read_text()
        pay.require(original.count("<HomeHero />") == 1 and "MobileAppSection" not in original, "Homepage structure requires review")
        before = environment_fingerprint()
        preserved = source_fingerprint(root)
        target = Path(tempfile.mkdtemp(prefix="mca-mobile-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-", dir=pay.RELEASES))
        shutil.copytree(root, target, dirs_exist_ok=True, symlinks=True, ignore=shutil.ignore_patterns("node_modules", ".git", ".output", ".tanstack", ".vinxi", "dist"))
        target.chmod(0o700)
        changed = 'import MobileAppSection from "@/components/MobileAppSection";\n' + original.replace("<HomeHero />", "<HomeHero />\n        <MobileAppSection />", 1)
        (target / "src/routes/index.tsx").write_text(changed)
        shutil.copyfile(source, target / "src/components/MobileAppSection.tsx")
        pay.require(source_fingerprint(target) == preserved, "Files outside mobile section changed")
        migrated_files = [pay.local_copy(root, target, p) for p in files]
        migrated_envs = [pay.local_copy(root, target, p) for p in envfiles]
        target_dir = pay.local_copy(root, target, directory)
        override = target_dir / "mobile-app.compose.json"
        override.write_text(json.dumps({"services": {service: {"build": {"context": str(target)}, "image": "mca-mobile:" + target.name}}}))
        command = pay.compose(project, target_dir, [*migrated_files, override], migrated_envs)
        log = pay.PRIVATE / ("mobile-app-build-" + target.name + ".log")
        print("BUILDING_MOBILE_SECTION", flush=True)
        with log.open("w") as stream:
            build = subprocess.run([str(x) for x in [*command, "build", service]], stdout=stream, stderr=subprocess.STDOUT)
        pay.require(build.returncode == 0, "Build failed before deployment; current app unchanged. See private build log.")
        rollback = old + ["up", "-d", "--force-recreate", "--no-build", "--no-deps", "--wait", service]
        (target / "mobile-app-rollback.json").write_text(json.dumps(rollback))
        (target / MARKER).write_text(digest + "\n")
        print("ACTIVATING_MOBILE_SECTION", flush=True)
        try:
            pay.run(*command, "up", "-d", "--no-build", "--no-deps", "--wait", service)
            pay.require(environment_fingerprint() == before, "Runtime settings changed")
            for host in ["markacentrumacademy.eu", "www.markacentrumacademy.eu"]:
                for path in ["/", "/katalog", "/auth"]:
                    with urllib.request.urlopen("https://" + host + path, timeout=30) as r:
                        body = r.read().decode()
                        pay.require(r.status == 200, "Public route failed")
                        if path == "/": pay.require('id="aplikacja"' in body and "Wkrótce w Google Play" in body, "Mobile section missing from public homepage")
            current, *_ = pay.inspect_current(APP)
            pay.require(current == target and source_fingerprint(current) == preserved, "Release preservation check failed")
        except BaseException:
            pay.run(*rollback)
            raise
        print("MOBILE_SECTION_ACTIVE languages=PL,NL,FR,EN,DE runtime=unchanged educational_files=unchanged public_routes=200", flush=True)

if __name__ == "__main__":
    try: main()
    except Exception as error:
        print(str(error) if isinstance(error, ValueError) else type(error).__name__, file=sys.stderr)
        sys.exit(1)
