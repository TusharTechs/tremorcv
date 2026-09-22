const $ = s => document.querySelector(s);
const SEL = {};
const fmt = (v, n = 2) => (v == null || Number.isNaN(v)) ? "—" : (+v).toFixed(n);

/* ---------- canvas plotting (no chart library: zero CDN deps, exact control) ---- */
function dpi(cv) {
  const r = window.devicePixelRatio || 1, w = cv.clientWidth, h = +cv.dataset.h;
  cv.width = w * r; cv.height = h * r;
  cv.style.height = h + "px";   // pin CSS height: otherwise the backing-store size
                                // becomes the layout height and the page doubles
  const c = cv.getContext("2d"); c.setTransform(r, 0, 0, r, 0, 0);
  return { c, w, h };
}
const CSSV = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

function axes(c, w, h, pad, xr, yr, xlab, ylab, ylog) {
  c.strokeStyle = CSSV("--line"); c.fillStyle = CSSV("--dim");
  c.font = "10px ui-monospace,monospace"; c.lineWidth = 1;
  c.beginPath(); c.moveTo(pad.l, pad.t); c.lineTo(pad.l, h - pad.b);
  c.lineTo(w - pad.r, h - pad.b); c.stroke();
  for (let i = 0; i <= 5; i++) {
    const x = pad.l + (w - pad.l - pad.r) * i / 5;
    const v = xr[0] + (xr[1] - xr[0]) * i / 5;
    c.beginPath(); c.moveTo(x, h - pad.b); c.lineTo(x, h - pad.b + 4); c.stroke();
    c.textAlign = "center"; c.fillText(v.toFixed(v < 10 ? 1 : 0), x, h - pad.b + 15);
  }
  for (let i = 0; i <= 4; i++) {
    const y = h - pad.b - (h - pad.t - pad.b) * i / 4;
    let v;
    if (ylog) v = Math.pow(10, Math.log10(yr[0]) + (Math.log10(yr[1]) - Math.log10(yr[0])) * i / 4);
    else v = yr[0] + (yr[1] - yr[0]) * i / 4;
    c.strokeStyle = i ? "rgba(255,255,255,.045)" : CSSV("--line");
    c.beginPath(); c.moveTo(pad.l, y); c.lineTo(w - pad.r, y); c.stroke();
    c.fillStyle = CSSV("--dim"); c.textAlign = "right";
    c.fillText(ylog ? v.toExponential(0) : (v < 0.1 ? v.toFixed(3) : v.toFixed(2)),
               pad.l - 6, y + 3);
  }
  c.textAlign = "center"; c.fillStyle = CSSV("--dim");
  c.fillText(xlab, (pad.l + w - pad.r) / 2, h - 2);
  c.save(); c.translate(11, (pad.t + h - pad.b) / 2); c.rotate(-Math.PI / 2);
  c.fillText(ylab, 0, 0); c.restore();
}

function drawSpectrum(d, peaks, shaft) {
  const cv = $("#spec"); const { c, w, h } = dpi(cv);
  c.clearRect(0, 0, w, h);
  if (!d || !d.freqs.length) return;
  const pad = { l: 52, r: 14, t: 12, b: 26 };
  const xr = [0, d.freqs[d.freqs.length - 1]];
  const amax = Math.max(...d.amps, 1e-6), hi = amax * 1.12;
  const X = f => pad.l + (w - pad.l - pad.r) * (f - xr[0]) / (xr[1] - xr[0] || 1);
  const Y = a => h - pad.b - (h - pad.t - pad.b) * Math.min(a / hi, 1);
  axes(c, w, h, pad, xr, [0, hi], "Hz", "px", false);

  if (shaft) {                                   // harmonic comb
    [1, 2, 3].forEach(k => {
      const f = shaft * k; if (f > xr[1]) return;
      c.strokeStyle = "rgba(77,212,196,.22)"; c.setLineDash([3, 3]);
      c.beginPath(); c.moveTo(X(f), pad.t); c.lineTo(X(f), h - pad.b); c.stroke();
      c.setLineDash([]); c.fillStyle = "rgba(77,212,196,.65)";
      c.font = "10px ui-monospace,monospace"; c.textAlign = "center";
      c.fillText(k + "×", X(f), pad.t + 9);
    });
  }
  c.beginPath(); c.moveTo(X(d.freqs[0]), h - pad.b);
  d.freqs.forEach((f, i) => c.lineTo(X(f), Y(d.amps[i])));
  c.lineTo(X(d.freqs[d.freqs.length - 1]), h - pad.b); c.closePath();
  c.fillStyle = "rgba(77,212,196,.13)"; c.fill();
  c.strokeStyle = CSSV("--accent"); c.lineWidth = 1.4; c.beginPath();
  d.freqs.forEach((f, i) => i ? c.lineTo(X(f), Y(d.amps[i])) : c.moveTo(X(f), Y(d.amps[i])));
  c.stroke();

  (peaks || []).slice(0, 3).forEach((p, i) => {
    c.fillStyle = i ? "rgba(240,168,66,.8)" : CSSV("--warn");
    c.beginPath(); c.arc(X(p.freq_hz), Y(p.amp_px), 3.5, 0, 7); c.fill();
    if (i === 0) {
      c.font = "600 11px ui-monospace,monospace"; c.textAlign = "left";
      c.fillText(`${p.freq_hz.toFixed(2)} Hz`, X(p.freq_hz) + 7, Y(p.amp_px) - 4);
    }
  });
}

