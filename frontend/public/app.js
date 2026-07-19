// DakPro Academy — app.js v2
// ─────────────────────────────────────────────────────────────
// Pas API_BASE aan naar jouw Codespaces URL!
// const API_BASE = "https://[jouw-naam]-3000.app.github.dev";
// ─────────────────────────────────────────────────────────────
const API_BASE = "";

// Stripe Payment Links — vervang met je echte links na Stripe setup
const BUY_URLS = {
  "kurs-roofing-nl": "https://buy.stripe.com/test_placeholder_roofing",
  "kurs-lei-nl":     "https://buy.stripe.com/test_placeholder_lei",
  "kurs-vgm-nl":     "https://buy.stripe.com/test_placeholder_vgm",
};

// Echte projectfoto's als cursusbanners (jouw eigen foto's!)
const BANNER_IMAGES = {
  "kurs-roofing-nl": "/images/thumb_plat-overzicht.jpg",
  "kurs-lei-nl":     "/images/thumb_leien-eindresultaat.jpg",
  "kurs-vgm-nl":     null,
};

const BANNER_FALLBACK = {
  "kurs-roofing-nl": "",
  "kurs-lei-nl":     "slate",
  "kurs-vgm-nl":     "green",
};

// ── State ─────────────────────────────────────────────────────
let state = {
  email: localStorage.getItem("dakpro_email") || null,
  courses: [],
  currentCourse: null,
  currentCourseData: null,
  currentLesson: null,
  openStageIdx: 0,
  examAnswers: {},
};

// ── API ───────────────────────────────────────────────────────
async function api(path, options = {}) {
  const res = await fetch(API_BASE + path, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

// ── Screen / Tab ──────────────────────────────────────────────
function showScreen(id) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  const el = document.getElementById("screen-" + id);
  if (el) el.classList.add("active");
  window.scrollTo(0, 0);
}

function switchTabActive(tab) {
  document.querySelectorAll(".tab-item").forEach(t => t.classList.remove("active"));
  const el = document.getElementById("tab-" + tab);
  if (el) el.classList.add("active");
}

function switchTab(tab) {
  switchTabActive(tab);
  if (tab === "catalog") renderCatalog();
  if (tab === "profile") renderProfile();
}

// ── Toast ─────────────────────────────────────────────────────
function toast(msg, type = "") {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = "toast show " + type;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => (t.className = "toast " + type), 2600);
}

// ── Login ─────────────────────────────────────────────────────
function handleLogin() {
  const input = document.getElementById("login-email");
  const email = input.value.trim().toLowerCase();
  if (!email || !email.includes("@")) { toast("Voer een geldig e-mailadres in", "error"); return; }
  state.email = email;
  localStorage.setItem("dakpro_email", email);
  document.getElementById("topbar-email").textContent = email;
  renderCatalog();
}

function handleLogout() {
  localStorage.removeItem("dakpro_email");
  state.email = null;
  state.courses = [];
  document.getElementById("topbar-email").textContent = "Inloggen";
  showScreen("login");
}

