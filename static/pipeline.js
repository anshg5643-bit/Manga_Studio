(() => {
  const { $, esc } = FK; let defaults = {};
  const pairs = [["thr", "keep_threshold", "vThr", 2], ["alpha", "alpha", "vAl", 1], ["sthr", "speaker_thr", "vSt", 2]];
  const paint = () => pairs.forEach(([id, , v, d]) => { $("#" + v).textContent = (+$("#" + id).value).toFixed(d); FK.fillRange($("#" + id)); });
  pairs.forEach(([id]) => $("#" + id).addEventListener("input", paint));
  const fillForm = c => { $("#thr").value = c.keep_threshold; $("#alpha").value = c.alpha; $("#sthr").value = c.speaker_thr; $("#spk").value = c.speaker_mode; $("#bk").value = c.backend; $("#rtl").checked = c.rtl; $("#pan").checked = c.use_panels; paint(); };
  const read = () => ({ keep_threshold: +$("#thr").value, alpha: +$("#alpha").value, speaker_thr: +$("#sthr").value, speaker_mode: $("#spk").value, backend: $("#bk").value, rtl: $("#rtl").checked, use_panels: $("#pan").checked });
  async function init() {
    if (!FK.user) return;
    const s = await FK.api("/api/settings"); defaults = s.defaults; fillForm(s.config);
    try { const g = (await FK.api("/api/samples")).groups; $("#tg").innerHTML = g.length ? g.map(x => `<option value="${esc(x.name)}">${esc(x.name.slice(-26))} (${x.count})</option>`).join("") : '<option value="">No folders. Edit sample_dirs.txt</option>'; } catch (_) {}
    status();
  }
  async function status() {
    const s = await FK.api("/api/system"), cv = s.filterMeta && s.filterMeta.learned_cv, row = (l, ok, d) => `<div class="row" style="justify-content:space-between;align-items:center"><div><b>${l}</b><div class="muted small">${d}</div></div><span class="tag"><b style="background:${ok ? "var(--lime)" : "#555c66"};color:${ok ? "#0b0c0a" : "#fff"}">${ok ? "ready" : "missing"}</b></span></div>`;
    $("#status").innerHTML = row("OCR engine", !!s.onnxruntime, s.onnxruntime ? "RapidOCR on ONNX Runtime " + esc(s.onnxruntime) : "onnxruntime not installed") +
      row("Trained text filter", s.trainedFilter, s.trainedFilter ? (cv ? `Cross-validated F1 ${(cv.f1 * 100).toFixed(1)}%` : "Trained") : "Using the hand-written rule. Train it below.") +
      row("Qwen2.5-VL LoRA adapter", s.vlmReady, s.vlmReady ? "Adapter and PyTorch found" : `${s.torch ? "PyTorch found" : "PyTorch not installed"}, ${s.vlmAdapter ? "adapter found" : "no adapter in models/qwen_lora"}`) +
      row("Google sign-in", s.googleConfigured, s.googleConfigured ? "Client ID set in api_keys.txt" : "Add GOOGLE_CLIENT_ID to api_keys.txt") +
      `<div class="muted small">Python ${esc(s.python)} · ${s.cpu} CPU cores</div>`;
  }
  $("#save").onclick = async () => { try { fillForm((await FK.put("/api/settings", read())).config); $("#sMsg").textContent = "Saved."; FK.toast("Defaults saved"); } catch (e) { $("#sMsg").textContent = e.message; } };
  $("#reset").onclick = async () => { fillForm((await FK.del("/api/settings")).config); $("#sMsg").textContent = "Back to defaults."; };

  $("#train").onclick = async () => {
    if (!FK.requireAuth()) return; const e = $("#tErr"); e.hidden = true;
    if (!$("#tl").files[0] || !$("#tg").value) { e.textContent = "Choose a dataset folder and a labels.jsonl file."; e.hidden = false; return; }
    const fd = new FormData(); fd.append("group", $("#tg").value); fd.append("labels", $("#tl").files[0]); $("#train").disabled = true;
    try {
      const { job } = await FK.api("/api/train", { method: "POST", body: fd }); $("#tProg").hidden = false; $("#tRep").hidden = true;
      const t = setInterval(async () => {
        const d = await FK.api(`/api/train/${job}`).catch(() => null); if (!d) return clearInterval(t);
        $("#tCount").textContent = `${d.done} / ${d.total} sequences`; $("#tBar").style.width = d.done / d.total * 100 + "%";
        if (d.status !== "running") { clearInterval(t); $("#train").disabled = false;
          if (d.status === "error") { $("#tTitle").textContent = "Training failed"; e.textContent = d.error; e.hidden = false; return; }
          const r = d.report, m = (l, x) => `<div class="card"><div class="metric"><b>${x == null ? "n/a" : (x * 100).toFixed(1) + "%"}</b><span>${l}</span></div></div>`;
          $("#tTitle").textContent = "Filter trained and saved"; $("#tRep").hidden = false;
          $("#tRep").innerHTML = m("Rule baseline F1", r.rule_baseline.f1) + m("Learned (CV) F1", r.learned_cv && r.learned_cv.f1) + m("Learned (CV) recall", r.learned_cv && r.learned_cv.recall); status(); }
      }, 1500);
    } catch (ex) { e.textContent = ex.message; e.hidden = false; $("#train").disabled = false; }
  };
  document.addEventListener("fk:ready", init); document.addEventListener("fk:auth", init);
})();
