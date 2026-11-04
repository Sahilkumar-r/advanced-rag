// ragx PWA. No framework, no build step. All user and model text goes in through textContent, never innerHTML (strict CSP and XSS safety).
const NS = "http://www.w3.org/2000/svg";
const ICONS = {
  send: "M22 2 11 13M22 2l-7 20-4-9-9-4z", mic: "M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3zM19 10v2a7 7 0 0 1-14 0v-2M12 19v3",
  clip: "m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48",
  moon: "M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z", sun: "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4",
  up: "M7 10v12M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88z",
  copy: "M9 9h11v11H9zM5 15H4V4h11v1", trash: "M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6", x: "M18 6 6 18M6 6l12 12",
  book: "M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 19.5V4.5A2.5 2.5 0 0 1 6.5 2H20v15H6.5A2.5 2.5 0 0 0 4 19.5z", chat: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  clock: "M12 6v6l4 2M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z", db: "M12 8c4.97 0 9-1.34 9-3s-4.03-3-9-3-9 1.34-9 3 4.03 3 9 3zM3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3",
  sliders: "M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6", shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
};
const $ = (s, r = document) => r.querySelector(s);
const tidy = (s) => (s || "").replace(/\s*\{\s*#[^}]*\}/g, "").replace(/`/g, ""); // upstream headings carry { #anchor } fragments and backticks

function h(tag, props, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat(2)) if (kid != null && kid !== false) e.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  return e;
}
function icon(name, cls = "") {
  const s = document.createElementNS(NS, "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("class", "i " + cls); s.setAttribute("aria-hidden", "true");
  const p = document.createElementNS(NS, "path"); p.setAttribute("d", ICONS[name]); s.append(p);
  return s;
}
const store = (area) => ({
  get(k, d) { try { const v = area.getItem(k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { area.setItem(k, JSON.stringify(v)); } catch { /* private mode or full: the app still works without it */ } },
  del(k) { try { area.removeItem(k); } catch { /* ignore */ } },
});
const local = store(window.localStorage), session = store(window.sessionStorage);

const S = { access: null, refresh: null, me: null, chat: null, busy: false, image: null, rec: null };
let settings = { theme: "dark", speak: false, voice: "", ...local.get("ragx.settings", {}) };

// ---- banner and theme --------------------------------------------------
const banner = (msg) => { const b = $("#banner"); b.textContent = msg; b.hidden = !msg; };
function applyTheme() {
  const t = settings.theme === "system" ? (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark") : settings.theme;
  document.documentElement.dataset.theme = t;
  const btn = $("#theme-btn"); btn.replaceChildren(icon(t === "dark" ? "sun" : "moon"));
  btn.setAttribute("aria-label", t === "dark" ? "Switch to light theme" : "Switch to dark theme");
  $('meta[name="theme-color"]').setAttribute("content", t === "dark" ? "#020617" : "#f8fafc");
}
const saveSettings = () => { local.set("ragx.settings", settings); applyTheme(); };

// ---- api ---------------------------------------------------------------
class ApiError extends Error { constructor(status, detail) { super(detail); this.status = status; } }
let refreshing = null;
async function refreshTokens() {
  if (!S.refresh) return false;
  refreshing ||= fetch("/api/auth/refresh", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh: S.refresh }) })
    .then(async (r) => { if (!r.ok) return false; const d = await r.json(); setTokens(d.access, d.refresh); return true; }).catch(() => false).finally(() => { refreshing = null; });
  return refreshing;
}
function setTokens(access, refresh) { S.access = access; S.refresh = refresh || null; session.set("ragx.tok", { access, refresh: S.refresh }); }
async function api(path, { method = "GET", json, form, retry = true } = {}) {
  const headers = {}; let body;
  if (S.access) headers.Authorization = "Bearer " + S.access;
  if (json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(json); } else if (form) body = form;
  let res;
  try { res = await fetch(path, { method, headers, body }); } catch { throw new ApiError(0, "offline"); }
  if (res.status === 401 && retry && S.refresh && await refreshTokens()) return api(path, { method, json, form, retry: false });
  if (res.status === 401 && !S.access) throw new ApiError(401, "unauthorized"); // a failed sign in, not an expired session
  if (res.status === 401) { signOut("Your session ended. Sign in again."); throw new ApiError(401, "expired"); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, typeof data.detail === "string" ? data.detail : res.statusText);
  return data;
}
function friendly(e) {
  const m = { 0: "You are offline or the server cannot be reached. Your question was not sent.", 429: "Too many requests. Wait a minute and try again.", 503: "The answer service is busy right now. Try again in a moment.",
    413: "That file is too large. Use a PNG, JPEG or WebP up to 4 MB.", 415: "That file type is not supported. Use a PNG, JPEG or WebP.", 403: "Your account cannot do that." };
  return m[e.status] || `Something went wrong (code ${e.status ?? "unknown"}).`;
}
window.addEventListener("offline", () => banner("You are offline. You can read earlier chats, but new questions need a connection."));
window.addEventListener("online", () => banner(""));

// ---- routing -----------------------------------------------------------
const main = $("#main");
const can = (p) => S.me && S.me.permissions.includes(p);
function tabsFor() {
  const t = [["chat", "Chat", "chat"]];
  if (can("view_history")) t.push(["history", "History", "clock"]);
  if (can("manage_memory")) t.push(["memory", "Memory", "db"]);
  t.push(["settings", "Settings", "sliders"]);
  if (can("view_metrics") || can("manage_users")) t.push(["admin/" + (can("manage_users") ? "users" : "evals"), "Admin", "shield"]);
  return t;
}
function renderTabs(route) {
  const nav = $("#tabs"); nav.hidden = !S.me;
  nav.replaceChildren(...tabsFor().map(([r, label, ic]) => h("a", { href: "#/" + r, "aria-current": route.split("/")[0] === r.split("/")[0] ? "page" : null }, icon(ic), label)));
}
function route() {
  const r = (location.hash.replace(/^#\/?/, "") || "chat");
  $("#who").textContent = S.me ? (S.me.guest ? "guest" : S.me.email) : "";
  if (!S.me) { renderTabs(""); return viewLogin(); }
  renderTabs(r);
  main.className = ""; main.replaceChildren();
  const view = { chat: viewChat, history: viewHistory, memory: viewMemory, settings: viewSettings }[r.split("/")[0]];
  if (r.startsWith("admin")) return viewAdmin(r.split("/")[1] || "users");
  (view || viewChat)();
  main.focus({ preventScroll: true });
}
window.addEventListener("hashchange", route);
function signOut(msg) {
  if (S.refresh) fetch("/api/auth/logout", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh: S.refresh }) }).catch(() => {});
  S.access = S.refresh = S.me = S.chat = null; session.del("ragx.tok");
  route(); if (msg) banner(msg);
}

// ---- login -------------------------------------------------------------
function viewLogin() {
  main.className = ""; const err = h("div", { class: "err", id: "login-err", role: "alert" });
  const email = h("input", { class: "input", id: "email", type: "email", autocomplete: "username", required: true });
  const pw = h("input", { class: "input", id: "pw", type: "password", autocomplete: "current-password", required: true });
  const submit = async (ev) => {
    ev.preventDefault(); err.textContent = "";
    try { const d = await api("/api/auth/login", { method: "POST", json: { email: email.value, password: pw.value } }); setTokens(d.access, d.refresh); await start(); banner(""); }
    catch (e) { err.textContent = e.status === 401 ? "Email or password is not right." : e.status === 429 ? "Too many attempts. Wait a minute." : friendly(e); }
  };
  const guest = async () => { try { const d = await api("/api/auth/guest", { method: "POST" }); setTokens(d.access, null); await start(); banner(""); } catch (e) { err.textContent = friendly(e); } };
  main.replaceChildren(
    h("h2", { text: "Sign in" }),
    h("p", { class: "note", text: "Ask questions about the FastAPI and Pydantic docs. Every answer shows the pages it came from." }),
    h("form", { onsubmit: submit, novalidate: false },
      h("div", { class: "field" }, h("label", { for: "email", text: "Email" }), email),
      h("div", { class: "field" }, h("label", { for: "pw", text: "Password" }), pw),
      err, h("div", { class: "row" }, h("button", { class: "btn primary", type: "submit", text: "Sign in" }), h("button", { class: "btn", type: "button", onclick: guest, text: "Continue as guest" }))),
    h("p", { class: "note", text: "Demo accounts are for testing. Guests get a lower rate limit and no memory. Answers can be wrong, so check the source. This runs on free tier models, so replies can be slow." }));
  email.focus();
}

// ---- rendering text ----------------------------------------------------
function copyText(text, btn) {
  const done = () => { const old = btn.textContent; btn.textContent = "Copied"; setTimeout(() => (btn.textContent = old), 1500); };
  (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(done).catch(() => { btn.textContent = "Copy failed"; });
}
function inline(text, details) {
  const out = [];
  for (const part of text.split(/(`[^`\n]+`|\*\*[^*\n]+\*\*|(?:\[\d+\])+)/)) {
    if (!part) continue;
    if (part.startsWith("`")) out.push(h("code", { text: part.slice(1, -1) }));
    else if (part.startsWith("**")) out.push(h("strong", { text: part.slice(2, -2) }));
    else if (/^\[\d+\]/.test(part)) for (const n of part.match(/\d+/g)) {
      const d = details && details[+n - 1];
      out.push(d ? h("button", { class: "cite", type: "button", "aria-label": `Open source ${n}: ${tidy(d.heading) || d.doc}`, onclick: () => openSource(d) }, `[${n}]`) : `[${n}]`);
    } else out.push(part);
  }
  return out;
}
function renderText(text, details) {
  const frag = document.createDocumentFragment();
  text.split("```").forEach((part, i) => {
    if (i % 2 === 1) {
      const code = part.replace(/^[A-Za-z0-9_+.-]*\n/, "").replace(/\n$/, "");
      const copy = h("button", { class: "btn small copy", type: "button", "aria-label": "Copy code" }, "Copy"); copy.addEventListener("click", () => copyText(code, copy));
      frag.append(h("div", { class: "code" }, copy, h("pre", {}, h("code", { text: code }))));
      return;
    }
    for (const block of part.split(/\n{2,}/)) {
      const lines = block.split("\n").filter((l) => l.trim());
      if (!lines.length) continue;
      if (lines.every((l) => /^\s*([-*]|\d+\.)\s+/.test(l))) frag.append(h("ul", {}, lines.map((l) => h("li", {}, inline(l.replace(/^\s*([-*]|\d+\.)\s+/, ""), details)))));
      else frag.append(h("p", {}, lines.flatMap((l, k) => (k ? [h("br"), ...inline(l, details)] : inline(l, details)))));
    }
  });
  return frag;
}
const stepText = (s) => {
  const fixed = { retrieve: "Searched the docs", generate: "Wrote the answer from the top sources", rewrite: "Rewrote the question and searched again" };
  if (fixed[s]) return fixed[s];
  let r;
  if ((r = /^need_retrieval=(\w+)/.exec(s))) return r[1] === "True" ? "Checked that the question is about FastAPI or Pydantic" : "Decided the question is off topic";
  if ((r = /^relevant=(\d+)\/(\d+)/.exec(s))) return `Kept ${r[1]} of ${r[2]} sources as relevant`;
  if ((r = /^supported=(\w+) useful=(\w+)/.exec(s))) return `Checked the answer against its sources (supported: ${r[1]}, useful: ${r[2]})`;
  if (s.startsWith("retrieved_injection")) return "Dropped a source that contained instructions";
  return s;
};
const REASONS = { prompt_injection: "That looked like an instruction aimed at the assistant, so it was not sent.", too_long: "That question is too long. Shorten it and try again.",
  image_prompt_injection: "That image contained text that looked like instructions to the assistant, so it was not used.", unreadable: "I could not read anything useful in that image." };

// ---- source drawer -----------------------------------------------------
function openSource(d) {
  let dlg = $("#drawer"); dlg?.remove();
  const safe = d.url && /^https?:\/\//.test(d.url);
  dlg = h("dialog", { id: "drawer", "aria-labelledby": "drawer-title" },
    h("div", { class: "row space" }, h("h2", { id: "drawer-title", text: tidy(d.heading) || d.doc }), h("button", { class: "btn icon", type: "button", "aria-label": "Close source", onclick: () => dlg.close() }, icon("x"))),
    h("p", { class: "note mono", text: `Source ${d.n} from ${d.doc}` }), h("pre", { text: d.text }),
    safe ? h("p", {}, h("a", { href: d.url, target: "_blank", rel: "noopener noreferrer", text: "Open the original page" })) : null);
  dlg.addEventListener("close", () => dlg.remove()); document.body.append(dlg); dlg.showModal();
}

// ---- chat --------------------------------------------------------------
const chats = () => local.get("ragx.chats", []);
function saveChat() {
  if (!S.chat || !S.chat.messages.length) return;
  const all = chats().filter((c) => c.id !== S.chat.id); all.unshift(S.chat);
  local.set("ragx.chats", all.slice(0, 50));
}
const newChat = () => (S.chat = { id: crypto.randomUUID().replace(/-/g, "").slice(0, 24), title: "", ts: Date.now(), messages: [] });
const SUGGESTED = ["How do I declare a path parameter?", "What is the difference between a before and an after validator in Pydantic?", "How do I allow requests from another origin?", "How do I stop Pydantic from turning a string into an integer?"];

function answerCard(m) {
  const meta = m.meta || {}, flags = meta.flags || [], det = meta.source_details || [];
  if (m.error) return h("div", { class: "answer refusal" }, h("p", { text: m.error }));
  const refusal = meta.refused;
  const card = h("div", { class: "answer" + (refusal ? " refusal" : "") });
  if (refusal) card.append(h("h3", { text: meta.reason ? "That was not sent" : "I could not answer that from the docs" }));
  card.append(refusal && meta.reason ? h("p", { text: REASONS[meta.reason] || m.text }) : renderText(m.text, det));
  if (refusal && !meta.reason) {
    card.append(h("p", { class: "note", text: "Try different words, or check the docs directly." }));
    if (det.length) card.append(h("p", { class: "note", text: "Nearest pages I searched:" }), h("div", { class: "chips" }, det.map((d) => h("button", { class: "chip", type: "button", onclick: () => openSource(d) }, tidy(d.heading) || d.doc))));
  }
  const pills = [];
  if (!refusal && (meta.citations || []).length) pills.push(h("span", { class: "pill ok", text: `Cited from ${new Set(det.filter((d) => meta.citations.includes(d.n)).map((d) => d.doc)).size || meta.citations.length} page(s)` }));
  if (!refusal && flags.includes("no_citation")) pills.push(h("span", { class: "pill warn", text: "No citation. Check the docs before relying on this." }));
  if (flags.includes("bad_citation")) pills.push(h("span", { class: "pill warn", text: "A citation did not match a source." }));
  if (flags.some((f) => f.startsWith("pii"))) pills.push(h("span", { class: "pill", text: "Personal data was removed from your question." }));
  if (flags.some((f) => f.startsWith("leak"))) pills.push(h("span", { class: "pill warn", text: "Sensitive text was removed from this answer." }));
  if (meta.cache) pills.push(h("span", { class: "pill", text: "Served from cache" }));
  if (pills.length) card.append(h("div", { class: "meta" }, pills));
  if (det.length && !refusal) card.append(h("div", { class: "chips" }, det.map((d) => h("button", { class: "chip", type: "button", onclick: () => openSource(d) }, icon("book"), ` [${d.n}] ${tidy(d.heading) || d.doc}`))));
  const steps = (meta.steps || []).map(stepText);
  card.append(h("details", { class: "why" }, h("summary", { text: "Why this answer" }), h("ul", {}, [...steps.map((s) => h("li", { text: s })), h("li", { text: `${det.length} source(s) used` })])));
  card.append(feedbackRow(m, meta));
  return card;
}
function feedbackRow(m, meta) {
  const row = h("div", { class: "meta" });
  const vote = async (v, btn) => {
    try { await api("/api/feedback", { method: "POST", json: { trace_id: meta.trace_id || null, value: v } }); m.voted = v; saveChat(); row.querySelectorAll("button[data-v]").forEach((b) => b.setAttribute("aria-pressed", String(b === btn))); row.querySelector(".thanks").textContent = "Thanks, noted."; }
    catch (e) { row.querySelector(".thanks").textContent = friendly(e); }
  };
  const mk = (v, label, cls) => { const b = h("button", { class: "btn small icon", type: "button", "data-v": v, "aria-label": label, "aria-pressed": String(m.voted === v) }, icon("up", cls)); b.addEventListener("click", () => vote(v, b)); return b; };
  const cp = h("button", { class: "btn small", type: "button" }, icon("copy"), "Copy answer"); cp.addEventListener("click", () => copyText(m.text, cp));
  row.append(mk(1, "This answer helped", ""), mk(-1, "This answer did not help", "flip"), cp, h("span", { class: "note thanks", role: "status" }));
  return row;
}
function renderLog(log) {
  log.replaceChildren();
  if (!S.chat.messages.length) {
    log.append(h("div", { class: "empty" }, h("h2", { text: "Ask about FastAPI or Pydantic" }), h("p", { text: "Type, speak, or attach a screenshot of an error." }),
      h("div", { class: "chips" }, SUGGESTED.map((q) => h("button", { class: "chip", type: "button", onclick: () => send(q) }, q)))));
    return;
  }
  for (const m of S.chat.messages) log.append(m.role === "user"
    ? h("div", { class: "msg user" }, h("span", { class: "who", text: "you" }), m.text, m.image ? h("span", { class: "note", text: " (with an image)" }) : null)
    : h("div", { class: "msg" }, h("span", { class: "who", text: "ragx" }), answerCard(m)));
  log.lastElementChild.scrollIntoView({ block: "end" });
}
async function send(text, file) {
  if (S.busy) return;
  text = (text || "").trim(); if (!text && !file) return;
  const log = $("#log"); S.busy = true; $("#send")?.setAttribute("disabled", "");
  if (!S.chat) newChat();
  if (!S.chat.title) S.chat.title = (text || "Image question").slice(0, 80);
  S.chat.messages.push({ role: "user", text: text || "Image question", image: !!file }); renderLog(log);
  const wait = h("div", { class: "msg", "aria-busy": "true" }, h("span", { class: "who", text: "ragx" }), h("div", { class: "answer thinking", text: file ? "Reading the image and searching the docs" : "Searching the docs" })); log.append(wait); wait.scrollIntoView({ block: "end" });
  try {
    let res;
    if (file) { const f = new FormData(); f.append("image", file); f.append("question", text); res = await api("/api/ask-image", { method: "POST", form: f }); }
    else res = await api("/api/ask", { method: "POST", json: { question: text, session_id: S.chat.id } });
    const det = (res.source_details || []).map((d) => ({ ...d, text: (d.text || "").slice(0, 1500) }));
    S.chat.messages.push({ role: "assistant", text: res.text, meta: { refused: res.refused, reason: res.reason, citations: res.citations, source_details: det, flags: res.flags, cache: res.cache, trace_id: res.trace_id, steps: res.steps } });
    if (res.read_from_image?.summary) S.chat.messages.at(-1).meta.steps = [`Read the image: ${res.read_from_image.summary}`, ...(res.steps || [])];
    if (settings.speak && !res.refused) speak(res.text);
  } catch (e) { if (e.status !== 401) S.chat.messages.push({ role: "assistant", error: friendly(e) }); }
  finally { S.busy = false; wait.remove(); $("#send")?.removeAttribute("disabled"); saveChat(); if ($("#log")) renderLog($("#log")); }
}
function speak(text) {
  if (!("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text.replace(/```[\s\S]*?```/g, " code omitted. ").replace(/\[\d+\]/g, "").replace(/[`*]/g, ""));
  const v = speechSynthesis.getVoices().find((x) => x.name === settings.voice); if (v) u.voice = v;
  speechSynthesis.cancel(); speechSynthesis.speak(u);
}

function viewChat() {
  main.className = "chat";
  if (!S.chat) newChat();
  const log = h("div", { class: "log", id: "log", role: "log", "aria-live": "polite", "aria-label": "Conversation" });
  const ta = h("textarea", { class: "input", id: "q", rows: "1", maxlength: "1000", "aria-label": "Your question", placeholder: "Ask a question" });
  const status = h("div", { id: "composer-status", role: "status", "aria-live": "polite" });
  const panel = h("div", { id: "panel" });
  const fileIn = h("input", { type: "file", accept: "image/png,image/jpeg,image/webp", hidden: true, id: "file" });
  const attach = h("button", { class: "btn icon", type: "button", "aria-label": "Attach a screenshot", title: can("ask_image") ? "Attach a screenshot" : "Image questions need a developer account", "aria-disabled": can("ask_image") ? null : "true" }, icon("clip"));
  const mic = h("button", { class: "btn icon", type: "button", id: "mic", "aria-label": "Record a question", "aria-pressed": "false" }, icon("mic"));
  const sendBtn = h("button", { class: "btn primary icon", type: "button", id: "send", "aria-label": "Send question" }, icon("send"));
  const clearImage = () => { S.image = null; fileIn.value = ""; panel.replaceChildren(); };
  const go = () => { const t = ta.value; const f = S.image; ta.value = ""; clearImage(); send(t, f); };
  attach.addEventListener("click", () => { if (!can("ask_image")) { status.textContent = "Image questions need a developer account."; return; } fileIn.click(); });
  fileIn.addEventListener("change", () => {
    const f = fileIn.files[0]; if (!f) return;
    if (!/^image\/(png|jpeg|webp)$/.test(f.type) || f.size > 4 * 1024 * 1024) { status.textContent = friendly({ status: f.size > 4 * 1024 * 1024 ? 413 : 415 }); fileIn.value = ""; return; }
    S.image = f; status.textContent = "";
    const url = URL.createObjectURL(f);
    panel.replaceChildren(h("div", { class: "preview" }, h("img", { src: url, alt: "Preview of the attached screenshot" }), h("span", { class: "note", text: f.name }), h("button", { class: "btn small", type: "button", onclick: clearImage }, icon("x"), "Remove")));
  });
  mic.addEventListener("click", () => toggleRecord(mic, status, panel, ta));
  sendBtn.addEventListener("click", go);
  ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); go(); } });
  main.append(log, h("div", { class: "composer" }, h("div", { class: "inner" }, panel, status, h("div", { class: "row" }, ta, attach, mic, sendBtn), fileIn)));
  renderLog(log);
}

// ---- voice -------------------------------------------------------------
async function toggleRecord(btn, status, panel, ta) {
  if (S.rec) { S.rec.stop(); return; }
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { status.textContent = "Voice input is not supported in this browser. Type your question instead."; return; }
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); } catch { status.textContent = "The microphone is blocked. Allow it in the browser, or type your question."; return; }
  const chunks = []; const rec = new MediaRecorder(stream); S.rec = rec;
  rec.ondataavailable = (e) => chunks.push(e.data);
  const stopTimer = setTimeout(() => rec.state === "recording" && rec.stop(), 30000);
  rec.onstop = async () => {
    clearTimeout(stopTimer); stream.getTracks().forEach((t) => t.stop()); S.rec = null; btn.setAttribute("aria-pressed", "false"); btn.setAttribute("aria-label", "Record a question");
    status.textContent = "Turning speech into text";
    try {
      const f = new FormData(); f.append("audio", new Blob(chunks, { type: rec.mimeType }), "clip");
      const d = await api("/api/ask-voice", { method: "POST", form: f }); status.textContent = "";
      const edit = h("input", { class: "input", "aria-label": "Transcript. Edit it if it is wrong.", value: d.transcript });
      panel.replaceChildren(h("div", { class: "card" }, h("p", { class: "note", text: "Check what I heard, then confirm." }), edit,
        h("div", { class: "row" }, h("button", { class: "btn primary", type: "button", onclick: () => { panel.replaceChildren(); send(edit.value); } }, "Ask this"),
          h("button", { class: "btn", type: "button", onclick: () => { ta.value = edit.value; panel.replaceChildren(); ta.focus(); } }, "Edit in the box"), h("button", { class: "btn", type: "button", onclick: () => panel.replaceChildren() }, "Discard"))));
      edit.focus();
    } catch (e) { status.textContent = friendly(e); }
  };
  rec.start(); btn.setAttribute("aria-pressed", "true"); btn.setAttribute("aria-label", "Stop recording");
  status.replaceChildren(h("span", { class: "rec" }, h("span", { class: "dot" }), "Recording. Tap the microphone to stop."));
}

