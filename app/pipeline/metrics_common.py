"""Shared helpers for fidelity / privacy metric modules."""

from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype
from sklearn.preprocessing import MinMaxScaler, StandardScaler


def align_feature_frames(
    real_df: pd.DataFrame,
    synth_df: pd.DataFrame,
    label_col: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    common = [c for c in real_df.columns if c in synth_df.columns and c != label_col]
    return real_df[common].copy(), synth_df[common].copy()


def numeric_matrix(df: pd.DataFrame, label_col: str | None = None) -> np.ndarray:
    work = df.drop(columns=[label_col], errors="ignore") if label_col else df
    numeric = work.select_dtypes(include=[np.number])
    return numeric.fillna(numeric.median()).to_numpy(dtype=float)


def scale_pair(
    real_df: pd.DataFrame,
    synth_df: pd.DataFrame,
    method: str = "standard",
) -> tuple[np.ndarray, np.ndarray]:
    if method == "minmax":
        scaler = MinMaxScaler()
    else:
        scaler = StandardScaler()
    x_real = scaler.fit_transform(real_df)
    x_synth = scaler.transform(synth_df)
    return x_real, x_synth


def subsample_rows(arr: np.ndarray, max_rows: int, seed: int = 42) -> np.ndarray:
    if len(arr) <= max_rows:
        return arr
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(arr), size=max_rows, replace=False)
    return arr[idx]


def round_float(value: float, digits: int = 4) -> float:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return float("nan")
    return round(float(value), digits)
