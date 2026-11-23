#!/usr/bin/env python3
"""Deploy Academy privacy pages and links using the active application source."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("certificate_release", HERE.parent / "cert/release.py")
cert = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cert)
pay = cert.pay
PATCH = HERE / "privacy.patch"
MARKER = "privacy-release.sha256"

CHECK_JS = """
(async () => {
  for (const path of ['/privacy','/delete-account']) {
    const r = await fetch('http://127.0.0.1:3000' + path);
    const text = await r.text();
    if (r.status !== 200 || !r.headers.get('content-type')?.includes('text/html') ||
        !text.includes('info@markaconstruct.be') || !text.includes('id="en"')) process.exit(2);
  }
  const home = await fetch('http://127.0.0.1:3000/');
  if (!home.ok || !(await home.text()).includes('href="/delete-account#')) process.exit(3);
  console.log('Public privacy pages and app links verified.');
})().catch(() => process.exit(4));
"""

def apply(mode):
    root, project, service, directory, files, envfiles, previous = pay.inspect_current(cert.APP)
    before = cert.fingerprint()
    pay.require(len(before) == 64, "Payment configuration could not be verified")
    expected = hashlib.sha256(PATCH.read_bytes()).hexdigest()
    if mode == "rollback":
        pay.require((root / MARKER).is_file(), "Active application has no privacy release marker")
        cmd = json.loads((root / "previous-compose.json").read_text())
        pay.require(cmd[:4] == ["docker", "compose", "--project-name", project]
                    and cmd[-6:] == ["up", "-d", "--no-build", "--no-deps", "--wait", service],
                    "Invalid saved rollback command")
        pay.run(*cmd)
        pay.require(cert.fingerprint() == before, "Restored runtime configuration differs")
        print("Previous Academy application restored.")
        return
    if (root / MARKER).is_file() and (root / MARKER).read_text().strip() == expected:
        pay.run("docker", "exec", cert.APP, "node", "-e", CHECK_JS)
        print("Privacy release already active.")
        return
    pay.run("git", "apply", "--check", PATCH, cwd=root)
    if mode == "check":
        print("Active source, privacy patch and runtime settings verified.")
        return
    target = Path(tempfile.mkdtemp(prefix="privacy-", dir=pay.RELEASES))
    try:
        shutil.copytree(root, target, dirs_exist_ok=True, symlinks=True,
                        ignore=shutil.ignore_patterns(".git", "node_modules", ".output", ".tanstack", ".vinxi", "dist"))
        target.chmod(0o700)
        pay.run("git", "apply", PATCH, cwd=target)
        dest = pay.local_copy(root, target, directory)
        override = dest / "privacy.compose.json"
        override.write_text(json.dumps({"services": {service: {
            "build": {"context": str(target)}, "image": "mca-privacy:" + target.name,
        }}}))
        next_cmd = pay.compose(project, dest,
            [*[pay.local_copy(root, target, file) for file in files], override],
            [pay.local_copy(root, target, file) for file in envfiles])
        pay.run(*next_cmd, "build", service)
    except BaseException:
        shutil.rmtree(target)
        raise
    up = ["up", "-d", "--no-build", "--no-deps", "--wait", service]
    (target / "previous-compose.json").write_text(json.dumps(previous + up))
    (target / MARKER).write_text(expected + "\n")
    try:
        pay.run(*next_cmd, *up)
        pay.require(cert.fingerprint() == before, "Runtime configuration changed")
        pay.run("docker", "exec", cert.APP, "node", "-e", CHECK_JS)
    except BaseException:
        pay.run(*previous, *up)
        raise
    print("PRIVACY_RELEASE_HEALTHY")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", choices=("check", "deploy", "rollback"), default="deploy")
    args = parser.parse_args()
    try:
        pay.require(os.geteuid() == 0 and pay.PRIVATE.is_dir(), "Use the Academy host terminal")
        os.umask(0o077)
        with (pay.PRIVATE / "checkout-release.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            apply(args.mode)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        if isinstance(error, ValueError):
            print(str(error), file=sys.stderr)
        sys.exit("Privacy release stopped.")
