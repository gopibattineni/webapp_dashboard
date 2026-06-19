"""CTAB-GAN+ helpers for regression datasets (Metro, Online Shopping)."""

from __future__ import annotations

import numpy as np
import pandas as pd

ONLINE_SHOPPING_CAT_COLS = [
    "country",
    "page 1 (main category)",
    "page 2 (clothing model)",
    "colour",
    "location",
    "model photography",
]
ONLINE_SHOPPING_NUM_COLS = ["year", "month", "day", "order", "price 2", "page"]

METRO_CTAB_CATEGORICAL = ["holiday", "weather_main"]
METRO_CTAB_NUMERIC = ["temp", "rain_1h", "snow_1h", "clouds_all"]

ONLINE_SHOPPING_CTAB_CATEGORICAL = ONLINE_SHOPPING_CAT_COLS
ONLINE_SHOPPING_CTAB_NUMERIC = ONLINE_SHOPPING_NUM_COLS


def build_metro_ctab_raw(data: pd.DataFrame, target_col: str = "traffic_volume") -> pd.DataFrame:
    df = data.copy().drop(columns=["date_time"], errors="ignore")
    y = pd.to_numeric(df[target_col], errors="coerce")
    x = df.drop(columns=[target_col], errors="ignore")
    for col in METRO_CTAB_NUMERIC:
        if col in x.columns:
            x[col] = pd.to_numeric(x[col], errors="coerce")
    for col in ["holiday", "weather_main", "weather_description"]:
        if col in x.columns:
            x[col] = x[col].fillna("None").astype(str)
    out = pd.concat([x.reset_index(drop=True), y.to_frame(name=target_col)], axis=1)
    out[target_col] = pd.to_numeric(out[target_col], errors="coerce").fillna(0)
    return out


def build_online_shopping_ctab_raw(data: pd.DataFrame, target_col: str = "price") -> pd.DataFrame:
    df = data.copy().drop(columns=["session ID"], errors="ignore")
    y = pd.to_numeric(df[target_col], errors="coerce")
    x = df.drop(columns=[target_col], errors="ignore")
    for col in ONLINE_SHOPPING_NUM_COLS:
        if col in x.columns:
            x[col] = pd.to_numeric(x[col], errors="coerce")
    for col in ONLINE_SHOPPING_CAT_COLS:
        if col in x.columns:
            x[col] = x[col].fillna("None").astype(str)
    out = pd.concat([x.reset_index(drop=True), y.to_frame(name=target_col)], axis=1)
    out[target_col] = pd.to_numeric(out[target_col], errors="coerce")
    valid = out[[target_col] + [c for c in ONLINE_SHOPPING_NUM_COLS if c in out.columns]].notna().all(axis=1)
    return out.loc[valid].reset_index(drop=True)


