(() => {
  const { $, $$, esc } = FK; let A = null, saveT = null, preview = null;
  const setSaved = s => $("#saveState").textContent = s;
  const save = async () => { try { A = (await FK.patch(`/api/analyses/${A.id}`, { detail: A.detail })).analysis; setSaved("Saved"); } catch (e) { setSaved("Not saved"); FK.toast(e.message); } };
  const touch = () => { setSaved("Saving…"); clearTimeout(saveT); saveT = setTimeout(save, 500); render(); };
  const rename = (from, to) => { to = to.trim().replace(/\s+/g, "_"); if (!to || to === from) return; A.detail.forEach(p => p.forEach(l => { if (l.speaker === from) l.speaker = to; })); touch(); };

  function render() {
    $("#empty").hidden = !!A; $("#main2").hidden = !A; if (!A) return;
    $("#openIn").href = `/analyzer?open=${A.id}`;
    const names = FK.speakerNames(A.detail), all = [...names, ...(A.detail.flat().some(l => l.speaker === "NARRATION") ? ["NARRATION"] : [])];
    const cnt = n => A.detail.map(p => p.filter(l => l.speaker === n).length);
    $("#mSp").textContent = names.length; $("#mAll").textContent = names.filter(n => cnt(n).every(c => c > 0)).length; $("#mOnce").textContent = names.filter(n => cnt(n).reduce((a, b) => a + b, 0) === 1).length;
    $("#rows").innerHTML = all.map(n => { const c = cnt(n), tot = c.reduce((a, b) => a + b, 0);
      return `<tr><td>${FK.pill(n, names)}</td>${c.map(x => `<td>${x}</td>`).join("")}<td><b>${tot}</b></td>
      <td>${n === "NARRATION" ? '<span class="muted small">fixed</span>' : `<input data-ren="${esc(n)}" value="${esc(n)}" style="width:130px;padding:6px 10px" aria-label="Rename ${esc(n)}">`}</td>
      <td><select data-merge="${esc(n)}" style="width:130px;padding:6px 10px"><option value="">Choose…</option>${all.filter(o => o !== n).map(o => `<option>${esc(o)}</option>`).join("")}</select></td>
      <td>${n === "NARRATION" ? "" : `<button class="btn sm ghost" data-narr="${esc(n)}">Make narration</button>`}</td></tr>`; }).join("");
    const opt = names.map(n => `<option>${esc(n)}</option>`).join(""); $("#swA").innerHTML = opt; $("#swB").innerHTML = opt; if (names[1]) $("#swB").value = names[1];
    $("#timeline").innerHTML = A.detail.map((p, pi) => `<div><div class="muted small" style="margin-bottom:6px">Page ${pi + 1}</div><div class="row" style="gap:6px">${p.length ? p.map((l, i) => `<button class="num" data-dot="${pi}:${i}" title="${esc(l.speaker)}: ${esc(l.text)}" style="background:${FK.colorFor(l.speaker, names)};border:0;cursor:pointer">${l.order}</button>`).join("") : '<span class="muted small">No text</span>'}</div></div>`).join("");
  }
  $("#rows").addEventListener("change", e => { const t = e.target; if (t.dataset.ren !== undefined) rename(t.dataset.ren, t.value); if (t.dataset.merge !== undefined && t.value) rename(t.dataset.merge, t.value); });
  $("#rows").addEventListener("click", e => { const b = e.target.closest("[data-narr]"); if (b) rename(b.dataset.narr, "NARRATION"); });
  $("#swBtn").onclick = () => { const a = $("#swA").value, b = $("#swB").value; if (!a || a === b) return FK.toast("Pick two different speakers"); A.detail.forEach(p => p.forEach(l => { l.speaker = l.speaker === a ? b : l.speaker === b ? a : l.speaker; })); touch(); };
  $("#timeline").addEventListener("click", e => { const b = e.target.closest("[data-dot]"); if (!b) return; const [pi, i] = b.dataset.dot.split(":").map(Number); const names = FK.speakerNames(A.detail); if (!names.length) return; const l = A.detail[pi][i]; l.speaker = names[(names.indexOf(l.speaker) + 1) % names.length]; touch(); });

  $("#reThr").addEventListener("input", e => $("#reThrV").textContent = (+e.target.value).toFixed(2));
  $("#rePrev").onclick = async () => {
    $("#reMsg").textContent = "Working…"; $("#reApply").disabled = true;
    try { preview = (await FK.post(`/api/analyses/${A.id}/rerun`, { config: { speaker_mode: $("#reMode").value, speaker_thr: +$("#reThr").value } })).preview;
      const n = FK.speakerNames(preview.detail).length; $("#reMsg").textContent = `Would give ${n} speaker${n === 1 ? "" : "s"} across ${preview.detail.flat().length} lines.`; $("#reApply").disabled = false; }
    catch (e) { $("#reMsg").textContent = e.message; }
  };
  $("#reApply").onclick = async () => { if (!confirm("Replace this analysis with the automatic result? Your manual edits will be lost.")) return; try { A = (await FK.post(`/api/analyses/${A.id}/rerun`, { save: true, config: { speaker_mode: $("#reMode").value, speaker_thr: +$("#reThr").value } })).analysis; $("#reMsg").textContent = "Applied."; $("#reApply").disabled = true; render(); } catch (e) { FK.toast(e.message); } };

  const go = () => FK.initPicker($("#pick"), a => { A = a; render(); });
  document.addEventListener("fk:ready", go); document.addEventListener("fk:auth", go);
})();
