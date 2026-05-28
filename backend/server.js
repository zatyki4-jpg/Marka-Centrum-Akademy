// backend/server.js — DakPro Academy v2
require("dotenv").config();
const express = require("express");
const cors = require("cors");
const path = require("path");
const stripe = require("stripe")(process.env.STRIPE_SECRET_KEY || "sk_test_placeholder");
const { get, all, run } = require("./db");

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use("/stripe/webhook", express.raw({ type: "application/json" }));
app.use(express.json());

const PUBLIC_DIR = path.join(__dirname, "../frontend/public");
app.use(express.static(PUBLIC_DIR));
app.get("/health", (req, res) => res.json({ status: "ok", service: "DakPro Academy API", version: "2.0.0" }));

// ── GET /catalog-with-access?email= ───────────────────────────
app.get("/catalog-with-access", async (req, res) => {
  const { email } = req.query;
  if (!email) return res.status(400).json({ error: "email vereist" });
  try {
    const courses = await all(`SELECT id, title, description, lang, price_eur FROM courses WHERE is_published=1 ORDER BY rowid`);
    const now = new Date().toISOString().slice(0, 10);
    for (const c of courses) {
      const enrollment = await get(
        `SELECT id FROM enrollments WHERE user_email=? AND course_id=? AND activation_date<=? AND expiry_date>=?`,
        [email, c.id, now, now]
      );
      const lessonCount = await get(`SELECT COUNT(*) as cnt FROM lessons l JOIN stages s ON l.stage_id=s.id WHERE s.course_id=?`, [c.id]);
      const doneCount = await get(`SELECT COUNT(*) as cnt FROM lesson_progress lp JOIN lessons l ON lp.lesson_id=l.id JOIN stages s ON l.stage_id=s.id WHERE s.course_id=? AND lp.user_email=?`, [c.id, email]);
      c.access = enrollment ? "active" : "preview";
      c.lesson_count = lessonCount.cnt;
      c.done_count = doneCount.cnt;
      c.progress_pct = lessonCount.cnt > 0 ? Math.round((doneCount.cnt / lessonCount.cnt) * 100) : 0;
    }
    res.json(courses);
  } catch (err) { console.error(err); res.status(500).json({ error: err.message }); }
});

// ── GET /courses/:id/stages?email= ────────────────────────────
app.get("/courses/:id/stages", async (req, res) => {
  const { id } = req.params;
  const { email } = req.query;
  if (!email) return res.status(400).json({ error: "email vereist" });
  try {
    const now = new Date().toISOString().slice(0, 10);
    const enrollment = await get(`SELECT id FROM enrollments WHERE user_email=? AND course_id=? AND activation_date<=? AND expiry_date>=?`, [email, id, now, now]);
    const hasAccess = !!enrollment;
    const stages = await all(`SELECT id, title, position FROM stages WHERE course_id=? ORDER BY position`, [id]);
    for (const st of stages) {
      const lessons = await all(`SELECT id, title, type, duration_min, position, is_free_preview FROM lessons WHERE stage_id=? ORDER BY position`, [st.id]);
      for (const l of lessons) {
        const done = await get(`SELECT id FROM lesson_progress WHERE user_email=? AND lesson_id=?`, [email, l.id]);
        const attempts = await get(`SELECT COUNT(*) as cnt FROM quiz_attempts WHERE user_email=? AND lesson_id=?`, [email, l.id]);
        l.completed = !!done;
        l.accessible = hasAccess || l.is_free_preview === 1;
        l.attempts_used = attempts ? attempts.cnt : 0;
      }
      st.lessons = lessons;
    }
    res.json({ course_id: id, has_access: hasAccess, stages });
  } catch (err) { console.error(err); res.status(500).json({ error: err.message }); }
});

// ── GET /lessons/:id?email= ────────────────────────────────────
app.get("/lessons/:id", async (req, res) => {
  const { id } = req.params;
  const { email } = req.query;
  if (!email) return res.status(400).json({ error: "email vereist" });
  try {
    const lesson = await get(`SELECT * FROM lessons WHERE id=?`, [id]);
    if (!lesson) return res.status(404).json({ error: "Les niet gevonden" });
    const stage = await get(`SELECT course_id FROM stages WHERE id=?`, [lesson.stage_id]);
    const now = new Date().toISOString().slice(0, 10);
    const enrollment = await get(`SELECT id FROM enrollments WHERE user_email=? AND course_id=? AND activation_date<=? AND expiry_date>=?`, [email, stage.course_id, now, now]);
    if (!enrollment && lesson.is_free_preview !== 1) return res.status(403).json({ error: "Geen toegang. Koop eerst de cursus." });
    if (lesson.type === "quiz" || lesson.type === "exam") {
      const questions = await all(`SELECT id, question, option_a, option_b, option_c, option_d, position FROM quiz_questions WHERE lesson_id=? ORDER BY position`, [id]);
      lesson.questions = questions;
      const attempts = await get(`SELECT COUNT(*) as cnt FROM quiz_attempts WHERE user_email=? AND lesson_id=?`, [email, id]);
      lesson.attempts_used = attempts ? attempts.cnt : 0;
    }
    res.json(lesson);
  } catch (err) { console.error(err); res.status(500).json({ error: err.message }); }
});

