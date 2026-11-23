import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { PGlite } from '@electric-sql/pglite';
import { validatePurchase, PLAY_COURSES } from '../src/lib/mca-play-domain.ts';
import { verifyAndApply, playCheckout, accountId } from '../src/lib/mca-play.server.ts';

const course = Object.keys(PLAY_COURSES)[0], sku = PLAY_COURSES[course];
const user = '00000000-0000-4000-8000-000000000001';
const other = '00000000-0000-4000-8000-000000000002';
const account = 'a'.repeat(64);
const purchase = (state = 'PURCHASED') => ({
  productLineItem: [{ productId: sku, productOfferDetails: { quantity: 1, refundableQuantity: 1,
    purchaseOptionId: 'lifetime', consumptionState: 'CONSUMPTION_STATE_YET_TO_BE_CONSUMED' } }],
  obfuscatedExternalAccountId: account, purchaseStateContext: { purchaseState: state },
  acknowledgementState: 'ACKNOWLEDGEMENT_STATE_PENDING', orderId: 'GPA.1234-5678-9012-34567',
  ...(state === 'PURCHASED' ? { purchaseCompletionTime: new Date().toISOString() } : {}),
});

test('requires Google-confirmed account, product, quantity, state and completion time', () => {
  assert.equal(validatePurchase(purchase(), sku, account).state, 'purchased');
  assert.equal(validatePurchase(purchase('PENDING'), sku, account).state, 'pending');
  assert.equal(validatePurchase(purchase('CANCELLED'), sku, account).state, 'cancelled');
  const cases = [
    p => delete p.obfuscatedExternalAccountId,
    p => { p.obfuscatedExternalAccountId = 'b'.repeat(64); },
    p => { p.productLineItem[0].productId = 'other'; },
    p => { p.productLineItem[0].productOfferDetails.quantity = 2; },
    p => { p.productLineItem[0].productOfferDetails.rentOfferDetails = {}; },
    p => { p.purchaseStateContext.purchaseState = 'UNKNOWN'; },
    p => { p.purchaseCompletionTime = 'invalid'; },
    p => { p.productLineItem[0].productOfferDetails.consumptionState = 'CONSUMPTION_STATE_CONSUMED'; },
  ];
  for (const change of cases) { const p = purchase(); change(p); assert.throws(() => validatePurchase(p, sku, account)); }
  const refunded = purchase(); refunded.productLineItem[0].productOfferDetails.refundableQuantity = 0;
  assert.equal(validatePurchase(refunded, sku, account).state, 'cancelled');
});

async function database() {
  const db = new PGlite();
  await db.exec(`CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;
    CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY);
    CREATE TABLE public.courses(id uuid PRIMARY KEY,is_published boolean NOT NULL DEFAULT true);
    CREATE TABLE public.enrollments(user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
      course_id uuid REFERENCES courses(id),status text,activation_date timestamptz,expiry_date timestamptz,
      promo_access boolean NOT NULL DEFAULT false,PRIMARY KEY(user_id,course_id));
    CREATE TABLE public.mca_checkout_orders(user_id uuid,course_id uuid,status text);
    CREATE TABLE public.promo_campaigns(id uuid PRIMARY KEY,code text);
    CREATE TABLE public.promo_redemptions(user_id uuid,campaign_id uuid REFERENCES promo_campaigns(id));
    INSERT INTO auth.users VALUES('${user}'),('${other}'); INSERT INTO courses VALUES('${course}',true);`);
  await db.exec(await readFile(new URL('../supabase/migrations/20261123090000_mca_google_play.sql', import.meta.url), 'utf8'));
  return db;
}

function rpcFor(db) {
  return async (name, params) => {
    assert.match(name, /^mca_play_[a-z_]+$/);
    const values = Object.values(params);
    const row = await db.query(`SELECT public.${name}(${Object.keys(params).map((key, index) => `${key} => $${index + 1}`).join(',')}) AS result`, values);
    return row.rows[0].result;
  };
}

