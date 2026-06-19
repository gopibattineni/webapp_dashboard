"""Task type detection for classification vs regression utility."""

from __future__ import annotations

import pandas as pd

# UCI datasets used as regression in the experimental notebooks
REGRESSION_UCI_IDS = {492, 553}  # Metro Interstate, Online Shopping
REGRESSION_PRESET_IDS = {"metro", "online_shopping"}


def detect_task_type(
    data: pd.DataFrame,
    target_col: str,
    uci_id: int | None = None,
    preset_id: str | None = None,
    unique_threshold: int = 15,
) -> str:
    """
    Return 'regression' or 'classification'.
    Numeric target with many unique values, or known regression datasets → regression.
    """
    if preset_id in REGRESSION_PRESET_IDS:
        return "regression"

    if uci_id in REGRESSION_UCI_IDS:
        return "regression"

    y = data[target_col]
    if pd.api.types.is_numeric_dtype(y) and y.nunique() > unique_threshold:
        return "regression"

    return "classification"
