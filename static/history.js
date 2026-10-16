(() => {
  const { $, $$, esc } = FK; let list = [], picked = new Set(), src = "";
  async function load() { if (!FK.user) return; list = await FK.listAnalyses(); render(); }
  function render() {
    const q = $("#q").value.toLowerCase(), v = list.filter(a => (!src || a.source === src) && a.title.toLowerCase().includes(q));
    $("#empty").hidden = list.length > 0; $("#expAll").hidden = !list.length; $("#bulk").hidden = !picked.size; $("#selN").textContent = picked.size;
    $("#grid").innerHTML = v.map(a => `<article class="card hcard ${picked.has(a.id) ? "picked" : ""}" data-id="${a.id}">
      <div class="thumb" style="background-image:url('/api/analyses/${a.id}/overlay/0.jpg')"></div>
      <div class="body"><div class="row" style="justify-content:space-between;align-items:center"><b style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(a.title)}">${esc(a.title)}</b>${a.edited ? '<span class="tag" style="padding:1px 9px;font-size:12px">edited</span>' : ""}</div>
        <span class="muted small">${FK.fmtDate(a.created)} · ${a.nLines.reduce((x, y) => x + y, 0)} lines (${a.nLines.join(" / ")}) · ${a.secs}s</span>
        <div class="row" style="gap:6px"><a class="btn sm lime" href="/analyzer?open=${a.id}">Open</a><button class="btn sm" data-pick>${picked.has(a.id) ? "Unselect" : "Select"}</button><button class="btn sm ghost" data-ren>Rename</button><button class="btn sm ghost danger" data-del>Delete</button></div></div></article>`).join("");
  }
  $("#grid").addEventListener("click", async e => {
    const card = e.target.closest(".hcard"); if (!card) return; const id = +card.dataset.id, a = list.find(x => x.id === id);
    if (e.target.closest("[data-pick]")) { picked.has(id) ? picked.delete(id) : picked.add(id); render(); }
    else if (e.target.closest("[data-ren]")) { const t = prompt("New title", a.title); if (t && t.trim()) { await FK.patch(`/api/analyses/${id}`, { title: t }); a.title = t.trim(); render(); } }
    else if (e.target.closest("[data-del]")) { if (confirm(`Delete "${a.title}"?`)) { await FK.del(`/api/analyses/${id}`); list = list.filter(x => x.id !== id); picked.delete(id); render(); } }
    else if (!e.target.closest("a")) location.href = `/analyzer?open=${id}`;
  });
  $("#q").addEventListener("input", render);
  $$("#srcF button").forEach(b => b.onclick = () => { src = b.dataset.v; $$("#srcF button").forEach(x => x.setAttribute("aria-selected", x === b)); render(); });
  $("#clrSel").onclick = () => { picked.clear(); render(); };
  $("#delSel").onclick = async () => { if (!confirm(`Delete ${picked.size} analyses?`)) return; for (const id of picked) await FK.del(`/api/analyses/${id}`); picked.clear(); load(); };
  $("#expSel").onclick = () => location.href = `/api/export?ids=${[...picked].join(",")}`;
  $("#expAll").onclick = () => location.href = "/api/export";
  document.addEventListener("fk:ready", load); document.addEventListener("fk:auth", load);
})();