// ── Catalog ───────────────────────────────────────────────────
async function renderCatalog() {
  showScreen("catalog");
  switchTabActive("catalog");
  const container = document.getElementById("catalog-list");
  container.innerHTML = `<div class="loading"><div class="spinner"></div><div class="loading-text">Cursussen laden...</div></div>`;
  try {
    const courses = await api(`/catalog-with-access?email=${encodeURIComponent(state.email)}`);
    state.courses = courses;
    renderCatalogCards(courses);
  } catch (err) {
    container.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠</div><div class="empty-title">Kan cursussen niet laden</div><div class="empty-sub">${err.message}</div></div>`;
  }
}

function renderCatalogCards(courses) {
  const container = document.getElementById("catalog-list");
  if (!courses.length) {
    container.innerHTML = `<div class="empty-state"><div class="empty-icon">📚</div><div class="empty-title">Geen cursussen gevonden</div></div>`;
    return;
  }
  container.innerHTML = `<div class="section-label">Mijn cursussen</div>` +
    courses.map(c => {
      const access = c.access;
      const tagClass = access === "active" ? "tag-active" : "tag-preview";
      const tagLabel = access === "active" ? "Actief" : "Voorbeeld";
      const priceFmt = "€\u00a0" + (c.price_eur / 100).toFixed(0) + ",—";
      const bgImg = BANNER_IMAGES[c.id];
      const bannerStyle = bgImg
        ? `style="background-image:url('${bgImg}');background-size:cover;background-position:center;"`
        : "";
      const bannerClass = BANNER_FALLBACK[c.id] || "";
      return `
        <div class="course-card" onclick="openCourse('${c.id}')">
          <div class="course-banner ${bannerClass}" ${bannerStyle}>
            <span class="banner-tag ${tagClass}">${tagLabel}</span>
          </div>
          <div class="course-body">
            <div class="course-title">${c.title}</div>
            <div class="course-sub">${c.description || ""}</div>
            <div class="course-meta">
              <span>${c.lesson_count} lessen</span>
              <span>${access === "active" ? c.progress_pct + "% voltooid" : priceFmt}</span>
            </div>
            ${access === "active" ? `<div class="progress-bar"><div class="progress-fill" style="width:${c.progress_pct}%"></div></div>` : ""}
          </div>
        </div>`;
    }).join("");
}

// ── Course ────────────────────────────────────────────────────
async function openCourse(courseId) {
  const course = state.courses.find(c => c.id === courseId);
  state.currentCourse = course;
  state.openStageIdx = 0;
  document.getElementById("course-header-title").textContent = course ? course.title : courseId;
  const container = document.getElementById("stage-list");
  container.innerHTML = `<div class="loading"><div class="spinner"></div><div class="loading-text">Inhoud laden...</div></div>`;
  showScreen("course");
  try {
    const data = await api(`/courses/${courseId}/stages?email=${encodeURIComponent(state.email)}`);
    state.currentCourseData = data;
    renderStageList(data);
  } catch (err) {
    container.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠</div><div class="empty-title">${err.message}</div></div>`;
  }
}

function renderStageList(data) {
  const container = document.getElementById("stage-list");
  container.innerHTML = "";
  data.stages.forEach((stage, si) => {
    const div = document.createElement("div");
    div.className = "stage-item";
    const isOpen = si === state.openStageIdx;
    const allLocked = stage.lessons.every(l => !l.accessible);
    div.innerHTML = `
      <div class="stage-header" onclick="toggleStage(${si})">
        <div class="stage-num ${allLocked ? "locked" : ""}">${stage.position}</div>
        <div class="stage-info">
          <div class="stage-name">${stage.title}</div>
          <div class="stage-lessons">${stage.lessons.length} lessen</div>
        </div>
        <div class="stage-chevron">${isOpen ? "▲" : "▼"}</div>
      </div>
      ${isOpen ? renderLessonRows(stage.lessons) : ""}`;
    container.appendChild(div);
  });
  if (!data.has_access) {
    const course = state.currentCourse;
    const priceFmt = course ? "€\u00a0" + (course.price_eur / 100).toFixed(0) + ",—" : "";
    const pw = document.createElement("div");
    pw.innerHTML = `
      <div class="paywall-wrapper">
        <div class="paywall-card">
          <div class="paywall-title">Volledige toegang</div>
          <div class="paywall-price">${priceFmt}</div>
          <div class="paywall-per">Eenmalige betaling · 12 maanden toegang</div>
          <ul class="paywall-features">
            <li><span class="check">✓</span> Alle modules en lessen</li>
            <li><span class="check">✓</span> Tussentoetsen na elke module</li>
            <li><span class="check">✓</span> Eindexamen met officieel certificaat</li>
            <li><span class="check">✓</span> Toegang op alle apparaten (PWA)</li>
          </ul>
          <button class="btn btn-primary btn-full" onclick="goToBuy('${course ? course.id : ""}')">Nu kopen via Stripe</button>
        </div>
      </div>`;
    container.appendChild(pw);
  }
}

function renderLessonRows(lessons) {
  const iconMap  = { video: "▶", text: "📄", quiz: "✏", exam: "📋" };
  const classMap = { video: "icon-video", text: "icon-text", quiz: "icon-quiz", exam: "icon-exam" };
  return `<div class="lesson-items">${lessons.map(l => {
    const locked = !l.accessible;
    const badge  = locked ? "locked" : l.completed ? "done" : l.is_free_preview ? "free" : "current";
    const labels = { locked: "Vergrendeld", done: "Voltooid", free: "Gratis", current: "" };
    const cls    = { locked: "badge-locked", done: "badge-done", free: "badge-free", current: "badge-current" };
    return `<div class="lesson-row ${locked ? "locked-row" : ""}" onclick="${locked ? "showLockedMsg()" : `openLesson('${l.id}')`}">
      <div class="lesson-icon ${classMap[l.type]}">${iconMap[l.type]}</div>
      <div class="lesson-info">
        <div class="lesson-name">${l.title}</div>
        <div class="lesson-meta">${l.duration_min > 0 ? l.duration_min + " min" : "Leestekst"}${l.attempts_used > 0 ? ` · ${l.attempts_used} poging(en)` : ""}</div>
      </div>
      ${labels[badge] ? `<span class="lesson-badge ${cls[badge]}">${labels[badge]}</span>` : ""}
    </div>`;
  }).join("")}</div>`;
}

