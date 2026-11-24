#!/usr/bin/env python3
"""Read-only status of the explicitly designated MCA Play test account."""
import importlib.util
import os
from pathlib import Path
import uuid
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("play",HERE.parent/"google-play/setup.py")
play=importlib.util.module_from_spec(spec)
spec.loader.exec_module(play)
if os.geteuid()!=0:
    raise RuntimeError("Existing Academy server root session required")
uid=play.psql("SELECT id FROM auth.users WHERE lower(email)=:'email' AND raw_user_meta_data->>'mca_play_account'='test';",email="play-test@markacentrumacademy.eu")
uid=str(uuid.UUID(uid))
print("TEST_ORDERS")
print(play.psql("""SELECT coalesce(jsonb_agg(jsonb_build_object(
'product',product_id,'status',status,'test',is_test,'ack',acknowledged,'paid_at',paid_at)
ORDER BY created_at),'[]'::jsonb)
FROM public.mca_play_orders WHERE user_id=:'uid'::uuid;""",uid=uid))
print("TEST_ENROLLMENTS")
print(play.psql("""SELECT coalesce(jsonb_agg(jsonb_build_object(
'course',course_id,'status',status,'expiry',expiry_date,'promo',promo_access)
ORDER BY course_id),'[]'::jsonb)
FROM public.enrollments WHERE user_id=:'uid'::uuid;""",uid=uid))
for course,sku in zip(play.COURSES,play.SKUS):
    print("ACCESS",sku,play.psql("SELECT public.mca_play_access(:'uid'::uuid,:'course'::uuid);",uid=uid,course=course))
