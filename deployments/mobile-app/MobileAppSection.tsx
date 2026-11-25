import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { isPlayPurchaseSurface } from "@/lib/mca-purchase-surface";

const copy = {
  pl: {
    eyebrow: "MCA W TELEFONIE", title: "Twoje kursy zawsze pod ręką.",
    body: "Korzystaj z Marka Centrum Academy na telefonie. Wersja na Androida czeka na zatwierdzenie w Google Play. Już teraz możesz otworzyć kursy w przeglądarce i dodać skrót do ekranu głównego.",
    store: "Wkrótce w Google Play", install: "Jak dodać do telefonu", close: "Ukryj instrukcję",
    android: "Android / Samsung", androidSteps: "Otwórz tę stronę w Chrome → menu ⋮ → Dodaj do ekranu głównego. Jeśli przeglądarka zaproponuje instalację, postępuj zgodnie z jej instrukcjami.",
    ios: "iPhone / iPad", iosSteps: "Otwórz tę stronę w Safari → Udostępnij → Do ekranu początkowego.",
    note: "Skrót otwiera wersję internetową. To samo konto i zakupione kursy."
  },
  nl: {
    eyebrow: "MCA OP JE TELEFOON", title: "Je cursussen binnen handbereik.",
    body: "Gebruik Marka Centrum Academy op je telefoon. De Android-app wacht op goedkeuring in Google Play. Je kunt de cursussen nu al in je browser openen en een snelkoppeling aan je startscherm toevoegen.",
    store: "Binnenkort in Google Play", install: "Toevoegen aan je telefoon", close: "Instructies verbergen",
    android: "Android / Samsung", androidSteps: "Open deze pagina in Chrome → menu ⋮ → Toevoegen aan startscherm. Als de browser installatie aanbiedt, volg dan de instructies.",
    ios: "iPhone / iPad", iosSteps: "Open deze pagina in Safari → Deel → Zet op beginscherm.",
    note: "De snelkoppeling opent de webversie. Hetzelfde account en je aangekochte cursussen."
  },
  fr: {
    eyebrow: "MCA SUR VOTRE TÉLÉPHONE", title: "Vos cours à portée de main.",
    body: "Utilisez Marka Centrum Academy sur votre téléphone. L’application Android est en attente de validation sur Google Play. Vous pouvez déjà accéder aux cours dans votre navigateur et ajouter un raccourci à votre écran d’accueil.",
    store: "Bientôt sur Google Play", install: "Ajouter sur votre téléphone", close: "Masquer les instructions",
    android: "Android / Samsung", androidSteps: "Ouvrez cette page dans Chrome → menu ⋮ → Ajouter à l’écran d’accueil. Si le navigateur propose une installation, suivez ses instructions.",
    ios: "iPhone / iPad", iosSteps: "Ouvrez cette page dans Safari → Partager → Sur l’écran d’accueil.",
    note: "Le raccourci ouvre la version web. Même compte et mêmes cours achetés."
  },
  en: {
    eyebrow: "MCA ON YOUR PHONE", title: "Your courses, close at hand.",
    body: "Use Marka Centrum Academy on your phone. The Android app is awaiting Google Play approval. You can already open the courses in your browser and add a shortcut to your home screen.",
    store: "Coming soon to Google Play", install: "Add to your phone", close: "Hide instructions",
    android: "Android / Samsung", androidSteps: "Open this page in Chrome → menu ⋮ → Add to Home screen. If the browser offers installation, follow its instructions.",
    ios: "iPhone / iPad", iosSteps: "Open this page in Safari → Share → Add to Home Screen.",
    note: "The shortcut opens the web version. The same account and purchased courses."
  },
  de: {
    eyebrow: "MCA AUF DEINEM SMARTPHONE", title: "Deine Kurse immer griffbereit.",
    body: "Nutze Marka Centrum Academy auf deinem Smartphone. Die Android-App wartet auf die Freigabe bei Google Play. Du kannst die Kurse schon jetzt im Browser öffnen und eine Verknüpfung zum Startbildschirm hinzufügen.",
    store: "Bald bei Google Play", install: "Zum Smartphone hinzufügen", close: "Anleitung ausblenden",
    android: "Android / Samsung", androidSteps: "Öffne diese Seite in Chrome → Menü ⋮ → Zum Startbildschirm hinzufügen. Falls der Browser eine Installation anbietet, folge den Anweisungen.",
    ios: "iPhone / iPad", iosSteps: "Öffne diese Seite in Safari → Teilen → Zum Home-Bildschirm.",
    note: "Die Verknüpfung öffnet die Webversion. Dasselbe Konto und deine gekauften Kurse."
  },
};

export default function MobileAppSection() {
  const { lang } = useI18n();
  const c = copy[lang as keyof typeof copy] ?? copy.pl;
  const [open, setOpen] = useState(false);
  const [native, setNative] = useState(false);
  useEffect(() => { setNative(isPlayPurchaseSurface()); }, []);
  if (native) return null;
  return (
    <section id="aplikacja" aria-labelledby="mca-app-title" className="bg-ink px-4 pb-10 pt-2 sm:pb-14">
      <div className="mx-auto max-w-4xl rounded-2xl border border-gold/30 bg-white/5 p-6 text-white sm:p-8">
        <p className="text-xs font-bold tracking-widest text-gold">{c.eyebrow}</p>
        <h2 id="mca-app-title" className="mt-3 text-2xl font-bold sm:text-3xl">{c.title}</h2>
        <p className="mt-3 max-w-3xl text-sm leading-relaxed text-white/80 sm:text-base">{c.body}</p>
        <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center">
          <span role="status" className="inline-flex min-h-12 items-center justify-center rounded-xl border border-white/20 bg-black/20 px-5 py-3 text-sm font-semibold text-white/70">{c.store}</span>
          <button type="button" aria-expanded={open} aria-controls="mca-phone-instructions" onClick={() => setOpen(!open)} className="inline-flex min-h-12 items-center justify-center rounded-xl bg-gold px-5 py-3 text-sm font-bold text-ink transition-opacity hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-gold">{open ? c.close : c.install}</button>
        </div>
        {open && (
          <div id="mca-phone-instructions" className="mt-5 space-y-4 rounded-xl border border-white/15 bg-black/20 p-5 text-sm leading-relaxed">
            <div><h3 className="font-bold text-gold">{c.android}</h3><p className="mt-1 text-white/85">{c.androidSteps}</p></div>
            <div><h3 className="font-bold text-gold">{c.ios}</h3><p className="mt-1 text-white/85">{c.iosSteps}</p></div>
            <p className="border-t border-white/15 pt-3 text-xs text-white/65">{c.note}</p>
          </div>
        )}
      </div>
    </section>
  );
}
