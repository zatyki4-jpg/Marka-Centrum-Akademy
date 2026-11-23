import { reconcilePlayPurchases } from '../src/lib/mca-play.server.ts';

try {
  const result = await reconcilePlayPurchases();
  console.log(JSON.stringify(result));
  if (result.failed) process.exitCode = 1;
} catch {
  console.error('Google Play reconciliation failed; no account or payment details logged.');
  process.exitCode = 1;
}
