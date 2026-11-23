import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

type Product = { itemId: string; title: string; price: { currency: string; value: string } };
type DigitalGoods = { getDetails(ids: string[]): Promise<Product[]>;
  listPurchases(): Promise<Array<{ itemId: string; purchaseToken: string }>> };
type Config = { sku: string; accountId: string; status: string };
type PlayResponse = PaymentResponse & { details: { purchaseToken?: string; token?: string } };

const words = {
  pl: { buy: 'Kup przez Google Play', restore: 'Przywróć zakup', sign: 'Zaloguj się, aby kupić kurs',
    unavailable: 'Zakupy Google Play są chwilowo niedostępne.', error: 'Nie udało się potwierdzić zakupu. Jeśli zapłacono, wybierz „Przywróć zakup”.',
    pending: 'Płatność czeka na potwierdzenie Google Play. Kurs odblokuje się po jej zatwierdzeniu.',
    restored: 'Dostęp do kursu jest aktywny.', empty: 'Na tym koncie Google Play nie znaleziono zakupu tego kursu.',
    mismatch: 'Ten zakup należy do innego konta MCA. Zaloguj się na konto użyte podczas zakupu.', busy: 'Sprawdzam…' },
  en: { buy: 'Buy with Google Play', restore: 'Restore purchase', sign: 'Sign in to buy the course',
    unavailable: 'Google Play purchases are temporarily unavailable.', error: 'Could not verify the purchase. If you have paid, select “Restore purchase”.',
    pending: 'Payment is awaiting Google Play confirmation. Access will unlock once approved.', restored: 'Course access is active.',
    empty: 'No purchase of this course was found on this Google Play account.', mismatch: 'This purchase belongs to another MCA account. Sign in to the account used for the purchase.', busy: 'Checking…' },
  nl: { buy: 'Kopen via Google Play', restore: 'Aankoop herstellen', sign: 'Meld je aan om de cursus te kopen',
    unavailable: 'Aankopen via Google Play zijn tijdelijk niet beschikbaar.', error: 'De aankoop kon niet worden bevestigd. Kies “Aankoop herstellen” als je al betaald hebt.',
    pending: 'De betaling wacht op bevestiging door Google Play. Daarna wordt de cursus vrijgegeven.', restored: 'Je toegang tot de cursus is actief.',
    empty: 'Geen aankoop van deze cursus gevonden op dit Google Play-account.', mismatch: 'Deze aankoop hoort bij een ander MCA-account. Meld je aan met het account waarmee je hebt gekocht.', busy: 'Controleren…' },
  de: { buy: 'Über Google Play kaufen', restore: 'Kauf wiederherstellen', sign: 'Zum Kurskauf anmelden',
    unavailable: 'Google-Play-Käufe sind vorübergehend nicht verfügbar.', error: 'Der Kauf konnte nicht bestätigt werden. Falls bereits bezahlt, „Kauf wiederherstellen“ wählen.',
    pending: 'Die Zahlung wartet auf die Bestätigung von Google Play. Danach wird der Kurs freigeschaltet.', restored: 'Der Kurszugang ist aktiv.',
    empty: 'Kein Kauf dieses Kurses in diesem Google-Play-Konto gefunden.', mismatch: 'Dieser Kauf gehört zu einem anderen MCA-Konto. Melde dich mit dem beim Kauf verwendeten Konto an.', busy: 'Wird geprüft…' },
  fr: { buy: 'Acheter via Google Play', restore: 'Restaurer l’achat', sign: 'Connectez-vous pour acheter le cours',
    unavailable: 'Les achats Google Play sont temporairement indisponibles.', error: 'L’achat n’a pas pu être confirmé. Si vous avez payé, choisissez « Restaurer l’achat ».',
    pending: 'Le paiement attend la confirmation de Google Play. Le cours sera ensuite débloqué.', restored: 'L’accès au cours est actif.',
    empty: 'Aucun achat de ce cours trouvé sur ce compte Google Play.', mismatch: 'Cet achat appartient à un autre compte MCA. Connectez-vous au compte utilisé lors de l’achat.', busy: 'Vérification…' },
};

