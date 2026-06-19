/** Publication-quality chart helpers for the results dashboard. */

if (typeof Chart !== "undefined" && typeof ChartMatrix !== "undefined") {
  Chart.register(ChartMatrix.MatrixController, ChartMatrix.MatrixElement);
}
if (typeof Chart !== "undefined" && typeof ChartDataLabels !== "undefined") {
  Chart.register(ChartDataLabels);
}

const CM_FONT = '"Computer Modern Serif", "Computer Modern", serif';

function cmCanvasFont(size, weight = "normal") {
  const w =
    weight === "bold" || weight === 700 || weight === "700" || weight === 600 || weight === "600"
      ? "bold"
      : "normal";
  return `${w} ${size}px ${CM_FONT}`;
}

function chartFont(size = 13, weight = "normal") {
  const w =
    weight === "bold" || weight === 700 || weight === "700" || weight === 600 || weight === "600"
      ? "bold"
      : "normal";
  return { family: CM_FONT, size, weight: w };
}

if (typeof Chart !== "undefined") {
  Chart.defaults.font.family = CM_FONT;
}

const GENERATOR_ORDER = [
  "CTGAN",
  "CopulaGAN",
  "TVAE",
  "GaussianCopula",
  "WGAN_GP",
  "CTABGAN",
];

const GEN_COLORS = {
  CTGAN: "#2563eb",
  CopulaGAN: "#7c3aed",
  TVAE: "#0891b2",
  GaussianCopula: "#16a34a",
  WGAN_GP: "#d97706",
  CTABGAN: "#dc2626",
};

const GEN_SHORT = {
  CTGAN: "CTGAN",
  CopulaGAN: "Copula",
  TVAE: "TVAE",
  GaussianCopula: "GaussCop",
  WGAN_GP: "WGAN",
  CTABGAN: "CTAB",
};

const GEN_LABEL = {
  CTGAN: "CTGAN",
  CopulaGAN: "CopulaGAN",
  TVAE: "TVAE",
  GaussianCopula: "GaussianCopula",
  WGAN_GP: "WGAN-GP",
  CTABGAN: "CTABGAN",
};

const chartRegistry = {};

const heatmapValuePlugin = {
  id: "heatmapValues",
  afterDatasetsDraw(chart) {
    if (chart.config.type !== "matrix") return;
    const { ctx } = chart;
    const dataset = chart.data.datasets[0];
    const meta = chart.getDatasetMeta(0);
    const { min = 0, max = 1, higherIsBetter = false } = chart.options.plugins?.heatmapScale || {};

    meta.data.forEach((elem, i) => {
      const raw = dataset.data[i];
      if (raw?.v == null || Number.isNaN(raw.v)) return;

      const w = elem.width || 0;
      const h = elem.height || 0;
      if (w < 14 || h < 12) return;

      const center =
        typeof elem.getCenterPoint === "function"
          ? elem.getCenterPoint()
          : { x: elem.x + w / 2, y: elem.y + h / 2 };

      const v = Number(raw.v);
      const text = v >= 10 ? v.toFixed(0) : v >= 1 ? v.toFixed(1) : v.toFixed(2);
      let t = max > min ? (v - min) / (max - min) : 0;
      if (higherIsBetter) t = 1 - t;
      const fill = t > 0.52 ? "#ffffff" : "#0f172a";
      const stroke = t > 0.52 ? "rgba(15,23,42,0.5)" : "rgba(255,255,255,0.7)";
      const fontSize = Math.max(10, Math.min(14, Math.floor(Math.min(w, h) * 0.36)));

      ctx.save();
      ctx.font = cmCanvasFont(fontSize, "bold");
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.lineWidth = 3;
      ctx.strokeStyle = stroke;
      ctx.fillStyle = fill;
      ctx.strokeText(text, center.x, center.y);
      ctx.fillText(text, center.x, center.y);
      ctx.restore();
    });
  },
};

if (typeof Chart !== "undefined") {
  Chart.register(heatmapValuePlugin);
}

const errorBarPlugin = {
  id: "errorBars",
  afterDatasetsDraw(chart) {
    const cfg = chart.config.options?.plugins?.errorBars;
    if (!cfg?.values || chart.config.type !== "bar") return;
    const meta = chart.getDatasetMeta(0);
    const { ctx } = chart;
    const yScale = chart.scales.y;
    ctx.save();
    ctx.strokeStyle = cfg.color || "#334155";
    ctx.lineWidth = 1.6;
    meta.data.forEach((bar, i) => {
      const err = cfg.values[i];
      const mean = chart.data.datasets[0].data[i];
      if (err == null || mean == null) return;
      const yTop = yScale.getPixelForValue(mean + err);
      const yBot = yScale.getPixelForValue(mean - err);
      const x = bar.x;
      const cap = 7;
      ctx.beginPath();
      ctx.moveTo(x, yTop);
      ctx.lineTo(x, yBot);
      ctx.moveTo(x - cap, yTop);
      ctx.lineTo(x + cap, yTop);
      ctx.moveTo(x - cap, yBot);
      ctx.lineTo(x + cap, yBot);
      ctx.stroke();
    });
    ctx.restore();
  },
};

if (typeof Chart !== "undefined") {
  Chart.register(errorBarPlugin);
}

const paperBgPlugin = {
  id: "paperBg",
  beforeDraw(chart) {
    if (!isPaperTheme()) return;
    const { ctx } = chart;
    const w = chart.width;
    const h = chart.height;
    ctx.save();
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, w, h);
    ctx.restore();
  },
};

if (typeof Chart !== "undefined") {
  Chart.register(paperBgPlugin);
}