function toggleStage(si) {
  state.openStageIdx = state.openStageIdx === si ? -1 : si;
  renderStageList(state.currentCourseData);
}

function showLockedMsg() { toast("Koop de cursus om toegang te krijgen", "error"); }

function goToBuy(courseId) {
  const url = BUY_URLS[courseId];
  if (url && !url.includes("placeholder")) window.open(url, "_blank");
  else toast("Stripe link nog niet ingesteld (zie BUY_URLS in app.js)");
}

// ── Lesson ────────────────────────────────────────────────────
async function openLesson(lessonId) {
  document.getElementById("lesson-content").innerHTML = `<div class="loading"><div class="spinner"></div><div class="loading-text">Les laden...</div></div>`;
  showScreen("lesson");
  try {
    const lesson = await api(`/lessons/${lessonId}?email=${encodeURIComponent(state.email)}`);
    state.currentLesson = lesson;
    renderLesson(lesson);
  } catch (err) {
    document.getElementById("lesson-content").innerHTML = `<div class="empty-state"><div class="empty-icon">🔒</div><div class="empty-title">Geen toegang</div><div class="empty-sub">${err.message}</div></div>`;
  }
}

// Rendert les-inhoud: markdown (nieuwe lessen) of HTML (seed) -> veilige HTML.
// marked verwerkt markdown; bestaande HTML-blokken laat het ongemoeid.
function renderContent(raw) {
  if (!raw) return "";
  try {
    var html = (typeof marked !== "undefined")
      ? marked.parse(raw, { gfm: true, breaks: false })
      : raw;
    if (typeof DOMPurify !== "undefined") {
      html = DOMPurify.sanitize(html, { ADD_ATTR: ["target"] });
    }
    return html;
  } catch (e) {
    return raw;
  }
}

function renderLesson(lesson) {
  document.getElementById("lesson-title").textContent = lesson.title;
  const area = document.getElementById("lesson-content");
  if (lesson.type === "video") {
    area.innerHTML = `<div class="content-area">
      <div class="video-block">
        <div class="play-btn" onclick="toast('Video wordt afgespeeld...')">
          <svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg>
        </div>
        <div class="video-duration">${lesson.duration_min} min</div>
      </div>
      ${lesson.content ? `<div class="lesson-text">${renderContent(lesson.content)}</div>` : ""}
      <div style="margin-top:20px;"><button class="btn btn-primary btn-full" onclick="completeLesson('${lesson.id}')">Les voltooid ✓</button></div>
    </div>`;
  } else if (lesson.type === "text") {
    area.innerHTML = `<div class="content-area">
      <div class="lesson-text">${renderContent(lesson.content)}</div>
      <div style="margin-top:20px;"><button class="btn btn-primary btn-full" onclick="completeLesson('${lesson.id}')">Les gelezen ✓</button></div>
    </div>`;
  } else if (lesson.type === "quiz") {
    renderQuizLesson(lesson);
  } else if (lesson.type === "exam") {
    renderExamLesson(lesson);
  }
}

async function completeLesson(lessonId) {
  try {
    await api(`/lessons/${lessonId}/complete`, { method: "POST", body: JSON.stringify({ email: state.email }) });
    toast("Les voltooid!", "success");
    setTimeout(() => backToCourse(), 800);
  } catch (err) { toast(err.message, "error"); }
}

// ── Quiz ──────────────────────────────────────────────────────
let quizState = { selected: null, submitted: false, qIndex: 0, allAnswers: {} };

function renderQuizLesson(lesson) {
  quizState = { selected: null, submitted: false, qIndex: 0, allAnswers: {} };
  renderQuizQuestion(lesson, 0);
}

