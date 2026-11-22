#!/usr/bin/env python3
"""Check the payment overlay or deploy it on the existing Academy Docker host."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PATCH = HERE / "academy-checkout.patch"
RELEASES = Path("/srv/marka-course-academy/releases")
PRIVATE = RELEASES.parent / "private"
DB = "mca-sb-db"
MIGRATION = "supabase/migrations/20261122234000_mca_stripe_checkout.sql"
LIVE_PRICES = {
    "STRIPE_PRICE_BASIC": "price_1Uej4hIcl2W7iMTxaiHPUqGo",
    "STRIPE_PRICE_RENOVATION": "price_1Uej5CIcl2W7iMTxLKxgp06s",
}
ALLOWED_CONTAINERS = ["mca-course-test", "marka-course-academy"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(*args, cwd=None, capture=False):
    process = subprocess.run(
        [str(a) for a in args], cwd=cwd, check=True,
        stdout=subprocess.PIPE if capture else None, text=True,
    )
    return process.stdout if capture else None


def validate(root):
    require((root / "src/routes/kurs.$slug.tsx").is_file(), "Expected the Academy course application")
    run("git", "apply", "--check", PATCH, cwd=root)


def compose(project, cwd, files, envfiles):
    cmd = ["docker", "compose", "--project-name", project, "--project-directory", str(cwd)]
    for env in envfiles:
        cmd.extend(["--env-file", str(env)])
    for file in files:
        cmd.extend(["-f", str(file)])
    return cmd


def inspect_current(container):
    labels = json.loads(run("docker", "inspect", "--format", "{{json .Config.Labels}}", container, capture=True))
    project = labels["com.docker.compose.project"]
    service = labels["com.docker.compose.service"]
    directory = Path(labels["com.docker.compose.project.working_dir"]).resolve()
    files = [Path(item).resolve() for item in labels["com.docker.compose.project.config_files"].split(",")]
    saved_envs = labels.get("com.docker.compose.project.environment_file", "")
    envfiles = [Path(item).resolve() for item in saved_envs.split(",") if item]
    if not envfiles and (directory / ".env").is_file():
        envfiles = [directory / ".env"]
    base = compose(project, directory, files, envfiles)
    # This JSON can contain secrets: keep it in memory, never print it.
    cfg = json.loads(run(*base, "config", "--format", "json", capture=True))
    app = cfg["services"][service]
    require(app.get("container_name") == container, "Unexpected container in Compose configuration")
    root = Path(app["build"]["context"]).resolve()
    require(root.is_relative_to(RELEASES) and root != RELEASES, "Unexpected active application source")
    require(all(path.is_file() for path in files + envfiles), "Live Compose inputs missing")
    return root, project, service, directory, files, envfiles, base


def local_copy(original, destination, path):
    return destination / path.relative_to(original) if path.is_relative_to(original) else path


def make_release(root):
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = Path(tempfile.mkdtemp(prefix=f"checkout-{now}-", dir=RELEASES))
    try:
        shutil.copytree(
            root, target, dirs_exist_ok=True, symlinks=True,
            ignore=shutil.ignore_patterns("node_modules", ".git", ".output", ".tanstack", ".vinxi", "dist"),
        )
        target.chmod(0o700)
        run("git", "apply", PATCH, cwd=target)
    except BaseException:
        shutil.rmtree(target)
        raise
    return target


def migrate(source):
    sql = source.read_text().strip()
    require(sql.startswith("BEGIN;") and sql.endswith("COMMIT;"), "Migration requires a transaction")
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    marker = "academy-checkout-" + checksum
    psql = ["docker", "exec", "-i", DB, "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"]
    status = run(*psql, "-A", "-t", "-c",
        "SELECT CASE WHEN to_regclass('public.mca_checkout_orders') IS NULL THEN 'absent' "
        "ELSE coalesce(obj_description(to_regclass('public.mca_checkout_orders'),'pg_class'),'unknown') END",
        capture=True).strip()
    if status == marker:
        print("Payment schema already installed")
        return
    require(status == "absent", "An existing payment schema has a different migration fingerprint")
    body = sql[:-len("COMMIT;")] + f"COMMENT ON TABLE public.mca_checkout_orders IS '{marker}';\nCOMMIT;\n"
    subprocess.run(psql, text=True, input=body, check=True)


def validate_runtime(env):
    names = ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_PRICE_BASIC", "STRIPE_PRICE_RENOVATION",
             "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY")
    missing = [key for key in names if not env.get(key)]
    require(not missing, "Missing runtime settings: " + ", ".join(missing))
    require(re.fullmatch(r"(?:sk|rk)_live_[a-zA-Z0-9]+", env["STRIPE_SECRET_KEY"]), "Production requires a live Stripe key")
    require(re.fullmatch(r"whsec_[a-zA-Z0-9]+", env["STRIPE_WEBHOOK_SECRET"]), "Invalid webhook signing configuration")
    require(all(re.fullmatch(r"price_[a-zA-Z0-9]+", env[key]) for key in names[2:4]), "Invalid price configuration")
    require(env[names[2]] != env[names[3]], "The courses need separate Stripe prices")
    require(env.get("MCA_CHECKOUT_ORIGIN", "https://markacentrumacademy.eu") == "https://markacentrumacademy.eu",
            "The production checkout origin must match the Academy website")


def deploy(args):
    root, project, service, directory, files, envfiles, old = inspect_current(args.container)
    require(directory.is_relative_to(root), "Unexpected Compose working directory outside release")
    marker = root / "checkout-release.sha256"
    expected = hashlib.sha256(PATCH.read_bytes()).hexdigest()
    if marker.is_file() and marker.read_text().strip() == expected:
        print(f"Payment release is already active: {root}")
        return
    validate(root)
    secrets = args.secrets.resolve(strict=True)
    require(secrets.is_file() and secrets.stat().st_mode & 0o077 == 0, "Supply an owner-only runtime env file")
    require(not secrets.is_relative_to(RELEASES), "Runtime secrets must stay outside application releases")
    require(run("docker", "inspect", "--format", "{{.State.Running}}", DB, capture=True).strip()=="true", "Academy database is unavailable")
    target = make_release(root)
    migrated_files = [local_copy(root, target, f) for f in files]
    migrated_envs = [local_copy(root, target, f) for f in envfiles]
    target_dir = local_copy(root, target, directory)
    override = target_dir / "checkout-runtime.compose.json"
    require(target_dir.is_relative_to(target), "Unexpected Compose working directory outside release")
    override.write_text(json.dumps({"services": {service: {
        "build": {"context": str(target)},
        "image": f"mca-checkout:{target.name}",
        "environment": LIVE_PRICES,
        "env_file": [str(secrets)],
    }}}))
    next_cmd = compose(project, target_dir, [*migrated_files, override], migrated_envs)
    conf = json.loads(run(*next_cmd, "config", "--format", "json", capture=True))
    effective = conf["services"][service].get("environment", {})
    validate_runtime(effective)
    run(*next_cmd, "build", service)
    # Additive payment schema is installed transactionally before the app can accept checkouts.
    migrate(target / MIGRATION)
    rollback = old + ["up", "-d", "--no-build", "--no-deps", "--wait", service]
    (target / "previous-compose.json").write_text(json.dumps(rollback))
    (target / "checkout-release.sha256").write_text(expected + "\n")
    try:
        run(*next_cmd, "up", "-d", "--no-build", "--no-deps", "--wait", service)
    except (subprocess.CalledProcessError, KeyboardInterrupt):
        print("Replacement failed health checks. Restoring the previous app.", file=sys.stderr)
        run(*rollback)
        raise
    print(f"Payment release healthy: {target}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    check = modes.add_parser("check", help="Read-only preflight against an application source tree")
    check.add_argument("root", type=Path)
    apply = modes.add_parser("deploy", help="Build, migrate and replace the existing web service")
    apply.add_argument("--container", default="mca-course-test", choices=ALLOWED_CONTAINERS)
    apply.add_argument("--secrets", default=PRIVATE / "stripe-checkout.env", type=Path)
    restore = modes.add_parser("rollback", help="Restore the app serving before the checkout release")
    restore.add_argument("--container", required=True, choices=ALLOWED_CONTAINERS)
    args = parser.parse_args()
    if args.mode == "check":
        validate(args.root.resolve())
        print("Source preflight passed")
        return
    require(os.geteuid() == 0 and PRIVATE.is_dir(), "Run deploy on the existing Academy host")
    os.umask(0o077)
    with (PRIVATE / "checkout-release.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.mode == "deploy":
            deploy(args)
        else:
            root, project, service, *_ = inspect_current(args.container)
            cmd = json.loads((root / "previous-compose.json").read_text())
            require(isinstance(cmd, list) and cmd[:4] == ["docker", "compose", "--project-name", project]
                    and cmd[-6:] == ["up", "-d", "--no-build", "--no-deps", "--wait", service],
                    "Invalid saved rollback command")
            run(*cmd)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as e:
        print(f"Release stopped: {e}", file=sys.stderr)
        sys.exit(1)