function heatmapLegendId(canvasId) {
  return canvasId.replace("heatmap-", "heatmap-legend-");
}

function updateHeatmapLegend(canvasId, min, max, label, higherIsBetter = false) {
  const el = document.getElementById(heatmapLegendId(canvasId));
  if (!el) return;
  const lo = heatColor(min, min, max, higherIsBetter);
  const hi = heatColor(max, min, max, higherIsBetter);
  el.innerHTML = `
    <div class="scale-bar" style="background: linear-gradient(to right, ${lo}, ${hi})"></div>
    <div class="scale-labels">
      <span>${higherIsBetter ? "Low" : "Low"} · ${min.toFixed(2)}</span>
      <span class="scale-mid">${label}</span>
      <span>High · ${max.toFixed(2)}</span>
    </div>
    <p class="scale-hint">${higherIsBetter ? "Green = higher TSTR (better)" : "Green = lower utility loss (better synthetic data)"}</p>
  `;
}

function isPaperTheme() {
  return document.body.classList.contains("paper-theme");
}

function themeColors() {
  if (isPaperTheme()) {
    return { text: "#1e293b", muted: "#64748b", grid: "#e2e8f0", bg: "#ffffff" };
  }
  return { text: "#e8edf4", muted: "#8b9cb3", grid: "#2d3a4f", bg: "transparent" };
}

function baseOptions() {
  const c = themeColors();
  return {
    responsive: true,
    maintainAspectRatio: false,
    layout: { padding: { bottom: 8, top: 4 } },
    plugins: {
      title: { display: false },
      themeColors: c,
      legend: {
        display: true,
        position: "bottom",
        labels: {
          color: c.text,
          boxWidth: 16,
          padding: 14,
          font: chartFont(13),
        },
      },
      tooltip: {
        titleFont: chartFont(14, "bold"),
        bodyFont: chartFont(13),
      },
      datalabels: { display: false },
    },
    scales: {},
  };
}

function barValueLabels(c, { decimals = 2, suffix = "" } = {}) {
  return {
    display: true,
    anchor: "end",
    align: "top",
    offset: 2,
    color: c.text,
    font: chartFont(13, "bold"),
    formatter: (v) => {
      if (v == null || Number.isNaN(v)) return "";
      const n = Number(v);
      return (Number.isInteger(n) ? String(n) : n.toFixed(decimals)) + suffix;
    },
  };
}

function generatorLegendLabels(chart) {
  const ds = chart.data.datasets[0];
  if (!ds) return [];
  return chart.data.labels.map((label, i) => ({
    text: label,
    fillStyle: Array.isArray(ds.backgroundColor)
      ? ds.backgroundColor[i]
      : ds.backgroundColor,
    strokeStyle: "transparent",
    lineWidth: 0,
    hidden: false,
    index: i,
  }));
}

function destroyChart(id) {
  const canvas = document.getElementById(id);
  if (!canvas) {
    delete chartRegistry[id];
    return;
  }
  const existing = Chart.getChart(canvas);
  if (existing) existing.destroy();
  delete chartRegistry[id];
}

function registerChart(id, chart) {
  chartRegistry[id] = chart;
  return chart;
}

const EXPORT_DPR = 2;
const EXPORT_PAD = 40;
const EXPORT_CD_WIDTH = 900;
const EXPORT_CD_HEIGHT = 480;
const OVERVIEW_CHART_IDS = new Set([
  "chart-cd",
  "chart-tstr-sd",
  "chart-trtr-gap",
  "heatmap-tstr",
  "heatmap-clf",
  "heatmap-reg",
  "chart-win-rate",
]);
const DATASET_CHART_IDS = new Set([
  "summary-chart",
  "chart-trtr-tstr",
  "chart-model-drop",
  "chart-radar",
]);

let exportContext = null;

function setExportContext(ctx) {
  exportContext = ctx;
}

function waitFrames(n = 2) {
  return new Promise((resolve) => {
    const step = () => {
      n -= 1;
      if (n <= 0) resolve();
      else requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
}

function downloadDataUrl(dataUrl, filename) {
  const a = document.createElement("a");
  a.href = dataUrl;
  a.download = filename;
  a.click();
}

function getFigureMeta(canvasId) {
  const canvas = document.getElementById(canvasId);
  const card = canvas?.closest(".figure-card");
  return {
    title: card?.querySelector(".figure-title")?.textContent?.trim() || "",
    caption: card?.querySelector(".figure-caption")?.textContent?.trim() || "",
  };
}

function chartHasPluginTitle(chart) {
  return !!chart?.options?.plugins?.title?.display;
}

function getExportHeader(canvasId, chart) {
  const meta = getFigureMeta(canvasId);
  const hasChartTitle = chartHasPluginTitle(chart);
  return {
    // Match on-screen layout: title/caption live in HTML or inside the chart — not both.
    title: hasChartTitle ? "" : meta.title,
    caption: hasChartTitle ? "" : meta.caption,
  };
}

async function ensureFontsReady() {
  if (!document.fonts?.load) return;
  try {
    await Promise.all([
      document.fonts.load('normal 12px "Computer Modern Serif"'),
      document.fonts.load('bold 12px "Computer Modern Serif"'),
      document.fonts.load('bold 22px "Computer Modern Serif"'),
    ]);
    await document.fonts.ready;
  } catch {
    /* use fallback serif if CDN font unavailable */
  }
}

function loadImage(dataUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Failed to load chart image"));
    img.src = dataUrl;
  });
}

function imageToCanvas(img) {
  const w = img.naturalWidth || img.width;
  const h = img.naturalHeight || img.height;
  const off = document.createElement("canvas");
  off.width = w;
  off.height = h;
  const ctx = off.getContext("2d");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, w, h);
  ctx.drawImage(img, 0, 0, w, h);
  return { canvas: off, pixelW: w, pixelH: h };
}

