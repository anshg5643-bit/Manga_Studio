(() => {
  const { $, $$, esc } = FK;
  let A = null, page = 0, saveT = null, groups = [];
  const busy = on => { $("#busy").hidden = !on; $("#go").disabled = on; $("#loadSeq").disabled = on; };
  const showErr = t => { const e = $("#err"); e.textContent = t || ""; e.hidden = !t; };

  // ---------- slots
  const slots = $$(".slot");
  const fill = (s, f) => { if (!f) return; const dt = new DataTransfer(); dt.items.add(f); $("input", s).files = dt.files; const img = $("img", s); img.src = URL.createObjectURL(f); img.hidden = false; s.classList.add("has"); };
  function dropMany(files, startAt) { const fs = [...files].filter(f => f.type.startsWith("image/")).sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true })); if (fs.length >= 2) fs.slice(0, 3).forEach((f, i) => fill(slots[i], f)); else if (fs[0]) fill(slots[startAt], fs[0]); }
  slots.forEach((s, idx) => {
    $("input", s).addEventListener("change", e => dropMany(e.target.files, idx));
    ["dragenter", "dragover"].forEach(ev => s.addEventListener(ev, e => { e.preventDefault(); s.classList.add("drag"); }));
    ["dragleave", "drop"].forEach(ev => s.addEventListener(ev, e => { e.preventDefault(); s.classList.remove("drag"); }));
    s.addEventListener("drop", e => dropMany(e.dataTransfer.files, idx));
  });
  $("#optThr").addEventListener("input", e => $("#thrVal").textContent = (+e.target.value).toFixed(2));

  // ---------- load saved defaults + samples
  async function init() {
    if (!FK.user) return;
    try { const c = (await FK.api("/api/settings")).config; $("#optSpk").value = c.speaker_mode; $("#optRtl").value = c.rtl ? "1" : "0"; $("#optThr").value = c.keep_threshold; $("#optPan").checked = c.use_panels; $("#thrVal").textContent = (+c.keep_threshold).toFixed(2); FK.fillRange($("#optThr")); } catch (_) {}
    try {
      groups = (await FK.api("/api/samples")).groups;
      if (groups.length) { $("#sampleWrap").hidden = false; $("#grpSel").innerHTML = groups.map((g, i) => `<option value="${i}">${esc(g.name.slice(-22))} (${g.count})</option>`).join(""); fillSeq(); }
    } catch (_) {}
    const open = new URLSearchParams(location.search).get("open");
    if (open) { try { A = await FK.loadAnalysis(open); page = 0; render(); } catch (e) { showErr(e.message); } }
  }
  const fillSeq = () => { const g = groups[+$("#grpSel").value]; $("#seqSel").innerHTML = g ? g.ids.map(i => `<option>${esc(i)}</option>`).join("") : ""; };
  $("#grpSel").onchange = fillSeq;
  $("#randSeq").onclick = () => { const s = $("#seqSel"); s.selectedIndex = Math.floor(Math.random() * s.options.length); $("#loadSeq").click(); };
  document.addEventListener("fk:auth", init); document.addEventListener("fk:ready", init);

  const cfgFromUi = () => ({ speaker_mode: $("#optSpk").value, rtl: $("#optRtl").value === "1", keep_threshold: +$("#optThr").value, use_panels: $("#optPan").checked });
  async function run(fn) {
    showErr(""); busy(true);
    try { const d = await fn(); A = d.analysis; page = 0; render(); }
    catch (e) { if (e.status === 401) FK.openPortal("signup", "Sign in to analyze pages."); else showErr(e.message); }
    finally { busy(false); }
  }
  $("#form").addEventListener("submit", e => {
    e.preventDefault(); if (!FK.requireAuth("Create an account to read your pages.")) return;
    const fs = slots.map(s => $("input", s).files[0]); if (fs.some(f => !f)) return showErr("Add all three pages first, or load a sample sequence.");
    const fd = new FormData(); fs.forEach((f, i) => fd.append(`page${i + 1}`, f));
    const c = cfgFromUi(); Object.entries(c).forEach(([k, v]) => fd.append(k, typeof v === "boolean" ? (v ? "1" : "0") : v));
    run(() => FK.api("/api/analyze", { method: "POST", body: fd }));
  });
  $("#loadSeq").onclick = () => { if (!FK.requireAuth()) return; const id = $("#seqSel").value; if (id) run(() => FK.post("/api/analyze_sample", { id, config: cfgFromUi() })); };

  // ---------- result rendering
  const lines = () => A.detail[page];
  const renumber = () => A.detail.forEach(p => p.forEach((l, i) => l.order = i + 1));
  function setSaved(s) { $("#saveState").textContent = s; }
  function scheduleSave() { setSaved("Saving…"); clearTimeout(saveT); saveT = setTimeout(save, 700); }
  async function save() {
    try { const d = await FK.patch(`/api/analyses/${A.id}`, { detail: A.detail, rejected: A.rejected, title: $("#title").value }); A.overlays = d.analysis.overlays; A.title = d.analysis.title; setSaved("Saved"); setOverlay(); }
    catch (e) { setSaved("Not saved"); FK.toast(e.message); }
  }
  const setOverlay = () => { $("#ov").src = A.overlays[page] + `&rejected=${$("#showRej").checked ? 1 : 0}`; };
  function render() {
    $("#result").hidden = false; $("#title").value = A.title; $("#exportMenu").hidden = false; $("#copyBtn").hidden = false;
    $$("#tabs button").forEach((b, i) => { b.setAttribute("aria-selected", i === page); b.textContent = `Page ${i + 1} · ${A.detail[i].length}`; b.onclick = () => { page = i; render(); }; });
    setOverlay(); setSaved("Saved");
    const names = FK.speakerNames(A.detail);
    $("#legend").innerHTML = [...names, ...(A.detail.flat().some(d => d.speaker === "NARRATION") ? ["NARRATION"] : [])].map(n => FK.pill(n, names)).join("");
    const opts = [...new Set([...names, "NARRATION"])];
    $("#lines").innerHTML = lines().map((l, i) => `<div class="line" data-i="${i}" style="animation-delay:${Math.min(i, 12) * 35}ms">
      <span class="num" style="background:${FK.colorFor(l.speaker, names)}">${l.order}</span>
      <div><select aria-label="Speaker">${opts.map(o => `<option ${o === l.speaker ? "selected" : ""}>${esc(o)}</option>`).join("")}<option value="__new">New speaker…</option></select>
        <div class="txt" contenteditable="true" spellcheck="false" role="textbox" aria-label="Line text">${esc(l.text)}</div></div>
      <div class="acts"><button class="iconbtn" data-a="up" title="Move up" aria-label="Move up">↑</button><button class="iconbtn" data-a="down" title="Move down" aria-label="Move down">↓</button><button class="iconbtn" data-a="del" title="Delete line" aria-label="Delete line">×</button></div></div>`).join("");
    $("#empty").hidden = lines().length > 0;
    const rej = (A.rejected[page] || []); $("#rejBox").hidden = !rej.length;
    $("#rejList").innerHTML = rej.map((r, i) => `<button data-r="${i}">${esc(r.text)} <span class="muted small">(${Math.round(r.p_keep * 100)}%)</span></button>`).join("");
    $("#note").textContent = A.config && A.config.speaker_mode ? `Speakers: ${A.config.speaker_mode}. Read in ${A.secs}s. ${A.edited ? "You have edited this result." : ""}` : "";
  }
  $("#showRej").onchange = setOverlay;
  $("#title").addEventListener("input", scheduleSave);

  // line interactions (event delegation)
  $("#lines").addEventListener("input", e => { if (e.target.classList.contains("txt")) { lines()[+e.target.closest(".line").dataset.i].text = e.target.textContent; scheduleSave(); } });
  $("#lines").addEventListener("change", e => {
    if (e.target.tagName !== "SELECT") return; const i = +e.target.closest(".line").dataset.i; let v = e.target.value;
    if (v === "__new") { v = (prompt("New speaker name (letters, numbers, no spaces):", "char" + (FK.speakerNames(A.detail).length + 1)) || "").trim().replace(/\s+/g, "_"); if (!v) { render(); return; } }
    lines()[i].speaker = v; scheduleSave(); render();
  });
  $("#lines").addEventListener("click", e => {
    const b = e.target.closest("[data-a]"); if (!b) return; const i = +b.closest(".line").dataset.i, L = lines();
    if (b.dataset.a === "del") L.splice(i, 1);
    else if (b.dataset.a === "up" && i > 0) [L[i - 1], L[i]] = [L[i], L[i - 1]];
    else if (b.dataset.a === "down" && i < L.length - 1) [L[i + 1], L[i]] = [L[i], L[i + 1]];
    renumber(); scheduleSave(); render();
  });
  $("#addLine").onclick = () => { const names = FK.speakerNames(A.detail); lines().push({ speaker: names[0] || "char1", text: "New line", order: lines().length + 1, p_keep: 1, box: null }); scheduleSave(); render(); const t = $$("#lines .txt").pop(); t && t.focus(); };
  $("#rejList").addEventListener("click", e => { const b = e.target.closest("[data-r]"); if (!b) return; const [r] = A.rejected[page].splice(+b.dataset.r, 1); const names = FK.speakerNames(A.detail); lines().push({ speaker: names[0] || "char1", text: r.text, order: lines().length + 1, p_keep: r.p_keep, box: r.box }); scheduleSave(); render(); });

  // hover highlight on the page image
  const hl = $("#hl");
  $("#lines").addEventListener("mouseover", e => {
    const row = e.target.closest(".line"); const l = row && lines()[+row.dataset.i], sz = A && A.sizes[page];
    if (!l || !l.box || !sz) { hl.hidden = true; return; }
    const [x0, y0, x1, y1] = l.box; Object.assign(hl.style, { left: x0 / sz[0] * 100 + "%", top: y0 / sz[1] * 100 + "%", width: (x1 - x0) / sz[0] * 100 + "%", height: (y1 - y0) / sz[1] * 100 + "%" }); hl.hidden = false;
  });
  $("#lines").addEventListener("mouseleave", () => hl.hidden = true);
  $("#shotwrap").onclick = () => { const lb = $("#lightbox"); $("img", lb).src = $("#ov").src; lb.classList.add("on"); };
  $("#lightbox").onclick = () => $("#lightbox").classList.remove("on");
  document.addEventListener("keydown", e => e.key === "Escape" && $("#lightbox").classList.remove("on"));

  FK.wireExportMenu($("#exportMenu"), () => A);
  $("#copyBtn").onclick = () => A && FK.clip(FK.exporters.jsonl(A).trim());
  window.addEventListener("beforeunload", e => { if ($("#saveState").textContent === "Saving…") { e.preventDefault(); e.returnValue = ""; } });
})();