function renderQuizQuestion(lesson, qi) {
  const q = lesson.questions[qi];
  const area = document.getElementById("lesson-content");
  const attLeft = Math.max(0, 2 - (lesson.attempts_used || 0));
  area.innerHTML = `<div class="content-area"><div class="quiz-card">
    <div class="quiz-label">Tussentoets</div>
    <div class="quiz-progress">Vraag ${qi+1} van ${lesson.questions.length}</div>
    <div class="quiz-question">${q.question}</div>
    <div class="quiz-options">
      ${["option_a","option_b","option_c","option_d"].map((k,i) =>
        `<div class="quiz-option" id="opt-${i}" onclick="selectQuizOption(${i})">
          <div class="option-letter">${String.fromCharCode(65+i)}</div><span>${q[k]}</span>
        </div>`).join("")}
    </div>
    <div class="quiz-footer">
      <span class="attempts-badge">${attLeft} pogingen resterend</span>
      <button class="btn btn-primary btn-sm" id="quiz-submit-btn" onclick="submitQuizAnswer(${qi},'${lesson.id}')" disabled>Bevestigen</button>
    </div>
  </div></div>`;
  quizState.selected = null; quizState.submitted = false;
}

function selectQuizOption(i) {
  if (quizState.submitted) return;
  quizState.selected = i;
  document.querySelectorAll(".quiz-option").forEach((el,idx) => el.classList.toggle("selected", idx===i));
  document.getElementById("quiz-submit-btn").disabled = false;
}

function submitQuizAnswer(qi, lessonId) {
  const lesson = state.currentLesson;
  const q = lesson.questions[qi];
  if (quizState.selected === null) return;
  quizState.submitted = true;
  quizState.allAnswers[q.id] = quizState.selected;
  const correct = q.correct_index;
  document.querySelectorAll(".quiz-option").forEach((el,i) => {
    el.classList.remove("selected"); el.classList.add("disabled");
    if (i===correct) el.classList.add("correct");
    else if (i===quizState.selected) el.classList.add("wrong");
  });
  const btn = document.getElementById("quiz-submit-btn");
  btn.textContent = quizState.selected===correct ? "✓ Goed!" : "✗ Fout";
  btn.disabled = true;
  if (qi === lesson.questions.length-1) {
    setTimeout(() => submitFullQuiz(lesson), 1200);
  } else {
    setTimeout(() => { quizState.qIndex++; renderQuizQuestion(lesson, quizState.qIndex); }, 1200);
  }
}

async function submitFullQuiz(lesson) {
  try {
    const result = await api("/quiz/submit", { method:"POST", body: JSON.stringify({ email: state.email, lesson_id: lesson.id, answers: quizState.allAnswers }) });
    toast(result.passed ? `Geslaagd! Score: ${result.score}%` : `Score: ${result.score}% — min. 70% nodig`, result.passed ? "success" : "error");
    setTimeout(() => backToCourse(), 1500);
  } catch (err) { toast(err.message, "error"); }
}

// ── Exam ──────────────────────────────────────────────────────
function renderExamLesson(lesson) {
  state.examAnswers = {};
  const area = document.getElementById("lesson-content");
  area.innerHTML = `<div class="content-area">
    <div class="exam-intro">
      <div class="exam-intro-icon">📋</div>
      <div class="exam-intro-title">Eindexamen</div>
      <div class="exam-intro-sub">${lesson.questions.length} vragen · minimaal 70% · 1 poging</div>
    </div>
    ${lesson.questions.map((q,qi) => `
      <div class="exam-q">
        <div class="exam-q-num">Vraag ${qi+1} van ${lesson.questions.length}</div>
        <div class="exam-q-text">${q.question}</div>
        <div class="exam-options">
          ${["option_a","option_b","option_c","option_d"].map((k,i) =>
            `<div class="exam-opt" id="exam-${qi}-${i}" onclick="selectExamOpt('${q.id}',${qi},${i})">
              <span style="font-weight:600;color:var(--accent);min-width:16px;">${String.fromCharCode(65+i)}.</span>
              <span>${q[k]}</span>
            </div>`).join("")}
        </div>
      </div>`).join("")}
    <button class="btn btn-primary btn-full" style="margin-top:8px;" onclick="submitExam()">Examen indienen</button>
  </div>`;
}

