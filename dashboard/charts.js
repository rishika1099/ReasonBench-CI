/* Tiny dependency-free SVG chart library shared by all portfolio dashboards.
   Forms: bar, groupedBar, line (multi-series with crosshair), scatter, heatmap.
   All charts get hover tooltips; legends render automatically for >= 2 series. */

(function () {
  const NS = "http://www.w3.org/2000/svg";
  const SERIES = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)", "var(--s5)", "var(--s6)", "var(--s7)", "var(--s8)"];
  const SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#1c5cab", "#104281", "#0d366b"];

  function el(tag, attrs, parent) {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }

  function fmt(v, digits) {
    if (v === null || v === undefined || Number.isNaN(v)) return "-";
    if (v === 0) return "0";
    if (typeof digits === "number") return v.toFixed(digits);
    const a = Math.abs(v);
    if (a >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
    if (a >= 100) return v.toFixed(0);
    if (a >= 10) return v.toFixed(1);
    if (a >= 1) return v.toFixed(2);
    return v.toFixed(3);
  }

  function niceTicks(max, n) {
    if (max <= 0) max = 1;
    const raw = max / n;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) || raw;
    const ticks = [];
    for (let v = 0; v <= max * 1.0001; v += step) ticks.push(+v.toPrecision(12));
    return ticks;
  }

  function tipFor(box) {
    let t = box.querySelector(".viz-tip");
    if (!t) {
      t = document.createElement("div");
      t.className = "viz-tip";
      box.appendChild(t);
    }
    return t;
  }

  function showTip(box, tip, x, y, html) {
    tip.innerHTML = html;
    tip.style.display = "block";
    const bw = box.clientWidth, tw = tip.offsetWidth;
    let left = x + 12;
    if (left + tw > bw - 4) left = x - tw - 12;
    tip.style.left = Math.max(4, left) + "px";
    tip.style.top = Math.max(4, y - tip.offsetHeight - 10) + "px";
  }

  function tipRow(color, label, value) {
    return '<div class="r"><span class="sw" style="background:' + color + '"></span>' + label + ": <b>" + value + "</b></div>";
  }

  function legend(box, series) {
    if (series.length < 2) return;
    const lg = document.createElement("div");
    lg.className = "viz-legend";
    series.forEach(s => {
      lg.innerHTML += '<span class="li"><span class="sw" style="background:' + s.color + '"></span>' + s.name + "</span>";
    });
    box.parentNode.insertBefore(lg, box);
  }

  function frame(box, opts) {
    // fixed viewBox width; the SVG scales to the container via width:100%,
    // so we never depend on a mid-layout clientWidth reading
    const W = opts.width || 640;
    const H = opts.height || 240;
    const pad = Object.assign({ t: 12, r: 14, b: 34, l: 48 }, opts.pad || {});
    const svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: "100%", height: H }, box);
    return { svg, W, H, pad, iw: W - pad.l - pad.r, ih: H - pad.t - pad.b };
  }

  function yAxis(f, max, unit) {
    const ticks = niceTicks(max, 4);
    ticks.forEach(v => {
      const y = f.pad.t + f.ih - (v / max) * f.ih;
      el("line", { x1: f.pad.l, x2: f.pad.l + f.iw, y1: y, y2: y, stroke: "var(--grid)", "stroke-width": 1 }, f.svg);
      el("text", { x: f.pad.l - 6, y: y + 4, "text-anchor": "end", "font-size": 11, fill: "var(--ink-muted)" }, f.svg)
        .textContent = fmt(v) + (unit && v === ticks[ticks.length - 1] ? "" : "");
    });
    el("line", { x1: f.pad.l, x2: f.pad.l + f.iw, y1: f.pad.t + f.ih, y2: f.pad.t + f.ih, stroke: "var(--baseline)", "stroke-width": 1 }, f.svg);
    if (unit) el("text", { x: f.pad.l - 38, y: f.pad.t - 1, "font-size": 11, fill: "var(--ink-muted)" }, f.svg).textContent = unit;
    return ticks[ticks.length - 1];
  }

  /* Vertical bars with 4px rounded data-end and 2px gaps. */
  function bar(box, opts) {
    box.classList.add("chart-box");
    const f = frame(box, opts);
    const tip = tipFor(box);
    const labels = opts.labels, values = opts.values;
    const color = opts.color || SERIES[0];
    const max = yAxis(f, Math.max(...values) * (opts.showValues ? 1.16 : 1.08), opts.unit);
    const n = values.length;
    const slot = f.iw / n;
    const bw = Math.min(slot - 2, opts.maxBarWidth || 46);
    values.forEach((v, i) => {
      const h = Math.max(1, (v / max) * f.ih);
      const x = f.pad.l + i * slot + (slot - bw) / 2;
      const y = f.pad.t + f.ih - h;
      const r = Math.min(4, bw / 2, h);
      const c = Array.isArray(color) ? color[i % color.length] : color;
      const d = "M" + x + "," + (y + h) + " v" + (-(h - r)) + " q0,-" + r + " " + r + ",-" + r +
        " h" + (bw - 2 * r) + " q" + r + ",0 " + r + "," + r + " v" + (h - r) + " z";
      const p = el("path", { d, style: "fill:" + c }, f.svg);
      p.addEventListener("mousemove", e => {
        const rb = box.getBoundingClientRect();
        showTip(box, tip, e.clientX - rb.left, e.clientY - rb.top,
          '<div class="t">' + labels[i] + "</div>" + tipRow(c, opts.unit || "value", fmt(v, opts.digits)));
      });
      p.addEventListener("mouseleave", () => tip.style.display = "none");
      if (opts.showValues) {
        el("text", { x: x + bw / 2, y: y - 5, "text-anchor": "middle", "font-size": 11, fill: "var(--ink-2)" }, f.svg)
          .textContent = fmt(v, opts.digits);
      }
      const lbl = el("text", { x: x + bw / 2, y: f.pad.t + f.ih + 16, "text-anchor": "middle", "font-size": 11, fill: "var(--ink-muted)" }, f.svg);
      lbl.textContent = String(labels[i]).length > 14 ? String(labels[i]).slice(0, 13) + "…" : labels[i];
    });
  }

  /* Grouped vertical bars, one color per series, 2px gap inside groups. */
  function groupedBar(box, opts) {
    box.classList.add("chart-box");
    const series = opts.series.map((s, i) => ({ name: s.name, values: s.values, color: s.color || SERIES[i] }));
    legend(box, series);
    const f = frame(box, opts);
    const tip = tipFor(box);
    const labels = opts.labels;
    const maxV = Math.max(...series.flatMap(s => s.values));
    const max = yAxis(f, maxV * 1.08, opts.unit);
    const n = labels.length, k = series.length;
    const slot = f.iw / n;
    const groupW = Math.min(slot - 8, k * 26);
    const bw = Math.max(4, groupW / k - 2);
    labels.forEach((lab, i) => {
      series.forEach((s, j) => {
        const v = s.values[i];
        if (v === null || v === undefined) return;
        const h = Math.max(1, (v / max) * f.ih);
        const gx = f.pad.l + i * slot + (slot - groupW) / 2;
        const x = gx + j * (bw + 2);
        const y = f.pad.t + f.ih - h;
        const r = Math.min(4, bw / 2, h);
        const d = "M" + x + "," + (y + h) + " v" + (-(h - r)) + " q0,-" + r + " " + r + ",-" + r +
          " h" + (bw - 2 * r) + " q" + r + ",0 " + r + "," + r + " v" + (h - r) + " z";
        const p = el("path", { d, style: "fill:" + s.color }, f.svg);
        p.addEventListener("mousemove", e => {
          const rb = box.getBoundingClientRect();
          showTip(box, tip, e.clientX - rb.left, e.clientY - rb.top,
            '<div class="t">' + lab + "</div>" + tipRow(s.color, s.name, fmt(v, opts.digits) + (opts.unitSuffix || "")));
        });
        p.addEventListener("mouseleave", () => tip.style.display = "none");
      });
      const lbl = el("text", { x: f.pad.l + i * slot + slot / 2, y: f.pad.t + f.ih + 16, "text-anchor": "middle", "font-size": 11, fill: "var(--ink-muted)" }, f.svg);
      lbl.textContent = String(lab).length > 14 ? String(lab).slice(0, 13) + "…" : lab;
    });
  }

  /* Multi-series line chart with shared crosshair tooltip. */
  function line(box, opts) {
    box.classList.add("chart-box");
    const series = opts.series.map((s, i) => ({ name: s.name, values: s.values, color: s.color || SERIES[i] }));
    legend(box, series);
    const f = frame(box, opts);
    const tip = tipFor(box);
    const xs = opts.x;
    const allV = series.flatMap(s => s.values).filter(v => v !== null && v !== undefined);
    const maxV = opts.yMax !== undefined ? opts.yMax : Math.max(...allV) * 1.08;
    const max = yAxis(f, maxV, opts.unit);
    const px = i => f.pad.l + (xs.length === 1 ? f.iw / 2 : (i / (xs.length - 1)) * f.iw);
    const py = v => f.pad.t + f.ih - (v / max) * f.ih;
    const step = Math.max(1, Math.ceil(xs.length / 8));
    xs.forEach((x, i) => {
      if (i % step !== 0 && i !== xs.length - 1) return;
      el("text", { x: px(i), y: f.pad.t + f.ih + 16, "text-anchor": "middle", "font-size": 11, fill: "var(--ink-muted)" }, f.svg).textContent = x;
    });
    if (opts.xLabel) el("text", { x: f.pad.l + f.iw / 2, y: f.H - 2, "text-anchor": "middle", "font-size": 11, fill: "var(--ink-muted)" }, f.svg).textContent = opts.xLabel;
    series.forEach(s => {
      let d = "";
      s.values.forEach((v, i) => {
        if (v === null || v === undefined) return;
        d += (d ? " L" : "M") + px(i) + "," + py(v);
      });
      el("path", { d, fill: "none", style: "stroke:" + s.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, f.svg);
    });
    const cross = el("line", { y1: f.pad.t, y2: f.pad.t + f.ih, stroke: "var(--baseline)", "stroke-width": 1, opacity: 0 }, f.svg);
    const dots = series.map(s => el("circle", { r: 4, style: "fill:" + s.color + ";stroke:var(--surface-1);stroke-width:2", opacity: 0 }, f.svg));
    const hit = el("rect", { x: f.pad.l, y: f.pad.t, width: f.iw, height: f.ih, fill: "transparent" }, f.svg);
    hit.addEventListener("mousemove", e => {
      const rb = box.getBoundingClientRect();
      const mx = e.clientX - rb.left;
      const svgX = mx * (f.W / box.clientWidth);
      let i = Math.round(((svgX - f.pad.l) / f.iw) * (xs.length - 1));
      i = Math.max(0, Math.min(xs.length - 1, i));
      cross.setAttribute("x1", px(i)); cross.setAttribute("x2", px(i));
      cross.setAttribute("opacity", 1);
      let html = '<div class="t">' + (opts.xLabel ? opts.xLabel + " " : "") + xs[i] + "</div>";
      series.forEach((s, j) => {
        const v = s.values[i];
        if (v === null || v === undefined) { dots[j].setAttribute("opacity", 0); return; }
        dots[j].setAttribute("cx", px(i)); dots[j].setAttribute("cy", py(v)); dots[j].setAttribute("opacity", 1);
        html += tipRow(s.color, s.name, fmt(v, opts.digits) + (opts.unitSuffix || ""));
      });
      showTip(box, tip, mx, e.clientY - rb.top, html);
    });
    hit.addEventListener("mouseleave", () => {
      tip.style.display = "none"; cross.setAttribute("opacity", 0);
      dots.forEach(d => d.setAttribute("opacity", 0));
    });
  }

  /* Scatter plot: points = [{x, y, label, series}] */
  function scatter(box, opts) {
    box.classList.add("chart-box");
    const names = [...new Set(opts.points.map(p => p.series || ""))];
    const series = names.map((n, i) => ({ name: n, color: SERIES[i] }));
    if (names.length > 1) legend(box, series);
    const f = frame(box, opts);
    const tip = tipFor(box);
    const maxX = Math.max(...opts.points.map(p => p.x)) * 1.08;
    const maxY = Math.max(...opts.points.map(p => p.y)) * 1.08;
    const max = yAxis(f, maxY, opts.yUnit);
    niceTicks(maxX, 5).forEach(v => {
      const x = f.pad.l + (v / maxX) * f.iw;
      el("text", { x, y: f.pad.t + f.ih + 16, "text-anchor": "middle", "font-size": 11, fill: "var(--ink-muted)" }, f.svg).textContent = fmt(v);
    });
    if (opts.xLabel) el("text", { x: f.pad.l + f.iw / 2, y: f.H - 2, "text-anchor": "middle", "font-size": 11, fill: "var(--ink-muted)" }, f.svg).textContent = opts.xLabel;
    opts.points.forEach(p => {
      const color = series[names.indexOf(p.series || "")].color;
      const cx = f.pad.l + (p.x / maxX) * f.iw;
      const cy = f.pad.t + f.ih - (p.y / max) * f.ih;
      const c = el("circle", { cx, cy, r: 5, style: "fill:" + color + ";stroke:var(--surface-1);stroke-width:2" }, f.svg);
      c.addEventListener("mousemove", e => {
        const rb = box.getBoundingClientRect();
        showTip(box, tip, e.clientX - rb.left, e.clientY - rb.top,
          '<div class="t">' + (p.label || p.series || "") + "</div>" +
          tipRow(color, opts.xLabel || "x", fmt(p.x)) + tipRow(color, opts.yUnit || "y", fmt(p.y)));
      });
      c.addEventListener("mouseleave", () => tip.style.display = "none");
      if (p.label && opts.labelPoints) {
        el("text", { x: cx + 8, y: cy + 4, "font-size": 11, fill: "var(--ink-2)" }, f.svg).textContent = p.label;
      }
    });
  }

  function lerpSeq(t) {
    const s = Math.max(0, Math.min(0.9999, t)) * (SEQ.length - 1);
    const i = Math.floor(s), fr = s - i;
    const a = SEQ[i], b = SEQ[i + 1];
    const c = k => Math.round(parseInt(a.slice(k, k + 2), 16) * (1 - fr) + parseInt(b.slice(k, k + 2), 16) * fr);
    return "rgb(" + c(1) + "," + c(3) + "," + c(5) + ")";
  }

  /* Heatmap: rows x cols matrix, sequential blue ramp, tooltip per cell. */
  function heatmap(box, opts) {
    box.classList.add("chart-box");
    const rows = opts.rows, cols = opts.cols, vals = opts.values;
    const pad = { t: 10, r: 14, b: 40, l: opts.leftPad || 92 };
    const W = opts.width || 640;
    const cw = (W - pad.l - pad.r) / cols.length;
    const ch = opts.cellHeight || 30;
    const H = pad.t + rows.length * ch + pad.b;
    const svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: "100%", height: H }, box);
    const tip = tipFor(box);
    let lo = opts.min !== undefined ? opts.min : Math.min(...vals.flat());
    let hi = opts.max !== undefined ? opts.max : Math.max(...vals.flat());
    if (hi === lo) hi = lo + 1;
    rows.forEach((r, i) => {
      el("text", { x: pad.l - 8, y: pad.t + i * ch + ch / 2 + 4, "text-anchor": "end", "font-size": 11, fill: "var(--ink-2)" }, svg).textContent = r;
      cols.forEach((c, j) => {
        const v = vals[i][j];
        const t = (v - lo) / (hi - lo);
        const cell = el("rect", {
          x: pad.l + j * cw + 1, y: pad.t + i * ch + 1,
          width: cw - 2, height: ch - 2, rx: 3, fill: lerpSeq(t)
        }, svg);
        if (opts.showValues && cw > 34) {
          el("text", {
            x: pad.l + j * cw + cw / 2, y: pad.t + i * ch + ch / 2 + 4,
            "text-anchor": "middle", "font-size": 10.5,
            fill: t > 0.55 ? "#ffffff" : "#0b0b0b"
          }, svg).textContent = fmt(v, opts.digits);
        }
        cell.addEventListener("mousemove", e => {
          const rb = box.getBoundingClientRect();
          showTip(box, tip, e.clientX - rb.left, e.clientY - rb.top,
            '<div class="t">' + r + " / " + c + "</div>" + tipRow(lerpSeq(t), opts.unit || "value", fmt(v, opts.digits)));
        });
        cell.addEventListener("mouseleave", () => tip.style.display = "none");
      });
    });
    cols.forEach((c, j) => {
      el("text", { x: pad.l + j * cw + cw / 2, y: pad.t + rows.length * ch + 16, "text-anchor": "middle", "font-size": 11, fill: "var(--ink-muted)" }, svg).textContent = c;
    });
    if (opts.xLabel) el("text", { x: pad.l + (W - pad.l - pad.r) / 2, y: H - 4, "text-anchor": "middle", "font-size": 11, fill: "var(--ink-muted)" }, svg).textContent = opts.xLabel;
  }

  function tiles(container, items) {
    items.forEach(it => {
      const t = document.createElement("div");
      t.className = "tile";
      t.innerHTML = '<div class="k">' + it.k + '</div><div class="v">' + it.v + "</div>" +
        (it.d ? '<div class="d ' + (it.dir || "") + '">' + it.d + "</div>" : "");
      container.appendChild(t);
    });
  }

  function table(container, cols, rows) {
    const t = document.createElement("table");
    t.className = "data";
    t.innerHTML = "<thead><tr>" + cols.map(c =>
      "<th" + (c.num ? ' class="num"' : "") + ">" + c.label + "</th>").join("") + "</tr></thead>";
    const tb = document.createElement("tbody");
    rows.forEach(r => {
      const tr = document.createElement("tr");
      tr.innerHTML = cols.map(c => "<td" + (c.num ? ' class="num"' : "") + ">" + r[c.key] + "</td>").join("");
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    container.appendChild(t);
  }

  window.Charts = { bar, groupedBar, line, scatter, heatmap, tiles, table, fmt, SERIES };
})();
