"""Load pre-computed TRTR/TSTR Excel results from the audit notebooks."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

SYNTH_ROOT = Path(__file__).resolve().parents[3]
AUDIT_RESULTS_ROOT = (
    SYNTH_ROOT
    / "Synthetic_Data_Audit"
    / "SYNTH"
    / "Single run_Data_leak_Synth_Quality"
)

GENERATOR_SHEETS = [
    "CTGAN",
    "CopulaGAN",
    "TVAE",
    "GaussianCopula",
    "WGAN_GP",
    "CTABGAN",
]

DATASET_SHORT_NAMES: dict[str, str] = {
    "cancer": "Cancer",
    "magic": "MAGIC",
    "adult": "Adult",
    "forest_cover": "Forest",
    "bank": "Bank",
    "wine": "Wine",
    "mushroom": "Mushroom",
    "cdc_diabetes": "CDC Diab.",
    "metro": "Metro",
    "online_shopping": "E-Shop",
}

AUDIT_DATASETS: list[dict[str, Any]] = [
    {
        "id": "cancer",
        "name": "Breast Cancer Wisconsin",
        "folder": "1. Cancer",
        "task_type": "classification",
        "excel": "TRTR_TSTR_results.xlsx",
        "uci_id": 17,
    },
    {
        "id": "magic",
        "name": "MAGIC Gamma Telescope",
        "folder": "2. MAGIC Gamma Telescope",
        "task_type": "classification",
        "excel": "TRTR_TSTR_results.xlsx",
        "uci_id": 159,
    },
    {
        "id": "adult",
        "name": "Adult Census",
        "folder": "3. Adult",
        "task_type": "classification",
        "excel": "TRTR_TSTR_results.xlsx",
        "uci_id": 2,
    },
    {
        "id": "forest_cover",
        "name": "Forest Cover Type",
        "folder": "4. Forest cover dataset",
        "task_type": "classification",
        "excel": "TRTR_TSTR_results.xlsx",
        "uci_id": 31,
    },
    {
        "id": "bank",
        "name": "Bank Marketing",
        "folder": "5. Bank Markting",
        "task_type": "classification",
        "excel": "TRTR_TSTR_results.xlsx",
        "uci_id": 222,
    },
    {
        "id": "wine",
        "name": "Wine Quality",
        "folder": "6. Wine dataset",
        "task_type": "classification",
        "excel": "TRTR_TSTR_results.xlsx",
        "uci_id": 186,
    },
    {
        "id": "mushroom",
        "name": "Secondary Mushroom",
        "folder": "7. Mushroom dataset",
        "task_type": "classification",
        "excel": "TRTR_TSTR_results.xlsx",
        "uci_id": 848,
    },
    {
        "id": "cdc_diabetes",
        "name": "CDC Diabetes",
        "folder": "8. CDC diabetes dataset",
        "task_type": "classification",
        "excel": "TRTR_TSTR_results.xlsx",
        "uci_id": 891,
    },
    {
        "id": "metro",
        "name": "Metro Interstate Traffic",
        "folder": "9. Metro interstate",
        "task_type": "regression",
        "excel": "TRTR_TSTR_results_regression.xlsx",
        "uci_id": 492,
    },
    {
        "id": "online_shopping",
        "name": "Online Shopping (Clickstream)",
        "folder": "10. online shopping",
        "task_type": "regression",
        "excel": "TRTR_TSTR_results_regression.xlsx",
        "uci_id": 553,
    },
]


def _dataset_meta(meta: dict[str, Any]) -> dict[str, Any]:
    path = AUDIT_RESULTS_ROOT / meta["folder"] / meta["excel"]
    return {
        "id": meta["id"],
        "name": meta["name"],
        "folder": meta["folder"],
        "task_type": meta["task_type"],
        "uci_id": meta["uci_id"],
        "available": path.is_file(),
        "excel_path": str(path) if path.is_file() else None,
    }


def list_audit_datasets(task_type: str | None = None) -> list[dict[str, Any]]:
    datasets = [_dataset_meta(m) for m in AUDIT_DATASETS]
    if task_type in ("classification", "regression"):
        datasets = [d for d in datasets if d["task_type"] == task_type]
    return datasets


def _drop_formatted_columns(df: pd.DataFrame) -> pd.DataFrame:
    keep = [
        c
        for c in df.columns
        if "±" not in str(c) and not re.search(r"\(Mean", str(c), re.I)
    ]
    return df[keep]


def _json_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    cleaned = _drop_formatted_columns(df)
    cleaned = cleaned.where(pd.notnull(cleaned), None)
    records = cleaned.to_dict(orient="records")
    out: list[dict[str, Any]] = []
    for row in records:
        out.append(
            {
                k: (float(v) if isinstance(v, (int, float)) and v is not None else v)
                for k, v in row.items()
            }
        )
    return out


def _best_worst(summary: list[dict[str, Any]], task_type: str) -> dict[str, str | None]:
    if not summary:
        return {"best": None, "worst": None}
    if task_type == "regression":
        key = "R2_Drop"
    else:
        key = "Accuracy_Drop"
    ranked = sorted(summary, key=lambda r: r.get(key) or 0)
    return {
        "best": ranked[0].get("Synthetic_Model"),
        "worst": ranked[-1].get("Synthetic_Model"),
    }


@lru_cache(maxsize=32)
def load_dataset_results(dataset_id: str) -> dict[str, Any]:
    meta = next((m for m in AUDIT_DATASETS if m["id"] == dataset_id), None)
    if meta is None:
        raise KeyError(f"Unknown dataset id: {dataset_id}")

    path = AUDIT_RESULTS_ROOT / meta["folder"] / meta["excel"]
    if not path.is_file():
        raise FileNotFoundError(f"Results file not found: {path}")

    xl = pd.ExcelFile(path)
    sheet_names = set(xl.sheet_names)

    trtr = _json_records(pd.read_excel(path, sheet_name="TRTR_Results"))
    summary = _json_records(pd.read_excel(path, sheet_name="Summary"))
    all_comparisons = _json_records(pd.read_excel(path, sheet_name="All_Comparisons"))

    quality_metrics = None
    if "Quality_Metrics" in sheet_names:
        quality_metrics = _json_records(pd.read_excel(path, sheet_name="Quality_Metrics"))

    generators: dict[str, list[dict[str, Any]]] = {}
    for gen in GENERATOR_SHEETS:
        if gen in sheet_names:
            generators[gen] = _json_records(pd.read_excel(path, sheet_name=gen))

    highlights = _best_worst(summary, meta["task_type"])

    return {
        **_dataset_meta(meta),
        "short_name": DATASET_SHORT_NAMES.get(meta["id"], meta["name"]),
        "sheets": list(sheet_names),
        "highlights": highlights,
        "trtr_results": trtr,
        "summary": summary,
        "all_comparisons": all_comparisons,
        "quality_metrics": quality_metrics,
        "generators": generators,
    }


@lru_cache(maxsize=1)
def load_benchmark_overview() -> dict[str, Any]:
    """Cross-dataset aggregates for publication heatmaps and win-rate charts."""
    classification: list[dict[str, Any]] = []
    regression: list[dict[str, Any]] = []
    win_counts: dict[str, int] = {g: 0 for g in GENERATOR_SHEETS}

    for meta in AUDIT_DATASETS:
        try:
            data = load_dataset_results(meta["id"])
        except FileNotFoundError:
            continue

        task = meta["task_type"]
        metric_key = "R2_Drop" if task == "regression" else "Accuracy_Drop"
        generators: dict[str, float | None] = {}
        for row in data["summary"]:
            gen = row.get("Synthetic_Model")
            if gen:
                generators[gen] = row.get(metric_key)

        best = data["highlights"].get("best")
        if best:
            win_counts[best] = win_counts.get(best, 0) + 1

        entry = {
            "id": meta["id"],
            "name": meta["name"],
            "short_name": DATASET_SHORT_NAMES.get(meta["id"], meta["name"]),
            "task_type": task,
            "metric_key": metric_key,
            "best": best,
            "generators": generators,
        }
        if task == "regression":
            regression.append(entry)
        else:
            classification.append(entry)

    return {
        "generators": GENERATOR_SHEETS,
        "classification": classification,
        "regression": regression,
        "win_counts": win_counts,
        "n_datasets": len(classification) + len(regression),
    }
