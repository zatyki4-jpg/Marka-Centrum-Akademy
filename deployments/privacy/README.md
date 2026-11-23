# Academy privacy and account deletion

The public pages are `/privacy` and `/delete-account`. The privacy policy and deletion instructions are available in Polish and English. Footer and registration links are labelled in all five application languages. Requests go to `info@markaconstruct.be` and require administrator handling.

## Deployment

Run `python3 release.py check`, then `python3 release.py` from this directory on the existing Academy host. The release copies the active application source, applies the seven-file patch, builds with the existing Compose inputs and verifies public responses, app links and a fingerprint of payment and authentication settings. A failed switch restores the prior application. Run `python3 release.py rollback` to restore it manually.

Run `python3 account_deletion.py test` to exercise account, enrolment, progress, certificate, promotional participation and feedback deletion inside a rolled-back database transaction. The fixture uses a unique example.invalid address and sends no email.

## Handling a request

1. Read the request received at `info@markaconstruct.be`. Verify that the requester controls the account email. If the address is unavailable, establish account ownership through proportionate verification.
2. Obtain the exact account UUID and run `python3 account_deletion.py plan USER_UUID`. Review the displayed account and purchase records. Keep the output in the private support case.
3. Settle or expire any outstanding Stripe checkout session. Identify records that have to be kept under accounting obligations or an actual dispute and record the reason and applicable retention deadline in the case. Administrator ownership and user-owned storage require individual handling to preserve training materials.
4. Execute `python3 account_deletion.py erase USER_UUID --confirm-user-id USER_UUID` after the review. The transaction deletes promotional feedback and participation, the authentication account and dependent profile, roles, enrolments, progress, quiz and examination attempts, certificates, sessions and identities. Completed purchase evidence is saved separately with owner-only permissions under `/srv/marka-course-academy/private/deleted-account-purchase-records`.
5. Request deletion from relevant providers, including Stripe where applicable, and process support mailbox data. Document legally required provider retention. Find backups containing the account and erase or anonymise it in restorable copies, or restrict the copies until their documented expiry. Record the erased UUID in the restricted restoration record and reapply erasure before any restored database is brought online.
6. Existing signed access tokens can remain valid until their configured expiry. Confirm expiry and that login, token refresh and public certificate verification no longer return the erased account’s data. Check all additional data categories identified in the request before marking it complete.
7. Reply within one month with the result and any retained categories, grounds and retention periods. Document any permitted extension within that month. Review the separate purchase archive against the retention deadline and remove records when their ground expires.

`USER_UUID` in the command examples means the exact UUID returned by the verified account lookup. The package has no scheduled deletion and grants no public deletion API access.

## Verified deployment facts

On 23 November 2026 the active application was `mca-course-test`, its PostgreSQL and authentication services were `mca-sb-db` and `mca-sb-auth`, and the server was in Nuremberg, Germany. Authentication used `https://api.markacentrumacademy.eu`, and account mail used Hetzner `mail.your-server.de`. Web-server logs rotated daily with 14 archives. User-owned storage object count was zero. The privacy copy uses existing company contact information and provider disclosures.

Google's privacy and deletion requirements are described at https://support.google.com/googleplay/android-developer/answer/10144311 and https://support.google.com/googleplay/android-developer/answer/13327111. Stripe's transfer mechanisms and retention are described at https://stripe.com/privacy.
