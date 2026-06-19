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

function renderTable(rows, container, { compact = false } = {}) {
  if (!rows?.length) {
    container.innerHTML = "<p class='hint'>No data.</p>";
    return;
  }
  const cols = Object.keys(rows[0]);
  const html = `
    <table class="${compact ? "compact" : ""}">
      <thead><tr>${cols.map((c) => `<th>${c}</th>`).join("")}</tr></thead>
      <tbody>${rows
        .map(
          (r) =>
            `<tr>${cols.map((c) => `<td>${r[c] ?? "—"}</td>`).join("")}</tr>`
        )
        .join("")}</tbody>
    </table>`;
  container.innerHTML = html;
}
