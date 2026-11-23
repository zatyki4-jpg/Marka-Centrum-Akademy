#!/usr/bin/env python3
"""Plan, test or carry out erasure after a verified Academy account request."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import uuid

HERE = Path(__file__).resolve().parent
PRIVATE = Path('/srv/marka-course-academy/private')
SQL = (HERE / 'erase.sql').read_text()
PSQL = ['docker', 'exec', '-i', 'mca-sb-db', 'psql', '-XAtq', '-v', 'ON_ERROR_STOP=1',
        '-U', 'postgres', '-d', 'postgres']

def run(sql, target, purchases=None):
    variables = ['-v', 'target_id=' + str(target), '-v', 'purchases=' + json.dumps(purchases or [])]
    return subprocess.check_output(PSQL + variables, input=sql, text=True).strip()

START = "BEGIN; SET LOCAL lock_timeout='10s'; SET LOCAL statement_timeout='30s';\n" \
        "SELECT set_config('mca.deletion_user', :'target_id', true);\n" \
        "SELECT set_config('mca.deletion_purchases', :'purchases', true);\n"
LOCK = "LOCK TABLE public.promo_redemptions, public.promo_feedback, public.mca_checkout_orders IN SHARE ROW EXCLUSIVE MODE;\n"

def test():
    target = uuid.uuid4()
    fixture = """
INSERT INTO auth.users(id, email, raw_user_meta_data, raw_app_meta_data, created_at, updated_at)
VALUES (current_setting('mca.deletion_user')::uuid,
        'privacy-qa-' || current_setting('mca.deletion_user') || '@example.invalid',
        '{"full_name":"Privacy QA"}', '{"provider":"email","providers":["email"]}', now(), now());
INSERT INTO public.enrollments(user_id, course_id, status)
SELECT current_setting('mca.deletion_user')::uuid, id, 'active' FROM public.courses ORDER BY id LIMIT 1;
INSERT INTO public.lesson_progress(user_id, lesson_id)
SELECT current_setting('mca.deletion_user')::uuid, id FROM public.lessons ORDER BY id LIMIT 1;
INSERT INTO public.certificates(number, user_id, course_id, full_name, course_title, score)
SELECT 'PRIVACY-QA-' || current_setting('mca.deletion_user'), current_setting('mca.deletion_user')::uuid,
       id, 'Privacy QA', title, 100 FROM public.courses ORDER BY id LIMIT 1;
INSERT INTO public.promo_redemptions(campaign_id, user_id)
SELECT id, current_setting('mca.deletion_user')::uuid FROM public.promo_campaigns ORDER BY id LIMIT 1;
INSERT INTO public.promo_feedback(redemption_id, user_id, rating, comment)
SELECT id, user_id, 5, 'Private transaction test' FROM public.promo_redemptions
WHERE user_id=current_setting('mca.deletion_user')::uuid;
DO $check$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.certificates WHERE user_id=current_setting('mca.deletion_user')::uuid)
     OR NOT EXISTS (SELECT 1 FROM public.promo_feedback WHERE user_id=current_setting('mca.deletion_user')::uuid) THEN
    RAISE EXCEPTION 'Fixture could not exercise certificates and promotional feedback';
  END IF;
END $check$;
"""
    run(START + fixture + LOCK + SQL + "ROLLBACK;", target)
    remaining = run("SELECT count(*) FROM auth.users WHERE id=:'target_id'::uuid", target)
    if remaining != '0':
        raise RuntimeError('Test fixture remained')
    print('ACCOUNT_ERASURE_TRANSACTION_TEST_OK')

def plan(target):
    result = run("""
SELECT jsonb_build_object(
 'id', u.id, 'email', u.email, 'full_name', p.full_name,
 'administrator', EXISTS(SELECT 1 FROM public.user_roles r WHERE r.user_id=u.id AND r.role='admin'),
 'purchases', COALESCE((SELECT jsonb_agg(to_jsonb(o) ORDER BY o.id) FROM public.mca_checkout_orders o WHERE o.user_id=u.id), '[]'::jsonb),
 'certificates', (SELECT count(*) FROM public.certificates c WHERE c.user_id=u.id),
 'enrolments', (SELECT count(*) FROM public.enrollments e WHERE e.user_id=u.id),
 'feedback', (SELECT count(*) FROM public.promo_feedback f WHERE f.user_id=u.id))
FROM auth.users u LEFT JOIN public.profiles p ON p.id=u.id WHERE u.id=:'target_id'::uuid;
""", target)
    return json.loads(result) if result else None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['test', 'plan', 'erase'])
    parser.add_argument('user_id', nargs='?', type=uuid.UUID)
    parser.add_argument('--confirm-user-id', type=uuid.UUID)
    args = parser.parse_args()
    if args.mode == 'test':
        test()
        return
    if args.user_id is None:
        parser.error('Supply the exact user UUID after verifying the request')
    record = plan(args.user_id)
    if record is None:
        print('Account already absent.')
        return
    if args.mode == 'plan':
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return
    if args.confirm_user_id != args.user_id:
        parser.error('Confirm the reviewed account UUID with --confirm-user-id')
    if record['administrator']:
        raise ValueError('Review administrator ownership before deletion')
    if any(item['status'] in ('pending','processing') for item in record['purchases']):
        raise ValueError('Resolve outstanding Stripe checkout sessions before erasure')
    # Retain completed purchase evidence separately from the active student account.
    paid = [item for item in record['purchases'] if item['status']=='paid']
    if paid:
        os.umask(0o077)
        archive = PRIVATE / 'deleted-account-purchase-records'
        archive.mkdir(mode=0o700, exist_ok=True)
        output = archive / (str(args.user_id) + '.json')
        output.write_text(json.dumps({key: record[key] for key in ('id','email','full_name')} | {'purchases': paid}, ensure_ascii=False))
        output.chmod(0o600)
    run(START + LOCK + SQL + 'COMMIT;', args.user_id, record['purchases'])
    print('Account and associated active database records erased.')
    print('Complete the provider, mailbox, backup and session-expiry checks in README.md before closing the request.')

if __name__ == '__main__':
    main()
