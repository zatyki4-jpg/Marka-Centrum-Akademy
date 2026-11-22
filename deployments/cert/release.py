#!/usr/bin/env python3
"""Deploy or roll back the Academy certificate presentation patch on the active checkout release."""
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
PATCH = HERE / "certificates.patch"
TOOLS = HERE.parent / "checkout-120" / "release.py"
spec = importlib.util.spec_from_file_location("payment_release", TOOLS)
pay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pay)
run, require = pay.run, pay.require
APP = "mca-course-test"
CHECKOUT = "e15046dae8b75dffddb7350880a6097ef66e8d62284232c48553a1ef412e6d3e"
MARKER = "certificate-release.sha256"

# Only a digest exits the running container. Include all Stripe / Supabase settings,
# the checkout origin, and verify both actual price IDs before allowing a switch.
DIGEST_JS = """
const crypto = require('node:crypto');
const e = process.env;
const expected = %s;
if (Object.entries(expected).some(([k,v]) => e[k] !== v) ||
    !['STRIPE_SECRET_KEY','STRIPE_WEBHOOK_SECRET','SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY',
      'SUPABASE_PUBLISHABLE_KEY'].every(k => e[k])) process.exit(2);
const keys = Object.keys(e).filter(k => /^(STRIPE_|SUPABASE_|MCA_)/.test(k)).sort();
process.stdout.write(crypto.createHash('sha256').update(JSON.stringify(keys.map(k=>[k,e[k]]))).digest('hex'));
""" % json.dumps(pay.LIVE_PRICES)


def fingerprint():
    return run("docker", "exec", APP, "node", "-e", DIGEST_JS, capture=True).strip()


def label(name):
    return run("docker", "inspect", "-f", '{{ index .Config.Labels "com.docker.compose.' + name + '" }}',
               APP, capture=True).strip()


def inputs():
    project, service = label("project"), label("service")
    directory = Path(label("project.working_dir")).resolve(strict=True)
    root = directory.parent.parent
    require(root.parent == pay.RELEASES and directory == root / "deploy/hetzner", "Unexpected active release directory")
    require((root / "checkout-release.sha256").read_text().strip() == CHECKOUT,
            "The verified production checkout release is required")
    files = [Path(f).resolve(strict=True) for f in label("project.config_files").split(",")]
    env = label("project.environment_file")
    envfiles = [Path(f).resolve(strict=True) for f in env.split(",") if f and f != "<no value>"]
    if not envfiles and (directory / ".env").is_file():
        envfiles = [directory / ".env"]
    checkout_file = directory / "checkout-runtime.compose.json"
    require(checkout_file in files, "Active checkout Compose override is missing")
    current = json.loads(checkout_file.read_text())["services"][service]
    require(current["environment"] == pay.LIVE_PRICES and
            current["env_file"] == [str(pay.PRIVATE / "stripe-checkout.env")], "Unexpected live price or private env reference")
    is_cert = (root / MARKER).is_file()
    effective_file = directory / "certificate.compose.json" if is_cert else checkout_file
    require(files[-1] == effective_file, "Unrecognized active Compose overrides")
    effective = json.loads(effective_file.read_text())["services"][service]
    image = run("docker", "inspect", "-f", "{{.Config.Image}}", APP, capture=True).strip()
    require(Path(effective["build"]["context"]) == root and effective["image"] == image,
            "Running checkout image and source context differ")
    return root, project, service, directory, files, envfiles


def apply(mode):
    root, project, service, directory, files, envfiles = inputs()
    old = pay.compose(project, directory, files, envfiles)
    same_env = fingerprint()
    require(len(same_env) == 64, "Payment configuration check failed")
    expected = hashlib.sha256(PATCH.read_bytes()).hexdigest()
    if mode == "rollback":
        require((root / MARKER).is_file(), "Active image is not a certificate release")
        cmd = json.loads((root / "previous-compose.json").read_text())
        require(cmd[:4] == ["docker", "compose", "--project-name", project] and
                cmd[-6:] == ["up", "-d", "--no-build", "--no-deps", "--wait", service], "Invalid rollback command")
        run(*cmd)
        require(fingerprint() == same_env, "Restored application's payment environment differs")
        print("Previous Academy checkout release restored.")
        return
    if (root / MARKER).is_file() and (root / MARKER).read_text().strip() == expected:
        print("Certificate release already active.")
        return
    run("git", "apply", "--check", PATCH, cwd=root)
    if mode == "check":
        print("Active checkout, payment settings and certificate source verified.")
        return
    target = Path(tempfile.mkdtemp(prefix="cert-", dir=pay.RELEASES))
    try:
        shutil.copytree(root, target, dirs_exist_ok=True, symlinks=True,
                        ignore=shutil.ignore_patterns(".git","node_modules",".output",".tanstack",".vinxi","dist"))
        target.chmod(0o700)
        run("git", "apply", PATCH, cwd=target)
        remap = lambda p: pay.local_copy(root, target, p)
        dest = remap(directory)
        override = dest / "certificate.compose.json"
        override.write_text(json.dumps({"services": {service: {"build": {"context": str(target)}, "image": "mca-cert:" + target.name}}}))
        next_cmd = pay.compose(project, dest, [*[remap(f) for f in files], override], [remap(f) for f in envfiles])
        run(*next_cmd, "build", service)
    except BaseException:
        shutil.rmtree(target)
        raise
    up = ["up", "-d", "--no-build", "--no-deps", "--wait", service]
    (target / "previous-compose.json").write_text(json.dumps(old + up))
    (target / MARKER).write_text(expected + "\n")
    try:
        run(*next_cmd, *up)
        require(fingerprint() == same_env, "Payment runtime comparison failed")
    except BaseException:
        run(*old, *up)
        raise
    print("Certificate release healthy. Production payment environment verified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", choices=("check","deploy","rollback"), default="deploy")
    args = parser.parse_args()
    try:
        require(os.geteuid() == 0 and pay.PRIVATE.is_dir(), "Use the Academy host root terminal")
        os.umask(0o077)
        with (pay.PRIVATE / "checkout-release.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            apply(args.mode)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        if type(error) is ValueError:
            print(str(error), file=sys.stderr)
        sys.exit("Certificate release stopped.")