function getChartInstance(canvasId) {
  const entry = chartRegistry[canvasId];
  if (entry?.canvas) return entry;
  const canvas = document.getElementById(canvasId);
  return canvas ? Chart.getChart(canvas) : null;
}

function wrapText(ctx, text, maxWidth) {
  if (!text) return [];
  const words = text.split(/\s+/);
  const lines = [];
  let line = "";
  words.forEach((word) => {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line);
      line = word;
    } else {
      line = test;
    }
  });
  if (line) lines.push(line);
  return lines;
}

function drawTextLines(ctx, lines, x, y, lineHeight, color, font) {
  ctx.fillStyle = color;
  ctx.font = font;
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  lines.forEach((line, i) => {
    ctx.fillText(line, x, y + i * lineHeight);
  });
  return lines.length * lineHeight;
}

function drawHeatmapLegendBar(ctx, x, y, barW, barH, scaleMeta) {
  if (!scaleMeta) return 0;
  const { min, max, label, higherIsBetter } = scaleMeta;
  const steps = 120;
  for (let i = 0; i < steps; i++) {
    const t = i / (steps - 1);
    const v = min + t * (max - min);
    ctx.fillStyle = heatColor(v, min, max, higherIsBetter);
    const sliceW = barW / steps;
    ctx.fillRect(x + i * sliceW, y, sliceW + 0.5, barH);
  }
  ctx.strokeStyle = "#cbd5e1";
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, barW, barH);
  ctx.fillStyle = "#475569";
  ctx.font = cmCanvasFont(13, "normal");
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  ctx.fillText(min.toFixed(2), x, y + barH + 8);
  ctx.textAlign = "center";
  ctx.fillText(label || "Scale", x + barW / 2, y + barH + 8);
  ctx.textAlign = "right";
  ctx.fillText(max.toFixed(2), x + barW, y + barH + 8);
  const hint = higherIsBetter
    ? "Green = higher TSTR (better)"
    : "Green = lower utility loss (better synthetic data)";
  ctx.textAlign = "center";
  ctx.fillStyle = "#64748b";
  ctx.font = cmCanvasFont(12, "normal");
  ctx.fillText(hint, x + barW / 2, y + barH + 28);
  return barH + 48;
}

function paintCdDiagram(ctx, width, height, cd, c) {
  const bg = c.bg === "transparent" ? "#ffffff" : c.bg;
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, width, height);

  const gens = GENERATOR_ORDER.filter((g) => cd.avg_ranks[g] != null).sort(
    (a, b) => cd.avg_ranks[a] - cd.avg_ranks[b]
  );
  const k = gens.length;
  const fontScale = Math.max(1, width / 640);
  const labelFont = cmCanvasFont(Math.round(12 * fontScale), "bold");
  ctx.font = labelFont;
  const labelPad = 12 * fontScale;
  const maxLabelW = Math.max(
    ...gens.map((g) => ctx.measureText(GEN_LABEL[g] || g).width),
    48 * fontScale
  );
  const margin = {
    top: 36 * fontScale,
    right: 28 * fontScale,
    bottom: 28 * fontScale,
    left: maxLabelW + labelPad,
  };
  const plotW = width - margin.left - margin.right;
  const rowH = (height - margin.top - margin.bottom) / Math.max(k, 1);
  const minRank = 1;
  const maxRank = k;

  const rankX = (rank) =>
    margin.left + ((rank - minRank) / Math.max(maxRank - minRank, 1)) * plotW;

  ctx.fillStyle = c.muted;
  ctx.font = cmCanvasFont(Math.round(12 * fontScale), "bold");
  ctx.textAlign = "center";
  ctx.fillText("Best", margin.left, 18 * fontScale);
  ctx.fillText("Worst", width - margin.right, 18 * fontScale);
  if (cd.chi2 != null) {
    ctx.font = cmCanvasFont(Math.round(11 * fontScale), "normal");
    ctx.fillText(
      `Friedman χ²=${Number(cd.chi2).toFixed(2)}, p=${Number(cd.p).toExponential(1)}`,
      width / 2,
      18 * fontScale
    );
  }

  ctx.strokeStyle = c.grid;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(margin.left, margin.top);
  ctx.lineTo(width - margin.right, margin.top);
  ctx.stroke();

  for (let t = minRank; t <= maxRank; t++) {
    const x = rankX(t);
    ctx.strokeStyle = c.grid;
    ctx.beginPath();
    ctx.moveTo(x, margin.top);
    ctx.lineTo(x, height - margin.bottom);
    ctx.stroke();
    ctx.fillStyle = c.muted;
    ctx.font = cmCanvasFont(Math.round(10 * fontScale), "normal");
    ctx.textAlign = "center";
    ctx.fillText(String(t), x, height - 8 * fontScale);
  }

  const barY = margin.top - 14 * fontScale;
  const pairs = cd.not_significant_pairs || [];
  pairs.forEach(([g1, g2]) => {
    const r1 = cd.avg_ranks[g1];
    const r2 = cd.avg_ranks[g2];
    if (r1 == null || r2 == null) return;
    const x1 = rankX(r1);
    const x2 = rankX(r2);
    ctx.strokeStyle = "#64748b";
    ctx.lineWidth = 2 * fontScale;
    ctx.beginPath();
    ctx.moveTo(x1, barY);
    ctx.lineTo(x2, barY);
    ctx.stroke();
  });

  gens.forEach((gen, i) => {
    const rank = cd.avg_ranks[gen];
    const y = margin.top + rowH * i + rowH / 2;
    const x = rankX(rank);
    const half = Math.min(28 * fontScale, plotW / (k * 2.2));

    ctx.strokeStyle = GEN_COLORS[gen] || "#3b82f6";
    ctx.lineWidth = 5 * fontScale;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(x - half, y);
    ctx.lineTo(x + half, y);
    ctx.stroke();

    ctx.fillStyle = c.text;
    ctx.font = labelFont;
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    ctx.fillText(GEN_LABEL[gen] || gen, margin.left - labelPad / 2, y);
    ctx.textAlign = "left";
    ctx.fillText(`(${rank.toFixed(2)})`, x + half + 6 * fontScale, y);
  });
}

