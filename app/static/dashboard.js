const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

let allDatasets = [];
let overviewData = null;
let currentData = null;
let activeGenerator = null;

function useStaticData() {
  if (document.body?.dataset.static === "true") return true;
  return /github\.io$/i.test(window.location.hostname);
}

function staticBase() {
  const meta = document.querySelector('meta[name="github-pages-base"]');
  if (meta?.content) return meta.content;
  const parts = window.location.pathname.split("/").filter(Boolean);
  if (parts.length && parts[parts.length - 1].includes(".")) parts.pop();
  if (!parts.length) return "./";
  return `/${parts.join("/")}/`;
}

async function api(path) {
  if (useStaticData()) {
    const base = staticBase();
    if (path === "/api/results/datasets") {
      const res = await fetch(`${base}data/datasets.json`);
      if (!res.ok) throw new Error("Failed to load datasets.json");
      return res.json();
    }
    if (path === "/api/results/overview") {
      const res = await fetch(`${base}data/overview.json`);
      if (!res.ok) throw new Error("Failed to load overview.json");
      return res.json();
    }
    const match = path.match(/^\/api\/results\/datasets\/([^/]+)$/);
    if (match) {
      const res = await fetch(`${base}data/datasets/${match[1]}.json`);
      if (!res.ok) throw new Error(`Dataset not found: ${match[1]}`);
      return res.json();
    }
    throw new Error(`Unknown static API path: ${path}`);
  }

  const res = await fetch(path);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

function taskBadge(taskType) {
  return `<span class="task-badge ${taskType}">${taskType}</span>`;
}

function formatClassificationTrtr(row) {
  return {
    Model: row.Model,
    Accuracy: formatMeanSd(row["Accuracy Mean"], row["Accuracy Std"]),
    F1: formatMeanSd(row["F1 Mean"], row["F1 Std"]),
    Precision: formatMeanSd(row["Precision Mean"], row["Precision Std"]),
    Recall: formatMeanSd(row["Recall Mean"], row["Recall Std"]),
  };
}

function formatRegressionTrtr(row) {
  return {
    Model: row.Model,
    "R²": formatMeanSd(row["R2 Mean"], row["R2 Std"]),
    RMSE: formatMeanSd(row["RMSE Mean"], row["RMSE Std"]),
    MAE: formatMeanSd(row["MAE Mean"], row["MAE Std"]),
  };
}

function formatClassificationComparison(row) {
  return {
    Model: row.Model,
    Generator: row.Synthetic_Model,
    "Acc Drop": formatDrop(row.Accuracy_Drop),
    "TRTR Acc": formatMeanSd(row["Accuracy Mean_TRTR"], row["Accuracy Std_TRTR"]),
    "TSTR Acc": formatMeanSd(row["Accuracy Mean_TSTR"], row["Accuracy Std_TSTR"]),
    "F1 Drop": formatDrop(row.F1_Drop),
    "TRTR F1": formatMeanSd(row["F1 Mean_TRTR"], row["F1 Std_TRTR"]),
    "TSTR F1": formatMeanSd(row["F1 Mean_TSTR"], row["F1 Std_TSTR"]),
  };
}

function formatRegressionComparison(row) {
  return {
    Model: row.Model,
    Generator: row.Synthetic_Model,
    "R² Drop": formatDrop(row.R2_Drop),
    "TRTR R²": formatMeanSd(row["R2 Mean_TRTR"], row["R2 Std_TRTR"]),
    "TSTR R²": formatMeanSd(row["R2 Mean_TSTR"], row["R2 Std_TSTR"]),
    "RMSE Δ": formatDrop(row.RMSE_Increase),
    "TRTR RMSE": formatMeanSd(row["RMSE Mean_TRTR"], row["RMSE Std_TRTR"]),
    "TSTR RMSE": formatMeanSd(row["RMSE Mean_TSTR"], row["RMSE Std_TSTR"]),
  };
}

function formatGeneratorRow(row, taskType) {
  if (taskType === "regression") {
    return {
      Model: row.Model,
      "R² Drop": formatDrop(row.R2_Drop),
      "TRTR R²": formatMeanSd(row["R2 Mean_TRTR"], row["R2 Std_TRTR"]),
      "TSTR R²": formatMeanSd(row["R2 Mean_TSTR"], row["R2 Std_TSTR"]),
      "TRTR RMSE": formatMeanSd(row["RMSE Mean_TRTR"], row["RMSE Std_TRTR"]),
      "TSTR RMSE": formatMeanSd(row["RMSE Mean_TSTR"], row["RMSE Std_TSTR"]),
    };
  }
  return {
    Model: row.Model,
    "Acc Drop": formatDrop(row.Accuracy_Drop),
    "TRTR Acc": formatMeanSd(row["Accuracy Mean_TRTR"], row["Accuracy Std_TRTR"]),
    "TSTR Acc": formatMeanSd(row["Accuracy Mean_TSTR"], row["Accuracy Std_TSTR"]),
    "TRTR F1": formatMeanSd(row["F1 Mean_TRTR"], row["F1 Std_TRTR"]),
    "TSTR F1": formatMeanSd(row["F1 Mean_TSTR"], row["F1 Std_TSTR"]),
  };
}

function formatSummaryRow(row, taskType) {
  if (taskType === "regression") {
    return {
      Generator: row.Synthetic_Model,
      "R² Drop": formatDrop(row.R2_Drop),
      "MSE Increase": formatDrop(row.MSE_Increase),
      "RMSE Increase": formatDrop(row.RMSE_Increase),
      "MAE Increase": formatDrop(row.MAE_Increase),
    };
  }
  return {
    Generator: row.Synthetic_Model,
    "Accuracy Drop": formatDrop(row.Accuracy_Drop),
    "F1 Drop": formatDrop(row.F1_Drop),
    "Precision Drop": formatDrop(row.Precision_Drop),
    "Recall Drop": formatDrop(row.Recall_Drop),
  };
}

function renderDatasetList() {
  const filter = $("#dash-task-filter").value;
  const list = $("#dataset-list");
  const filtered =
    filter === "all"
      ? allDatasets
      : allDatasets.filter((d) => d.task_type === filter);

  if (!filtered.length) {
    list.innerHTML = "<p class='hint'>No datasets match this filter.</p>";
    return;
  }

  list.innerHTML = filtered
    .map(
      (d) => `
    <button type="button" class="dataset-btn ${d.id === currentData?.id ? "active" : ""} ${!d.available ? "disabled" : ""}"
      data-id="${d.id}" ${!d.available ? "disabled title='Excel file missing'" : ""}>
      <span class="ds-btn-name">${d.name}</span>
      ${taskBadge(d.task_type)}
      ${!d.available ? '<span class="missing-tag">missing</span>' : ""}
    </button>`
    )
    .join("");

  $$(".dataset-btn:not(.disabled)").forEach((btn) => {
    btn.addEventListener("click", () => loadDataset(btn.dataset.id));
  });
}

function populateGeneratorFilter(data) {
  const select = $("#gen-filter");
  const gens = [...new Set(data.all_comparisons.map((r) => r.Synthetic_Model))];
  select.innerHTML =
    '<option value="all">All generators</option>' +
    gens.map((g) => `<option value="${g}">${g}</option>`).join("");

  const paperSelect = $("#paper-gen-select");
  const genNames = Object.keys(data.generators);
  paperSelect.innerHTML = genNames.map((g) => `<option value="${g}">${g}</option>`).join("");
  if (genNames.length) {
    activeGenerator = paperSelect.value;
  }
}

function renderAllComparisons(data) {
  const filter = $("#gen-filter").value;
  let rows = data.all_comparisons;
  if (filter !== "all") {
    rows = rows.filter((r) => r.Synthetic_Model === filter);
  }
  const fmt =
    data.task_type === "regression"
      ? formatRegressionComparison
      : formatClassificationComparison;
  renderTable(rows.map(fmt), $("#all-table"));
}

function renderGeneratorTab(data, genName) {
  activeGenerator = genName;
  const rows = data.generators[genName] || [];
  renderTable(rows.map((r) => formatGeneratorRow(r, data.task_type)), $("#generator-table"));

  $$("#gen-pills .gen-pill").forEach((pill) => {
    pill.classList.toggle("active", pill.dataset.gen === genName);
  });
}

function syncExportContext() {
  DashboardCharts.setExportContext({
    overview: overviewData,
    datasetData: currentData,
    selectedGen: $("#paper-gen-select")?.value || activeGenerator,
  });
}

function refreshCharts(scope = "dataset") {
  const gen = $("#paper-gen-select")?.value || activeGenerator;
  if (scope === "overview" || scope === "all") {
    DashboardCharts.refreshOverviewCharts(overviewData);
  }
  if ((scope === "dataset" || scope === "all") && currentData) {
    DashboardCharts.refreshDatasetCharts(currentData, gen);
  }
  syncExportContext();
}

function renderDashboard(data) {
  currentData = data;
  $("#dashboard-placeholder").classList.add("hidden");
  $("#dashboard-content").classList.remove("hidden");

  $("#ds-title").textContent = data.name;
  $("#ds-meta").innerHTML = `UCI ${data.uci_id} · ${taskBadge(data.task_type)} · Folder: <code>${data.folder}</code>`;

  const hl = data.highlights || {};
  $("#ds-highlights").innerHTML = `
    <span class="highlight best">Best: <strong>${hl.best || "—"}</strong></span>
    <span class="highlight worst">Worst: <strong>${hl.worst || "—"}</strong></span>
  `;

  const fmtTrtr =
    data.task_type === "regression" ? formatRegressionTrtr : formatClassificationTrtr;
  const summaryRows = data.summary.map((r) => formatSummaryRow(r, data.task_type));

  renderTable(summaryRows, $("#overview-summary"));
  renderTable(data.trtr_results.slice(0, 3).map(fmtTrtr), $("#overview-trtr"), { compact: true });
  renderTable(data.trtr_results.map(fmtTrtr), $("#trtr-table"));
  renderTable(summaryRows, $("#summary-table"));

  populateGeneratorFilter(data);
  renderAllComparisons(data);

  const qualityTab = $("#tab-quality");
  if (data.quality_metrics?.length) {
    qualityTab.classList.remove("hidden");
    renderTable(data.quality_metrics, $("#quality-table"));
  } else {
    qualityTab.classList.add("hidden");
  }

  const genNames = Object.keys(data.generators);
  const pills = $("#gen-pills");
  pills.innerHTML = genNames
    .map((g) => `<button type="button" class="gen-pill" data-gen="${g}">${g}</button>`)
    .join("");
  $$("#gen-pills .gen-pill").forEach((pill) => {
    pill.addEventListener("click", () => renderGeneratorTab(data, pill.dataset.gen));
  });
  if (genNames.length) renderGeneratorTab(data, genNames[0]);

  renderDatasetList();
  updatePerDatasetFigureTitles(data);
  refreshCharts();
}

function updatePerDatasetFigureTitles(data, gen) {
  if (!data) return;
  const dsName = data.short_name || data.name;
  const metric = data.task_type === "regression" ? "R²" : "accuracy";
  const trtrTitle = $("#fig-trtr-tstr-title");
  const dropTitle = $("#fig-model-drop-title");
  if (trtrTitle) trtrTitle.textContent = `TRTR vs TSTR — ${dsName}`;
  if (dropTitle) {
    const g = gen || $("#paper-gen-select")?.value;
    dropTitle.textContent = g
      ? `Utility drop by model — ${g} (${dsName})`
      : `Utility drop by model — ${dsName}`;
  }
  const trtrCap = trtrTitle?.nextElementSibling;
  if (trtrCap?.classList.contains("figure-caption")) {
    trtrCap.textContent = `Mean ${metric} averaged over 10 downstream models (blue = train on real, red = train on synthetic)`;
  }
}

async function loadDataset(id) {
  try {
    $$(".dataset-btn").forEach((b) => b.classList.toggle("active", b.dataset.id === id));
    const data = await api(`/api/results/datasets/${id}`);
    renderDashboard(data);
  } catch (err) {
    alert(`Failed to load dataset: ${err.message}`);
  }
}

function initTabs() {
  $$("#result-tabs .tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const name = tab.dataset.tab;
      $$("#result-tabs .tab").forEach((t) => t.classList.toggle("active", t === tab));
      $$("#dashboard-content .tab-content").forEach((panel) => {
        panel.classList.toggle("active", panel.id === `tab-${name}`);
      });
    });
  });
}

