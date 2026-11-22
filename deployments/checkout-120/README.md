# Academy Checkout · EUR 120

This release overlays the separate, self-hosted Academy application on Hetzner. Apply it to the active TanStack source. The GitHub repository root contains the legacy DakPro application.

| Academy course | One-time price in EUR | Stripe live price |
| --- | ---: | --- |
| Monter bitumicznych pokryć dachowych | 120.00 | `price_1Uej4hIcl2W7iMTxaiHPUqGo` |
| Monter bitumicznych pokryć dachowych – poziom 2: renowacja dachów płaskich | 120.00 | `price_1Uej5CIcl2W7iMTxLKxgp06s` |

A confirmed purchase grants lifetime access to that course, its materials and its exam. Course completion requirements and certificate conditions still apply.

## Runtime settings

The active Compose application provides `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`. The release override supplies the two production price IDs. Store these additional settings on the host in an owner-only env file outside the releases directory.

| Variable | Value |
| --- | --- |
| `STRIPE_SECRET_KEY` | Live Stripe secret or restricted key for creating and reading Checkout Sessions |
| `STRIPE_WEBHOOK_SECRET` | Signing secret for this exact live destination |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key for the active self-hosted Academy Supabase instance |

To prepare the runtime file, open a private root terminal on the existing Academy host, enter this release directory and run:

```sh
python3 configure.py
```

Enter the Stripe live API key, then the live webhook destination's signing secret at the hidden prompts. Type or paste secrets directly into the host terminal. Terminal recording or screen sharing that captures keyboard input should be disabled. The bootstrap obtains the service role locally from the running Academy backend configuration and writes `/srv/marka-course-academy/private/stripe-checkout.env` atomically with mode 0600. On subsequent runs it keeps existing values, other settings and comments, and fills only missing entries. An invalid existing value or a mismatch stops the operation before writing. Continue with the separate deploy command after setup completes.

The public web checkout origin is `https://markacentrumacademy.eu`. Register the Stripe destination `https://markacentrumacademy.eu/api/stripe/webhook` for the account's own `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, and `checkout.session.expired` events. Store the destination signing secret directly on the host. A free-standing payment link cannot supply an authenticated order binding.

## Preflight and release

From this release directory on the Academy host:

```sh
python3 release.py check /srv/marka-course-academy/releases/ui-20261122
docker ps --format '{{.Names}}' | grep -Ex 'mca-course-test|marka-course-academy'
```

The recorded production web container is `mca-course-test`. Select the active Academy web container returned by the host. After all runtime settings are present, run:

```sh
python3 release.py deploy
```

The runner discovers the running service's Compose project, copies its source to a new release, applies the checked patch, builds the new image, and installs the transactionally guarded schema on `mca-sb-db`. It restarts only the existing web service and waits for Docker health. Failed replacements automatically restore the previous service. To restore the previous application manually, run:

```sh
python3 release.py rollback --container mca-course-test
```

The payment schema and recorded payment history remain available after application rollback. Once the webhook is serving again, use Stripe's delivery history to retry any failed events.

## Acceptance

Test with separate Stripe test-mode and Supabase staging configuration. Open each course as a signed-in test student, verify the checkout shows EUR 120 once, and complete using Stripe test payment details. Inspect the paid order, its matching enrollment with a null expiry, and the student's course panel. Repeat webhook delivery to confirm it produces one enrollment. An unpaid or canceled checkout must leave the course locked. Confirm that an authenticated existing enrollment and protected promotional access continue to work. Publishing the patch, building the image, and successful unit tests alone do not establish that a live charge and live course access have been observed.

## Live price verification

After production deployment, run `python3 smoke.py` on the Academy host as root. The command sends authenticated requests through the real course checkout for both products. It checks the held-open sessions directly with Stripe, including the EUR 120 amount, one-time price, product and quantity. It creates a randomized QA learner on the local Academy backend and sends no email. It never submits payment details.

The command expires the two sessions, waits for the Academy webhook to record the expirations, then removes the marker-matched QA user and its associated rows. Stripe retains its expired session records. If any session is paid, still usable, or cannot be reconciled, the script retains the QA account and prints a random marker for `python3 smoke.py --cleanup MARKER`. On an interrupted run, use the marker printed at startup. The command emits no checkout URLs, credentials, email addresses or customer records.
