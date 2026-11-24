import { useQuery } from "@tanstack/react-query";
import { CourseCheckout } from "@/components/CourseCheckout";
import { supabase } from "@/integrations/supabase/client";
import { useI18n } from "@/lib/i18n";
import { formatPrice } from "@/lib/format";

const messages = {
  pl: { title: "Wybierz dostęp do kursu", help: "Jeśli nie masz jeszcze dostępu do lekcji, wybierz właściwy kurs poniżej. Po zakupie lekcje będą dostępne w panelu kursanta.", loading: "Sprawdzam dostępne kursy…", error: "Nie udało się wczytać zakupu. Otwórz katalog kursów i spróbuj ponownie." },
  nl: { title: "Kies je cursus", help: "Heb je nog geen toegang tot de les? Kies hieronder de juiste cursus. Na aankoop vind je de lessen in je cursistenportaal.", loading: "Cursussen laden…", error: "De aankoop kon niet worden geladen. Open de cursuscatalogus en probeer opnieuw." },
  en: { title: "Choose your course", help: "If you do not have access to the lesson yet, choose the appropriate course below. After purchase, its lessons will be available in your learner dashboard.", loading: "Loading courses…", error: "Could not load the purchase options. Open the course catalogue and try again." },
  fr: { title: "Choisissez votre formation", help: "Si vous n’avez pas encore accès à la leçon, choisissez la formation correspondante ci-dessous. Après l’achat, ses leçons seront disponibles dans votre espace personnel.", loading: "Chargement des formations…", error: "Impossible de charger les achats. Ouvrez le catalogue des formations et réessayez." },
  de: { title: "Kurs auswählen", help: "Wenn Sie noch keinen Zugang zur Lektion haben, wählen Sie unten den passenden Kurs. Nach dem Kauf stehen die Lektionen in Ihrem Kursbereich bereit.", loading: "Kurse werden geladen…", error: "Die Kaufoptionen konnten nicht geladen werden. Öffnen Sie den Kurskatalog und versuchen Sie es erneut." },
};

export function LessonPurchaseOptions() {
  const { lang } = useI18n();
  const text = messages[lang as keyof typeof messages] || messages.en;
  const courses = useQuery({
    queryKey: ["lesson-purchase-course-options"],
    staleTime: 60_000,
    retry: 1,
    queryFn: async () => {
      const { data, error } = await supabase.from("courses")
        .select("id, slug, title, price_cents, currency")
        .eq("is_published", true)
        .in("id", ["11111111-1111-4111-8111-111111111111", "f166433e-5157-4341-9a38-800c62795ebd"])
        .order("level", { ascending: true });
      if (error) throw new Error("course_options_unavailable");
      return (data || []).filter(course => course.slug && course.title
        && typeof course.price_cents === "number" && course.price_cents > 0
        && typeof course.currency === "string");
    },
  });
  return <section className="mt-6 space-y-4 text-left" aria-label={text.title}>
    <div><h2 className="text-xl font-semibold">{text.title}</h2>
      <p className="mt-2 text-sm text-muted-foreground">{text.help}</p></div>
    {courses.isPending && <p role="status">{text.loading}</p>}
    {(courses.isError || (!courses.isPending && !courses.data?.length)) && <p role="alert">{text.error}</p>}
    {courses.data?.map(course => <div key={course.id} className="rounded-xl border bg-card p-4 space-y-3">
      <h3 className="font-semibold">{course.title}</h3>
      <p>{formatPrice(course.price_cents, course.currency, lang)}</p>
      <CourseCheckout courseId={course.id} slug={course.slug} />
    </div>)}
  </section>;
}