// ── POST /lessons/:id/complete ─────────────────────────────────
app.post("/lessons/:id/complete", async (req, res) => {
  const { id } = req.params;
  const { email } = req.body;
  if (!email) return res.status(400).json({ error: "email vereist" });
  try {
    await run(`INSERT OR IGNORE INTO lesson_progress (user_email, lesson_id) VALUES (?, ?)`, [email, id]);
    res.json({ success: true });
  } catch (err) { res.status(500).json({ error: err.message }); }
});

// ── POST /quiz/submit ──────────────────────────────────────────
app.post("/quiz/submit", async (req, res) => {
  const { email, lesson_id, answers } = req.body;
  if (!email || !lesson_id || !answers) return res.status(400).json({ error: "email, lesson_id en answers vereist" });
  try {
    const lesson = await get(`SELECT type FROM lessons WHERE id=?`, [lesson_id]);
    const maxAttempts = lesson && lesson.type === "exam" ? 1 : 2;
    const attempts = await get(`SELECT COUNT(*) as cnt FROM quiz_attempts WHERE user_email=? AND lesson_id=?`, [email, lesson_id]);
    if (attempts.cnt >= maxAttempts) return res.status(429).json({ error: `Maximum ${maxAttempts} pogingen bereikt`, attempts_used: attempts.cnt });
    const questions = await all(`SELECT id, correct_index FROM quiz_questions WHERE lesson_id=? ORDER BY position`, [lesson_id]);
    let correct = 0;
    const results = questions.map(q => {
      const given = answers[q.id];
      const isCorrect = given === q.correct_index;
      if (isCorrect) correct++;
      return { question_id: q.id, given, correct_index: q.correct_index, is_correct: isCorrect };
    });
    const score = questions.length > 0 ? Math.round((correct / questions.length) * 100) : 0;
    const passed = score >= 70;
    await run(`INSERT INTO quiz_attempts (user_email, lesson_id, answers, score, passed) VALUES (?, ?, ?, ?, ?)`, [email, lesson_id, JSON.stringify(answers), score, passed ? 1 : 0]);
    if (passed) await run(`INSERT OR IGNORE INTO lesson_progress (user_email, lesson_id) VALUES (?, ?)`, [email, lesson_id]);
    res.json({ score, passed, correct, total: questions.length, results, attempts_used: attempts.cnt + 1, max_attempts: maxAttempts });
  } catch (err) { console.error(err); res.status(500).json({ error: err.message }); }
});

// ── GET /enrollments?email= ────────────────────────────────────
app.get("/enrollments", async (req, res) => {
  const { email } = req.query;
  if (!email) return res.status(400).json({ error: "email vereist" });
  try {
    const rows = await all(`SELECT e.course_id, e.activation_date, e.expiry_date, c.title FROM enrollments e JOIN courses c ON e.course_id=c.id WHERE e.user_email=?`, [email]);
    res.json(rows);
  } catch (err) { res.status(500).json({ error: err.message }); }
});

// ── POST /stripe/webhook ───────────────────────────────────────
// Vervang met je echte Stripe Price IDs
const PRICE_MAP = {
  "price_ROOFING_NL": { courseId: "kurs-roofing-nl" },
  "price_LEI_NL":     { courseId: "kurs-lei-nl" },
  "price_VGM_NL":     { courseId: "kurs-vgm-nl" },
};

app.post("/stripe/webhook", async (req, res) => {
  const sig = req.headers["stripe-signature"];
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  let event;
  try { event = stripe.webhooks.constructEvent(req.body, sig, secret); }
  catch (err) { console.error("Webhook fout:", err.message); return res.status(400).send(`Webhook Error: ${err.message}`); }
  if (event.type === "checkout.session.completed") {
    const session = event.data.object;
    const email = session.customer_details?.email;
    const lineItems = await stripe.checkout.sessions.listLineItems(session.id);
    for (const item of lineItems.data) {
      const mapping = PRICE_MAP[item.price?.id];
      if (!mapping) { console.warn("Onbekende price_id:", item.price?.id); continue; }
      const activation = new Date().toISOString().slice(0, 10);
      const expiry = new Date(Date.now() + 365*24*60*60*1000).toISOString().slice(0, 10);
      try {
        await run(`INSERT OR REPLACE INTO enrollments (user_email, course_id, stripe_session_id, activation_date, expiry_date) VALUES (?, ?, ?, ?, ?)`, [email, mapping.courseId, session.id, activation, expiry]);
        console.log(`Enrollment granted: ${email} → ${mapping.courseId}`);
      } catch (err) { console.error("Enrollment error:", err.message); }
    }
  }
  res.json({ received: true });
});

app.get("*", (req, res) => res.sendFile(path.join(PUBLIC_DIR, "index.html")));
app.listen(PORT, "0.0.0.0", () => console.log(`DakPro API v2 on port ${PORT}`));
