(() => {
  const { $, esc } = FK; let timer = null;
  const err = t => { const e = $("#err"); e.textContent = t || ""; e.hidden = !t; };
  async function init() { if (!FK.user) return; try { const g = (await FK.api("/api/samples")).groups; $("#grp").innerHTML = g.length ? g.map(x => `<option value="${esc(x.name)}">${esc(x.name.slice(-26))} (${x.count} sequences)</option>`).join("") : '<option value="">No folders found. Edit sample_dirs.txt</option>'; } catch (_) {} }
  document.addEventListener("fk:ready", init); document.addEventListener("fk:auth", init);

  $("#start").onclick = async () => {
    if (!FK.requireAuth()) return; err(""); const zip = $("#zipFile").files[0]; if (!zip && !$("#grp").value) return err("Upload a ZIP of 15 sequences or pick a local dataset folder.");
    const fd = new FormData(); if (zip) fd.append("zip_file", zip); else fd.append("group", $("#grp").value); if ($("#ids").files[0]) fd.append("ids_file", $("#ids").files[0]); if ($("#limit").value) fd.append("limit", $("#limit").value); if ($("#spk").value) fd.append("speaker_mode", $("#spk").value);
    $("#start").disabled = true;
    try { const { job, total } = await FK.api("/api/batch/start", { method: "POST", body: fd }); if (total !== 15) FK.toast(`Processing ${total} sequences; expected 15.`); $("#prog").hidden = false; $("#dl").hidden = true; $("#check").innerHTML = ""; $("#pStats").hidden = true; $("#tb").innerHTML = ""; poll(job); }
    catch (e) { err(e.message); $("#start").disabled = false; }
  };
  function poll(job) {
    clearInterval(timer);
    const tick = async () => {
      let d; try { d = await FK.api(`/api/batch/${job}`); } catch (e) { clearInterval(timer); err(e.message); $("#start").disabled = false; return; }
      $("#pCount").textContent = `${d.done} / ${d.total}`; $("#pBar").style.width = (d.total ? d.done / d.total * 100 : 0) + "%";
      $("#tb").innerHTML = d.rows.slice().reverse().map(r => `<tr><td><code>${esc(r.id)}</code></td>${r.lines.map(n => `<td>${n}</td>`).join("")}<td>${r.secs}</td></tr>`).join("");
      if (d.status === "done") {
        clearInterval(timer); $("#start").disabled = false; $("#pTitle").textContent = "Finished"; $("#pStats").hidden = false;
        $("#sLines").textContent = d.totalLines; $("#sEmpty").textContent = d.emptyPages; $("#sSecs").textContent = d.secs + "s";
        $("#check").innerHTML = (d.issues && d.issues.length) ? `<div class="card" style="border-color:var(--danger)"><b>Format check found ${d.issues.length} problem(s)</b><ul>${d.issues.slice(0, 8).map(i => `<li>${esc(i)}</li>`).join("")}</ul></div>` : `<div class="tag"><b>OK</b> Format check passed: every row has 3 page lists and valid lines.</div>`;
        if (d.errors.length) $("#check").innerHTML += `<p class="err">${d.errors.length} sequence(s) failed and were written with empty pages: ${esc(d.errors[0])}</p>`;
        $("#dl").href = `/api/batch/${job}/download`; $("#dl").hidden = false;
      } else $("#pTitle").textContent = "Running…";
    };
    tick(); timer = setInterval(tick, 1500);
  }
})();
