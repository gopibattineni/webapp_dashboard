let sessionId = null;
let pollTimer = null;
let allPresets = [];
let selectedPresetId = null;

const $ = (sel) => document.querySelector(sel);

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

function formatMeanSd(mean, std, decimals = 4) {
  if (mean == null || Number.isNaN(Number(mean))) return "—";
  const m = Number(mean).toFixed(decimals);
  let s;
  if (std == null || Number.isNaN(Number(std))) {
    s = (0).toFixed(decimals);
  } else {
    const sd = Number(std);
    const rounded = sd.toFixed(decimals);
    s = sd !== 0 && Number(rounded) === 0 ? sd.toFixed(6) : rounded;
  }
  return `${m} ± ${s}`;
}

function formatDrop(value, decimals = 4) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  return Number(value).toFixed(decimals);
}

function renderTable(rows, container) {
  if (!rows?.length) return;
  const cols = Object.keys(rows[0]);
  const html = `
    <table>
      <thead><tr>${cols.map((c) => `<th>${c}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((r) => `<tr>${cols.map((c) => `<td>${r[c] ?? ""}</td>`).join("")}</tr>`).join("")}</tbody>
    </table>`;
  container.innerHTML = html;
  container.classList.remove("hidden");
}

function statGrid(stats) {
  return `<div class="stat-grid">${Object.entries(stats)
    .map(([k, v]) => `<div class="stat"><div class="label">${k}</div><div class="value">${v}</div></div>`)
    .join("")}</div>`;
}

// Presets
function renderPresetButtons(presets) {
  const container = $("#preset-buttons");
  container.innerHTML = "";
  if (!presets.length) {
    const empty = document.createElement("p");
    empty.className = "preset-empty hint";
    const filter = $("#task-type-filter").value;
    empty.textContent =
      filter === "all"
        ? "No dataset presets available."
        : `No ${filter} datasets in the preset list.`;
    container.appendChild(empty);
    return;
  }
  presets.forEach((p) => {
    const btn = document.createElement("button");
    btn.className = `preset-btn ${p.task_type}${selectedPresetId === p.id ? " active" : ""}`;
    btn.textContent = `${p.name} (${p.task_type})`;
    btn.title = `UCI ${p.uci_id} · ${p.task_type}`;
    btn.onclick = () => {
      selectedPresetId = p.id;
      $("#uci-id").value = p.uci_id;
      renderPresetButtons(
        getFilteredPresets($("#task-type-filter").value)
      );
    };
    container.appendChild(btn);
  });
}

function getFilteredPresets(taskType) {
  if (taskType === "all") return allPresets;
  return allPresets.filter((p) => p.task_type === taskType);
}

async function loadPresets() {
  allPresets = await api("/api/datasets/presets");
  renderPresetButtons(getFilteredPresets($("#task-type-filter").value));
  $("#task-type-filter").onchange = () => {
    renderPresetButtons(getFilteredPresets($("#task-type-filter").value));
  };
  $("#uci-id").oninput = () => {
    selectedPresetId = null;
    renderPresetButtons(getFilteredPresets($("#task-type-filter").value));
  };
}

// Step 1: Load
$("#btn-load").onclick = async () => {
  const uciId = parseInt($("#uci-id").value, 10);
  if (!uciId && !selectedPresetId) return alert("Enter a valid UCI ID or choose a preset");

  $("#btn-load").disabled = true;
  $("#btn-load").textContent = "Loading...";

  try {
    const body = selectedPresetId ? { preset_id: selectedPresetId } : { uci_id: uciId };
    const data = await api("/api/load", {
      method: "POST",
      body: JSON.stringify(body),
    });
    sessionId = data.session_id;
    selectedPresetId = data.metadata?.preset_id || selectedPresetId;

    const info = $("#load-info");
    info.classList.remove("hidden");
    const taskType = data.task_type || data.metadata?.task_type || "classification";
    info.innerHTML = `
      <strong>${data.metadata.name}</strong> (UCI ${data.metadata.uci_id})
      <span class="task-badge ${taskType}">${taskType}</span><br/>
      Shape: ${data.shape[0]} rows × ${data.shape[1]} columns
      ${statGrid({
        "Suggested target": data.suggested_target,
        "Problem type": taskType,
        Instances: data.metadata.num_instances ?? data.shape[0],
        Features: data.metadata.num_features ?? data.shape[1] - 1,
      })}
    `;

    $("#target-col").value = data.suggested_target;
    $("#target-col").placeholder = data.suggested_target;
    renderTable(data.preview, $("#preview-table"));
    $("#btn-preprocess").disabled = false;
  } catch (e) {
    alert("Load failed: " + e.message);
  } finally {
    $("#btn-load").disabled = false;
    $("#btn-load").textContent = "Load Dataset";
  }
};

// Step 2: Preprocess
$("#btn-preprocess").onclick = async () => {
  if (!sessionId) return;

  $("#btn-preprocess").disabled = true;
  $("#btn-preprocess").textContent = "Preprocessing...";

  try {
    const targetCol = $("#target-col").value.trim() || null;
    const data = await api("/api/preprocess", {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        target_col: targetCol,
        n_subsample: parseInt($("#n-subsample").value, 10),
        test_size: parseFloat($("#test-size").value),
        seed: parseInt($("#seed").value, 10),
      }),
    });

    const panel = $("#preprocess-info");
    panel.classList.remove("hidden");
    panel.innerHTML = `
      <strong>Preprocessing complete</strong>
      <span class="task-badge ${data.task_type}">${data.task_type}</span>
      ${statGrid({
        Target: data.target_col,
        "Problem type": data.task_type,
        Total: data.n_total,
        "Train (generators)": `${data.n_train} (${data.train_fraction * 100}%)`,
        "Holdout (utility)": `${data.n_test} (${data.test_fraction * 100}%)`,
        "Downstream models": data.downstream_models,
        Seeds: data.evaluation_seeds,
      })}
      <p style="margin-top:0.75rem;color:var(--muted)">Missing values imputed. Generators will train on ${data.n_train} rows only.</p>
    `;

    $("#btn-run").disabled = false;
  } catch (e) {
    alert("Preprocess failed: " + e.message);
  } finally {
    $("#btn-preprocess").disabled = false;
    $("#btn-preprocess").textContent = "Preprocess";
  }
};

// Step 3: Run experiment
$("#btn-run").onclick = async () => {
  if (!sessionId) return;

  const runFidelity = $("#run-fidelity").checked;
  const runPrivacy = $("#run-privacy").checked;
  const runUtility = $("#run-utility").checked;

  if (!runFidelity && !runPrivacy && !runUtility) {
    return alert("Select at least one experimental setup");
  }

  $("#btn-run").disabled = true;
  $("#progress-panel").classList.remove("hidden");
  $("#step-results").classList.add("hidden");
  $("#progress-log").innerHTML = "";
  $("#progress-fill").style.width = "5%";

  try {
    await api("/api/experiment", {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        n_synthetic: parseInt($("#n-synthetic").value, 10),
        seed: parseInt($("#seed").value, 10),
        run_fidelity: runFidelity,
        run_privacy: runPrivacy,
        run_utility: runUtility,
        fast_mode: $("#fast-mode").checked,
      }),
    });

    pollStatus();
  } catch (e) {
    alert("Failed to start: " + e.message);
    $("#btn-run").disabled = false;
  }
};

function pollStatus() {
  if (pollTimer) clearInterval(pollTimer);

  pollTimer = setInterval(async () => {
    try {
      const status = await api(`/api/experiment/${sessionId}/status`);
      const log = $("#progress-log");
      log.innerHTML = status.progress.map((m) => `<li>${m}</li>`).join("");
      log.scrollTop = log.scrollHeight;

      const pct = Math.min(95, 10 + status.progress.length * 8);
      $("#progress-fill").style.width = pct + "%";

      if (status.status === "completed") {
        clearInterval(pollTimer);
        $("#progress-fill").style.width = "100%";
        await loadResults();
        $("#btn-run").disabled = false;
      } else if (status.status === "failed") {
        clearInterval(pollTimer);
        log.innerHTML += `<li class="error">${status.error}</li>`;
        $("#btn-run").disabled = false;
      }
    } catch (e) {
      console.error(e);
    }
  }, 2000);
}

async function loadResults() {
  const results = await api(`/api/experiment/${sessionId}/results`);
  $("#step-results").classList.remove("hidden");

  renderGeneratorStatus(results);
  renderFidelity(results.fidelity);
  renderPrivacy(results.privacy);
  renderUtility(results.utility);
}

function renderGeneratorStatus(results) {
  const el = $("#step-results");
  let banner = document.getElementById("generator-status-banner");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "generator-status-banner";
    banner.className = "info-panel";
    el.insertBefore(banner, el.querySelector(".tabs"));
  }

  const expected = results.generators_expected || [];
  const ran = results.generators_run || [];
  const errors = results.generator_errors || {};

  const rows = expected.map((g) => ({
    Generator: g,
    Status: ran.includes(g) ? "OK" : "Failed",
    Error: errors[g] || (ran.includes(g) ? "" : "Not completed"),
  }));

  banner.innerHTML = `<strong>Generators:</strong> ${ran.length} / ${expected.length} completed`;
  const wrap = document.createElement("div");
  wrap.className = "table-wrap";
  renderTable(rows, wrap);
  banner.appendChild(wrap);

  if (ran.length < expected.length) {
    banner.innerHTML += `<p class="hint warn-hint" style="margin-top:0.75rem">Only ${ran.length} generator(s) finished. Uncheck Fast mode and allow 30–60+ min for all 6 on CPU.</p>`;
  }
}

function renderFidelity(fidelity) {
  const el = $("#tab-fidelity");
  if (!fidelity) {
    el.innerHTML = "<p class='hint'>Fidelity not run.</p>";
    return;
  }

  const metricKeys = [
    ["overall_score", "SDV Overall", true],
    ["column_shapes_score", "Column Shapes", true],
    ["column_pair_trends_score", "Pair Trends", true],
    ["ks_complement_mean", "KS Complement (mean)", true],
    ["js_divergence_mean", "JS Divergence (mean)", false],
    ["wasserstein_mean", "Wasserstein (mean)", false],
    ["gower_cross_mean", "Gower Cross", true],
    ["mmd_rbf", "MMD (RBF)", false],
    ["c2st_accuracy", "C2ST Accuracy", false],
  ];

  const rows = Object.entries(fidelity).map(([gen, m]) => {
    if (m.error) return { Generator: gen, Error: m.error };
    const row = { Generator: gen };
    metricKeys.forEach(([key, label, higherBetter]) => {
      const v = m[key];
      if (v == null || Number.isNaN(v)) return;
      row[label] = higherBetter ? `${(v * 100).toFixed(1)}%` : v.toFixed(4);
    });
    return row;
  });

  el.innerHTML = "<p class='hint'>Higher SDV / KS / Gower = better fidelity. Lower JS / Wasserstein / MMD / C2ST = better overlap.</p>";
  const wrap = document.createElement("div");
  wrap.className = "table-wrap";
  renderTable(rows, wrap);
  el.appendChild(wrap);

  const detail = document.createElement("div");
  detail.className = "score-card";
  detail.style.marginTop = "1rem";
  Object.entries(fidelity).forEach(([gen, m]) => {
    if (m.error) return;
    const card = document.createElement("div");
    card.className = "generator-score";
    card.innerHTML = `<h3>${gen}</h3>
      <div class="detail">KS min: ${m.ks_complement_min ?? "—"} · Gower real: ${m.gower_intra_real_mean ?? "—"} · Gower synth: ${m.gower_intra_synth_mean ?? "—"}</div>`;
    detail.appendChild(card);
  });
  el.appendChild(detail);
}

function renderPrivacy(privacy) {
  const el = $("#tab-privacy");
  if (!privacy) {
    el.innerHTML = "<p class='hint'>Privacy not run.</p>";
    return;
  }

  const rows = Object.entries(privacy).map(([gen, m]) => {
    if (m.error) return { Generator: gen, Error: m.error };
    const nn = m.nearest_neighbor || {};
    const dcr = m.dcr || {};
    const mah = m.mahalanobis || {};
    const hunC = m.hungarian_cosine || {};
    const hunM = m.hungarian_mahalanobis || {};
    const mia = m.mia || {};
    return {
      Generator: gen,
      "NN mean (↑)": nn.mean_nn_distance,
      "DCR min": dcr.min_nn_distance,
      "Mahalanobis mean": mah.mean_mahalanobis,
      "Hungarian cos": hunC.mean_matched_distance,
      "Hungarian mah": hunM.mean_matched_distance,
      "MIA AUC": mia.attack_auc,
      "MIA synth member %": mia.synthetic_member_rate != null ? (mia.synthetic_member_rate * 100).toFixed(1) + "%" : "—",
      "MIA advantage": mia.attack_advantage,
    };
  });

  el.innerHTML = "<p class='hint'>Higher NN/DCR distances = safer. MIA AUC near 0.5 and low synthetic member rate = better privacy.</p>";
  const wrap = document.createElement("div");
  wrap.className = "table-wrap";
  renderTable(rows, wrap);
  el.appendChild(wrap);
}

function renderUtility(utility) {
  const el = $("#tab-utility");
  if (!utility) {
    el.innerHTML = "<p class='hint'>Utility not run.</p>";
    return;
  }

  const task = utility.task_type || "classification";
  const nSeeds = utility.n_seeds || 10;
  const header = `<p class='hint'>Task: <strong>${task}</strong> · ${utility.n_models || 10} downstream models · ${nSeeds} seeds · Metrics: <strong>Mean ± SD</strong> · Generators: ${(utility.generators_evaluated || []).join(", ")}</p>`;

  el.innerHTML = header;

  if (utility.trtr?.length) {
    const trtrTitle = document.createElement("h3");
    trtrTitle.style.margin = "0.75rem 0 0.5rem";
    trtrTitle.textContent = `TRTR baseline (train real → test holdout, ${nSeeds} seeds)`;
    el.appendChild(trtrTitle);
    const trtrWrap = document.createElement("div");
    trtrWrap.className = "table-wrap";
    const trtrRows = utility.trtr.map((r) => {
      if (r.Error) return { Model: r.Model, Error: r.Error };
      if (task === "regression") {
        return {
          Model: r.Model,
          "R²": formatMeanSd(r["R2 Mean"], r["R2 Std"]),
          RMSE: formatMeanSd(r["RMSE Mean"], r["RMSE Std"]),
          MAE: formatMeanSd(r["MAE Mean"], r["MAE Std"]),
        };
      }
      return {
        Model: r.Model,
        Accuracy: formatMeanSd(r["Accuracy Mean"], r["Accuracy Std"]),
        F1: formatMeanSd(r["F1 Mean"], r["F1 Std"]),
        Precision: formatMeanSd(r["Precision Mean"], r["Precision Std"]),
        Recall: formatMeanSd(r["Recall Mean"], r["Recall Std"]),
      };
    });
    renderTable(trtrRows, trtrWrap);
    el.appendChild(trtrWrap);
  }

  const summaryTitle = document.createElement("h3");
  summaryTitle.style.margin = "1rem 0 0.5rem";
  summaryTitle.textContent =
    task === "regression"
      ? "Average R² drop by generator (mean of model-level drops)"
      : "Average accuracy drop by generator (mean of model-level drops)";
  el.appendChild(summaryTitle);

  const wrap = document.createElement("div");
  wrap.className = "table-wrap";
  renderTable(utility.summary, wrap);
  el.appendChild(wrap);

  if (utility.per_generator) {
    Object.entries(utility.per_generator).forEach(([gen, rows]) => {
      const h = document.createElement("h3");
      h.style.margin = "1.25rem 0 0.5rem";
      h.textContent = `${gen} — TRTR vs TSTR (${nSeeds} seeds, Mean ± SD)`;
      el.appendChild(h);
      const tw = document.createElement("div");
      tw.className = "table-wrap";
      const slim = rows.map((r) => {
        if (r.Error) return { Model: r.Model, Error: r.Error };
        if (task === "regression") {
          return {
            Model: r.Model,
            "R² Drop": formatDrop(r.R2_Drop),
            "TRTR R²": formatMeanSd(r["R2 Mean_TRTR"], r["R2 Std_TRTR"]),
            "TSTR R²": formatMeanSd(r["R2 Mean_TSTR"], r["R2 Std_TSTR"]),
            "TRTR RMSE": formatMeanSd(r["RMSE Mean_TRTR"], r["RMSE Std_TRTR"]),
            "TSTR RMSE": formatMeanSd(r["RMSE Mean_TSTR"], r["RMSE Std_TSTR"]),
            "TRTR MAE": formatMeanSd(r["MAE Mean_TRTR"], r["MAE Std_TRTR"]),
            "TSTR MAE": formatMeanSd(r["MAE Mean_TSTR"], r["MAE Std_TSTR"]),
          };
        }
        return {
          Model: r.Model,
          "Acc Drop": formatDrop(r.Accuracy_Drop),
          "F1 Drop": formatDrop(r.F1_Drop),
          "TRTR Acc": formatMeanSd(r["Accuracy Mean_TRTR"], r["Accuracy Std_TRTR"]),
          "TSTR Acc": formatMeanSd(r["Accuracy Mean_TSTR"], r["Accuracy Std_TSTR"]),
          "TRTR F1": formatMeanSd(r["F1 Mean_TRTR"], r["F1 Std_TRTR"]),
          "TSTR F1": formatMeanSd(r["F1 Mean_TSTR"], r["F1 Std_TSTR"]),
          "TRTR Prec": formatMeanSd(r["Precision Mean_TRTR"], r["Precision Std_TRTR"]),
          "TSTR Prec": formatMeanSd(r["Precision Mean_TSTR"], r["Precision Std_TSTR"]),
          "TRTR Rec": formatMeanSd(r["Recall Mean_TRTR"], r["Recall Std_TRTR"]),
          "TSTR Rec": formatMeanSd(r["Recall Mean_TSTR"], r["Recall Std_TSTR"]),
        };
      });
      renderTable(slim, tw);
      el.appendChild(tw);
    });
  }
}

// Tabs
document.querySelectorAll(".tab").forEach((tab) => {
  tab.onclick = () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
    tab.classList.add("active");
    $(`#tab-${tab.dataset.tab}`).classList.add("active");
  };
});

loadPresets();
