"""Preprocessing — mirrors Adult / Bank / CDC notebook logic."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from app.pipeline.ctabgan_helpers import (
    build_metro_ctab_raw,
    build_online_shopping_ctab_raw,
)


def _safe_stratify(y: pd.Series):
    y = pd.Series(y).reset_index(drop=True)
    if y.nunique() < 2 or y.value_counts().min() < 2:
        return None
    return y


def handle_missing_values(
    data: pd.DataFrame,
    missing_token: str = "?",
) -> tuple[pd.DataFrame, dict]:
    """
    Replace missing tokens with NaN, then impute:
    - numeric columns: mean
    - categorical columns: mode
    """
    df = data.copy()
    stats = {"missing_before": {}, "imputed": {}}

    if missing_token:
        df = df.replace(missing_token, np.nan)

    for col in df.columns:
        n_missing = int(df[col].isna().sum())
        if n_missing:
            stats["missing_before"][col] = n_missing

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    cat_cols = df.select_dtypes(exclude=[np.number]).columns

    for col in numeric_cols:
        if df[col].isna().any():
            fill = df[col].mean()
            df[col] = df[col].fillna(fill)
            stats["imputed"][col] = {"strategy": "mean", "value": float(fill)}

    for col in cat_cols:
        if df[col].isna().any():
            mode_val = df[col].mode()
            fill = mode_val.iloc[0] if len(mode_val) else "unknown"
            df[col] = df[col].fillna(fill)
            stats["imputed"][col] = {"strategy": "mode", "value": str(fill)}

    return df, stats


def encode_categoricals(
    data: pd.DataFrame,
    target_col: str,
    skip_target: bool = True,
) -> tuple[pd.DataFrame, dict[str, LabelEncoder]]:
    """Label-encode object/category columns (Adult / Mushroom notebook pattern)."""
    df = data.copy()
    encoders: dict[str, LabelEncoder] = {}

    for col in df.select_dtypes(include=["object", "category"]).columns:
        if skip_target and col == target_col:
            continue
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        encoders[col] = le

    return df, encoders


def clean_string_target(series: pd.Series) -> pd.Series:
    """Normalize string labels (Adult income: strip trailing dots)."""
    if series.dtype == object or isinstance(series.dtype, pd.CategoricalDtype):
        return series.astype(str).str.replace(".", "", regex=False).str.strip()
    return series


def preprocess_metro(data: pd.DataFrame, target_col: str = "traffic_volume") -> pd.DataFrame:
    """Metro Interstate notebook: drop date_time, one-hot encode categoricals."""
    df = data.copy()
    df = df.drop(columns=["date_time"], errors="ignore")

    y = pd.to_numeric(df[target_col], errors="coerce")
    x = df.drop(columns=[target_col], errors="ignore")

    for col in ["temp", "rain_1h", "snow_1h", "clouds_all"]:
        if col in x.columns:
            x[col] = pd.to_numeric(x[col], errors="coerce")

    for col in ["holiday", "weather_main", "weather_description"]:
        if col in x.columns:
            x[col] = x[col].fillna("None").astype(str)

    x = pd.get_dummies(x, drop_first=True).fillna(0)
    out = pd.concat([x, y.to_frame(name=target_col)], axis=1)
    return out.apply(pd.to_numeric, errors="coerce").fillna(0).astype(np.float64)


def preprocess_online_shopping(data: pd.DataFrame, target_col: str = "price") -> pd.DataFrame:
    """Online shopping notebook: one-hot categoricals, numeric target price."""
    df = data.copy()
    df = df.drop(columns=["session ID"], errors="ignore")

    cat_cols = [
        "country",
        "page 1 (main category)",
        "page 2 (clothing model)",
        "colour",
        "location",
        "model photography",
    ]
    num_cols = ["year", "month", "day", "order", "price 2", "page"]

    y = pd.to_numeric(df[target_col], errors="coerce")
    x = df.drop(columns=[target_col], errors="ignore")

    for col in num_cols:
        if col in x.columns:
            x[col] = pd.to_numeric(x[col], errors="coerce")

    x_encoded = x.copy()
    for col in cat_cols:
        if col in x_encoded.columns:
            x_encoded[col] = x_encoded[col].fillna("None").astype(str)

    x_encoded = pd.get_dummies(x_encoded, drop_first=True).fillna(0)
    out = pd.concat([x_encoded, y.to_frame(name=target_col)], axis=1)
    out = out.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)

    valid_cols = [c for c in num_cols if c in out.columns] + [target_col]
    valid = out[valid_cols].notna().all(axis=1)
    out = out.loc[valid].reset_index(drop=True)
    return out.fillna(0).astype(np.float64)


def resolve_target_column(data: pd.DataFrame, target_col: str | None, uci_id: int | None) -> str:
    """Pick target column — Adult notebook uses y.columns[0] (income), not last column."""
    if target_col and target_col in data.columns:
        return target_col
    if uci_id == 2 and "income" in data.columns:
        return "income"
    if uci_id == 492 and "traffic_volume" in data.columns:
        return "traffic_volume"
    if uci_id == 553 and "price" in data.columns:
        return "price"
    return data.columns[-1]


def subsample_data(
    data: pd.DataFrame,
    n_samples: int,
    target_col: str,
    seed: int = 42,
) -> pd.DataFrame:
    """Stratified subsample when dataset is larger than n_samples."""
    if len(data) <= n_samples:
        return data.reset_index(drop=True)

    sampled, _ = train_test_split(
        data,
        train_size=n_samples,
        stratify=_safe_stratify(data[target_col]),
        random_state=seed,
    )
    return sampled.reset_index(drop=True)


def split_for_generators(
    data: pd.DataFrame,
    target_col: str,
    test_size: float = 0.2,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    80% train_real for generators, 20% test_real holdout (no leakage).
    Matches forest_cover / cancer notebook split.
    """
    train_real, test_real = train_test_split(
        data,
        test_size=test_size,
        stratify=_safe_stratify(data[target_col]),
        random_state=seed,
    )
    return train_real.reset_index(drop=True), test_real.reset_index(drop=True)


