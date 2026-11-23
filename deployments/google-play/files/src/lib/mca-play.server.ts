import { createHash, createHmac, createSign } from 'node:crypto';
import { mcaRpc } from './mca-rpc.server.ts';
import { PLAY_PACKAGE, PLAY_COURSES, PlayError, validatePurchase } from './mca-play-domain.ts';

const API = `https://androidpublisher.googleapis.com/androidpublisher/v3/applications/${PLAY_PACKAGE}`;
const TOKEN_URL = 'https://oauth2.googleapis.com/token';
const HEADERS = { 'Cache-Control': 'no-store', 'Content-Type': 'application/json', 'X-Content-Type-Options': 'nosniff' };
let tokenCache: { value: string; expires: number } | undefined;
let tokenFlight: Promise<string> | undefined;

export function accountId(userId: string): string {
  const key = process.env['MCA_PLAY_ACCOUNT_SECRET'];
  if (!key || !/^[a-f0-9]{64}$/.test(key)) throw new PlayError('billing_unavailable', 503);
  return createHmac('sha256', key).update(`${PLAY_PACKAGE}:${userId}`).digest('hex');
}

function configured(): boolean {
  return process.env['MCA_PLAY_ENABLED'] === 'true' &&
    !!process.env['GOOGLE_PLAY_SERVICE_ACCOUNT_B64'] && /^[a-f0-9]{64}$/.test(process.env['MCA_PLAY_ACCOUNT_SECRET'] || '');
}