test('atomic grant, replay defense, acknowledgement retry, refunds and deletion', async () => {
  const db = await database();
  const rpc = rpcFor(db);
  let state = 'PENDING', calls = [], failAck = false;
  const token = 'google-purchase-token-a';
  const hash = createHash('sha256').update(token).digest('hex');
  const google = async (path, method = 'GET') => {
    calls.push(method);
    if (method === 'POST') {
      const access = await rpc('mca_play_access', { p_user_id: user, p_course_id: course });
      assert.equal(access.active, true, 'grant must commit before ack');
      if (failAck) throw Error('temporary');
      return null;
    }
    return purchase(state);
  };
  try {
    let result = await verifyAndApply(user, course, token, account, { rpc, google });
    assert.equal(result.status, 'pending');
    assert.equal((await rpc('mca_play_access', { p_user_id: user, p_course_id: course })).active, false);
    assert.deepEqual(calls, ['GET']);
    await assert.rejects(db.query('DELETE FROM auth.users WHERE id=$1', [user]), /Resolve pending/);
    state = 'PURCHASED'; failAck = true;
    result = await verifyAndApply(user, course, token, account, { rpc, google });
    assert.equal(result.status, 'purchased');
    assert.equal((await db.query('SELECT acknowledged FROM mca_play_orders')).rows[0].acknowledged, false);
    failAck = false;
    await verifyAndApply(user, course, token, account, { rpc, google });
    assert.equal((await db.query('SELECT acknowledged FROM mca_play_orders')).rows[0].acknowledged, true);
    assert.equal((await db.query('SELECT count(*)::int AS n FROM enrollments')).rows[0].n, 1);
    await assert.rejects(verifyAndApply(other, course, token, account, { rpc, google }), /play_purchase_conflict/);
    state = 'CANCELLED';
    await verifyAndApply(user, course, token, account, { rpc, google });
    assert.equal((await rpc('mca_play_access', { p_user_id: user, p_course_id: course })).active, false);
    state = 'PURCHASED';
    assert.equal((await verifyAndApply(user, course, token, account, { rpc, google })).status, 'cancelled', 'stale paid event cannot reopen refund');
    await db.query('DELETE FROM auth.users WHERE id=$1', [user]);
    const retained = (await db.query('SELECT user_id,deleted_at FROM mca_play_orders WHERE token_hash=$1', [hash])).rows[0];
    assert.equal(retained.user_id, null); assert.ok(retained.deleted_at);
    assert.equal((await db.query('SELECT count(*)::int AS n FROM mca_play_grants')).rows[0].n, 0);
  } finally { await db.close(); }
});

test('refund keeps existing lifetime, promotional and later Stripe access', async () => {
  for (const mode of ['lifetime', 'promo', 'stripe', 'finite']) {
    const db = await database(); const rpc = rpcFor(db); let state = 'PURCHASED';
    try {
      if (mode !== 'stripe') await db.query(`INSERT INTO enrollments VALUES($1,$2,'active',now()-interval '1 day',
        ${mode === 'finite' ? "now()+interval '30 days'" : 'NULL'},$3)`, [user, course, mode === 'promo']);
      const previous = (await db.query('SELECT expiry_date FROM enrollments')).rows[0]?.expiry_date;
      const google = async (_, method) => method === 'POST' ? null : purchase(state);
      await verifyAndApply(user, course, 'google-purchase-token-b', account, { rpc, google });
      if (mode === 'stripe') await db.query("INSERT INTO mca_checkout_orders VALUES($1,$2,'paid')", [user,course]);
      state = 'CANCELLED';
      await verifyAndApply(user, course, 'google-purchase-token-b', account, { rpc, google });
      assert.equal((await rpc('mca_play_access', { p_user_id: user, p_course_id: course })).active, true, mode);
      if (mode === 'finite') assert.deepEqual((await db.query('SELECT expiry_date FROM enrollments')).rows[0].expiry_date, previous);
    } finally { await db.close(); }
  }
});

test('anonymous callers cannot access private transactions or RPCs; rate limit is per user', async () => {
  const db = await database(); const rpc = rpcFor(db);
  try {
    for (let i = 0; i < 30; i++) assert.equal(await rpc('mca_play_rate_limit', { p_user_id: user }), true);
    assert.equal(await rpc('mca_play_rate_limit', { p_user_id: user }), false);
    assert.equal(await rpc('mca_play_rate_limit', { p_user_id: other }), true);
    await db.exec('SET ROLE authenticated');
    await assert.rejects(db.query('SELECT * FROM public.mca_play_orders'), /permission denied/);
    await assert.rejects(rpc('mca_play_access', { p_user_id: user, p_course_id: course }), /permission denied/);
  } finally { await db.close(); }
});

test('HTTP endpoint rejects unauthenticated calls and cross-origin requests without exposing details', async () => {
  let response = await playCheckout(new Request('https://markacentrumacademy.eu/api/academy/google-play', { method: 'POST' }));
  assert.equal(response.status, 401); assert.equal(response.headers.get('cache-control'), 'no-store');
  response = await playCheckout(new Request('https://markacentrumacademy.eu/api/academy/google-play', { method: 'POST', headers: { origin: 'https://attacker.invalid' } }));
  assert.equal(response.status, 403);
  process.env.MCA_PLAY_ACCOUNT_SECRET = 'b'.repeat(64);
  assert.equal(accountId(user).length, 64); assert.notEqual(accountId(user), accountId(other));
  delete process.env.MCA_PLAY_ACCOUNT_SECRET;
});