// ---- history, memory, settings ----------------------------------------
function viewHistory() {
  const q = h("input", { class: "input", type: "search", "aria-label": "Search past chats", placeholder: "Search past chats" });
  const list = h("div", {});
  const draw = () => {
    const term = q.value.toLowerCase(); const all = chats().filter((c) => !term || c.title.toLowerCase().includes(term) || c.messages.some((m) => (m.text || "").toLowerCase().includes(term)));
    list.replaceChildren(...(all.length ? all.map((c) => h("div", { class: "card row space" },
      h("div", {}, h("strong", { text: c.title || "Untitled" }), h("div", { class: "note", text: new Date(c.ts).toLocaleString() + `, ${c.messages.length} messages` })),
      h("div", { class: "row" }, h("button", { class: "btn small", type: "button", onclick: () => { S.chat = c; location.hash = "#/chat"; } }, "Open"),
        h("button", { class: "btn small danger", type: "button", "aria-label": `Delete chat ${c.title}`, onclick: () => { local.set("ragx.chats", chats().filter((x) => x.id !== c.id)); if (S.chat?.id === c.id) S.chat = null; draw(); } }, icon("trash"))))) : [h("p", { class: "note", text: "No chats yet." })]));
  };
  q.addEventListener("input", draw);
  main.append(h("h2", { text: "History" }), h("p", { class: "note", text: "Chats are kept in this browser only. The server does not store your messages." }), q, h("div", { class: "row" }, h("button", { class: "btn small danger", type: "button", onclick: () => { local.set("ragx.chats", []); S.chat = null; draw(); } }, "Delete all")), list);
  draw();
}
const MEM_ERR = { no_consent: "Turn memory on first.", pii: "That looks like personal data, so it was not saved.", injection_like: "That looks like an instruction, so it was not saved.", bad_length: "Keep it under 300 characters.", limit: "You reached the limit of 100 notes. Delete some first.", bad_kind: "Pick a type." };
async function viewMemory() {
  const err = h("div", { class: "err", role: "alert" }); const box = h("div", {});
  main.append(h("h2", { text: "Memory" }), h("p", { class: "note", text: "Notes you choose to keep, such as the library versions you use. They are labelled as untrusted when used, and you can delete any of them." }), err, box);
  const load = async () => {
    try {
      const d = await api("/api/memories"); err.textContent = "";
      const toggle = h("input", { type: "checkbox", id: "mem-on", checked: d.consent }); toggle.addEventListener("change", async () => { try { await api("/api/memories/consent", { method: "POST", json: { consent: toggle.checked } }); S.me.memory_consent = toggle.checked; load(); } catch (e) { err.textContent = friendly(e); } });
      const kind = h("select", { class: "input", id: "mem-kind", "aria-label": "Type of note" }, d.kinds.map((k) => h("option", { value: k, text: k.replace("_", " ") })));
      const text = h("input", { class: "input", id: "mem-text", maxlength: "300", "aria-label": "Note to remember", placeholder: "For example: I use FastAPI 0.115" });
      const add = async () => { try { await api("/api/memories", { method: "POST", json: { kind: kind.value, content: text.value } }); load(); } catch (e) { err.textContent = MEM_ERR[e.message] || friendly(e); } };
      const by = {}; d.memories.forEach((m) => (by[m.kind] ||= []).push(m));
      box.replaceChildren(...[ // null entries (memory off) are filtered out: replaceChildren would print them as the word null
        h("div", { class: "card row" }, toggle, h("label", { for: "mem-on", text: d.consent ? "Memory is on" : "Memory is off. Nothing is saved." })),
        d.consent ? h("div", { class: "card" }, h("div", { class: "row" }, kind, text, h("button", { class: "btn", type: "button", onclick: add, text: "Save note" }))) : null,
        ...(d.memories.length ? d.kinds.filter((k) => by[k]).map((k) => h("div", { class: "card" }, h("h3", { text: k.replace("_", " ") }), by[k].map((m) => h("div", { class: "row space" }, h("span", { text: m.content }),
          h("button", { class: "btn small danger", type: "button", "aria-label": `Delete note: ${m.content}`, onclick: async () => { try { await api("/api/memories/" + m.id, { method: "DELETE" }); load(); } catch (e) { err.textContent = friendly(e); } } }, icon("trash")))))) : [h("p", { class: "note", text: "No notes yet." })])].filter(Boolean));
    } catch (e) { err.textContent = friendly(e); }
  };
  load();
}
function viewSettings() {
  const theme = h("select", { class: "input", id: "theme" }, ["dark", "light", "system"].map((t) => h("option", { value: t, text: t, selected: settings.theme === t })));
  theme.addEventListener("change", () => { settings.theme = theme.value; saveSettings(); });
  const sp = h("input", { type: "checkbox", id: "speak", checked: settings.speak, disabled: !("speechSynthesis" in window) }); sp.addEventListener("change", () => { settings.speak = sp.checked; saveSettings(); });
  const voices = ("speechSynthesis" in window) ? speechSynthesis.getVoices().filter((v) => v.lang.startsWith("en")) : [];
  const voice = h("select", { class: "input", id: "voice", "aria-label": "Voice for spoken replies" }, [h("option", { value: "", text: "Default voice" }), ...voices.map((v) => h("option", { value: v.name, text: v.name, selected: settings.voice === v.name }))]);
  voice.addEventListener("change", () => { settings.voice = voice.value; saveSettings(); });
  main.append(h("h2", { text: "Settings" }),
    h("div", { class: "field" }, h("label", { for: "theme", text: "Theme" }), theme),
    h("div", { class: "card row" }, sp, h("label", { for: "speak", text: ("speechSynthesis" in window) ? "Speak replies out loud" : "Spoken replies are not supported in this browser" })), voice,
    h("div", { class: "card" }, h("h3", { text: "Data and privacy" }), h("p", { class: "note", text: "Questions go to free tier model providers, which may use them for training. Only ask about public docs. Do not paste secrets or personal data. Voice clips and images are processed in memory and not stored. Chats stay in this browser." })),
    h("div", { class: "row" }, h("button", { class: "btn danger", type: "button", onclick: () => signOut(""), text: "Sign out" })));
}