async function issueToken(): Promise<string> {
  let sa;
  try { sa = JSON.parse(Buffer.from(process.env['GOOGLE_PLAY_SERVICE_ACCOUNT_B64'] || '', 'base64').toString('utf8')); }
  catch { throw new PlayError('billing_unavailable', 503); }
  if (sa.type !== 'service_account' || !/^[^\s@]+@[^\s@]+\.iam\.gserviceaccount\.com$/.test(sa.client_email) ||
      typeof sa.private_key !== 'string' || (sa.token_uri && sa.token_uri !== TOKEN_URL)) {
    throw new PlayError('billing_unavailable', 503);
  }
  const now = Math.floor(Date.now() / 1000);
  const enc = (v: unknown) => Buffer.from(JSON.stringify(v)).toString('base64url');
  const unsigned = `${enc({ alg: 'RS256', typ: 'JWT' })}.${enc({ iss: sa.client_email,
    scope: 'https://www.googleapis.com/auth/androidpublisher', aud: TOKEN_URL, iat: now, exp: now + 3600 })}`;
  const signature = createSign('RSA-SHA256').update(unsigned).sign(sa.private_key).toString('base64url');
  const r = await fetch(TOKEN_URL, { method: 'POST', redirect: 'error', signal: AbortSignal.timeout(15000),
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer', assertion: `${unsigned}.${signature}` }) });
  if (!r.ok) throw new PlayError('billing_unavailable', 503);
  const p = await r.json();
  if (typeof p.access_token !== 'string' || !Number.isFinite(p.expires_in) || p.expires_in < 60) {
    throw new PlayError('billing_unavailable', 503);
  }
  tokenCache = { value: p.access_token, expires: Date.now() + Math.min(p.expires_in - 60, 3540) * 1000 };
  return p.access_token;
}

async function accessToken(): Promise<string> {
  if (tokenCache && tokenCache.expires > Date.now()) return tokenCache.value;
  if (!tokenFlight) tokenFlight = issueToken().finally(() => { tokenFlight = undefined; });
  return tokenFlight;
}

export async function publisher(path: string, method = 'GET'): Promise<any> {
  for (let attempt = 0; attempt < 2; attempt++) {
    const r = await fetch(API + path, { method, headers: { Authorization: `Bearer ${await accessToken()}`,
      ...(method === 'POST' ? { 'Content-Type': 'application/json' } : {}) },
      ...(method === 'POST' ? { body: '{}' } : {}), redirect: 'error', signal: AbortSignal.timeout(15000) });
    if (r.status === 401 && attempt === 0) { tokenCache = undefined; continue; }
    if (!r.ok) throw new PlayError(r.status === 404 || r.status === 400 ? 'purchase_not_found' : 'billing_unavailable',
      r.status === 404 || r.status === 400 ? 409 : 503);
    const text = await r.text();
    return text ? JSON.parse(text) : null;
  }
  throw new PlayError('billing_unavailable', 503);
}

type Rpc = <T>(name: string, params: Record<string, unknown>) => Promise<T>;
type PurchaseDependencies = { rpc: Rpc; google: typeof publisher };

export async function verifyAndApply(userId: string | null, courseId: string, purchaseToken: string,
  expectedAccount: string, deps: PurchaseDependencies = { rpc: mcaRpc, google: publisher }) {
  const sku = Object.hasOwn(PLAY_COURSES, courseId) ? PLAY_COURSES[courseId] : undefined;
  if (!sku || typeof purchaseToken !== 'string' || purchaseToken.length < 10 || purchaseToken.length > 4096 ||
      /[\s\x00-\x1f]/.test(purchaseToken)) throw new PlayError('invalid_request');
  const verifiedAt = new Date().toISOString();
  const tokenHash = createHash('sha256').update(purchaseToken).digest('hex');
  const raw = await deps.google(`/purchases/productsv2/tokens/${encodeURIComponent(purchaseToken)}`);
  const p = validatePurchase(raw, sku, expectedAccount);
  const result = await deps.rpc<{ status: 'pending' | 'purchased' | 'cancelled' }>('mca_play_apply', {
    p_token_hash: tokenHash, p_token: purchaseToken, p_user_id: userId, p_course_id: courseId,
    p_product_id: sku, p_account_id: expectedAccount, p_state: p.state, p_order_id: p.orderId,
    p_paid_at: p.paidAt, p_test: p.test, p_acknowledged: p.acknowledged, p_verified_at: verifiedAt,
  });
  // Grant is committed before acknowledgement. Failed acknowledgements stay in the retry queue.
  if (result.status === 'purchased' && p.state === 'purchased' && !p.acknowledged) {
    try {
      await deps.google(`/purchases/products/${encodeURIComponent(sku)}/tokens/${encodeURIComponent(purchaseToken)}:acknowledge`, 'POST');
      await deps.rpc('mca_play_acknowledged', { p_token_hash: tokenHash });
    } catch { /* Background reconciliation retries without logging purchase tokens. */ }
  }
  return result;
}

async function authenticatedUser(request: Request): Promise<string> {
  const bearer = request.headers.get('authorization');
  if (!bearer || !/^Bearer [^\s]{20,8192}$/.test(bearer)) throw new PlayError('authentication_required', 401);
  const url = process.env['SUPABASE_URL']; const key = process.env['SUPABASE_PUBLISHABLE_KEY'];
  if (!url || !key) throw new PlayError('billing_unavailable', 503);
  const r = await fetch(url.replace(/\/+$/, '') + '/auth/v1/user', {
    headers: { apikey: key, Authorization: bearer }, redirect: 'error', signal: AbortSignal.timeout(10000) });
  if (r.status === 401 || r.status === 403) throw new PlayError('authentication_required', 401);
  if (!r.ok) throw new PlayError('billing_unavailable', 503);
  const user = await r.json();
  if (typeof user.id !== 'string' || !/^[a-f0-9-]{36}$/.test(user.id)) throw new PlayError('authentication_required', 401);
  return user.id;
}

async function requestBody(request: Request) {
  if (!request.body || !request.headers.get('content-type')?.startsWith('application/json') ||
      Number(request.headers.get('content-length')) > 6144) throw new PlayError('invalid_request');
  let size = 0;
  const limited = request.body.pipeThrough(new TransformStream<Uint8Array, Uint8Array>({ transform(chunk, c) {
    size += chunk.byteLength; if (size > 6144) throw new PlayError('invalid_request'); c.enqueue(chunk);
  } }));
  return new Response(limited).json().catch(() => { throw new PlayError('invalid_request'); });
}

export async function playCheckout(request: Request): Promise<Response> {
  const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: HEADERS });
  try {
    const origin = request.headers.get('origin');
    if (origin && !['https://markacentrumacademy.eu', 'https://www.markacentrumacademy.eu'].includes(origin)) {
      throw new PlayError('invalid_origin', 403);
    }
    const userId = await authenticatedUser(request);
    const b = await requestBody(request);
    if (!b || typeof b !== 'object' || Array.isArray(b) || !['config', 'verify'].includes(b.action) ||
        typeof b.courseId !== 'string' || !Object.hasOwn(PLAY_COURSES, b.courseId) ||
        Object.keys(b).some(k => !['action', 'courseId', 'purchaseToken'].includes(k)) ||
        (b.action === 'verify' && typeof b.purchaseToken !== 'string')) throw new PlayError('invalid_request');
    if (!configured()) throw new PlayError('billing_unavailable', 503);
    const account = accountId(userId);
    if (b.action === 'config') {
      const access = await mcaRpc<{ active: boolean }>('mca_play_access', { p_user_id: userId, p_course_id: b.courseId });
      if (access.active) return reply({ ok: true, status: 'already_enrolled' });
      await accessToken();
      return reply({ ok: true, status: 'ready', sku: PLAY_COURSES[b.courseId], accountId: account });
    }
    const rate = await mcaRpc<boolean>('mca_play_rate_limit', { p_user_id: userId });
    if (!rate) throw new PlayError('try_later', 429);
    const result = await verifyAndApply(userId, b.courseId, b.purchaseToken, account);
    return reply({ ok: true, status: result.status }, result.status === 'pending' ? 202 : 200);
  } catch (error) {
    const known = error instanceof PlayError ? error : new PlayError('billing_unavailable', 503);
    return reply({ ok: false, error: known.code }, known.status);
  }
}

export async function reconcilePlayPurchases() {
  if (!configured()) return { enabled: false, checked: 0, failed: 0 };
  const orders = await mcaRpc<Array<{ token_hash: string; purchase_token: string; user_id: string | null;
    course_id: string; account_id: string }>>('mca_play_reconcile_batch', {});
  let failed = 0;
  for (const order of orders) {
    try { await verifyAndApply(order.user_id, order.course_id, order.purchase_token, order.account_id); }
    catch { failed++; await mcaRpc('mca_play_retry_later', { p_token_hash: order.token_hash }); }
  }
  return { enabled: true, checked: orders.length, failed };
}
