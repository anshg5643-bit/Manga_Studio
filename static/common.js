/* Fukidashi shared client: api helpers, auth portal, google sign-in, exporters */
(() => {
  document.documentElement.classList.add("js");
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const PALETTE = ["#c9f31d", "#7ad7ff", "#ff8fb1", "#ffcf5a", "#b49bff", "#5eead4"];
  const FK = window.FK = { $, $$, esc, user: window.__USER__, googleId: "", PALETTE };

  async function api(path, opts = {}) {
    const r = await fetch(path, { credentials: "same-origin", ...opts });
    let data = {};
    try { data = await r.json(); } catch (_) {}
    if (!r.ok) { const e = new Error(data.error || `Request failed (${r.status})`); e.status = r.status; e.field = data.field; if (r.status === 401 && FK.user) { FK.user = null; FK.renderAcct(); FK.applyLock(); } throw e; }
    return data;
  }
  const send = (m) => (p, body) => api(p, { method: m, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) });
  Object.assign(FK, { api, post: send("POST"), put: send("PUT"), patch: send("PATCH"), del: (p) => api(p, { method: "DELETE" }) });

  FK.toast = (t) => { const d = document.createElement("div"); d.className = "toast"; d.textContent = t; d.setAttribute("role", "status"); document.body.appendChild(d); setTimeout(() => { d.style.transition = "opacity .4s"; d.style.opacity = 0; setTimeout(() => d.remove(), 450); }, 2300); };
  FK.fmtDate = s => { try { return new Date(s).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }); } catch (_) { return s; } };
  FK.colorFor = (name, names) => name === "NARRATION" ? "#9aa0a8" : PALETTE[Math.max(0, names.indexOf(name)) % PALETTE.length];
  FK.speakerNames = (detail) => [...new Set(detail.flat().map(d => d.speaker).filter(s => s !== "NARRATION"))];
  FK.download = (name, text, mime = "text/plain") => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type: mime })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000); };
  FK.pill = (name, names) => `<span class="sp" style="background:${FK.colorFor(name, names)}">${esc(name)}</span>`;

  // ---------- exporters (all take an analysis {title, seqId, id, detail})
  const pagesOf = a => a.detail.map(p => [...p].sort((x, y) => x.order - y.order).map(l => ({ speaker: l.speaker, text: l.text })));
  FK.exporters = {
    jsonl: a => JSON.stringify({ sequence_id: a.seqId || `upload_${a.id}`, pages: pagesOf(a) }) + "\n",
    json: a => JSON.stringify({ sequence_id: a.seqId || `upload_${a.id}`, title: a.title, pages: pagesOf(a), detail: a.detail }, null, 2),
    csv: a => ["page,order,speaker,text", ...pagesOf(a).flatMap((p, i) => p.map((l, j) => [i + 1, j + 1, l.speaker, '"' + l.text.replace(/"/g, '""') + '"'].join(",")))].join("\n") + "\n",
    txt: a => pagesOf(a).map((p, i) => `--- Page ${i + 1} ---\n` + (p.map(l => `${l.speaker}: ${l.text}`).join("\n") || "(no text)")).join("\n\n") + "\n",
    md: a => `# ${a.title}\n\n` + pagesOf(a).map((p, i) => `## Page ${i + 1}\n\n` + (p.map((l, j) => `${j + 1}. **${l.speaker}**: ${l.text}`).join("\n") || "_No text_")).join("\n\n") + "\n",
  };
  FK.exportAnalysis = (a, fmt) => FK.download(`${(a.seqId || a.title || "analysis").replace(/[^\w.-]+/g, "_")}.${fmt === "md" ? "md" : fmt}`, FK.exporters[fmt](a), fmt === "json" ? "application/json" : "text/plain");
  FK.exportMenuHtml = `<button data-fmt="jsonl">Task JSONL (submission format)</button><button data-fmt="json">JSON with details</button><button data-fmt="csv">CSV</button><button data-fmt="txt">Plain-text script</button><button data-fmt="md">Markdown</button>`;
  FK.wireExportMenu = (root, getA) => {
    const pop = $(".pop", root); pop.innerHTML = FK.exportMenuHtml;
    $("[data-toggle]", root).onclick = e => { e.stopPropagation(); root.classList.toggle("open"); };
    pop.onclick = async e => { const f = e.target.dataset.fmt; if (!f) return; const a = getA(); if (!a) return FK.toast("Nothing to export yet"); FK.exportAnalysis(a, f); root.classList.remove("open"); };
    document.addEventListener("click", () => root.classList.remove("open"));
  };
  FK.clip = async (t) => { try { await navigator.clipboard.writeText(t); FK.toast("Copied"); } catch (_) { FK.toast("Copy blocked by the browser"); } };

  // ---------- header
  const BASIC = ["login", "signup", "reset"];
  FK.renderAcct = () => {
    const el = $("#acct"); if (!el) return; const u = FK.user;
    if (!u) { el.innerHTML = `<a class="btn sm ghost" href="/login">Sign in</a><button class="btn sm lime" data-portal="signup">Sign up</button>`; return; }
    el.innerHTML = `<a class="btn sm ghost" href="/analyzer">Open app</a><a class="btn sm" href="/account" title="${esc(u.email)}"><span class="sp" style="background:var(--lime);padding:0 8px">${esc((u.name || u.email)[0].toUpperCase())}</span>${esc(u.name)}</a><button class="btn sm ghost" id="logout">Log out</button>`;
    $("#logout").onclick = async () => { await FK.post("/api/logout"); FK.user = null; location.href = "/"; };
  };
  FK.applyLock = () => { const m = $(".app"); if (m) m.classList.toggle("locked", !FK.user); };
  const menu = $("#featMenu");
  if (menu) { $("#featBtn").onclick = e => { e.stopPropagation(); menu.classList.toggle("open"); $("#featBtn").setAttribute("aria-expanded", menu.classList.contains("open")); }; document.addEventListener("click", () => menu.classList.remove("open")); document.addEventListener("keydown", e => e.key === "Escape" && menu.classList.remove("open")); }

  // ---------- portal
  const portal = $("#portal"), bubble = portal && $(".bubble", portal); let lastFocus = null, mode = "signup";
  function setMode(m) {
    mode = m; $("#tabUp").setAttribute("aria-selected", m === "signup"); $("#tabIn").setAttribute("aria-selected", m === "login");
    $$("[data-mode]", portal).forEach(x => x.hidden = x.dataset.mode !== m);
    $("#pt").textContent = m === "signup" ? "Start reading manga text" : "Welcome back";
    $("#psub").textContent = m === "signup" ? "Free account. Your pages are processed on this machine." : "Sign in to keep analyzing sequences.";
    $$("[data-err]", portal).forEach(e => e.hidden = true);
  }
  FK.openPortal = (m = "signup", msg) => {
    if (!portal) return; lastFocus = document.activeElement; setMode(m); portal.hidden = false; document.body.style.overflow = "hidden";
    if (msg) { const e = $(`[data-mode=${m}] [data-err]`, portal); e.textContent = msg; e.hidden = false; }
    setTimeout(() => { const f = $(`[data-mode=${m}] input`, portal); f && f.focus({ preventScroll: true }); }, 450);
  };
  FK.closePortal = () => { if (!portal) return; portal.hidden = true; document.body.style.overflow = ""; lastFocus && lastFocus.focus && lastFocus.focus(); };
  FK.requireAuth = (msg) => { if (FK.user) return true; FK.openPortal("signup", msg); return false; };
  document.addEventListener("click", e => { const t = e.target.closest("[data-portal]"); if (t) { e.preventDefault(); FK.openPortal(t.dataset.portal); } });
  if (portal) {
    $("#tabUp").onclick = () => setMode("signup"); $("#tabIn").onclick = () => setMode("login");
    $("#portalClose").onclick = FK.closePortal; $(".veil", portal).onclick = FK.closePortal; portal.addEventListener("mousedown", e => { if (e.target === portal) FK.closePortal(); });
    document.addEventListener("keydown", e => {
      if (portal.hidden) return; if (e.key === "Escape") FK.closePortal();
      if (e.key === "Tab") { const f = $$("button,input,a[href]", bubble).filter(x => !x.disabled && x.offsetParent !== null); if (!f.length) return; const a = f[0], z = f[f.length - 1];
        if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); } else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); } }
    });
  }

  // ---------- auth forms (popup + /login + /signup pages)
  async function onSignedIn(u) {
    FK.user = u; FK.renderAcct(); FK.applyLock(); FK.closePortal(); FK.toast(`Signed in as ${u.name}`);
    const authPage = BASIC.includes(document.body.dataset.page);
    if (authPage) { location.href = new URLSearchParams(location.search).get("next") || "/analyzer"; return; }
    document.dispatchEvent(new CustomEvent("fk:auth", { detail: u }));
  }
  $$("form[data-auth]").forEach(f => {
    f.addEventListener("submit", async e => {
      e.preventDefault(); const kind = f.dataset.auth, err = $("[data-err]", f), btn = $("button[type=submit]", f); err.hidden = true;
      const show = (t, field) => { err.textContent = t; err.hidden = false; if (field && f[field]) f[field].focus(); };
      if (kind === "signup") {
        if (f.password.value !== f.repeat.value) return show("The two passwords do not match.", "repeat");
        if (!f.terms.checked) return show("Please accept the Terms and Conditions to continue.");
      }
      btn.disabled = true;
      try {
        const body = { email: f.email.value, password: f.password.value };
        if (kind === "signup") Object.assign(body, { name: f.name.value, repeat: f.repeat.value, marketing: f.marketing.checked });
        else body.remember = f.remember.checked;
        await onSignedIn((await FK.post(kind === "signup" ? "/api/signup" : "/api/login", body)).user);
      } catch (ex) { show(ex.message, ex.field); } finally { btn.disabled = false; }
    });
  });
  document.addEventListener("click", e => { const b = e.target.closest("[data-eye]"); if (!b) return; const i = b.parentElement.querySelector("input"); i.type = i.type === "password" ? "text" : "password"; });

  // ---------- google sign-in
  function setupGoogle() {
    const holders = $$("[data-gbtn]"); if (!holders.length) return;
    const fb = (msg) => $$("[data-gfallback]").forEach(b => { b.hidden = false; b.onclick = () => { const e = b.closest("form,div[data-mode],.authcard,.bubble").querySelector("[data-err]"); if (e) { e.textContent = msg; e.hidden = false; } }; });
    if (!FK.googleId) { fb("Google sign-in is not set up yet. Add GOOGLE_CLIENT_ID to api_keys.txt."); $$("[data-gnote]").forEach(n => n.hidden = false); return; }
    let tries = 0; const t = setInterval(() => {
      if (window.google && google.accounts && google.accounts.id) {
        clearInterval(t);
        google.accounts.id.initialize({ client_id: FK.googleId, callback: async r => { try { await onSignedIn((await FK.post("/api/google", { credential: r.credential })).user); } catch (ex) { FK.toast(ex.message); } }, auto_select: false, cancel_on_tap_outside: true });
        holders.forEach(h => google.accounts.id.renderButton(h, { theme: "filled_black", size: "large", width: 340, text: "continue_with", shape: "pill" }));
      } else if (++tries > 40) { clearInterval(t); fb("Could not load Google sign-in. Check your connection."); }
    }, 250);
  }

  // ---------- range sliders: lime fill
  FK.fillRange = r => r.style.setProperty("--p", ((r.value - r.min) / (r.max - r.min) * 100) + "%");
  document.addEventListener("input", e => { if (e.target.type === "range") FK.fillRange(e.target); });
  FK.initRanges = (root = document) => $$("input[type=range]", root).forEach(FK.fillRange);

  // ---------- shared fetchers
  FK.listAnalyses = async () => (await api("/api/analyses")).analyses;
  FK.loadAnalysis = async id => (await api(`/api/analyses/${id}`)).analysis;

  // ---------- analysis picker used by Speakers / Reading order
  FK.initPicker = async (sel, onLoad) => {
    if (!FK.user) return; let list = [];
    try { list = await FK.listAnalyses(); } catch (_) {}
    sel.innerHTML = list.length ? list.map(a => `<option value="${a.id}">${esc(a.title)} · ${FK.fmtDate(a.created)}</option>`).join("") : '<option value="">No analyses yet</option>';
    const q = new URLSearchParams(location.search).get("open"); if (q && list.some(a => String(a.id) === q)) sel.value = q;
    const load = async () => { if (!sel.value) return onLoad(null, list); try { onLoad(await FK.loadAnalysis(sel.value), list); } catch (e) { FK.toast(e.message); } };
    sel.onchange = load; await load();
  };

  // ---------- boot
  (async () => {
    FK.renderAcct(); FK.applyLock(); FK.initRanges();
    try { FK.googleId = (await api("/api/config")).googleClientId; } catch (_) {}
    setupGoogle();
    document.dispatchEvent(new CustomEvent("fk:ready"));
    // new visitors get the portal straight away (not on the dedicated sign-in pages)
    if (!FK.user && !BASIC.includes(document.body.dataset.page)) {
      // Show the welcome/auth portal only once per tab session, not on every feature navigation.
      let seen = false; try { seen = sessionStorage.getItem("fk_auth_intro_seen") === "1"; } catch (_) {}
      if (!seen) setTimeout(() => {
        if (!FK.user) { FK.openPortal("signup"); try { sessionStorage.setItem("fk_auth_intro_seen", "1"); } catch (_) {} }
      }, 600);
    }
  })();
})();