function captureCdCanvas(cd, width, height) {
  const off = document.createElement("canvas");
  off.width = Math.round(width * EXPORT_DPR);
  off.height = Math.round(height * EXPORT_DPR);
  const ctx = off.getContext("2d");
  ctx.scale(EXPORT_DPR, EXPORT_DPR);
  paintCdDiagram(ctx, width, height, cd, {
    text: "#1e293b",
    muted: "#64748b",
    grid: "#e2e8f0",
    bg: "#ffffff",
  });
  return { dataUrl: off.toDataURL("image/png"), chart: null };
}

function getHeatmapScaleMeta(canvasId) {
  const entry = chartRegistry[canvasId];
  const chart = entry?.canvas ? entry : Chart.getChart(document.getElementById(canvasId));
  return chart?.options?.plugins?.heatmapScale || null;
}

async function captureChartCanvas(canvasId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return null;

  const entry = chartRegistry[canvasId];
  if (entry?.cdData) {
    await ensureFontsReady();
    return captureCdCanvas(entry.cdData, EXPORT_CD_WIDTH, EXPORT_CD_HEIGHT);
  }

  const chart = getChartInstance(canvasId);
  if (!chart) return null;

  const oldDpr = chart.options.devicePixelRatio;
  const oldAnim = chart.options.animation;

  chart.options.animation = false;
  chart.options.devicePixelRatio = EXPORT_DPR;
  chart.resize();
  chart.update("none");
  await ensureFontsReady();
  await waitFrames(4);

  const rawUrl = chart.toBase64Image("image/png", 1);
  const img = await loadImage(rawUrl);
  const { canvas: off } = imageToCanvas(img);
  const dataUrl = off.toDataURL("image/png");

  chart.options.devicePixelRatio = oldDpr ?? window.devicePixelRatio ?? 1;
  chart.options.animation = oldAnim;
  chart.resize();
  chart.update("none");

  return { dataUrl, chart };
}

async function buildPublicationPng(canvasId) {
  const captured = await captureChartCanvas(canvasId);
  if (!captured) return null;

  const { dataUrl, chart } = captured;
  const { title, caption } = getExportHeader(canvasId, chart);
  const heatmapScale = canvasId.startsWith("heatmap-") ? getHeatmapScaleMeta(canvasId) : null;

  if (!title && !caption && !heatmapScale) {
    return dataUrl;
  }

  await ensureFontsReady();

  const img = await loadImage(dataUrl);
  const { canvas: chartCanvas, pixelW, pixelH } = imageToCanvas(img);
  const scale = pixelW / 900;
  const pad = Math.round(EXPORT_PAD * Math.max(scale, 1));
  const titleFont = cmCanvasFont(Math.round(18 * Math.max(scale, 1)), "bold");
  const captionFont = cmCanvasFont(Math.round(13 * Math.max(scale, 1)), "normal");
  const measure = document.createElement("canvas").getContext("2d");

  measure.font = titleFont;
  const titleLines = wrapText(measure, title, pixelW);
  measure.font = captionFont;
  const captionLines = wrapText(measure, caption, pixelW);

  const titleBlock = titleLines.length ? titleLines.length * Math.round(26 * scale) + 8 : 0;
  const captionBlock = captionLines.length ? captionLines.length * Math.round(20 * scale) + 12 : 0;
  const legendBlock = heatmapScale ? Math.round(72 * scale) : 0;
  const totalW = pixelW + pad * 2;
  const totalH = pad + titleBlock + captionBlock + pixelH + legendBlock + pad;

  const out = document.createElement("canvas");
  out.width = totalW;
  out.height = totalH;
  const ctx = out.getContext("2d");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, totalW, totalH);

  let y = pad;
  if (titleLines.length) {
    drawTextLines(ctx, titleLines, pad, y, Math.round(26 * scale), "#0f172a", titleFont);
    y += titleBlock;
  }
  if (captionLines.length) {
    drawTextLines(ctx, captionLines, pad, y, Math.round(20 * scale), "#64748b", captionFont);
    y += captionBlock;
  }

  ctx.drawImage(chartCanvas, pad, y, pixelW, pixelH);
  y += pixelH + Math.round(12 * scale);

  if (heatmapScale) {
    drawHeatmapLegendBar(ctx, pad, y, pixelW, Math.round(16 * scale), heatmapScale);
  }

  return out.toDataURL("image/png");
}

function setPaperTheme(on) {
  document.body.classList.toggle("paper-theme", on);
  const btn = document.querySelector("#btn-paper-theme");
  if (btn) btn.classList.toggle("active", on);
}

