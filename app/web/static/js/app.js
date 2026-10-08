/* ProfessorAI frontend — plain JavaScript, no build step.
 * Chat history lives in the browser (localStorage); the last turns are sent with each request. */
(() => {
  "use strict";

  // ---------- DOM ----------
  const $ = (id) => document.getElementById(id);
  const el = {
    app: $("app"), sidebar: $("sidebar"), scrim: $("scrim"), menuBtn: $("menuBtn"),
    status: $("status"), subjectList: $("subjectList"), modeList: $("modeList"),
    quizSettings: $("quizSettings"), difficulty: $("difficulty"),
    subjectChip: $("subjectChip"), modeChip: $("modeChip"), scoreChip: $("scoreChip"),
    clearBtn: $("clearBtn"), messages: $("messages"), composer: $("composer"),
    input: $("input"), sendBtn: $("sendBtn"), counter: $("counter"), hint: $("hint"),
  };

  // ---------- State ----------
  const STORAGE_KEY = "professorai.v1";
  const state = {
    config: null,
    subject: "general",
    mode: "normal",
    difficulty: "medium",
    log: [],            // [{role:"student"|"professor", format, answer}] — chat turns only
    busy: false,
    quiz: { score: 0, total: 0, asked: [], current: null },
  };

  const storage = {
    load() {
      try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; } catch { return {}; }
    },
    save() {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({
          subject: state.subject, mode: state.mode, difficulty: state.difficulty,
          log: state.log.slice(-60),
        }));
      } catch { /* storage unavailable — the app still works */ }
    },
  };

  // ---------- API ----------
  class ApiError extends Error {
    constructor(code, message) { super(message); this.code = code; }
  }

  async function api(path, body) {
    let res;
    try {
      res = await fetch(path, body === undefined ? {} : {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch {
      throw new ApiError("NETWORK", "Can't reach the ProfessorAI server. Is it still running?");
    }
    let data = null;
    try { data = await res.json(); } catch { /* non-JSON body */ }
    if (!res.ok) {
      const err = data && data.error;
      throw new ApiError(err?.code || "HTTP_" + res.status, err?.message || "Something went wrong. Please try again.");
    }
    return data;
  }

  // ---------- Helpers ----------
  const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function renderMarkdown(text) {
    if (window.marked && window.DOMPurify) {
      return DOMPurify.sanitize(marked.parse(text, { gfm: true, breaks: false }));
    }
    return `<p style="white-space:pre-wrap">${escapeHtml(text)}</p>`;   // CDN unavailable
  }

  function highlightJson(obj) {
    const json = escapeHtml(JSON.stringify(obj, null, 2));
    return json.replace(
      /(&quot;(?:\\.|[^\\])*?&quot;)(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g,
      (m, str, colon, lit) => {
        if (str) return colon ? `<span class="json-key">${str}</span>${colon}` : `<span class="json-str">${str}</span>`;
        if (lit) return `<span class="json-lit">${m}</span>`;
        return `<span class="json-num">${m}</span>`;
      });
  }

  async function copyText(text, btn) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); } catch { /* ignore */ }
      ta.remove();
    }
    const original = btn.innerHTML;
    btn.classList.add("done"); btn.textContent = "Copied ✓";
    setTimeout(() => { btn.classList.remove("done"); btn.innerHTML = original; }, 1400);
  }

  const COPY_ICON = '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M5 15V5a2 2 0 012-2h10" fill="none" stroke="currentColor" stroke-width="2"/></svg>';

  function scrollToBottom() {
    requestAnimationFrame(() => { el.messages.scrollTop = el.messages.scrollHeight; });
  }

  const subjectName = (id) => state.config?.subjects.find((s) => s.id === id)?.name || id;
  const modeName = (id) => state.config?.modes.find((m) => m.id === id)?.name || id;

  // ---------- Message rendering ----------
  function addMessage(role, bubbleHtml, { actions = [], bubbleClass = "" } = {}) {
    const wrap = document.createElement("div");
    wrap.className = `msg ${role}`;
    wrap.innerHTML = `<div class="msg-role">${role === "student" ? "Student" : "Professor"}</div>
      <div class="bubble ${bubbleClass}">${bubbleHtml}</div>`;
    if (actions.length) {
      const bar = document.createElement("div");
      bar.className = "msg-actions";
      actions.forEach((a) => bar.appendChild(a));
      wrap.appendChild(bar);
    }
    el.messages.appendChild(wrap);
    scrollToBottom();
    return wrap;
  }

  function copyButton(label, getText) {
    const btn = document.createElement("button");
    btn.type = "button"; btn.className = "small-btn";
    btn.innerHTML = `${COPY_ICON} ${label}`;
    btn.addEventListener("click", () => copyText(getText(), btn));
    return btn;
  }

  function renderStudent(text) {
    addMessage("student", escapeHtml(text));
  }

  function renderProfessor(entry) {
    const { format, answer } = entry;
    if (format === "json") {
      const text = JSON.stringify(answer, null, 2);
      addMessage("professor", `<pre class="json-block">${highlightJson(answer)}</pre>`,
        { actions: [copyButton("Copy JSON", () => text)] });
    } else if (entry.mode === "one_word") {
      addMessage("professor", `<div class="one-word">${escapeHtml(answer)}</div>`,
        { actions: [copyButton("Copy", () => answer)] });
    } else if (format === "markdown") {
      addMessage("professor", `<div class="md">${renderMarkdown(answer)}</div>`,
        { actions: [copyButton("Copy", () => answer)] });
    } else {
      addMessage("professor", `<div class="md"><p>${escapeHtml(answer)}</p></div>`,
        { actions: [copyButton("Copy", () => answer)] });
    }
  }

  function showTyping() {
    return addMessage("professor", '<div class="typing" aria-label="Professor is thinking"><span></span><span></span><span></span></div>');
  }

  function showError(err, retry) {
    const node = addMessage("professor", `
      <div class="err-title">
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 7v6M12 16.5v.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        Something went wrong
      </div>
      <p>${escapeHtml(err.message)}</p>`, { bubbleClass: "error-card" });
    if (retry) {
      const btn = document.createElement("button");
      btn.type = "button"; btn.className = "small-btn"; btn.textContent = "↻ Retry";
      btn.addEventListener("click", () => { node.remove(); retry(); });
      node.querySelector(".bubble").appendChild(btn);
    }
    if (["API_KEY_MISSING", "API_KEY_INVALID", "NETWORK"].includes(err.code)) checkHealth();
  }

  function renderWelcome() {
    const node = addMessage("professor", `
      <div class="welcome md">
        <p><strong>Hello! What would you like to learn today?</strong></p>
        <p>Choose a subject and a response mode, then ask me anything — a concept, a piece of code, or exam prep.</p>
        <div class="suggestions"></div>
      </div>`);
    const examples = ["Explain binary search", "What is polymorphism?", "Explain normalization in DBMS",
      "Difference between TCP and UDP", "What is a deadlock?"];
    const box = node.querySelector(".suggestions");
    examples.forEach((q) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "suggestion"; b.textContent = q;
      b.addEventListener("click", () => {
        if (state.mode === "quiz") setMode("normal");
        sendChat(q);
      });
      box.appendChild(b);
    });
  }

  function renderAll() {
    el.messages.innerHTML = "";
    renderWelcome();
    state.log.forEach((e) => (e.role === "student" ? renderStudent(e.answer) : renderProfessor(e)));
  }

  // ---------- Busy state ----------
  function setBusy(busy) {
    state.busy = busy;
    el.sendBtn.disabled = busy || !el.input.value.trim() || el.input.value.length > maxChars();
    el.input.setAttribute("aria-busy", String(busy));
  }
  const maxChars = () => state.config?.limits.max_question_chars || 4000;

  // ---------- Chat ----------
  function historyForApi() {
    const maxTurns = state.config?.limits.max_history_turns || 10;
    const maxLen = state.config?.limits.max_history_text_chars || 2000;
    return state.log.slice(-maxTurns).map((e) => {
      let text = typeof e.answer === "string" ? e.answer : JSON.stringify(e.answer);
      if (text.length > maxLen) text = text.slice(0, maxLen - 1) + "…";
      return { role: e.role, text };
    });
  }

  async function sendChat(question) {
    if (state.busy) return;
    const history = historyForApi();
    renderStudent(question);
    state.log.push({ role: "student", answer: question });
    storage.save();
    await askProfessor(question, history);
  }

  async function askProfessor(question, history) {
    setBusy(true);
    const typing = showTyping();
    try {
      const data = await api("/api/chat", { question, subject: state.subject, mode: state.mode, history });
      typing.remove();
      const entry = { role: "professor", format: data.format, mode: data.mode, answer: data.answer };
      state.log.push(entry);
      storage.save();
      renderProfessor(entry);
      setStatus("connected");
    } catch (err) {
      typing.remove();
      showError(err, () => askProfessor(question, history));
    } finally {
      setBusy(false);
    }
  }

  // ---------- Quiz ----------
  function updateScore() {
    el.scoreChip.textContent = `Score ${state.quiz.score}/${state.quiz.total * 10}`;
  }

  function resetQuiz() {
    state.quiz = { score: 0, total: 0, asked: [], current: null };
    updateScore();
  }

  async function nextQuestion(topic = null) {
    if (state.busy) return;
    setBusy(true);
    const typing = showTyping();
    try {
      const q = await api("/api/quiz/question", {
        subject: state.subject, difficulty: state.difficulty, topic, asked: state.quiz.asked,
      });
      typing.remove();
      state.quiz.asked.push(q.question);
      state.quiz.current = { ...q, answered: false };
      renderQuestion(state.quiz.current);
      setStatus("connected");
    } catch (err) {
      typing.remove();
      showError(err, () => nextQuestion(topic));
    } finally {
      setBusy(false);
      updateHint();
    }
  }

  function renderQuestion(q) {
    const n = state.quiz.asked.length;
    const node = addMessage("professor", `
      <div class="quiz-meta">
        <span class="chip">Question ${n}</span>
        <span class="chip">${escapeHtml(q.topic)}</span>
        <span class="chip">${escapeHtml(q.difficulty)}</span>
      </div>
      <p class="quiz-q">${escapeHtml(q.question)}</p>
      <div class="options"></div>`);
    const box = node.querySelector(".options");
    q.optionButtons = q.options.map((opt, i) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "option-btn";
      b.innerHTML = `<span class="option-letter">${String.fromCharCode(65 + i)}</span><span>${escapeHtml(opt)}</span>`;
      b.addEventListener("click", () => submitQuizAnswer(`${String.fromCharCode(65 + i)}. ${opt}`, b));
      box.appendChild(b);
      return b;
    });
  }

  async function submitQuizAnswer(answer, chosenBtn = null) {
    const q = state.quiz.current;
    if (!q || q.answered || state.busy) return;
    q.answered = true;
    q.optionButtons.forEach((b) => { b.disabled = true; });
    if (chosenBtn) chosenBtn.classList.add("chosen");
    else renderStudent(answer);
    await evaluate(q, answer);
  }

  async function evaluate(q, answer) {
    setBusy(true);
    const typing = showTyping();
    try {
      const r = await api("/api/quiz/evaluate", {
        subject: state.subject, question: q.question, options: q.options, student_answer: answer,
      });
      typing.remove();
      state.quiz.total += 1;
      state.quiz.score += r.score;
      updateScore();
      const node = addMessage("professor", `
        <div class="result-head ${r.correct ? "ok" : "bad"}">
          ${r.correct ? "✓ Correct" : "✗ Not quite"}
          <span class="marks">${r.score}/10 marks</span>
        </div>
        <div class="md">${renderMarkdown(r.feedback)}</div>
        <div class="model-answer"><div class="label">Model answer</div><div class="md">${renderMarkdown(r.model_answer)}</div></div>`);
      const next = document.createElement("button");
      next.type = "button"; next.className = "primary-btn"; next.textContent = "Next question →";
      next.addEventListener("click", () => { next.disabled = true; nextQuestion(); });
      node.querySelector(".bubble").appendChild(next);
    } catch (err) {
      typing.remove();
      showError(err, () => evaluate(q, answer));
    } finally {
      setBusy(false);
      updateHint();
    }
  }

  function startQuiz() {
    resetQuiz();
    addMessage("professor", `<div class="md"><p><strong>Quiz time — ${escapeHtml(subjectName(state.subject))}.</strong>
      I'll ask one question at a time. Click an option or type your answer. Each question is worth 10 marks.</p>
      <p style="color:var(--muted)">Tip: type a topic (e.g. “recursion”) when no question is open to get a question on it.</p></div>`);
    nextQuestion();
  }

  // ---------- Sidebar: subjects, modes, difficulty ----------
  function renderSubjects() {
    el.subjectList.innerHTML = "";
    state.config.subjects.forEach((s) => {
      const li = document.createElement("li");
      const b = document.createElement("button");
      b.type = "button"; b.className = "subject-btn" + (s.id === state.subject ? " active" : "");
      b.textContent = s.name;
      b.setAttribute("aria-pressed", String(s.id === state.subject));
      b.addEventListener("click", () => setSubject(s.id));
      li.appendChild(b);
      el.subjectList.appendChild(li);
    });
  }

  function renderModes() {
    el.modeList.innerHTML = "";
    state.config.modes.forEach((m) => {
      const label = document.createElement("label");
      label.className = "mode-option";
      label.innerHTML = `<input type="radio" name="mode" value="${m.id}" ${m.id === state.mode ? "checked" : ""}>
        <span class="radio"></span><span class="mode-label">${escapeHtml(m.name)}</span>`;
      label.querySelector("input").addEventListener("change", () => setMode(m.id));
      el.modeList.appendChild(label);
    });
  }

  function setSubject(id) {
    if (id === state.subject) return closeDrawer();
    state.subject = id;
    renderSubjects();
    updateChips();
    storage.save();
    closeDrawer();
    if (state.mode === "quiz" && !state.busy) startQuiz();
  }

  function setMode(id) {
    const wasQuiz = state.mode === "quiz";
    state.mode = id;
    const radio = el.modeList.querySelector(`input[value="${id}"]`);
    if (radio) radio.checked = true;
    el.quizSettings.hidden = id !== "quiz";
    el.scoreChip.hidden = id !== "quiz";
    updateChips();
    updateHint();
    storage.save();
    closeDrawer();
    if (id === "quiz" && !wasQuiz) startQuiz();
    if (id !== "quiz" && wasQuiz) state.quiz.current = null;
  }

  function updateChips() {
    el.subjectChip.textContent = subjectName(state.subject);
    el.modeChip.textContent = `Mode: ${modeName(state.mode)}`;
  }

  function updateHint() {
    if (state.mode !== "quiz") {
      el.input.placeholder = "Ask Professor…";
    } else if (state.quiz.current && !state.quiz.current.answered) {
      el.input.placeholder = "Your answer…";
    } else {
      el.input.placeholder = "Type a topic for the next question, or press Next…";
    }
  }

  el.difficulty.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-value]");
    if (!btn) return;
    state.difficulty = btn.dataset.value;
    el.difficulty.querySelectorAll("button").forEach((b) => {
      const on = b === btn;
      b.classList.toggle("active", on);
      b.setAttribute("aria-checked", String(on));
    });
    storage.save();
  });

  function syncDifficultyButtons() {
    el.difficulty.querySelectorAll("button").forEach((b) => {
      const on = b.dataset.value === state.difficulty;
      b.classList.toggle("active", on);
      b.setAttribute("aria-checked", String(on));
    });
  }

  // ---------- Mobile drawer ----------
  function openDrawer() {
    el.app.classList.add("drawer-open"); el.scrim.hidden = false;
    el.menuBtn.setAttribute("aria-expanded", "true");
  }
  function closeDrawer() {
    el.app.classList.remove("drawer-open"); el.scrim.hidden = true;
    el.menuBtn.setAttribute("aria-expanded", "false");
  }
  el.menuBtn.addEventListener("click", () => (el.app.classList.contains("drawer-open") ? closeDrawer() : openDrawer()));
  el.scrim.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });

  // ---------- Health ----------
  const STATUS_TEXT = {
    connected: '<span class="hide-sm">Gemini </span>Connected',
    not_configured: '<span class="hide-sm">API </span>Key not set',
    error: '<span class="hide-sm">Gemini </span>Key error',
    offline: "Offline",
  };
  function setStatus(s) {
    el.status.className = `status ${s}`;
    el.status.querySelector(".status-label").innerHTML = STATUS_TEXT[s] || escapeHtml(s);
  }
  async function checkHealth() {
    try {
      const h = await api("/api/health");
      setStatus(h.gemini);
      el.status.title = `Model: ${h.model}`;
    } catch {
      setStatus("offline");
    }
  }

  // ---------- Composer ----------
  function autoGrow() {
    el.input.style.height = "auto";
    el.input.style.height = Math.min(el.input.scrollHeight, 200) + "px";
  }
  function updateCounter() {
    const n = el.input.value.length;
    el.counter.textContent = `${n} / ${maxChars()}`;
    el.counter.classList.toggle("over", n > maxChars());
    setBusy(state.busy);
  }
  el.input.addEventListener("input", () => { autoGrow(); updateCounter(); });
  el.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      el.composer.requestSubmit();
    }
  });

  el.composer.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = el.input.value.trim();
    if (!text || state.busy || text.length > maxChars()) return;
    el.input.value = ""; autoGrow(); updateCounter();

    if (state.mode === "quiz") {
      const q = state.quiz.current;
      if (q && !q.answered) submitQuizAnswer(text);
      else { renderStudent(text); nextQuestion(text); }
      return;
    }
    sendChat(text);
  });

  el.clearBtn.addEventListener("click", () => {
    if (state.busy) return;
    state.log = [];
    storage.save();
    renderAll();
    if (state.mode === "quiz") startQuiz();
  });

  // ---------- Boot ----------
  async function init() {
    const saved = storage.load();
    checkHealth();
    try {
      state.config = await api("/api/config");
    } catch (err) {
      setStatus("offline");
      showError(err, () => location.reload());
      return;
    }
    const subjectIds = state.config.subjects.map((s) => s.id);
    const modeIds = state.config.modes.map((m) => m.id);
    state.subject = subjectIds.includes(saved.subject) ? saved.subject : state.config.default_subject;
    state.mode = modeIds.includes(saved.mode) ? saved.mode : state.config.default_mode;
    state.difficulty = ["easy", "medium", "hard"].includes(saved.difficulty) ? saved.difficulty : "medium";
    state.log = Array.isArray(saved.log) ? saved.log : [];

    renderSubjects();
    renderModes();
    syncDifficultyButtons();
    renderAll();
    const startMode = state.mode;
    state.mode = "normal";
    setMode(startMode);    // also starts the quiz if the saved mode was quiz
    updateCounter();
    el.input.focus();
  }

  init();
})();
