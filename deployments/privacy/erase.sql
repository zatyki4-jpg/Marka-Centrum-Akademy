-- Called inside a transaction after a verified request and retention review.
DO $erase$
DECLARE
  target uuid := current_setting('mca.deletion_user')::uuid;
  target_email text;
BEGIN
  SELECT email INTO target_email FROM auth.users WHERE id = target FOR UPDATE;
  IF NOT FOUND THEN RETURN; END IF;
  IF EXISTS (SELECT 1 FROM public.user_roles WHERE user_id = target AND role = 'admin') THEN
    RAISE EXCEPTION 'Administrator accounts require an ownership transfer review';
  END IF;
  IF EXISTS (SELECT 1 FROM storage.objects WHERE owner = target OR owner_id = target::text) THEN
    RAISE EXCEPTION 'Remove user-owned storage objects through the storage service first';
  END IF;
  IF EXISTS (SELECT 1 FROM public.mca_checkout_orders
             WHERE user_id = target AND status IN ('pending', 'processing')) THEN
    RAISE EXCEPTION 'Resolve outstanding Stripe checkout sessions before erasure';
  END IF;
  IF COALESCE((SELECT jsonb_agg(to_jsonb(o) ORDER BY o.id) FROM public.mca_checkout_orders o WHERE o.user_id=target), '[]'::jsonb)
     IS DISTINCT FROM current_setting('mca.deletion_purchases')::jsonb THEN
    RAISE EXCEPTION 'Purchase records changed, review the request again';
  END IF;
  DELETE FROM public.promo_feedback
    WHERE user_id = target OR redemption_id IN
      (SELECT id FROM public.promo_redemptions WHERE user_id = target);
  DELETE FROM public.promo_redemptions WHERE user_id = target;
  DELETE FROM auth.audit_log_entries
    WHERE payload->>'actor_id' = target::text OR lower(payload->>'actor_username') = lower(target_email);
  DELETE FROM auth.scim_users WHERE user_id = target;
  DELETE FROM auth.users WHERE id = target;
  IF EXISTS (SELECT 1 FROM public.profiles WHERE id = target)
     OR EXISTS (SELECT 1 FROM public.enrollments WHERE user_id = target)
     OR EXISTS (SELECT 1 FROM public.lesson_progress WHERE user_id = target)
     OR EXISTS (SELECT 1 FROM public.quiz_attempts WHERE user_id = target)
     OR EXISTS (SELECT 1 FROM public.final_exam_attempts WHERE user_id = target)
     OR EXISTS (SELECT 1 FROM public.certificates WHERE user_id = target)
     OR EXISTS (SELECT 1 FROM public.promo_redemptions WHERE user_id = target)
     OR EXISTS (SELECT 1 FROM public.promo_feedback WHERE user_id = target)
     OR EXISTS (SELECT 1 FROM auth.sessions WHERE user_id = target)
     OR EXISTS (SELECT 1 FROM auth.identities WHERE user_id = target) THEN
    RAISE EXCEPTION 'Associated account data remains, rolling back';
  END IF;
END
$erase$;
