BEGIN;

CREATE TABLE public.mca_play_orders (
  token_hash text PRIMARY KEY CHECK (token_hash ~ '^[a-f0-9]{64}$'),
  purchase_token text NOT NULL CHECK (length(purchase_token) BETWEEN 10 AND 4096),
  user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  course_id uuid NOT NULL REFERENCES public.courses(id),
  product_id text NOT NULL,
  account_id text NOT NULL CHECK (account_id ~ '^[a-f0-9]{64}$'),
  order_id text UNIQUE,
  status text NOT NULL CHECK (status IN ('pending','purchased','cancelled')),
  is_test boolean NOT NULL,
  acknowledged boolean NOT NULL DEFAULT false,
  paid_at timestamptz,
  verified_at timestamptz NOT NULL,
  last_checked_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
CREATE INDEX mca_play_reconcile_idx ON public.mca_play_orders(last_checked_at) WHERE status <> 'cancelled';
CREATE INDEX mca_play_user_course_idx ON public.mca_play_orders(user_id,course_id,status);

-- Preserve access bought elsewhere when a Google purchase is refunded.
CREATE TABLE public.mca_play_grants (
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  course_id uuid NOT NULL REFERENCES public.courses(id),
  baseline jsonb,
  granted_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(user_id,course_id)
);
CREATE TABLE public.mca_play_limits (
  user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  window_start timestamptz NOT NULL DEFAULT now(),
  attempts integer NOT NULL DEFAULT 1
);
ALTER TABLE public.mca_play_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mca_play_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mca_play_limits ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.mca_play_orders,public.mca_play_grants,public.mca_play_limits FROM PUBLIC,anon,authenticated,service_role;

CREATE FUNCTION public.mca_play_access(p_user_id uuid,p_course_id uuid) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path='' AS $$
  SELECT jsonb_build_object('active',
    EXISTS (SELECT 1 FROM public.enrollments WHERE user_id=p_user_id AND course_id=p_course_id
      AND (promo_access OR (status='active' AND (expiry_date IS NULL OR expiry_date>now()))))
    OR EXISTS (SELECT 1 FROM public.promo_redemptions r JOIN public.promo_campaigns c ON c.id=r.campaign_id
      WHERE r.user_id=p_user_id AND c.code='ROOFINGBETA10'));
$$;

CREATE FUNCTION public.mca_play_rate_limit(p_user_id uuid) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE n integer;
BEGIN
  INSERT INTO public.mca_play_limits AS l(user_id) VALUES(p_user_id)
  ON CONFLICT(user_id) DO UPDATE SET
    attempts=CASE WHEN l.window_start<now()-interval '1 minute' THEN 1 ELSE l.attempts+1 END,
    window_start=CASE WHEN l.window_start<now()-interval '1 minute' THEN now() ELSE l.window_start END
  RETURNING attempts INTO n;
  RETURN n<=30;
END $$;

CREATE FUNCTION public.mca_play_apply(
  p_token_hash text,p_token text,p_user_id uuid,p_course_id uuid,p_product_id text,p_account_id text,
  p_state text,p_order_id text,p_paid_at timestamptz,p_test boolean,p_acknowledged boolean,p_verified_at timestamptz
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
  sale public.mca_play_orders;
  enrollment public.enrollments;
  grant_row public.mca_play_grants;
  expected_product text;
  protected_access boolean;
BEGIN
  expected_product:=CASE p_course_id
    WHEN '11111111-1111-4111-8111-111111111111' THEN 'mca_bitumen_basic_lifetime'
    WHEN 'f166433e-5157-4341-9a38-800c62795ebd' THEN 'mca_bitumen_renovation_lifetime' END;
  IF expected_product IS NULL OR p_product_id IS DISTINCT FROM expected_product
    OR p_token_hash IS NULL OR p_token_hash !~ '^[a-f0-9]{64}$'
    OR p_account_id IS NULL OR p_account_id !~ '^[a-f0-9]{64}$'
    OR p_state IS NULL OR p_state NOT IN ('pending','purchased','cancelled')
    OR p_test IS NULL OR p_acknowledged IS NULL OR p_verified_at IS NULL
    OR p_verified_at>now()+interval '5 minutes' OR (p_state='purchased' AND p_paid_at IS NULL) THEN
    RAISE EXCEPTION 'invalid_play_purchase';
  END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended(p_token_hash,12));
  SELECT * INTO sale FROM public.mca_play_orders WHERE token_hash=p_token_hash FOR UPDATE;
  IF FOUND THEN
    IF sale.user_id IS DISTINCT FROM p_user_id OR sale.course_id IS DISTINCT FROM p_course_id
      OR sale.product_id IS DISTINCT FROM p_product_id OR sale.account_id IS DISTINCT FROM p_account_id
      OR sale.purchase_token IS DISTINCT FROM p_token OR sale.is_test IS DISTINCT FROM p_test
      OR (sale.order_id IS NOT NULL AND p_order_id IS DISTINCT FROM sale.order_id) THEN
      RAISE EXCEPTION 'play_purchase_conflict';
    END IF;
    IF sale.status='cancelled' OR sale.verified_at>p_verified_at
       OR (sale.status='purchased' AND p_state='pending') THEN
      UPDATE public.mca_play_orders SET last_checked_at=now() WHERE token_hash=p_token_hash;
      RETURN jsonb_build_object('status',sale.status);
    END IF;
  ELSE
    IF p_user_id IS NULL THEN RAISE EXCEPTION 'play_user_required'; END IF;
    IF NOT EXISTS(SELECT 1 FROM public.courses WHERE id=p_course_id AND is_published) THEN
      RAISE EXCEPTION 'play_course_unavailable';
    END IF;
    INSERT INTO public.mca_play_orders(token_hash,purchase_token,user_id,course_id,product_id,account_id,
      order_id,status,is_test,acknowledged,paid_at,verified_at)
    VALUES(p_token_hash,p_token,p_user_id,p_course_id,p_product_id,p_account_id,
      p_order_id,p_state,p_test,p_acknowledged,p_paid_at,p_verified_at);
  END IF;
  UPDATE public.mca_play_orders SET status=p_state,order_id=coalesce(order_id,p_order_id),
    acknowledged=acknowledged OR p_acknowledged,paid_at=coalesce(paid_at,p_paid_at),
    verified_at=p_verified_at,last_checked_at=now(),updated_at=now()
  WHERE token_hash=p_token_hash;

  IF p_user_id IS NULL THEN RETURN jsonb_build_object('status',p_state); END IF;
  -- Same lock as Stripe fulfillment serializes cross-provider grants.
  PERFORM pg_advisory_xact_lock(hashtextextended(p_user_id::text||p_course_id::text,0));
  SELECT * INTO enrollment FROM public.enrollments WHERE user_id=p_user_id AND course_id=p_course_id FOR UPDATE;
  SELECT * INTO grant_row FROM public.mca_play_grants WHERE user_id=p_user_id AND course_id=p_course_id FOR UPDATE;
  protected_access:=coalesce(enrollment.promo_access,false)
    OR EXISTS(SELECT 1 FROM public.mca_checkout_orders WHERE user_id=p_user_id AND course_id=p_course_id AND status='paid')
    OR EXISTS(SELECT 1 FROM public.promo_redemptions r JOIN public.promo_campaigns c ON c.id=r.campaign_id
      WHERE r.user_id=p_user_id AND c.code='ROOFINGBETA10');

  IF p_state='purchased' THEN
    IF grant_row.user_id IS NULL AND NOT protected_access
       AND NOT coalesce(enrollment.status='active' AND enrollment.expiry_date IS NULL,false) THEN
      INSERT INTO public.mca_play_grants(user_id,course_id,baseline,granted_at)
      VALUES(p_user_id,p_course_id,CASE WHEN enrollment.user_id IS NULL THEN NULL ELSE
        jsonb_build_object('status',enrollment.status,'activation_date',enrollment.activation_date,
                           'expiry_date',enrollment.expiry_date,'promo_access',enrollment.promo_access) END,p_paid_at);
    END IF;
    INSERT INTO public.enrollments AS e(user_id,course_id,status,activation_date,expiry_date,promo_access)
    VALUES(p_user_id,p_course_id,'active',p_paid_at,NULL,false)
    ON CONFLICT(user_id,course_id) DO UPDATE SET status='active',expiry_date=NULL,
      activation_date=coalesce(e.activation_date,EXCLUDED.activation_date);
  ELSIF p_state='cancelled' AND grant_row.user_id IS NOT NULL AND NOT EXISTS(
      SELECT 1 FROM public.mca_play_orders WHERE user_id=p_user_id AND course_id=p_course_id AND status='purchased') THEN
    IF NOT protected_access AND enrollment.status='active' AND enrollment.expiry_date IS NULL
       AND enrollment.activation_date IS NOT DISTINCT FROM coalesce(
         (grant_row.baseline->>'activation_date')::timestamptz,grant_row.granted_at) THEN
      UPDATE public.enrollments SET
        status=coalesce(grant_row.baseline->>'status','active'),
        activation_date=coalesce((grant_row.baseline->>'activation_date')::timestamptz,activation_date),
        expiry_date=CASE WHEN grant_row.baseline IS NULL THEN now() ELSE (grant_row.baseline->>'expiry_date')::timestamptz END,
        promo_access=coalesce((grant_row.baseline->>'promo_access')::boolean,false)
      WHERE user_id=p_user_id AND course_id=p_course_id;
    END IF;
    DELETE FROM public.mca_play_grants WHERE user_id=p_user_id AND course_id=p_course_id;
  END IF;
  RETURN jsonb_build_object('status',p_state);
END $$;

CREATE FUNCTION public.mca_play_acknowledged(p_token_hash text) RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path='' AS $$
  UPDATE public.mca_play_orders SET acknowledged=true,updated_at=now() WHERE token_hash=p_token_hash AND status='purchased';
$$;

CREATE FUNCTION public.mca_play_reconcile_batch() RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path='' AS $$
  SELECT coalesce(jsonb_agg(to_jsonb(x)),'[]'::jsonb) FROM (
    SELECT token_hash,purchase_token,user_id,course_id,account_id FROM public.mca_play_orders
    WHERE status<>'cancelled' AND last_checked_at<now()-CASE WHEN acknowledged THEN interval '1 hour' ELSE interval '30 seconds' END
    ORDER BY last_checked_at LIMIT 100
  ) x;
$$;
CREATE FUNCTION public.mca_play_retry_later(p_token_hash text) RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path='' AS $$
  UPDATE public.mca_play_orders SET last_checked_at=now() WHERE token_hash=p_token_hash;
$$;

CREATE FUNCTION public.mca_play_before_account_erasure() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
  IF EXISTS(SELECT 1 FROM public.mca_play_orders WHERE user_id=OLD.id
    AND (status='pending' OR (status='purchased' AND NOT acknowledged))) THEN
    RAISE EXCEPTION 'Resolve pending Google Play transactions before account erasure';
  END IF;
  UPDATE public.mca_play_orders SET deleted_at=now(),updated_at=now() WHERE user_id=OLD.id;
  RETURN OLD;
END $$;
CREATE TRIGGER mca_play_erasure_guard BEFORE DELETE ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.mca_play_before_account_erasure();

REVOKE ALL ON FUNCTION public.mca_play_access(uuid,uuid),public.mca_play_rate_limit(uuid),
  public.mca_play_apply(text,text,uuid,uuid,text,text,text,text,timestamptz,boolean,boolean,timestamptz),
  public.mca_play_acknowledged(text),public.mca_play_reconcile_batch(),public.mca_play_retry_later(text),
  public.mca_play_before_account_erasure() FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION public.mca_play_access(uuid,uuid),public.mca_play_rate_limit(uuid),
  public.mca_play_apply(text,text,uuid,uuid,text,text,text,text,timestamptz,boolean,boolean,timestamptz),
  public.mca_play_acknowledged(text),public.mca_play_reconcile_batch(),public.mca_play_retry_later(text)
  TO service_role;
NOTIFY pgrst,'reload schema';
COMMIT;
