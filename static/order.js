(() => {
  const { $, $$, esc } = FK; let A = null, page = 0, prev = null, saveT = null, rtl = true, dragFrom = null;
  const view = () => prev ? { detail: prev.detail, overlays: prev.overlays.map(o => o), sizes: prev.sizes, isPrev: true } : { detail: A.detail, overlays: A.overlays.map(o => o + "&rejected=1"), sizes: A.sizes, isPrev: false };
  const setSaved = s => $("#saveState").textContent = s;
  async function save() { try { A = (await FK.patch(`/api/analyses/${A.id}`, { detail: A.detail })).analysis; setSaved("Saved"); render(); } catch (e) { setSaved("Not saved"); FK.toast(e.message); } }
  const renumber = () => A.detail.forEach(p => p.forEach((l, i) => l.order = i + 1));

  function drawPath(v) {
    const svg = $("#path"), sz = v.sizes[page], L = v.detail[page].filter(l => l.box); svg.innerHTML = "";
    if (!$("#showPath").checked || !sz || L.length < 2) return;
    svg.setAttribute("viewBox", `0 0 ${sz[0]} ${sz[1]}`);
    const pts = L.map(l => [(l.box[0] + l.box[2]) / 2, (l.box[1] + l.box[3]) / 2]);
    svg.innerHTML = `<defs><marker id="ar" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L10 5L0 10z" fill="#c9f31d"/></marker></defs>` +
      pts.slice(1).map((p, i) => `<line x1="${pts[i][0]}" y1="${pts[i][1]}" x2="${p[0]}" y2="${p[1]}" stroke="#c9f31d" stroke-width="${sz[0] / 150}" stroke-dasharray="${sz[0] / 60} ${sz[0] / 90}" marker-end="url(#ar)" opacity=".95"/>`).join("");
  }
  function render() {
    $("#empty").hidden = !!A; $("#main2").hidden = !A; if (!A) return;
    $("#openIn").href = `/analyzer?open=${A.id}`; const v = view(), names = FK.speakerNames(A.detail);
    $$("#tabs button").forEach((b, i) => { b.setAttribute("aria-selected", i === page); b.onclick = () => { page = i; render(); }; });
    $("#ov").src = v.overlays[page]; $("#ov").onload = () => drawPath(v); drawPath(v);
    const oldIdx = {}; A.detail[page].forEach((l, i) => oldIdx[l.text + "|" + l.speaker] = i);
    $("#modeNote").textContent = v.isPrev ? "Previewing new order. Numbers show how far each line moved compared with your saved order." : "Drag a line to reorder it, or use the arrows. Changes save automatically.";
    $("#lines").innerHTML = v.detail[page].map((l, i) => { const o = oldIdx[l.text + "|" + l.speaker], d = o === undefined ? 0 : o - i;
      return `<div class="line" draggable="${!v.isPrev}" data-i="${i}" style="grid-template-columns:34px minmax(0,1fr) auto">
      <span class="num" style="background:${FK.colorFor(l.speaker, names)}">${i + 1}</span><div>${FK.pill(l.speaker, names)}<div style="margin-top:6px">${esc(l.text)}</div></div>
      ${v.isPrev ? `<span class="diff ${d > 0 ? "up" : d < 0 ? "dn" : ""}">${d === 0 ? "=" : (d > 0 ? "▲" : "▼") + Math.abs(d)}</span>` : `<div class="acts"><button class="iconbtn" data-a="up" aria-label="Move up">↑</button><button class="iconbtn" data-a="down" aria-label="Move down">↓</button></div>`}</div>`; }).join("") || '<p class="muted">No text on this page.</p>';
  }
  const move = (i, j) => { const L = A.detail[page]; if (j < 0 || j >= L.length) return; const [x] = L.splice(i, 1); L.splice(j, 0, x); renumber(); setSaved("Saving…"); clearTimeout(saveT); saveT = setTimeout(save, 500); render(); };
  $("#lines").addEventListener("click", e => { const b = e.target.closest("[data-a]"); if (!b) return; const i = +b.closest(".line").dataset.i; move(i, b.dataset.a === "up" ? i - 1 : i + 1); });
  $("#lines").addEventListener("dragstart", e => { const l = e.target.closest(".line"); if (l) { dragFrom = +l.dataset.i; e.dataTransfer.effectAllowed = "move"; } });
  $("#lines").addEventListener("dragover", e => { if (dragFrom !== null) e.preventDefault(); });
  $("#lines").addEventListener("drop", e => { const l = e.target.closest(".line"); if (l && dragFrom !== null) { e.preventDefault(); move(dragFrom, +l.dataset.i); } dragFrom = null; });

  $$("#dir button").forEach(b => b.onclick = () => { rtl = b.dataset.v === "1"; $$("#dir button").forEach(x => x.setAttribute("aria-selected", x === b)); });
  $("#alpha").addEventListener("input", e => $("#alV").textContent = (+e.target.value).toFixed(1));
  const cfg = () => ({ rtl, alpha: +$("#alpha").value, use_panels: $("#pan").checked });
  $("#prev").onclick = async () => { $("#msg").textContent = "Working…"; try { prev = (await FK.post(`/api/analyses/${A.id}/rerun`, { config: cfg() })).preview; $("#apply").disabled = false; $("#msg").textContent = "Preview ready. Apply to keep it (replaces manual edits), or tweak and preview again."; render(); } catch (e) { $("#msg").textContent = e.message; } };
  $("#apply").onclick = async () => { if (!confirm("Replace this analysis with the previewed order? Manual edits will be lost.")) return; try { A = (await FK.post(`/api/analyses/${A.id}/rerun`, { save: true, config: cfg() })).analysis; prev = null; $("#apply").disabled = true; $("#msg").textContent = "Applied."; render(); } catch (e) { FK.toast(e.message); } };
  $("#showPath").onchange = () => drawPath(view());

  const go = () => FK.initPicker($("#pick"), a => { A = a; prev = null; page = 0; $("#apply").disabled = true; if (a && a.config) { rtl = a.config.rtl !== false; $$("#dir button").forEach(b => b.setAttribute("aria-selected", (b.dataset.v === "1") === rtl)); $("#alpha").value = a.config.alpha ?? 1; $("#alV").textContent = (+$("#alpha").value).toFixed(1); $("#pan").checked = a.config.use_panels !== false; FK.initRanges(); } render(); });
  document.addEventListener("fk:ready", go); document.addEventListener("fk:auth", go);
})();
