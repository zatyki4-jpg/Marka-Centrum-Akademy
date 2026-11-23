# Academy Google Play integration

This overlay adds Google Play one-time course purchases to the deployed TanStack
Academy application. The repository root is an older application; do not deploy it.
The release copies the active Hetzner source, verifies the existing checkout hash,
preserves Stripe and Supabase runtime values, builds before switching, and restores
the previous application if health checks fail. Course content is not modified.

| Course | Course UUID | Play product | Option |
|---|---|---|---|
| Basic bitumen roofing | `11111111-1111-4111-8111-111111111111` | `mca_bitumen_basic_lifetime` | `lifetime` |
| Flat-roof renovation, level 2 | `f166433e-5157-4341-9a38-800c62795ebd` | `mca_bitumen_renovation_lifetime` | `lifetime` |

Package: `eu.markacentrumacademy.app`. Belgian consumer price: EUR 120 per course.
Each product is non-consumable and unlocks lifetime access. The client displays the
price returned by Google, including regional tax and currency differences.
Google Play Console products must be active and the purchase option backward compatible.

## Security and fulfillment

- The authenticated Supabase user is resolved on the server. The Google purchase
  must contain that user's HMAC-based obfuscated account ID, the exact SKU, one
  non-consumable item and the PURCHASED state. Pending purchases do not unlock access.
- Publisher API verification runs on the server using a dedicated service account.
- Transactional PostgreSQL fulfillment binds a token permanently to one account.
  Duplicate requests are idempotent; cancelled purchases cannot be reopened by a stale response.
- Enrollment commits before Google acknowledgement. A systemd timer retries
  acknowledgement and checks refunds; provider/network errors never imply a refund.
- Refunds restore previous access and preserve purchases through Stripe, lifetime
  grants and promotional access. Manual changes to enrollment dates are preserved.
- Payment tokens, credentials and user details are not written to application logs.
- Transactions are private service-role RPCs with RLS and no direct client table grants.
- Account erasure blocks unresolved pending or unacknowledged purchases; after
  settlement the ledger retains a pseudonymous transaction record, removes the user
  FK and deletes enrollment/grant/rate-limit records by the existing cascade rules.

## Deployment

On the existing host, from this directory:

```bash
python3 inspect.py
python3 release.py check
python3 release.py deploy
```

The initial deployment deliberately writes `MCA_PLAY_ENABLED=false` to an owner-only
`/srv/marka-course-academy/private/google-play.env` and generates a stable 32-byte
HMAC secret. The app presents an availability message in the Android purchase area.
Website Stripe purchases continue to use their existing code.

Required private settings before enabling purchases:

- `MCA_PLAY_ENABLED=true`
- `MCA_PLAY_ACCOUNT_SECRET`: the generated 64-character hexadecimal value. Preserve
  it across deployments; rotating it changes the binding of existing Google purchases.
- `GOOGLE_PLAY_SERVICE_ACCOUNT_B64`: base64 of the complete service-account JSON,
  stored only in the root-owned env file. Never commit it or place it in the frontend.

Google Cloud project prepared for this work: `mca-play-billing-583789026013`.
The Google Play Developer API must be enabled. The service account needs the Google
Play financial-data and order-management permissions, scoped to MCA only. Such
access needs the account owner's approval. No Cloud project roles are required by
the billing verifier. Do not enable purchasing until a genuine license-test purchase
verifies, grants access and is acknowledged on the server. The installed AAB 0.1.3
already contains Google Billing 8.3.0 and the Android Browser Helper bridge.

Rollback restores the previous app and stops the timer; it does not delete payment data:

```bash
python3 release.py rollback
```

## Validation

The tests use PGlite to execute the actual migration and exercise pending purchases,
token replay, duplicate fulfillment, acknowledgment retries, refunds, Stripe/promo
preservation, account erasure, RPC permissions, rate limits and unauthenticated HTTP.
Run in the actual application source or a scratch ESM harness with `files/` copied in
and the existing `src/lib/mca-rpc.server.ts`:

```bash
node --test tests/mca-play.test.mjs
```

The test dependency is `@electric-sql/pglite` version `0.3.14`. The deployed image is
built with the existing application lockfile. No new production dependency is added.

The installed timer invokes the mounted TypeScript retry entry point using Node 22's
type stripping. Its logs contain only counts. An end-to-end Android test still requires
the licensed Play tester account, active SKUs and authorized Google API credentials.

Primary references:

- https://chromeos.dev/en/publish/pwa-play-billing
- https://developers.google.com/android-publisher/getting_started
- https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.productsv2
- https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.products/acknowledge