function initExportButtons() {
  $$(".btn-export").forEach((btn) => {
    btn.title = "Download publication PNG (3× resolution, white background, title & caption)";
    btn.addEventListener("click", async () => {
      const id = btn.dataset.export;
      const name = currentData?.short_name || "benchmark";
      const file = btn.dataset.filename?.replace("fig_", `fig_${name}_`) || `${id}.png`;
      syncExportContext();
      await DashboardCharts.exportChart(id, file);
    });
  });
}

function initPaperTheme() {
  $("#btn-paper-theme").addEventListener("click", () => {
    document.body.classList.toggle("paper-theme");
    $("#btn-paper-theme").classList.toggle("active");
    refreshCharts("all");
  });
}

async function init() {
  initTabs();
  initExportButtons();
  initPaperTheme();

  $("#dash-task-filter").addEventListener("change", renderDatasetList);
  $("#gen-filter").addEventListener("change", () => {
    if (currentData) renderAllComparisons(currentData);
  });
  $("#paper-gen-select").addEventListener("change", () => {
    if (currentData) updatePerDatasetFigureTitles(currentData, $("#paper-gen-select").value);
    refreshCharts();
  });

  try {
    [allDatasets, overviewData] = await Promise.all([
      api("/api/results/datasets"),
      api("/api/results/overview"),
    ]);
    renderDatasetList();
    refreshCharts("overview");
    const first = allDatasets.find((d) => d.available);
    if (first) await loadDataset(first.id);
  } catch (err) {
    $("#dataset-list").innerHTML = `<p class="error">${err.message}</p>`;
  }
}

init();