async function exportChart(canvasId, filename) {
  const btn = document.querySelector(`[data-export="${canvasId}"]`);
  const prevLabel = btn?.textContent;

  if (btn) {
    btn.disabled = true;
    btn.textContent = "…";
  }

  try {
    setPaperTheme(true);
    if (exportContext?.overview && OVERVIEW_CHART_IDS.has(canvasId)) {
      refreshOverviewCharts(exportContext.overview);
    } else if (exportContext?.datasetData && DATASET_CHART_IDS.has(canvasId)) {
      refreshDatasetCharts(exportContext.datasetData, exportContext.selectedGen);
    }
    await ensureFontsReady();
    await waitFrames(6);
    await new Promise((r) => setTimeout(r, 250));

    const dataUrl = await buildPublicationPng(canvasId);
    if (dataUrl) {
      downloadDataUrl(dataUrl, filename);
    } else {
      throw new Error("Chart not ready — select a dataset and wait for figures to load.");
    }
  } catch (err) {
    console.error(err);
    alert(err.message || "PNG export failed. Please try again.");
  } finally {
    setPaperTheme(true);
    if (exportContext) {
      if (OVERVIEW_CHART_IDS.has(canvasId)) {
        refreshOverviewCharts(exportContext.overview);
      } else if (exportContext.datasetData) {
        refreshDatasetCharts(exportContext.datasetData, exportContext.selectedGen);
      }
    }
    if (btn) {
      btn.disabled = false;
      btn.textContent = prevLabel || "Download PNG";
    }
  }
}

function heatColor(value, min, max, invert = false) {
  if (value == null || Number.isNaN(value)) return "rgba(148,163,184,0.3)";
  let t = max > min ? (value - min) / (max - min) : 0;
  if (invert) t = 1 - t;
  const r = Math.round(34 + t * (220 - 34));
  const g = Math.round(197 - t * (197 - 38));
  const b = Math.round(94 - t * (94 - 38));
  return `rgba(${r},${g},${b},0.92)`;
}

function renderHeatmap(canvasId, rows, generators, metricLabel, opts = {}) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !rows.length) return;

  destroyChart(canvasId);

  const higherIsBetter = opts.higherIsBetter ?? /tstr/i.test(metricLabel);
  const values = [];
  rows.forEach((row) => {
    generators.forEach((gen) => {
      const v = row.generators?.[gen];
      if (v != null) values.push(v);
    });
  });
  const min = higherIsBetter ? Math.min(...values) : Math.min(...values, 0);
  const max = higherIsBetter ? Math.max(...values) : Math.max(...values, 0.01);

  const xLabels = generators.map((g) => GEN_SHORT[g] || g);
  const yLabels = rows.map((r) => r.short_name);

  const data = [];
  rows.forEach((row) => {
    generators.forEach((gen) => {
      data.push({
        x: GEN_SHORT[gen] || gen,
        y: row.short_name,
        v: row.generators?.[gen] ?? null,
      });
    });
  });

  const c = themeColors();
  const colCount = generators.length;
  const rowCount = rows.length;

  const chart = registerChart(
    canvasId,
    new Chart(canvas, {
      type: "matrix",
      data: {
        datasets: [
          {
            label: metricLabel,
            data,
            backgroundColor: (ctx) => {
              const v = ctx.dataset.data[ctx.dataIndex]?.v;
              return heatColor(v, min, max, higherIsBetter);
            },
            borderColor: isPaperTheme() ? "#cbd5e1" : "#1a2332",
            borderWidth: 2,
            width: ({ chart: ch }) => {
              const w = (ch.chartArea?.width || 300) / colCount;
              return Math.max(22, w - 3);
            },
            height: ({ chart: ch }) => {
              const h = (ch.chartArea?.height || 200) / rowCount;
              return Math.max(22, h - 3);
            },
          },
        ],
      },
      options: {
        ...baseOptions(),
        layout: { padding: { bottom: 12, top: 12, left: 8, right: 12 } },
        plugins: {
          ...baseOptions().plugins,
          heatmapScale: { min, max, label: metricLabel, higherIsBetter },
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => {
                const p = items[0].raw;
                return `${p.y} · ${p.x}`;
              },
              label: (item) =>
                `${metricLabel}: ${item.raw.v != null ? Number(item.raw.v).toFixed(4) : "—"}`,
            },
          },
        },
        scales: {
          x: {
            type: "category",
            labels: xLabels,
            offset: true,
            title: {
              display: true,
              text: "Generator",
              color: c.text,
              font: chartFont(14, "bold"),
              padding: { top: 8 },
            },
            ticks: {
              color: c.text,
              maxRotation: 45,
              minRotation: 0,
              font: chartFont(13, "bold"),
              padding: 8,
            },
            grid: { display: false },
          },
          y: {
            type: "category",
            labels: yLabels,
            offset: true,
            title: {
              display: true,
              text: "Dataset",
              color: c.text,
              font: chartFont(14, "bold"),
            },
            ticks: {
              color: c.text,
              font: chartFont(13, "bold"),
              padding: 8,
              autoSkip: false,
            },
            grid: { display: false },
          },
        },
      },
    })
  );
  updateHeatmapLegend(canvasId, min, max, metricLabel, higherIsBetter);
  return chart;
}

