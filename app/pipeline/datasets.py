"""Dataset presets and custom loaders (Metro, Online Shopping)."""

from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

from app.pipeline.loader import load_uci_dataset

WEBAPP_ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = WEBAPP_ROOT / "data" / "datasets"

ONLINE_SHOPPING_ZIP_URL = (
    "https://archive.ics.uci.edu/static/public/553/"
    "clickstream+data+for+online+shopping.zip"
)
ONLINE_SHOPPING_CSV_NAME = "e-shop clothing 2008.csv"

DATASET_PRESETS: list[dict] = [
    {"id": "cancer", "name": "Breast Cancer Wisconsin", "uci_id": 17, "task_type": "classification"},
    {"id": "magic", "name": "MAGIC Gamma Telescope", "uci_id": 159, "task_type": "classification"},
    {"id": "adult", "name": "Adult Census", "uci_id": 2, "task_type": "classification"},
    {"id": "bank", "name": "Bank Marketing", "uci_id": 222, "task_type": "classification"},
    {"id": "wine", "name": "Wine Quality", "uci_id": 186, "task_type": "classification"},
    {"id": "mushroom", "name": "Secondary Mushroom", "uci_id": 848, "task_type": "classification"},
    {"id": "cdc_diabetes", "name": "CDC Diabetes", "uci_id": 891, "task_type": "classification"},
    {"id": "forest_cover", "name": "Forest Cover Type", "uci_id": 31, "task_type": "classification"},
    {
        "id": "metro",
        "name": "Metro Interstate Traffic Volume",
        "uci_id": 492,
        "task_type": "regression",
        "target_col": "traffic_volume",
    },
    {
        "id": "online_shopping",
        "name": "Online Shopping (Clickstream)",
        "uci_id": 553,
        "task_type": "regression",
        "target_col": "price",
        "source": "clickstream",
    },
]


def get_preset(preset_id: str | None = None, uci_id: int | None = None) -> dict | None:
    if preset_id:
        for p in DATASET_PRESETS:
            if p["id"] == preset_id:
                return p
    if uci_id is not None:
        for p in DATASET_PRESETS:
            if p.get("uci_id") == uci_id:
                return p
    return None


def _ensure_online_shopping_csv() -> Path:
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = DATASETS_DIR / ONLINE_SHOPPING_CSV_NAME
    if csv_path.exists():
        return csv_path

    req = urllib.request.Request(
        ONLINE_SHOPPING_ZIP_URL,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        archive = zipfile.ZipFile(io.BytesIO(resp.read()))

    for name in archive.namelist():
        if name.endswith(".csv") and "clothing" in name.lower():
            archive.extract(name, DATASETS_DIR)
            extracted = DATASETS_DIR / name
            if extracted != csv_path:
                extracted.replace(csv_path)
            return csv_path

    raise FileNotFoundError("Online Shopping CSV not found inside UCI archive")


def load_online_shopping_dataset() -> tuple[pd.DataFrame, dict]:
    """Load clickstream e-shop clothing 2008 (UCI 553) — regression on price."""
    csv_path = _ensure_online_shopping_csv()
    raw = pd.read_csv(csv_path, sep=";")
    raw = raw.drop(columns=["session ID"], errors="ignore")

    target_col = "price"
    if target_col not in raw.columns:
        raise ValueError(f"Target column {target_col!r} not found in Online Shopping dataset")

    y = pd.to_numeric(raw[target_col], errors="coerce")
    x = raw.drop(columns=[target_col], errors="ignore")
    data = pd.concat([x, y.to_frame(name=target_col)], axis=1)

    metadata = {
        "uci_id": 553,
        "preset_id": "online_shopping",
        "name": "Online Shopping (Clickstream)",
        "num_instances": len(data),
        "num_features": x.shape[1],
        "has_missing_values": "unknown",
        "target_cols": [target_col],
        "feature_cols": list(x.columns),
        "columns": list(data.columns),
        "task_type": "regression",
        "source": "clickstream",
    }
    return data, metadata


def load_metro_dataset() -> tuple[pd.DataFrame, dict]:
    """Load Metro Interstate Traffic Volume (UCI 492)."""
    data, metadata = load_uci_dataset(492)
    metadata["preset_id"] = "metro"
    metadata["task_type"] = "regression"
    metadata["target_cols"] = ["traffic_volume"]
    return data, metadata


def load_dataset(
    uci_id: int | None = None,
    preset_id: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    preset = get_preset(preset_id=preset_id, uci_id=uci_id)

    if preset_id == "online_shopping" or (preset and preset.get("source") == "clickstream"):
        return load_online_shopping_dataset()

    if preset_id == "metro" or uci_id == 492:
        return load_metro_dataset()

    if uci_id is None:
        if preset:
            uci_id = preset["uci_id"]
        else:
            raise ValueError("Provide a UCI ID or dataset preset")

    data, metadata = load_uci_dataset(uci_id)
    if preset:
        metadata["preset_id"] = preset["id"]
        metadata["task_type"] = preset["task_type"]
    else:
        metadata["preset_id"] = None
    return data, metadata
