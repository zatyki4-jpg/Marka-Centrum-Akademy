#!/usr/bin/env python3
"""Provision Academy payment configuration from a root terminal on the existing host."""
import argparse
import base64
import fcntl
import getpass
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
import warnings

HOST = Path("/srv/marka-course-academy")
PRIVATE = HOST / "private"
DEST = PRIVATE / "stripe-checkout.env"
BACKEND = HOST / "backend-staging"
DAYS = "MCA_PAID_ACCESS_DAYS"
ROLE = "SUPABASE_SERVICE_ROLE_KEY"
NAMES = ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", ROLE, DAYS)
ROLE_ALIASES = ("SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY", ROLE)
ASSIGN = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z_0-9]*)\s*=\s*(.*)$")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_fields(raw, names):
    """Read literal values only. Preserve every untouched line of the original file."""
    fields = {}
    lines = raw.splitlines(keepends=True)
    for index, line in enumerate(lines):
        m = ASSIGN.match(line.rstrip("\r\n"))
        if not m or m[1] not in names:
            continue
        key, value = m.groups()
        require(key not in fields, f"Duplicate setting: {key}")
        value = re.split(r"\s+#", value.strip(), maxsplit=1)[0].strip()
        if value.startswith(("'", '"')):
            require(value[-1:] == value[:1] and len(value) >= 2, f"Invalid quoting: {key}")
            value = value[1:-1]
        fields[key] = (index, value)
    return lines, fields


def valid_role(value):
    if re.fullmatch(r"sb_secret_[A-Za-z0-9_-]{16,}", value):
        return True
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", value):
        return False
    try:
        payload = value.split(".")[1]
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return (isinstance(data, dict) and data.get("role") == "service_role"
                and ("exp" not in data or float(data["exp"]) > time.time()))
    except (ValueError, TypeError, UnicodeError):
        return False


def validated(key, value):
    if key == ROLE:
        ok = valid_role(value)
    elif key == DAYS:
        ok = re.fullmatch(r"[1-9][0-9]{0,4}", value) and int(value) <= 36500
    else:
        pattern = r"(?:sk|rk)_live_[A-Za-z0-9]{16,}" if key == "STRIPE_SECRET_KEY" else r"whsec_[A-Za-z0-9]{16,}"
        ok = re.fullmatch(pattern, value)
    require(ok, f"Invalid or expired setting: {key}")
    return value


def docker_value(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=10)
    return result.stdout.strip() if result.returncode == 0 else ""


def backend_role():
    # Do not inspect or print the full environment. Read a named field only from
    # the verified Academy backend project. Docker receives a name, never the key.
    label = '{{index .Config.Labels "com.docker.compose.project"}}'
    project = docker_value("inspect", "-f", label, "mca-sb-db")
    require(project == "mca-backend-staging", "Cannot identify the running Academy database project")
    require(docker_value("inspect", "-f", "{{.State.Running}}", "mca-sb-db") == "true", "Academy database is offline")
    container = "mca-sb-gateway"
    if docker_value("inspect", "-f", label, container) == project:
        for name in ROLE_ALIASES:
            value = docker_value("exec", container, "printenv", name)
            if valid_role(value):
                return value
    # Historical backend stores the service-role key in its root-owned Compose env.
    source = BACKEND / ".env"
    info = source.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022,
            "Unknown ownership or permissions on Academy backend configuration")
    _, fields = read_fields(source.read_text(), ROLE_ALIASES)
    valid = {v for _, v in fields.values() if valid_role(v)}
    require(len(valid) == 1, "No unique service-role key in the Academy backend configuration")
    return valid.pop()


def secret_input(tty, prompt):
    # getpass falls back to echoed input without a terminal. Treat that warning as an error.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        return getpass.getpass(prompt, stream=tty).strip()


def configure(tty, days):
    info = None
    raw = ""
    try:
        info = DEST.lstat()
    except FileNotFoundError:
        pass
    if info:
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
                and not info.st_mode & 0o077, "Existing payment configuration must be a private root-owned regular file")
        raw = DEST.read_bytes().decode()
    lines, fields = read_fields(raw, NAMES)
    old = {key: validated(key, value) for key, (_, value) in fields.items() if value}
    role = backend_role()
    require(old.get(ROLE, role) == role, "Existing payment role differs from the Academy backend; original file retained")
    if days is not None:
        validated(DAYS, days)
        require(old.get(DAYS, days) == days, "Existing access period differs; original file retained")
    new = {ROLE: role}
    if DAYS not in old:
        if days is None:
            tty.write("Liczba dni dostępu do kursu przed zdaniem egzaminu (zatwierdzona przez Academy): ")
            tty.flush()
            days = tty.readline().strip()
        new[DAYS] = validated(DAYS, days)
    for key, prompt in (("STRIPE_SECRET_KEY", "Klucz Stripe LIVE (sk_live_ lub rk_live_): "),
                        ("STRIPE_WEBHOOK_SECRET", "Sekret podpisu webhooka LIVE (whsec_): ")):
        if key not in old:
            new[key] = validated(key, secret_input(tty, prompt))
    missing = [key for key in NAMES if key not in old]
    if not missing:
        print("Payment settings are already complete. Existing file retained.")
        return
    for key in missing:
        entry = f"{key}={new[key]}\n"
        if key in fields:
            lines[fields[key][0]] = entry
        else:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(entry)
    fd, temp = tempfile.mkstemp(dir=PRIVATE, prefix=".checkout-env-")
    try:
        with os.fdopen(fd, "w") as out:
            out.write("".join(lines))
            out.flush()
            os.fsync(out.fileno())
        if info is None:
            # Atomic no-clobber if another process created the file meanwhile.
            os.link(temp, DEST)
        else:
            now = DEST.lstat()
            require((info.st_dev, info.st_ino, info.st_ctime_ns) == (now.st_dev, now.st_ino, now.st_ctime_ns),
                    "Payment configuration changed during setup; original file retained")
            os.replace(temp, DEST)
        dirfd = os.open(PRIVATE, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        Path(temp).unlink(missing_ok=True)
    print(f"Payment settings saved with mode 0600: {DEST}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--access-days", help="Approved initial number of days of paid access")
    args = parser.parse_args()
    require(os.geteuid() == 0, "Use the root terminal on the Academy host")
    require(HOST.is_dir() and BACKEND.is_dir(), "Existing Academy backend is missing")
    os.umask(0o077)
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    info = PRIVATE.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022,
            "Academy private directory must be root-owned with restricted write permissions")
    # Match the deployer's lock and require a terminal before handling any credentials.
    with open("/dev/tty", "r+b", buffering=0) as raw, io.TextIOWrapper(raw, encoding="utf-8", line_buffering=True) as tty:
        require(os.isatty(raw.fileno()), "A physical terminal or SSH TTY is required")
        with (PRIVATE / "checkout-release.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            configure(tty, args.access_days)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("Canceled. Existing payment configuration retained.")
    except (OSError, ValueError, EOFError, getpass.GetPassWarning, subprocess.TimeoutExpired) as e:
        # JSON/Unicode parse errors can contain excerpts of private files; never include them.
        if type(e) is ValueError:
            sys.exit(str(e))
        sys.exit("Setup stopped. Check root terminal access, backend configuration and file permissions.")
