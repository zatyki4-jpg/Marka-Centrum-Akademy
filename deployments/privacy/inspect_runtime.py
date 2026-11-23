#!/usr/bin/env python3
"""Read only the deployment facts needed for Academy privacy disclosures."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("payment_release", HERE.parent / "checkout-120/release.py")
pay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pay)

def query(sql):
    return subprocess.check_output([
        "docker", "exec", "mca-sb-db", "psql", "-XAt", "-v", "ON_ERROR_STOP=1",
        "-U", "postgres", "-d", "postgres", "-c", sql,
    ], text=True).strip()

if __name__ == "__main__":
    root, project, service, directory, files, envfiles, command = pay.inspect_current("mca-course-test")
    mode = sys.argv[1] if len(sys.argv) > 1 else "summary"
    if mode == "schema":
        print(query("SELECT conrelid::regclass::text || ' ' || pg_get_constraintdef(oid) FROM pg_constraint WHERE contype='f' AND confrelid='auth.users'::regclass ORDER BY 1"))
        print(query("SELECT table_name || ' ' || string_agg(column_name || ':' || data_type, ', ' ORDER BY ordinal_position) FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('mca_checkout_orders','mca_stripe_events','certificates','profiles','promo_participants','promo_feedback') GROUP BY table_name ORDER BY 1"))
    else:
        print("ACTIVE_SOURCE", root)
        for name in ("src/components/SiteFooter.tsx", "src/routes/auth.tsx", "src/lib/lovable-error-reporting.ts", "src/components/HelpAssistant.tsx"):
            print(name, hashlib.sha256((root / name).read_bytes()).hexdigest())
        for container in ("mca-course-test", "mca-sb-auth"):
            data = json.loads(subprocess.check_output(["docker", "inspect", container], text=True))[0]
            env = dict(value.split("=", 1) for value in data["Config"]["Env"] if "=" in value)
            print(container, {key: env[key] for key in ("SUPABASE_URL", "GOTRUE_SITE_URL", "GOTRUE_SMTP_HOST", "GOTRUE_SMTP_ADMIN_EMAIL", "GOTRUE_SMTP_SENDER_NAME") if key in env})
        print("USER_TABLES", query("SELECT string_agg(table_name || '.' || column_name, ', ' ORDER BY table_name,column_name) FROM information_schema.columns WHERE table_schema='public' AND (column_name LIKE '%user_id' OR column_name IN ('email','full_name','author_id','owner_id','customer_id','stripe_customer_id'))"))
        print("STORAGE", query("SELECT count(*) FROM storage.objects WHERE owner IS NOT NULL OR owner_id IS NOT NULL"))
        logrotate = Path("/etc/logrotate.d/nginx")
        if logrotate.is_file():
            print("LOG_ROTATION", ' '.join(line.strip() for line in logrotate.read_text().splitlines() if any(key in line for key in ("daily", "weekly", "monthly", "rotate", "maxage"))))
        print("READ_ONLY_INSPECTION_OK")