function renderWinRateChart(canvasId, winCounts) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  destroyChart(canvasId);

  const labels = GENERATOR_ORDER.filter((g) => winCounts[g] != null);
  const values = labels.map((g) => winCounts[g] || 0);
  const displayLabels = labels.map((g) => GEN_SHORT[g] || g);
  const c = themeColors();

  registerChart(
    canvasId,
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: displayLabels,
        datasets: [
          {
            label: "Datasets won (lowest utility loss)",
            data: values,
            backgroundColor: labels.map((g) => GEN_COLORS[g] || "#64748b"),
            borderWidth: 0,
            borderRadius: 4,
          },
        ],
      },
      options: {
        ...baseOptions(),
        plugins: {
          ...baseOptions().plugins,
          legend: {
            display: true,
            position: "bottom",
            labels: {
              color: c.text,
              boxWidth: 14,
              padding: 10,
              font: chartFont(12),
              generateLabels: (chart) =>
                labels.map((g, i) => ({
                  text: g,
                  fillStyle: GEN_COLORS[g],
                  strokeStyle: "transparent",
                  lineWidth: 0,
                  hidden: false,
                  index: i,
                })),
            },
            onClick: () => {},
          },
          datalabels: {
            ...barValueLabels(c, { decimals: 0 }),
            align: "end",
            anchor: "end",
            offset: 4,
          },
          tooltip: {
            callbacks: {
              title: (items) => labels[items[0].dataIndex],
              label: (item) => `Wins: ${item.raw} dataset(s)`,
            },
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            suggestedMax: Math.max(...values, 1) + 0.5,
            ticks: { stepSize: 1, color: c.muted, font: chartFont(12) },
            grid: { color: c.grid },
            title: {
              display: true,
              text: "Win count (# datasets)",
              color: c.muted,
              font: chartFont(13, "bold"),
            },
          },
          x: {
            title: {
              display: true,
              text: "Generator",
              color: c.muted,
              font: chartFont(13, "bold"),
            },
            ticks: { color: c.text, font: chartFont(12) },
            grid: { display: false },
          },
        },
      },
    })
  );
}

function renderTstrMeanSdChart(canvasId, tstrByGenerator) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !tstrByGenerator) return;

  destroyChart(canvasId);

  const labels = GENERATOR_ORDER.filter((g) => tstrByGenerator[g]);
  const means = labels.map((g) => tstrByGenerator[g].mean);
  const stds = labels.map((g) => tstrByGenerator[g].std ?? 0);
  const displayLabels = labels.map((g) => GEN_SHORT[g] || g);
  const c = themeColors();
  const floor = Math.min(...means.map((m, i) => m - stds[i]));

  registerChart(
    canvasId,
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: displayLabels,
        datasets: [
          {
            label: "Mean TSTR score",
            data: means,
            backgroundColor: labels.map((g) => GEN_COLORS[g] || "#64748b"),
            borderRadius: 4,
            borderWidth: 0,
          },
        ],
      },
      options: {
        ...baseOptions(),
        plugins: {
          ...baseOptions().plugins,
          legend: { display: false },
          errorBars: { values: stds, color: c.text },
          datalabels: {
            ...barValueLabels(c, { decimals: 3 }),
            anchor: "end",
            align: "top",
            offset: 4,
          },
        },
        scales: {
          y: {
            beginAtZero: false,
            suggestedMin: floor * 0.98,
            ticks: { color: c.muted, font: chartFont(12) },
            grid: { color: c.grid },
            title: {
              display: true,
              text: "Mean TSTR score",
              color: c.muted,
              font: chartFont(13, "bold"),
            },
          },
          x: {
            title: {
              display: true,
              text: "Generator",
              color: c.muted,
              font: chartFont(13, "bold"),
            },
            ticks: { color: c.text, font: chartFont(12) },
            grid: { display: false },
          },
        },
      },
    })
  );
}

function renderTrtrTstrGrouped(canvasId, data, title) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  destroyChart(canvasId);

  const isReg = data.task_type === "regression";
  const trtrKey = isReg ? "R2 Mean_TRTR" : "Accuracy Mean_TRTR";
  const tstrKey = isReg ? "R2 Mean_TSTR" : "Accuracy Mean_TSTR";
  const yLabel = isReg ? "Mean R²" : "Mean accuracy";

  const byGen = {};
  data.all_comparisons.forEach((row) => {
    const g = row.Synthetic_Model;
    if (!byGen[g]) byGen[g] = { trtr: [], tstr: [] };
    if (row[trtrKey] != null) byGen[g].trtr.push(row[trtrKey]);
    if (row[tstrKey] != null) byGen[g].tstr.push(row[tstrKey]);
  });

  const labels = GENERATOR_ORDER.filter((g) => byGen[g]);
  const xLabels = labels.map((g) => GEN_SHORT[g] || g);
  const trtrMeans = labels.map((g) => avg(byGen[g].trtr));
  const tstrMeans = labels.map((g) => avg(byGen[g].tstr));
  const c = themeColors();

  registerChart(
    canvasId,
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: xLabels,
        datasets: [
          {
            label: "TRTR (train on real)",
            data: trtrMeans,
            backgroundColor: "rgba(37, 99, 235, 0.88)",
            borderRadius: 4,
          },
          {
            label: "TSTR (train on synthetic)",
            data: tstrMeans,
            backgroundColor: "rgba(220, 38, 38, 0.82)",
            borderRadius: 4,
          },
        ],
      },
      options: {
        ...baseOptions(),
        plugins: {
          ...baseOptions().plugins,
          title: {
            display: !!title,
            text: title,
            color: c.text,
            font: chartFont(13, "bold"),
            padding: { bottom: 10 },
          },
          datalabels: {
            ...barValueLabels(c, { decimals: isReg ? 3 : 2 }),
            display: (ctx) => ctx.dataset.data[ctx.dataIndex] != null,
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            min: isReg ? undefined : 0,
            max: isReg ? undefined : 1,
            suggestedMin: isReg
              ? Math.min(...tstrMeans, ...trtrMeans) - 0.05
              : undefined,
            grace: isReg ? "5%" : 0,
            ticks: { color: c.muted, font: chartFont(12) },
            grid: { color: c.grid },
            title: {
              display: true,
              text: `${yLabel} (avg. over 10 models)`,
              color: c.muted,
              font: chartFont(13, "bold"),
            },
          },
          x: {
            title: {
              display: true,
              text: "Generator",
              color: c.muted,
              font: chartFont(13, "bold"),
            },
            ticks: { color: c.text, font: chartFont(12) },
            grid: { display: false },
          },
        },
      },
    })
  );
}

