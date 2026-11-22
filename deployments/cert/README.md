# Academy certificate corrections

This release moves the QR verification caption clear of the PDF artwork, keeps a single MCA prefix in the downloaded filename, and gives the student and public certificate pages a retry action when verification cannot reach the server. Existing credential numbers and verification URLs are preserved.

From the host's existing `/tmp/mcapay120/deployments/checkout-120` directory, fetch the certificate package and deploy it.

```sh
git fetch -q origin mca-cert && git switch --detach FETCH_HEAD && cd ../cert && python3 release.py
```

Run `python3 release.py check` for a read-only preflight or `python3 release.py rollback` to restore the previously healthy checkout application.

The runner identifies the active Academy service from Docker Compose, verifies its deployed checkout marker, both price IDs, and its existing private env file reference. It builds a sibling copy of the active application's source with the same Dockerfile and build arguments. The added Compose override contains only a build context and image name. The runner verifies a digest of payment and Supabase runtime settings before and after the switch and restores the previous service if health or payment configuration diverges. No database migration is required.

Local validation covered the production Nitro build, TypeScript, public and student page states, PDF rendering and QR decoding in all five languages, checkout configuration preservation and rollback. On the Academy site, open a valid certificate and a nonexistent number, then scan a newly downloaded certificate's QR to confirm the published result.