// ---- admin -------------------------------------------------------------
async function viewAdmin(tab) {
  const tabs = [["users", "Users", can("manage_users")], ["evals", "Evals", can("view_metrics")], ["system", "System", can("view_metrics")]].filter((t) => t[2]);
  if (!tabs.find((t) => t[0] === tab)) tab = tabs[0][0];
  const body = h("div", {}); const err = h("div", { class: "err", role: "alert" });
  main.className = ""; main.replaceChildren(h("h2", { text: "Admin" }), h("nav", { class: "subnav", "aria-label": "Admin sections" }, tabs.map(([t, l]) => h("a", { href: "#/admin/" + t, "aria-current": t === tab ? "page" : null }, l))), err, body);
  try { await ({ users: adminUsers, evals: adminEvals, system: adminSystem }[tab])(body, err); } catch (e) { err.textContent = friendly(e); }
}
async function adminUsers(body, err) {
  const [u, a] = await Promise.all([api("/api/admin/users"), api("/api/admin/audit")]);
  const rows = u.users.map((x) => {
    const role = h("select", { class: "input", "aria-label": `Role for ${x.email}` }, ["admin", "developer", "viewer", "guest"].map((r) => h("option", { value: r, text: r, selected: x.role === r })));
    const patch = async (b) => { try { await api("/api/admin/users/" + x.id, { method: "PATCH", json: b }); viewAdmin("users"); } catch (e) { err.textContent = e.status === 400 ? "You cannot change your own account here." : friendly(e); } };
    role.addEventListener("change", () => patch({ role: role.value }));
    return h("tr", {}, h("td", { text: x.email }), h("td", {}, role), h("td", {}, h("span", { class: "pill " + (x.is_active ? "ok" : "warn"), text: x.is_active ? "active" : "disabled" })),
      h("td", {}, h("button", { class: "btn small", type: "button", onclick: () => patch({ is_active: !x.is_active }), text: x.is_active ? "Disable" : "Enable" })));
  });
  const email = h("input", { class: "input", type: "email", "aria-label": "New user email" }); const pw = h("input", { class: "input", type: "password", "aria-label": "New user password, at least 12 characters", autocomplete: "new-password" });
  const role = h("select", { class: "input", "aria-label": "New user role" }, ["viewer", "developer", "admin"].map((r) => h("option", { value: r, text: r })));
  const create = async () => { try { await api("/api/admin/users", { method: "POST", json: { email: email.value, password: pw.value, role: role.value } }); viewAdmin("users"); } catch (e) { err.textContent = e.status === 409 ? "That email already exists." : e.status === 422 ? "Use a password of at least 12 characters and a valid role." : friendly(e); } };
  body.append(h("div", { class: "card tablewrap" }, h("table", {}, h("thead", {}, h("tr", {}, ["Email", "Role", "Status", ""].map((t) => h("th", { text: t })))), h("tbody", {}, rows))),
    h("div", { class: "card" }, h("h3", { text: "Add a user" }), h("div", { class: "row" }, email, pw, role, h("button", { class: "btn primary", type: "button", onclick: create, text: "Create" }))),
    h("div", { class: "card tablewrap" }, h("h3", { text: "Audit log (latest 100)" }), h("table", {}, h("thead", {}, h("tr", {}, ["When", "User", "Action", "Allowed"].map((t) => h("th", { text: t })))),
      h("tbody", {}, a.rows.map((r) => h("tr", {}, h("td", { text: new Date(r.ts * 1000).toLocaleString() }), h("td", { text: r.user_id ?? "none" }), h("td", { text: r.action + (r.target ? ` (${r.target})` : "") }), h("td", { text: r.allowed ? "yes" : "no" })))))));
}
async function adminEvals(body) {
  const d = await api("/api/admin/evals");
  const fmt = (v) => (typeof v === "number" ? (Math.abs(v) <= 1.5 ? v.toFixed(3) : String(v)) : String(v));
  body.append(h("p", { class: "note", text: "Latest recorded value of each key metric, with the result file and its date. Labels and test sets were written by Claude and are not human reviewed. Voice and image numbers are on synthetic data." }),
    h("div", { class: "card tablewrap" }, h("table", {}, h("thead", {}, h("tr", {}, ["Part", "Metric", "Value", "Run date"].map((t, i) => h("th", { class: i === 2 ? "num" : "", text: t })))),
      h("tbody", {}, d.results.map((r) => h("tr", {}, h("td", { text: r.part }), h("td", {}, r.metric, h("div", { class: "note", text: [r.note, r.file].filter(Boolean).join(", ") })), h("td", { class: "num", text: fmt(r.value) }), h("td", { text: r.date })))))),
    h("div", { class: "card" }, h("h3", { text: "Runs and schedule" }), h("p", { class: "note", text: "Run now is not available from here. Evals run from the command line or from the GitHub Actions workflows (nightly and weekly) once the repository is pushed. No scheduled run has completed yet." }),
      h("button", { class: "btn", type: "button", disabled: true, "aria-disabled": "true", text: "Run now (not built)" })));
}
async function adminSystem(body) {
  const m = await api("/api/admin/metrics"); const pct = (v) => (v == null ? "no data" : (v * 100).toFixed(1) + "%"); const ms = (v) => (v == null ? "no data" : (v / 1000).toFixed(1) + " s");
  const stat = (label, value) => h("div", { class: "stat" }, h("b", { text: value }), h("span", { text: label }));
  body.append(h("p", { class: "note", text: `Since the server started. Latency covers uncached answers only (last ${m.latency_window} of them). Trends over time are in Grafana.` }),
    h("div", { class: "grid" }, stat("questions", String(m.asks)), stat("latency p50", ms(m.latency_ms_p50_uncached)), stat("latency p95", ms(m.latency_ms_p95_uncached)), stat("tokens per uncached answer", m.tokens_per_uncached_ask ?? "no data"),
      stat("cache hit rate", pct(m.cache_hit_rate)), stat("fallback rate", pct(m.fallback_rate)), stat("refusal rate", pct(m.refusal_rate)), stat("blocked by guardrails", pct(m.blocked_rate)),
      stat("thumbs up rate", pct(m.thumbs_up_rate)), stat(`online faithfulness (n=${m.online_faithfulness_n})`, m.online_faithfulness_mean ?? "no data")),
    h("div", { class: "card tablewrap" }, h("h3", { text: "Providers" }), h("table", {}, h("thead", {}, h("tr", {}, ["Provider and result", "Calls"].map((t, i) => h("th", { class: i ? "num" : "", text: t })))),
      h("tbody", {}, Object.entries(m.providers || {}).map(([k, v]) => h("tr", {}, h("td", { text: k.replace(":", " ") }), h("td", { class: "num", text: v })))))),
    h("div", { class: "card" }, h("h3", { text: "Guardrail triggers" }), h("p", { class: "mono", text: JSON.stringify(m.guardrails || {}) || "none" })));
}

// ---- start -------------------------------------------------------------
async function start() {
  S.me = await api("/api/me");
  if (!location.hash || location.hash === "#/login") location.hash = "#/chat";
  applyTheme(); route();
}
async function boot() {
  applyTheme();
  $("#theme-btn").addEventListener("click", () => { settings.theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; saveSettings(); });
  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) navigator.serviceWorker.register("/sw.js").catch(() => {});
  const slow = setTimeout(() => banner("Waking up the server. The first request can take a minute."), 4000);
  try { await fetch("/api/health"); } catch { banner("The server cannot be reached."); }
  clearTimeout(slow); if ($("#banner").textContent.startsWith("Waking")) banner("");
  const t = session.get("ragx.tok", null);
  if (t?.access) { S.access = t.access; S.refresh = t.refresh; try { await start(); return; } catch { /* token no longer valid: fall through to the sign in form */ } }
  route();
}
boot();