function drawTrace(t, fps) {
  const cv = $("#trace"); const { c, w, h } = dpi(cv);
  c.clearRect(0, 0, w, h);
  if (!t || !t.length) return;
  const pad = { l: 52, r: 14, t: 10, b: 24 };
  const m = Math.max(...t.map(Math.abs), 1e-6) * 1.15;
  const secs = fps ? t.length / fps : t.length;
  axes(c, w, h, pad, [0, secs], [-m, m], "seconds", "px", false);
  const X = i => pad.l + (w - pad.l - pad.r) * i / (t.length - 1);
  const Y = v => (pad.t + h - pad.b) / 2 - (h - pad.t - pad.b) / 2 * (v / m);
  c.strokeStyle = CSSV("--accent"); c.lineWidth = 1; c.beginPath();
  t.forEach((v, i) => i ? c.lineTo(X(i), Y(v)) : c.moveTo(X(i), Y(v)));
  c.stroke();
}

/* ---------- rendering ------------------------------------------------------- */
function stats(p) {
  const m = p.measurement, q = p.quality, s = p.surface, pk = m.peaks[0];
  const items = [
    ["peak", pk ? fmt(pk.freq_hz) + " Hz" : "—"],
    ["amplitude", pk ? fmt(pk.amp_px, 3) + " px" : "—"],
    ["SNR", pk ? fmt(pk.snr, 1) : "—"],
    ["texture", fmt(s.texture_std, 1)],
    ["camera motion", fmt(m.cam_rms_px, 1) + " px"],
    ["stabilized", m.stabilized ? "yes" : "not needed"],
    ["rejected frames", fmt(m.reject_frac * 100, 1) + "%"],
    ["nyquist", fmt(m.nyquist_hz, 1) + " Hz"],
  ];
  $("#stats").innerHTML = items.map(([k, v]) =>
    `<div class="stat"><div class="k">${k}</div><div class="v${v.length > 9 ? " small" : ""}">${v}</div></div>`).join("");
  $("#specSub").textContent =
    `${m.fps} fps · ${fmt(m.duration_s, 1)} s · ${fmt(m.bin_hz, 3)} Hz resolution · noise floor ${fmt(m.noise_floor_px, 4)} px`;
  $("#traceSub").textContent = m.stabilized
    ? "after cancelling camera motion against the static reference"
    : "camera was steady enough that stabilization would only add noise";
}

function renderStep(ev) {
  const el = document.createElement("div");
  if (ev.type === "acquiring") {
    el.className = "step acquiring"; el.id = "acq" + ev.n;
    el.innerHTML = `<div class="hd"><span class="n">${ev.n}</span>
      <span class="act">capturing <span class="spin"></span></span></div>
      <div class="meta">${ev.describe}</div>`;
  } else {
    const prev = $("#acq" + ev.n); if (prev) prev.remove();
    const q = ev.quality;
    el.className = "step " + ev.decision;
    el.innerHTML = `<div class="hd"><span class="n">${ev.n}</span>
      <span class="act">${ev.decision.replace("_", " ")}</span></div>
      <div class="meta">${ev.describe}</div>
      <div class="badges">${q.trustworthy
        ? '<span class="badge ok">trustworthy</span>'
        : q.reasons.map(r => `<span class="badge">${r}</span>`).join("")}</div>
      <div class="why">${ev.why}</div>`;
  }
  $("#steps").appendChild(el);
  el.scrollIntoView({ behavior: "smooth", block: "end" });
}