function selectExamOpt(qId, qi, optIdx) {
  state.examAnswers[qId] = optIdx;
  for (let i=0; i<4; i++) {
    const el = document.getElementById(`exam-${qi}-${i}`);
    if (el) el.classList.toggle("selected", i===optIdx);
  }
}

async function submitExam() {
  const lesson = state.currentLesson;
  if (Object.keys(state.examAnswers).length < lesson.questions.length) {
    toast(`Beantwoord alle ${lesson.questions.length} vragen eerst`, "error"); return;
  }
  try {
    const result = await api("/quiz/submit", { method:"POST", body: JSON.stringify({ email: state.email, lesson_id: lesson.id, answers: state.examAnswers }) });
    showExamResult(result);
  } catch (err) { toast(err.message, "error"); }
}

function showExamResult(result) {
  showScreen("result");
  const courseName = state.currentCourse ? state.currentCourse.title : "Cursus";
  const today = new Date().toLocaleDateString("nl-NL", { year:"numeric", month:"long", day:"numeric" });
  const name = state.email ? state.email.split("@")[0].replace(/\./g," ") : "";
  document.getElementById("result-screen").innerHTML = `<div class="result-screen">
    <div class="result-icon">${result.passed ? "🎉" : "😔"}</div>
    <div class="result-score">${result.score}%</div>
    <div class="result-label">${result.correct} van ${result.total} correct</div>
    <div class="${result.passed ? "result-pass" : "result-fail"}">${result.passed ? "Geslaagd!" : "Gezakt — probeer na meer studie"}</div>
    ${result.passed ? `
      <div class="cert-block">
        <div class="cert-header">Certificaat van deelname</div>
        <div class="cert-name">${name}</div>
        <div class="cert-course">${courseName} — DakPro Academy</div>
        <div class="cert-date">Behaald op ${today}</div>
      </div>
      <button class="btn btn-green btn-full" style="margin-bottom:10px;" onclick="downloadCertificaat('${name}', '${courseName}', '${today}')"">Certificaat downloaden</button>` : ""}
    <button class="btn btn-secondary btn-full" onclick="goHome()">Terug naar cursussen</button>
  </div>`;
}

// ── Navigation ────────────────────────────────────────────────
function backToCourse() { if (state.currentCourse) openCourse(state.currentCourse.id); else renderCatalog(); }
function backToStages() { showScreen("course"); }
function goHome() { renderCatalog(); }

// ── Profile ───────────────────────────────────────────────────
async function renderProfile() {
  showScreen("profile");
  switchTabActive("profile");
  const courses = state.courses;
  const active = courses.filter(c => c.access==="active");
  const totalPct = active.length ? Math.round(active.reduce((s,c) => s+c.progress_pct,0)/active.length) : 0;
  const diplomas = active.filter(c => c.progress_pct===100).length;
  const initials = state.email ? state.email.slice(0,2).toUpperCase() : "??";
  document.getElementById("profile-screen").innerHTML = `
    <div class="profile-card">
      <div class="avatar">${initials}</div>
      <div class="profile-name">${state.email}</div>
      <div class="profile-email">DakPro Academy student</div>
      <div class="stat-row">
        <div class="stat-box"><div class="stat-val">${active.length}</div><div class="stat-lbl">Cursussen</div></div>
        <div class="stat-box"><div class="stat-val">${totalPct}%</div><div class="stat-lbl">Voortgang</div></div>
        <div class="stat-box"><div class="stat-val">${diplomas}</div><div class="stat-lbl">Diploma's</div></div>
      </div>
    </div>
    <div class="section-label">Mijn inschrijvingen</div>
    ${courses.map(c => `
      <div class="enrolled-item" onclick="openCourse('${c.id}')">
        <div class="e-dot ${c.access==="active"?"active":"preview"}"></div>
        <div class="e-info">
          <div class="e-name">${c.title}</div>
          <div class="e-prog">${c.access==="active"?c.progress_pct+"% voltooid · Actief":"Voorbeeld — toegang kopen"}</div>
        </div>
        <div class="e-arrow">›</div>
      </div>`).join("")}
    <div style="padding:18px 14px;">
      <button class="btn btn-secondary btn-full" onclick="handleLogout()">Uitloggen</button>
    </div>`;
}

// ── PWA ───────────────────────────────────────────────────────
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}

// ── Init ──────────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", () => {
  if (state.email) {
    document.getElementById("topbar-email").textContent = state.email;
    renderCatalog();
  } else {
    showScreen("login");
  }
});
