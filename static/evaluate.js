(() => {
  const { $, $$, esc } = FK; let R = null, sort = ["text_order_score", 1], sel = null, ip = 0;
  const err = t => { const e = $("#err"); e.textContent = t || ""; e.hidden = !t; };
  $("#run").onclick = async () => {
    if (!FK.requireAuth()) return; err(""); if (!$("#labels").files[0]) return err("Add a labels.jsonl file.");
    const fd = new FormData(); fd.append("labels", $("#labels").files[0]); if ($("#preds").files[0]) fd.append("predictions", $("#preds").files[0]);
    $("#run").disabled = true;
    try { R = await FK.api("/api/evaluate", { method: "POST", body: fd }); sel = null; $("#inspect").hidden = true; show(); } catch (e) { err(e.message); } finally { $("#run").disabled = false; }
  };
  const pct = x => (x * 100).toFixed(1) + "%";
  function show() {
    $("#out").hidden = false; const m = R.mean;
    $("#metrics").innerHTML = [["text_order_score", "Text and order"], ["balanced_joint_f1", "Speaker joint F1"], ["text_f1", "Text F1"], ["order_agreement", "Order agreement"]].map(([k, l], i) => `<div class="card ${i === 0 ? "lime" : ""}"><div class="metric"><b>${pct(m[k])}</b><span style="${i === 0 ? "color:#33400a" : ""}">${l}</span></div></div>`).join("");
    $("#skipped").textContent = `${R.rows.length} sequences scored. ${R.skipped.labelsOnly} label-only, ${R.skipped.predsOnly} prediction-only ids ignored.`;
    rows();
  }
  function rows() {
    const [k, dir] = sort; const rs = [...R.rows].sort((a, b) => (typeof a[k] === "string" ? a[k].localeCompare(b[k]) : a[k] - b[k]) * dir);
    $("#rows").innerHTML = rs.map(r => `<tr class="click" data-id="${esc(r.id)}" ${sel === r.id ? 'style="background:#ffffff0a"' : ""}><td><code>${esc(r.id)}</code></td><td>${pct(r.text_order_score)}</td><td>${pct(r.balanced_joint_f1)}</td><td>${pct(r.text_f1)}</td><td>${r.n_pred}</td><td>${r.n_ref}</td></tr>`).join("");
  }
  $("thead").addEventListener("click", e => { const k = e.target.dataset.s; if (!k) return; sort = [k, sort[0] === k ? -sort[1] : (k === "id" ? 1 : 1)]; rows(); });
  $("#rows").addEventListener("click", e => { const r = e.target.closest("[data-id]"); if (!r) return; sel = r.dataset.id; ip = 0; rows(); inspect(); $("#inspect").scrollIntoView({ behavior: "smooth", block: "nearest" }); });
  $$("#inTabs button").forEach((b, i) => b.onclick = () => { ip = i; inspect(); });
  function inspect() {
    const d = R.detail[sel]; $("#inspect").hidden = false; $("#inTitle").textContent = sel;
    $$("#inTabs button").forEach((b, i) => b.setAttribute("aria-selected", i === ip));
    const pairs = d.pairs[ip], mp = new Map(pairs.map(([i, j, s]) => [i, [j, s]])), mr = new Map(pairs.map(([i, j, s]) => [j, [i, s]]));
    $("#cPred").innerHTML = d.pred[ip].map((l, i) => `<div class="cl ${mp.has(i) ? "m" : "x"}"><small>${i + 1} · ${esc(l.speaker)}${mp.has(i) ? " · match " + Math.round(mp.get(i)[1] * 100) + "%" : " · no match"}</small>${esc(l.text)}</div>`).join("") || '<p class="muted">No lines predicted.</p>';
    $("#cRef").innerHTML = d.ref[ip].map((l, j) => `<div class="cl ${mr.has(j) ? "m" : "x"}"><small>${j + 1} · ${esc(l.speaker)}${mr.has(j) ? "" : " · missed"}</small>${esc(l.text)}</div>`).join("") || '<p class="muted">No reference lines.</p>';
  }
})();