async function callPlay(courseId: string, action: 'config' | 'verify', purchaseToken?: string) {
  const { data } = await supabase.auth.getSession();
  if (!data.session) throw new Error('authentication_required');
  const r = await fetch('/api/academy/google-play', { method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${data.session.access_token}` },
    body: JSON.stringify({ courseId, action, ...(purchaseToken ? { purchaseToken } : {}) }) });
  const payload = await r.json();
  if (!r.ok || !payload.ok) throw new Error(payload.error || 'billing_unavailable');
  return payload;
}

export function PlayCourseCheckout({ courseId, slug, className }: { courseId: string; slug: string; className?: string }) {
  const { user } = useAuth();
  const { lang, t: common } = useI18n();
  const t = words[lang as keyof typeof words] || words.en;
  const cache = useQueryClient();
  const [ready, setReady] = useState<{ service: DigitalGoods; config: Config; product: Product } | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<keyof typeof t | null>(null);

  useEffect(() => {
    let cancelled = false;
    setReady(null); setLoading(true); setMessage(null);
    async function prepare() {
      try {
        if (!user) return;
        const getService = (window as Window & { getDigitalGoodsService?: (method: string) => Promise<DigitalGoods> }).getDigitalGoodsService;
        if (!getService || !window.PaymentRequest) throw new Error('unavailable');
        const service = await getService.call(window, 'https://play.google.com/billing');
        const config: Config = await callPlay(courseId, 'config');
        if (config.status === 'already_enrolled') { if (!cancelled) setMessage('restored'); return; }
        const product = (await service.getDetails([config.sku])).find(p => p.itemId === config.sku);
        if (!product || !/^[A-Z]{3}$/.test(product.price.currency) || !/^\d+(\.\d+)?$/.test(product.price.value) ||
            !Number.isFinite(Number(product.price.value)) || Number(product.price.value) <= 0) throw new Error('unavailable');
        if (!cancelled) setReady({ service, config, product });
        // Recover payments completed while the application was closed.
        const owned = (await service.listPurchases()).filter(p => p.itemId === config.sku);
        for (const p of owned) {
          if (cancelled) return;
          try {
            const result = await callPlay(courseId, 'verify', p.purchaseToken);
            if (!cancelled && result.status === 'purchased') { setMessage('restored'); await refreshAccess(); }
            else if (!cancelled && result.status === 'pending') setMessage('pending');
          } catch { /* A manual restore remains available after a temporary network error. */ }
        }
      } catch { if (!cancelled) setMessage('unavailable'); }
      finally { if (!cancelled) setLoading(false); }
    }
    void prepare();
    return () => { cancelled = true; };
  }, [courseId, user?.id]);

  async function refreshAccess() {
    await cache.invalidateQueries({ queryKey: ['checkout-course-access', user?.id, courseId] });
    // Existing panel queries have several names; invalidation refreshes their access state.
    await cache.invalidateQueries();
  }

  function failure(error: unknown) {
    if (error instanceof DOMException && error.name === 'AbortError') { setMessage(null); return; }
    setMessage(error instanceof Error && error.message === 'account_mismatch' ? 'mismatch' : 'error');
  }

  async function buy() {
    if (!ready || busy) return;
    setBusy(true); setMessage(null);
    let response: PlayResponse | undefined;
    try {
      const payment = new PaymentRequest([{ supportedMethods: 'https://play.google.com/billing',
        data: { sku: ready.config.sku, obfuscatedAccountId: ready.config.accountId } }],
      { total: { label: ready.product.title, amount: ready.product.price } });
      response = await payment.show() as PlayResponse;
      const token = response.details.purchaseToken || response.details.token;
      if (!token) throw new Error('invalid_purchase');
      const result = await callPlay(courseId, 'verify', token);
      await response.complete(result.status === 'purchased' ? 'success' : 'unknown');
      response = undefined;
      setMessage(result.status === 'purchased' ? 'restored' : result.status === 'pending' ? 'pending' : 'error');
      if (result.status === 'purchased') await refreshAccess();
    } catch (error) {
      if (response) await response.complete('unknown').catch(() => {});
      failure(error);
    } finally { setBusy(false); }
  }

  async function restore() {
    if (!ready || busy) return;
    setBusy(true); setMessage(null);
    try {
      const purchases = (await ready.service.listPurchases()).filter(p => p.itemId === ready.config.sku);
      if (!purchases.length) { setMessage('empty'); return; }
      let purchased = false, pending = false;
      for (const p of purchases) {
        const result = await callPlay(courseId, 'verify', p.purchaseToken);
        purchased ||= result.status === 'purchased'; pending ||= result.status === 'pending';
      }
      setMessage(purchased ? 'restored' : pending ? 'pending' : 'empty');
      if (purchased) await refreshAccess();
    } catch (error) { failure(error); }
    finally { setBusy(false); }
  }

  if (!user) return <Button asChild className={className}><a href={'/auth?' + new URLSearchParams({ tryb: 'logowanie', next: '/kurs/' + slug })}>{t.sign}</a></Button>;
  const price = ready ? new Intl.NumberFormat(lang, { style: 'currency', currency: ready.product.price.currency }).format(Number(ready.product.price.value)) : '';
  return <div className="space-y-2">
    {ready && message !== 'restored' && <><Button className={className} disabled={busy || message === 'pending'} onClick={() => void buy()}>{busy ? t.busy : `${t.buy} — ${price}`}</Button>
      <Button variant="outline" className="w-full" disabled={busy} onClick={() => void restore()}>{t.restore}</Button></>}
    {message === 'restored' && <Button asChild className={className}><a href={'/panel/kurs/' + encodeURIComponent(slug)}>{common('common.open')}</a></Button>}
    {(loading || message) && <p role="status" className="text-sm text-muted-foreground">{loading ? t.busy : message ? t[message] : ''}</p>}
  </div>;
}