def sanitize_synthetic_target(
    synthetic: pd.DataFrame,
    train_real: pd.DataFrame,
    target_col: str,
) -> pd.DataFrame:
    """Clip synthetic target to valid training classes (Adult / SDV notebook pattern)."""
    out = synthetic.copy()
    if target_col not in out.columns:
        return out

    ref = train_real[target_col]
    valid = np.sort(ref.dropna().unique())
    if len(valid) == 0:
        return out

    vals = pd.to_numeric(out[target_col], errors="coerce")
    fill = ref.mode().iloc[0]
    vals = vals.fillna(fill)

    if len(valid) <= 20:
        # Map each value to nearest valid class (handles spurious SDV samples)
        valid_arr = np.asarray(valid, dtype=float)

        def _nearest(v):
            idx = int(np.argmin(np.abs(valid_arr - float(v))))
            return valid_arr[idx]

        vals = vals.map(_nearest)
    else:
        vals = vals.clip(valid.min(), valid.max())

    out[target_col] = vals.astype(ref.dtype)
    return out


def subsample_pair(
    df: pd.DataFrame,
    df_ctab: pd.DataFrame,
    n_samples: int,
    target_col: str,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if len(df) <= n_samples:
        return df.reset_index(drop=True), df_ctab.reset_index(drop=True)

    sampled, _ = train_test_split(
        df,
        train_size=n_samples,
        stratify=_safe_stratify(df[target_col]),
        random_state=seed,
    )
    idx = sampled.index
    return (
        sampled.reset_index(drop=True),
        df_ctab.loc[idx].reset_index(drop=True),
    )


def split_pair(
    df: pd.DataFrame,
    df_ctab: pd.DataFrame,
    target_col: str,
    test_size: float = 0.2,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    indices = np.arange(len(df))
    train_idx, test_idx = train_test_split(
        indices,
        test_size=test_size,
        stratify=_safe_stratify(df[target_col]),
        random_state=seed,
    )
    train_real = df.iloc[train_idx].reset_index(drop=True)
    test_real = df.iloc[test_idx].reset_index(drop=True)
    train_ctab = df_ctab.iloc[train_idx].reset_index(drop=True)
    test_ctab = df_ctab.iloc[test_idx].reset_index(drop=True)
    return train_real, test_real, train_ctab, test_ctab


def preprocess_pipeline(
    data: pd.DataFrame,
    target_col: str | None = None,
    n_subsample: int | None = 1000,
    test_size: float = 0.2,
    seed: int = 42,
    encode: bool = True,
    drop_columns: list[str] | None = None,
    uci_id: int | None = None,
    preset_id: str | None = None,
) -> dict:
    """Full preprocessing pipeline returning split data and diagnostics."""
    train_real_ctab = None
    test_real_ctab = None

    if preset_id == "metro":
        target_col = "traffic_volume"
        df_ctab = build_metro_ctab_raw(data, target_col)
        df = preprocess_metro(data, target_col)
        missing_stats = {"missing_before": {}, "imputed": {}}
        encoders = {}
    elif preset_id == "online_shopping":
        target_col = "price"
        df_ctab = build_online_shopping_ctab_raw(data, target_col)
        df = preprocess_online_shopping(data, target_col)
        if len(df_ctab) != len(df):
            min_len = min(len(df), len(df_ctab))
            df = df.iloc[:min_len].reset_index(drop=True)
            df_ctab = df_ctab.iloc[:min_len].reset_index(drop=True)
        missing_stats = {"missing_before": {}, "imputed": {}}
        encoders = {}
    else:
        df = data.copy()

        if drop_columns:
            df = df.drop(columns=[c for c in drop_columns if c in df.columns])

        target_col = resolve_target_column(df, target_col, uci_id)

        # Adult Census: clean income labels before imputation (exact notebook step)
        if uci_id == 2 or target_col == "income":
            df[target_col] = clean_string_target(df[target_col])

        df, missing_stats = handle_missing_values(df)

        # Coerce numeric-looking object columns
        for col in df.columns:
            if col != target_col and df[col].dtype == object:
                converted = pd.to_numeric(df[col], errors="coerce")
                if converted.notna().sum() > 0.8 * len(df):
                    df[col] = converted

        df, missing_stats2 = handle_missing_values(df)
        missing_stats["imputed"].update(missing_stats2.get("imputed", {}))

        encoders = {}
        if encode:
            # Encode all categoricals including target (Adult notebook pattern)
            for col in df.select_dtypes(include=["object", "category"]).columns:
                le = LabelEncoder()
                df[col] = le.fit_transform(df[col].astype(str))
                encoders[col] = le

    if n_subsample:
        if preset_id in ("metro", "online_shopping"):
            df, df_ctab = subsample_pair(df, df_ctab, n_subsample, target_col, seed)
        else:
            df = subsample_data(df, n_subsample, target_col, seed)

    if preset_id in ("metro", "online_shopping"):
        train_real, test_real, train_real_ctab, test_real_ctab = split_pair(
            df, df_ctab, target_col, test_size, seed
        )
    else:
        train_real, test_real = split_for_generators(df, target_col, test_size, seed)

    return {
        "data": df,
        "train_real": train_real,
        "test_real": test_real,
        "train_real_ctab": train_real_ctab,
        "test_real_ctab": test_real_ctab,
        "target_col": target_col,
        "missing_stats": missing_stats,
        "encoders": encoders,
        "preset_id": preset_id,
        "n_total": len(df),
        "n_train": len(train_real),
        "n_test": len(test_real),
        "train_fraction": round(1 - test_size, 2),
        "test_fraction": test_size,
    }
