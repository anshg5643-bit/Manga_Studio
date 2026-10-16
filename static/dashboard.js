(() => {
  const { $, esc } = FK;
  const cs = i => FK.PALETTE[i % FK.PALETTE.length];
  async function load() {
    if (!FK.user) return; const [s, sys] = await Promise.all([FK.api("/api/stats"), FK.api("/api/system").catch(() => null)]), t = s.totals;
    $("#empty").hidden = t.analyses > 0;
    $("#nAn").innerHTML = `${t.analyses}<small>total</small>`; $("#nLines").innerHTML = `${t.lines}<small>lines extracted</small>`; $("#nEdit").innerHTML = `${t.edited}<small>edited by hand</small>`;
    $("#avgConf").innerHTML = `${Math.round(t.avgConf * 100)}%<small>average</small>`;
    $("#recent").innerHTML = s.recent.length ? s.recent.map((a, i) => `<a class="member" href="/analyzer?open=${a.id}"><div class="avatar" style="background:${cs(i)}">${esc((a.title[0] || "?").toUpperCase())}</div><b style="display:block;font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(a.title)}</b><span class="muted small">${a.nLines.reduce((x, y) => x + y, 0)} lines</span></a>`).join("") : '<span class="muted small">Nothing yet</span>';
    // line chart
    const d = s.days, max = Math.max(1, ...d.map(x => x.n)), pts = d.map((x, i) => [i / (d.length - 1) * 300, 140 - x.n / max * 120]);
    $("#line").innerHTML = `<defs><linearGradient id="lg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c9f31d" stop-opacity=".35"/><stop offset="1" stop-color="#c9f31d" stop-opacity="0"/></linearGradient></defs><path d="M0 140 ${pts.map(p => `L${p[0]} ${p[1]}`).join(" ")} L300 140Z" fill="url(#lg)"/><polyline points="${pts.map(p => p.join(",")).join(" ")}" fill="none" stroke="#c9f31d" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>`;
    const lp = t.linesPerPage, lm = Math.max(1, ...lp);
    $("#perPage").innerHTML = lp.map((v, i) => `<div><b>Page ${i + 1}</b><div class="fill" style="width:${Math.max(14, v / lm * 100)}%">${v}</div></div>`).join("");
    const st = s.recent.slice(0, 3); $("#stackc").innerHTML = st.length ? st.map(a => `<a href="/analyzer?open=${a.id}"><span><b style="display:block;font-size:22px">${a.nLines.reduce((x, y) => x + y, 0)}</b><span style="opacity:.7;font-size:13px">${esc(a.title.slice(0, 24))}</span></span><span style="opacity:.7;font-size:13px">${FK.fmtDate(a.created)}</span></a>`).join("") : '<p class="muted small">No activity yet.</p>';
    $("#words").innerHTML = s.topWords.length ? s.topWords.map(([w, n]) => `<span class="tag">${esc(w)} <b>${n}</b></span>`).join("") : '<span class="muted small">No words yet</span>';
    $("#cols").innerHTML = d.map((x, i) => `<i title="${x.day}: ${x.n}" class="${x.n === max && x.n > 0 ? "hi" : ""}" style="height:${Math.max(3, x.n / max * 100)}%"></i>`).join("");
    const sm = Math.max(1, ...s.speakers.map(x => x[1])); $("#spk").innerHTML = s.speakers.map(([n, c], i) => `<div><b>${esc(n)}</b><div class="fill" style="width:${Math.max(12, c / sm * 100)}%;background:${n === "NARRATION" ? "#9aa0a8" : cs(i)}">${c}</div></div>`).join("") || '<span class="muted small">No speakers yet</span>';
    const cm = Math.max(1, ...s.confBins); $("#conf").innerHTML = s.confBins.map((c, i) => `<i title="${i * 20}-${i * 20 + 20}%: ${c}" class="${c === cm && c > 0 ? "hi" : ""}" style="height:${Math.max(3, c / cm * 100)}%"></i>`).join("");
    const m = (l, v) => `<div class="metric"><b style="font-size:26px">${v}</b><span>${l}</span></div>`;
    $("#sys").innerHTML = m("seconds per sequence", t.avgSecs) + (sys ? m("CPU cores", sys.cpu) + m("text filter", sys.trainedFilter ? "trained" : "rule-based") + m("OCR runtime", sys.onnxruntime ? "ONNX " + sys.onnxruntime : "n/a") : "");
  }
  document.addEventListener("fk:ready", load); document.addEventListener("fk:auth", load);
})();