function renderVerdict(ev) {
  const d = ev.diagnosis, ok = ev.decision === "report";
  const correct = d && ev.truth && d.fault === ev.truth.fault;
  $("#verdict").innerHTML = `<div class="verdict ${ev.decision}">
    <div class="lab">${ok ? "diagnosis" : "escalated to a human"}</div>
    <div class="fault">${d ? d.fault.replace(/_/g, " ") : "no call made"}</div>
    <div class="conf">${d ? "confidence " + fmt(d.confidence) : (ev.reason || "not trustworthy")}
      · ${ev.acquisitions} acquisition${ev.acquisitions > 1 ? "s" : ""} · ${ev.elapsed_s}s</div>
    ${ev.truth ? `<div class="truth">ground truth: <b>${ev.truth.fault.replace(/_/g, " ")}</b>
      at ${ev.truth.shaft_hz} Hz ${ok ? (correct ? "— <b style='color:var(--good)'>correct</b>"
        : "— <b style='color:var(--bad)'>wrong</b>") : "— declined rather than guessed"}</div>` : ""}
  </div>`;
}

/* ---------- custom select (native <select> cannot theme its open list) ------- */
function makeSelect(host, opts, value, onPick) {
  const cur = () => opts.find(o => o.v === host.dataset.v) || opts[0];
  host.dataset.v = value;
  host.innerHTML = `<button type="button" class="sel-btn"><span class="val"></span><span class="chev"></span></button>
    <div class="sel-list" hidden></div>`;
  const btn = host.querySelector(".sel-btn"), list = host.querySelector(".sel-list");
  const paint = () => { host.querySelector(".val").textContent = cur().label; };
  list.innerHTML = opts.map(o =>
    `<div class="sel-opt" data-v="${o.v}"><span class="tick"></span><span>${o.label}</span>${
      o.sub ? `<span class="sub">${o.sub}</span>` : ""}</div>`).join("");
  const sync = () => list.querySelectorAll(".sel-opt").forEach(el => {
    const on = el.dataset.v === host.dataset.v;
    el.classList.toggle("sel-on", on);
    el.querySelector(".tick").textContent = on ? "\u2713" : "";
  });
  const close = () => { list.hidden = true; host.classList.remove("open"); };
  btn.onclick = e => {
    e.stopPropagation();
    document.querySelectorAll(".sel.open").forEach(s => s !== host && (s.classList.remove("open"),
      s.querySelector(".sel-list").hidden = true));
    list.hidden = !list.hidden; host.classList.toggle("open", !list.hidden); sync();
  };
  list.onclick = e => {
    const o = e.target.closest(".sel-opt"); if (!o) return;
    host.dataset.v = o.dataset.v; paint(); sync(); close(); onPick && onPick(o.dataset.v);
  };
  document.addEventListener("click", close);
  host.addEventListener("keydown", e => e.key === "Escape" && close());
  paint(); sync();
  return { get value() { return host.dataset.v; } };
}

/* ---------- wiring ---------------------------------------------------------- */
let es = null;
async function boot() {
  try {
    const h = await (await fetch("/api/health")).json();
    $("#cvPill").textContent = "opencv " + h.opencv;
    $("#cvPill").classList.add("on");
    $("#coolPill").textContent = h.cool_verified ? "cool verified" : `cool: no (${h.instance})`;
    if (h.cool_verified) $("#coolPill").classList.add("on");
  } catch (e) { $("#cvPill").textContent = "backend offline"; }
  const cfg = await (await fetch("/api/config")).json();
  SEL.fault = makeSelect($("#faultSel"),
    cfg.faults.map(f => ({ v: f, label: f.replace(/_/g, " ") })), "misalignment");
  SEL.aim = makeSelect($("#aimSel"),
    Object.entries(cfg.aim_points).map(([k, v]) =>
      ({ v: k, label: k.replace(/_/g, " "), sub: "contrast " + v })), "housing");
}

