import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { accessStatus } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { PlayCourseCheckout } from "./PlayCourseCheckout";
import { isPlayPurchaseSurface } from "@/lib/mca-purchase-surface";

const copy = {
  pl: { retry: "Sprawdź płatność lub spróbuj ponownie", error: "Nie udało się otworzyć płatności. Spróbuj ponownie.", pending: "Czekamy na potwierdzenie od Stripe. Po potwierdzeniu kurs pojawi się w panelu kursanta." },
  nl: { retry: "Betaling controleren of opnieuw proberen", error: "De betaalpagina kon niet worden geopend. Probeer het opnieuw.", pending: "We wachten op de bevestiging van Stripe. Daarna verschijnt de cursus in je cursistenportaal." },
  fr: { retry: "Vérifier le paiement ou réessayer", error: "Impossible d’ouvrir la page de paiement. Réessayez.", pending: "Nous attendons la confirmation de Stripe. Le cours apparaîtra ensuite dans votre espace personnel." },
  en: { retry: "Check payment or try again", error: "The payment page could not be opened. Please try again.", pending: "Waiting for confirmation from Stripe. The course will appear in your dashboard after confirmation." },
  de: { retry: "Zahlung prüfen oder erneut versuchen", error: "Die Zahlungsseite konnte nicht geöffnet werden. Bitte versuchen Sie es erneut.", pending: "Wir warten auf die Bestätigung von Stripe. Anschließend erscheint der Kurs in Ihrem Kursbereich." },
};

export function CourseCheckout({ courseId, slug }: { courseId: string; slug: string }) {
  const { user, loading } = useAuth();
  const { t, lang } = useI18n();
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const [web, setWeb] = useState(false);
  const [surfaceReady, setSurfaceReady] = useState(false);
  useEffect(() => {
    setWeb(!isPlayPurchaseSurface());
    setSurfaceReady(true);
    setPending(new URLSearchParams(location.search).get("mca_payment") === "return");
    setFailed(false);
  }, [slug]);

  const enrollment = useQuery({
    queryKey: ["checkout-course-access", user?.id, courseId],
    enabled: Boolean(user),
    queryFn: async () => {
      const { data, error } = await supabase.from("enrollments")
        .select("status, activation_date, expiry_date, promo_access").eq("user_id", user!.id)
        .eq("course_id", courseId).maybeSingle();
      if (error) throw error;
      return accessStatus(data) === "active";
    },
    refetchInterval: (query) => pending && !query.state.data && query.state.dataUpdateCount < 20 ? 3000 : false,
  });
  const next = "/kurs/" + encodeURIComponent(slug);
  const signIn = () => location.assign("/auth?" + new URLSearchParams({ tryb: "logowanie", next }));
  async function start() {
    if (!web || busy) return;
    if (!user) return signIn();
    setFailed(false);
    setBusy(true);
    try {
      const { data } = await supabase.auth.getSession();
      if (!data.session) return signIn();
      const response = await fetch("/api/academy/checkout", {
        method: "POST", headers: { "Content-Type": "application/json", Authorization: "Bearer " + data.session.access_token },
        body: JSON.stringify({ courseId }),
      });
      if (response.status === 401) return signIn();
      if (!response.ok) throw new Error();
      const result = await response.json();
      if (result.status === "already_enrolled") { location.assign("/panel/kurs/" + encodeURIComponent(slug)); return; }
      if (result.status === "processing") { setPending(true); return; }
      if (result.status !== "open" || typeof result.url !== "string" || new URL(result.url).origin !== "https://checkout.stripe.com") throw new Error();
      location.assign(result.url);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }
  if (enrollment.data)
    return <Button size="lg" className="w-full" asChild><Link to="/panel/kurs/$slug" params={{ slug }}>{t("common.open")}</Link></Button>;
  if (!surfaceReady) return null;
  if (!web) return <PlayCourseCheckout courseId={courseId} slug={slug} className="w-full" />;
  if (pending && user)
    return (
      <div className="space-y-2">
        <p role="status">{copy[lang].pending}</p>
        <Button disabled={busy || loading} onClick={start}>{copy[lang].retry}</Button>
        <Button asChild variant="outline"><Link to="/panel">{t("nav.panel")}</Link></Button>
        {failed && <p role="alert" className="text-sm text-destructive">{copy[lang].error}</p>}
      </div>
    );
  return <>
    <Button size="lg" className="w-full" disabled={busy || loading} onClick={start}>{t("common.buy")}</Button>
    {failed && <p role="alert" className="text-sm text-destructive">{copy[lang].error}</p>}
  </>;
}