function renderModelDropChart(canvasId, rows, taskType, genName, title) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !rows.length) return;

  destroyChart(canvasId);

  const dropKey = taskType === "regression" ? "R2_Drop" : "Accuracy_Drop";
  const dropLabel = taskType === "regression" ? "R² drop" : "Accuracy drop";
  const sorted = [...rows].sort((a, b) => (a[dropKey] || 0) - (b[dropKey] || 0));
  const labels = sorted.map((r) => r.Model);
  const values = sorted.map((r) => r[dropKey] ?? 0);
  const c = themeColors();

  registerChart(
    canvasId,
    new Chart(canvas, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: dropLabel,
            data: values,
            backgroundColor: values.map((v) =>
              v <= 0.05
                ? "rgba(22, 163, 74, 0.85)"
                : v <= 0.2
                  ? "rgba(217, 119, 6, 0.85)"
                  : "rgba(220, 38, 38, 0.85)"
            ),
            borderRadius: 3,
          },
        ],
      },
      options: {
        indexAxis: "y",
        ...baseOptions(),
        plugins: {
          ...baseOptions().plugins,
          title: {
            display: !!title,
            text: title,
            color: c.text,
            font: chartFont(13, "bold"),
            padding: { bottom: 8 },
          },
          legend: { display: false },
          datalabels: {
            display: true,
            anchor: "end",
            align: "right",
            color: c.text,
            font: chartFont(12, "bold"),
            formatter: (v) => (v >= 1 ? v.toFixed(2) : v.toFixed(3)),
          },
        },
        scales: {
          x: {
            beginAtZero: true,
            ticks: { color: c.muted, font: chartFont(12) },
            grid: { color: c.grid },
            title: {
              display: true,
              text: `${dropLabel} (TRTR − TSTR)`,
              color: c.muted,
              font: chartFont(13, "bold"),
            },
          },
          y: {
            ticks: { color: c.text, font: chartFont(12) },
            grid: { display: false },
          },
        },
      },
    })
  );
}

function renderRadarChart(canvasId, summary, taskType, title) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !summary.length) return;

  destroyChart(canvasId);

  const c = themeColors();
  let labels;
  let keys;
  if (taskType === "regression") {
    labels = ["R² drop", "MSE ↑", "RMSE ↑", "MAE ↑"];
    keys = ["R2_Drop", "MSE_Increase", "RMSE_Increase", "MAE_Increase"];
  } else {
    labels = ["Acc. drop", "F1 drop", "Prec. drop", "Rec. drop"];
    keys = ["Accuracy_Drop", "F1_Drop", "Precision_Drop", "Recall_Drop"];
  }

  const datasets = summary.map((row) => {
    const gen = row.Synthetic_Model;
    const vals = keys.map((k) => Math.max(0, row[k] ?? 0));
    return {
      label: gen,
      data: vals,
      borderColor: GEN_COLORS[gen] || "#64748b",
      backgroundColor: (GEN_COLORS[gen] || "#64748b") + "33",
      borderWidth: 2,
      pointRadius: 3,
    };
  });

  registerChart(
    canvasId,
    new Chart(canvas, {
      type: "radar",
      data: { labels, datasets },
      options: {
        ...baseOptions(),
        plugins: {
          ...baseOptions().plugins,
          title: {
            display: !!title,
            text: title,
            color: c.text,
            font: chartFont(13, "bold"),
            padding: { bottom: 8 },
          },
          legend: {
            display: true,
            position: "bottom",
            labels: { color: c.text, boxWidth: 14, padding: 10, font: chartFont(12) },
          },
        },
        scales: {
          r: {
            beginAtZero: true,
            ticks: { color: c.muted, backdropColor: "transparent", font: chartFont(11) },
            grid: { color: c.grid },
            pointLabels: { color: c.text, font: chartFont(13) },
          },
        },
      },
    })
  );
}