$("#shaft").oninput = e => {
  $("#shaftV").textContent = (+e.target.value).toFixed(1);
  $("#rpmV").textContent = Math.round(e.target.value * 60);
};
$("#sev").oninput = e => $("#sevV").textContent = (+e.target.value).toFixed(2);
$("#tabSim").onclick = () => { $("#tabSim").classList.add("sel"); $("#tabUp").classList.remove("sel"); $("#paneSim").hidden = false; $("#paneUp").hidden = true; };
$("#tabUp").onclick = () => { $("#tabUp").classList.add("sel"); $("#tabSim").classList.remove("sel"); $("#paneUp").hidden = false; $("#paneSim").hidden = true; };

$("#run").onclick = () => {
  if (es) es.close();
  $("#steps").innerHTML = ""; $("#verdict").innerHTML = ""; $("#simErr").textContent = "";
  $("#previewCard").hidden = true;
  $("#run").disabled = true; $("#run").textContent = "Agent running…";
  const q = new URLSearchParams({
    shaft_hz: $("#shaft").value, fault: SEL.fault.value,
    severity_px: $("#sev").value, start_aim: SEL.aim.value,
  });
  es = new EventSource("/api/agent/stream?" + q);
  es.onmessage = m => {
    const ev = JSON.parse(m.data);
    if (ev.type === "acquiring") renderStep(ev);
    else if (ev.type === "step") {
      renderStep(ev);
      drawSpectrum(ev.spectrum, ev.measurement.peaks, ev.shaft_hz);
      drawTrace(ev.trace, ev.measurement.fps);
      stats(ev);
    } else if (ev.type === "done") {
      renderVerdict(ev); es.close(); es = null;
      $("#run").disabled = false; $("#run").textContent = "Run agent";
    }
  };
  es.onerror = () => {
    $("#simErr").textContent = "stream failed — is the server running?";
    if (es) es.close(); es = null;
    $("#run").disabled = false; $("#run").textContent = "Run agent";
  };
};

$("#file").onchange = e => {
  const f = e.target.files[0], b = $("#fileBtn");
  b.classList.toggle("has", !!f);
  b.querySelector(".nm").textContent = f ? f.name : "Choose a video";
  b.querySelector(".sz").textContent = f ? (f.size / 1048576).toFixed(1) + " MB" : "";
};

$("#analyze").onclick = async () => {
  const f = $("#file").files[0];
  if (!f) { $("#upErr").textContent = "choose a video first"; return; }
  $("#upErr").textContent = ""; $("#analyze").disabled = true;
  $("#analyze").textContent = "Measuring…"; $("#steps").innerHTML = ""; $("#verdict").innerHTML = "";
  const fd = new FormData(); fd.append("file", f); fd.append("fps", $("#fps").value);
  try {
    const r = await fetch("/api/measure", { method: "POST", body: fd });
    const p = await r.json();
    if (!r.ok) throw new Error(p.detail || r.statusText);
    const s = p.source;
    if (p.preview) {
      $("#preview").src = p.preview;
      $("#previewCard").hidden = false;
      const rd = p.roi_diagnostics || {};
      $("#previewSub").textContent = s.rois_auto
        ? `located automatically — ${fmt(rd.vibration_target, 2)} vs ${fmt(rd.vibration_reference, 2)} vibration energy after high-passing above ${rd.highpass_cut_hz} Hz`
        : "regions supplied manually";
    }
    drawSpectrum(p.spectrum, p.measurement.peaks, p.shaft_hz);
    drawTrace(p.trace, p.measurement.fps); stats(p);
    $("#steps").innerHTML = `<div class="step ${p.quality.trustworthy ? "report" : "escalate"}">
      <div class="hd"><span class="n">1</span><span class="act">measured</span></div>
      <div class="meta">${s.filename} · ${s.width}×${s.height} · ${s.frames} frames @ ${s.fps} fps</div>
      <div class="badges">${p.quality.trustworthy ? '<span class="badge ok">trustworthy</span>'
        : p.quality.reasons.map(r => `<span class="badge">${r}</span>`).join("")}</div>
      <div class="why">${p.shaft_hz ? `Shaft estimated at ${fmt(p.shaft_hz)} Hz by harmonic-comb scoring.`
        : "No peak rose above the SNR threshold."}</div></div>`;
    if (p.diagnosis) renderVerdict({ decision: "report", diagnosis: p.diagnosis,
      acquisitions: 1, elapsed_s: 0, truth: null });
  } catch (e) { $("#upErr").textContent = String(e.message || e); }
  $("#analyze").disabled = false; $("#analyze").textContent = "Measure";
};

boot();