def prepare_ctabgan_train_df(
    df: pd.DataFrame,
    categorical_cols: list[str],
    numeric_cols: list[str],
    label_col: str,
) -> pd.DataFrame:
    cols = categorical_cols + numeric_cols + [label_col]
    out = df[cols].copy()
    for col in categorical_cols:
        out[col] = out[col].fillna("None").astype(str)
    for col in numeric_cols + [label_col]:
        s = pd.to_numeric(out[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        fill = s.median() if s.notna().any() else 0
        out[col] = s.fillna(fill).astype(np.float64)
    return out


def align_to_train_schema(
    synth_df: pd.DataFrame,
    reference_df: pd.DataFrame,
    label_col: str,
) -> pd.DataFrame:
    df = synth_df.copy()
    y = pd.to_numeric(df[label_col], errors="coerce").fillna(0)
    x = df.drop(columns=[label_col], errors="ignore")
    x_ref = reference_df.drop(columns=[label_col], errors="ignore")

    if x.select_dtypes(include=["object", "string", "category"]).shape[1] > 0:
        x = pd.get_dummies(x, drop_first=True)

    x = x.reindex(columns=x_ref.columns, fill_value=0)
    x = x.apply(pd.to_numeric, errors="coerce").fillna(0).astype(np.float64)

    out = pd.concat([x.reset_index(drop=True), y.reset_index(drop=True)], axis=1)
    out.columns = reference_df.columns
    return out


def encode_online_shopping_ctabgan(
    synth_raw: pd.DataFrame,
    reference_df: pd.DataFrame,
    reference_raw: pd.DataFrame,
    label_col: str,
    seed: int = 42,
) -> pd.DataFrame:
    synth = synth_raw.copy()
    n = len(synth)
    rng = np.random.default_rng(seed)

    if "page 2 (clothing model)" not in synth.columns and "page 2 (clothing model)" in reference_raw.columns:
        pool = reference_raw["page 2 (clothing model)"].fillna("None").astype(str).values
        synth["page 2 (clothing model)"] = rng.choice(pool, size=n)

    for col in ONLINE_SHOPPING_CAT_COLS:
        if col in synth.columns:
            synth[col] = synth[col].fillna("None").astype(str)

    y = pd.to_numeric(synth[label_col], errors="coerce").replace([np.inf, -np.inf], np.nan)
    ref_y = pd.to_numeric(reference_raw[label_col], errors="coerce")
    y = y.fillna(ref_y.median() if ref_y.notna().any() else 0)

    x = synth.drop(columns=[label_col], errors="ignore")
    x = pd.get_dummies(x, drop_first=True)
    x_ref = reference_df.drop(columns=[label_col], errors="ignore")
    x = x.reindex(columns=x_ref.columns, fill_value=0)
    x = x.apply(pd.to_numeric, errors="coerce").fillna(0).astype(np.float64)

    out = pd.concat([x.reset_index(drop=True), y.reset_index(drop=True)], axis=1)
    out.columns = reference_df.columns
    return out


def sanitize_ctabgan_sample(
    raw,
    data_prep,
    ref_df: pd.DataFrame,
    numeric_cols: list[str],
    seed: int = 42,
) -> np.ndarray:
    df = pd.DataFrame(raw, columns=data_prep.df.columns)
    rng = np.random.default_rng(seed)

    for enc in getattr(data_prep, "label_encoder_list", []):
        col = enc["column"]
        n_classes = len(enc["label_encoder"].classes_)
        vals = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        vals = vals.fillna(0).clip(0, n_classes - 1)
        df[col] = np.round(vals)

    cols_to_fix = list(dict.fromkeys(list(data_prep.integer_columns or []) + numeric_cols))
    for col in cols_to_fix:
        if col not in df.columns or col not in ref_df.columns:
            continue
        ref = pd.to_numeric(ref_df[col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        if ref.empty:
            continue
        vals = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        if vals.notna().sum() == 0:
            df[col] = rng.choice(ref.values, size=len(df))
        else:
            fill = ref.median()
            vals = vals.fillna(fill).clip(ref.min(), ref.max())
            df[col] = vals

    return df.to_numpy()


def get_ctabgan_config(preset_id: str | None, target_col: str) -> dict | None:
    if preset_id == "metro":
        return {
            "categorical_columns": METRO_CTAB_CATEGORICAL,
            "mixed_columns": {},
            "general_columns": METRO_CTAB_NUMERIC + [target_col],
            "integer_columns": ["clouds_all", target_col],
            "numeric_columns": METRO_CTAB_NUMERIC,
            "problem_type": {"Regression": target_col},
        }
    if preset_id == "online_shopping":
        return {
            "categorical_columns": ONLINE_SHOPPING_CTAB_CATEGORICAL,
            "mixed_columns": {},
            "general_columns": ONLINE_SHOPPING_NUM_COLS + [target_col],
            "integer_columns": [],
            "numeric_columns": ONLINE_SHOPPING_NUM_COLS,
            "problem_type": {"Regression": target_col},
        }
    return None