function renderSummaryBar(canvasId, data, title) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  destroyChart(canvasId);

  const isReg = data.task_type === "regression";
  const labels = data.summary.map((r) => r.Synthetic_Model);
  const xLabels = labels.map((g) => GEN_SHORT[g] || g);
  const values = data.summary.map((r) => (isReg ? r.R2_Drop : r.Accuracy_Drop));
  const metricLabel = isReg ? "Avg. R² drop" : "Avg. accuracy drop";
  const c = themeColors();

  registerChart(
    canvasId,
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: xLabels,
        datasets: [
          {
            label: metricLabel,
            data: values,
            backgroundColor: labels.map((g, i) =>
              i === 0
                ? "rgba(22, 163, 74, 0.9)"
                : (GEN_COLORS[g] || "#3b82f6") + "cc"
            ),
            borderWidth: 0,
            borderRadius: 4,
          },
        ],
      },
      options: {
        ...baseOptions(),
        plugins: {
          ...baseOptions().plugins,
          title: {
            display: !!title,
            text: title,
            color: c.text,
            font: chartFont(13, "bold"),
            padding: { bottom: 10 },
          },
          legend: {
            display: true,
            position: "bottom",
            labels: {
              color: c.text,
              generateLabels: (chart) =>
                labels.map((g, i) => ({
                  text: `${g} (${Number(values[i]).toFixed(3)})`,
                  fillStyle: chart.data.datasets[0].backgroundColor[i],
                  strokeStyle: "transparent",
                  lineWidth: 0,
                  hidden: false,
                  index: i,
                })),
            },
            onClick: () => {},
          },
          datalabels: barValueLabels(c, { decimals: 3 }),
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { color: c.muted, font: chartFont(12) },
            grid: { color: c.grid },
            title: {
              display: true,
              text: metricLabel,
              color: c.muted,
              font: chartFont(13, "bold"),
            },
          },
          x: {
            title: {
              display: true,
              text: "Generator (ranked best → worst)",
              color: c.muted,
              font: chartFont(13, "bold"),
            },
            ticks: { color: c.text, font: chartFont(12) },
            grid: { display: false },
          },
        },
      },
    })
  );
}

function tstrHeatmapRows(rows) {
  return (rows || []).map((r) => ({
    ...r,
    generators: r.tstr_generators || r.generators,
  }));
}

function renderCdDiagram(canvasId, cd) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !cd?.avg_ranks) return;

  destroyChart(canvasId);

  const c = themeColors();
  const parent = canvas.parentElement;
  const width = Math.max(320, parent?.clientWidth || 640);
  const height = Math.max(220, parent?.clientHeight || 280);
  const dpr = window.devicePixelRatio || 1;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;

  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  paintCdDiagram(ctx, width, height, cd, c);

  chartRegistry[canvasId] = { cdData: cd };
}

function renderGapChart(canvasId, gapByGenerator) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !gapByGenerator) return;

  destroyChart(canvasId);

  const labels = GENERATOR_ORDER.filter((g) => gapByGenerator[g]);
  const means = labels.map((g) => gapByGenerator[g].mean);
  const stds = labels.map((g) => gapByGenerator[g].std ?? 0);
  const displayLabels = labels.map((g) => GEN_SHORT[g] || g);
  const c = themeColors();

  registerChart(
    canvasId,
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: displayLabels,
        datasets: [
          {
            label: "TRTR − TSTR gap",
            data: means,
            backgroundColor: labels.map((g) => GEN_COLORS[g] || "#64748b"),
            borderRadius: 4,
            borderWidth: 0,
          },
        ],
      },
      options: {
        ...baseOptions(),
        plugins: {
          ...baseOptions().plugins,
          legend: { display: false },
          errorBars: { values: stds, color: c.text },
          datalabels: {
            ...barValueLabels(c, { decimals: 3 }),
            anchor: "end",
            align: "top",
            offset: 4,
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { color: c.muted, font: chartFont(12) },
            grid: { color: c.grid },
            title: {
              display: true,
              text: "TRTR − TSTR (smaller = better synthetic data)",
              color: c.muted,
              font: chartFont(13, "bold"),
            },
          },
          x: {
            title: {
              display: true,
              text: "Generator",
              color: c.muted,
              font: chartFont(13, "bold"),
            },
            ticks: { color: c.text, font: chartFont(12) },
            grid: { display: false },
          },
        },
      },
    })
  );
}

function avg(arr) {
  if (!arr.length) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function refreshOverviewCharts(overview) {
  if (!overview) return;
  renderCdDiagram("chart-cd", overview.friedman_cd);
  renderTstrMeanSdChart("chart-tstr-sd", overview.tstr_by_generator);
  renderGapChart("chart-trtr-gap", overview.gap_by_generator);
  renderHeatmap(
    "heatmap-tstr",
    tstrHeatmapRows(overview.tstr_all || [...overview.classification, ...overview.regression]),
    overview.generators,
    "Mean TSTR"
  );
  renderHeatmap(
    "heatmap-clf",
    overview.classification,
    overview.generators,
    "Accuracy drop"
  );
  renderHeatmap(
    "heatmap-reg",
    overview.regression,
    overview.generators,
    "R² drop"
  );
  renderWinRateChart("chart-win-rate", overview.win_counts);
}

function refreshDatasetCharts(datasetData, selectedGen) {
  if (!datasetData) return;

  const dsName = datasetData.short_name || datasetData.name;
  renderSummaryBar(
    "summary-chart",
    datasetData,
    `Generator ranking — ${dsName}`
  );
  renderTrtrTstrGrouped(
    "chart-trtr-tstr",
    datasetData,
    `TRTR vs TSTR — ${dsName}`
  );
  renderRadarChart(
    "chart-radar",
    datasetData.summary,
    datasetData.task_type,
    `Multi-metric utility drop — ${dsName}`
  );
  const gen = selectedGen || Object.keys(datasetData.generators)[0];
  if (gen && datasetData.generators[gen]) {
    renderModelDropChart(
      "chart-model-drop",
      datasetData.generators[gen],
      datasetData.task_type,
      gen,
      `Utility drop by model — ${gen} (${dsName})`
    );
  }
}

function refreshAllCharts(overview, datasetData, selectedGen) {
  refreshOverviewCharts(overview);
  refreshDatasetCharts(datasetData, selectedGen);
}

window.DashboardCharts = {
  GENERATOR_ORDER,
  GEN_COLORS,
  destroyChart,
  exportChart,
  setExportContext,
  setPaperTheme,
  refreshOverviewCharts,
  refreshDatasetCharts,
  refreshAllCharts,
  renderModelDropChart,
};
