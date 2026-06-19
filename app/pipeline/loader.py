"""Load datasets from the UCI ML Repository."""

from __future__ import annotations

import pandas as pd
from ucimlrepo import fetch_ucirepo


def load_uci_dataset(uci_id: int) -> tuple[pd.DataFrame, dict]:
    """Fetch a UCI dataset and return features+targets merged with metadata."""
    dataset = fetch_ucirepo(id=uci_id)

    x = dataset.data.features
    y = dataset.data.targets

    if isinstance(y, pd.DataFrame) and y.shape[1] == 1:
        y = y.iloc[:, 0]
    elif isinstance(y, pd.DataFrame) and y.shape[1] > 1:
        # Multi-target: use last target column as label (matches notebook convention).
        pass

    if isinstance(y, pd.Series):
        data = pd.concat([x, y.to_frame(name=y.name or "target")], axis=1)
    else:
        data = pd.concat([x, y], axis=1)

    variables = dataset.variables
    metadata = {
        "uci_id": uci_id,
        "name": getattr(dataset.metadata, "name", f"UCI-{uci_id}"),
        "num_instances": getattr(dataset.metadata, "num_instances", len(data)),
        "num_features": getattr(dataset.metadata, "num_features", x.shape[1]),
        "has_missing_values": getattr(dataset.metadata, "has_missing_values", "unknown"),
        "target_cols": list(y.columns) if isinstance(y, pd.DataFrame) else [data.columns[-1]],
        "feature_cols": list(x.columns),
        "columns": list(data.columns),
    }

    return data, metadata
