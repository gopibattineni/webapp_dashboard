"""Extended fidelity metrics — SDV models / Cancer.ipynb experimental setup."""

from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype
from scipy.spatial.distance import jensenshannon
from scipy.stats import wasserstein_distance
from sdv.evaluation.single_table import QualityReport, evaluate_quality
from sdv.metadata import SingleTableMetadata
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.metrics.pairwise import rbf_kernel
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler, StandardScaler

from app.pipeline.metrics_common import align_feature_frames, round_float, subsample_rows


def _prob_vectors_numeric(real, synth, bins=30, eps=1e-12):
    real = pd.to_numeric(real, errors="coerce").dropna().to_numpy()
    synth = pd.to_numeric(synth, errors="coerce").dropna().to_numpy()
    edges = np.histogram_bin_edges(np.concatenate([real, synth]), bins=bins)
    r_hist, _ = np.histogram(real, bins=edges)
    s_hist, _ = np.histogram(synth, bins=edges)
    r = r_hist.astype(float) + eps
    s = s_hist.astype(float) + eps
    r /= r.sum()
    s /= s.sum()
    return r, s


def _prob_vectors_categorical(real, synth, eps=1e-12):
    r_counts = real.astype(str).value_counts(dropna=False)
    s_counts = synth.astype(str).value_counts(dropna=False)
    keys = r_counts.index.union(s_counts.index)
    r = r_counts.reindex(keys, fill_value=0).to_numpy(dtype=float) + eps
    s = s_counts.reindex(keys, fill_value=0).to_numpy(dtype=float) + eps
    r /= r.sum()
    s /= s.sum()
    return r, s


def compute_js_divergence(
    real_df: pd.DataFrame,
    synth_df: pd.DataFrame,
    bins: int = 30,
    normalize: bool = True,
) -> dict:
    common_cols = [c for c in real_df.columns if c in synth_df.columns]
    real = real_df[common_cols].copy()
    synth = synth_df[common_cols].copy()

    if normalize:
        num_cols = [c for c in common_cols if is_numeric_dtype(real[c])]
        if num_cols:
            scaler = MinMaxScaler()
            real[num_cols] = scaler.fit_transform(real[num_cols])
            synth[num_cols] = scaler.transform(synth[num_cols])

    values = []
    for col in common_cols:
        r_col, s_col = real[col], synth[col]
        if is_numeric_dtype(r_col):
            p, q = _prob_vectors_numeric(r_col, s_col, bins=bins)
        else:
            p, q = _prob_vectors_categorical(r_col, s_col)[:2]
        values.append(float(jensenshannon(p, q, base=2) ** 2))

    return {
        "js_divergence_mean": round_float(np.mean(values)),
        "js_divergence_median": round_float(np.median(values)),
        "js_divergence_max": round_float(np.max(values)),
    }


def compute_wasserstein(
    real_df: pd.DataFrame,
    synth_df: pd.DataFrame,
) -> dict:
    common_cols = [
        c
        for c in real_df.columns
        if c in synth_df.columns and is_numeric_dtype(real_df[c])
    ]
    if not common_cols:
        return {"wasserstein_mean": float("nan")}

    real = real_df[common_cols].copy()
    synth = synth_df[common_cols].copy()
    scaler = MinMaxScaler()
    real_scaled = scaler.fit_transform(real)
    synth_scaled = scaler.transform(synth)

    dists = [
        wasserstein_distance(real_scaled[:, i], synth_scaled[:, i])
        for i in range(len(common_cols))
    ]
    return {
        "wasserstein_mean": round_float(np.mean(dists)),
        "wasserstein_median": round_float(np.median(dists)),
        "wasserstein_max": round_float(np.max(dists)),
    }


def compute_ks_complement_mean(
    train_real: pd.DataFrame,
    synthetic_data: pd.DataFrame,
    metadata: SingleTableMetadata,
) -> dict:
    try:
        qr = QualityReport()
        qr.generate(
            real_data=train_real,
            synthetic_data=synthetic_data,
            metadata=metadata.to_dict(),
        )
        details = qr.get_details("Column Shapes")
        scores = details["Score"].astype(float)
        return {
            "ks_complement_mean": round_float(scores.mean()),
            "ks_complement_median": round_float(scores.median()),
            "ks_complement_min": round_float(scores.min()),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ks_complement_error": str(exc)}


def compute_gower_similarity(
    real_df: pd.DataFrame,
    synth_df: pd.DataFrame,
    max_rows: int = 500,
) -> dict:
    try:
        import gower
    except ImportError:
        return {"gower_error": "gower package not installed"}

    n_real = min(len(real_df), max_rows)
    n_synth = min(len(synth_df), max_rows)
    xr = real_df.sample(n=n_real, random_state=42) if len(real_df) > n_real else real_df
    xs = synth_df.sample(n=n_synth, random_state=42) if len(synth_df) > n_synth else synth_df

    g_real = 1 - gower.gower_matrix(xr)
    g_synth = 1 - gower.gower_matrix(xs)
    real_upper = g_real[np.triu_indices_from(g_real, k=1)]
    synth_upper = g_synth[np.triu_indices_from(g_synth, k=1)]

    combined = pd.concat([xr, xs], ignore_index=True)
    g_combined = 1 - gower.gower_matrix(combined)
    cross_block = g_combined[:n_real, n_real:]

    return {
        "gower_intra_real_mean": round_float(float(np.mean(real_upper))),
        "gower_intra_synth_mean": round_float(float(np.mean(synth_upper))),
        "gower_cross_mean": round_float(float(np.mean(cross_block))),
    }


def mmd_rbf(x: np.ndarray, y: np.ndarray, gamma: float | None = None) -> float:
    if gamma is None:
        z = np.vstack([x, y])
        dists = np.sqrt(((z[:, None, :] - z[None, :, :]) ** 2).sum(-1))
        med = np.median(dists[dists > 0])
        gamma = 1.0 / (2 * (med**2)) if med > 0 else 1.0

    kxx = rbf_kernel(x, x, gamma=gamma)
    kyy = rbf_kernel(y, y, gamma=gamma)
    kxy = rbf_kernel(x, y, gamma=gamma)
    n, m = len(x), len(y)
    if n < 2 or m < 2:
        return float("nan")
    return float(
        (kxx.sum() - np.trace(kxx)) / (n * (n - 1))
        + (kyy.sum() - np.trace(kyy)) / (m * (m - 1))
        - 2 * kxy.mean()
    )


def compute_mmd_c2st(
    real_features: pd.DataFrame,
    synth_features: pd.DataFrame,
    max_rows: int = 1500,
    seed: int = 42,
) -> dict:
    scaler = StandardScaler()
    x_real = scaler.fit_transform(real_features)
    x_synth = scaler.transform(synth_features)
    x_real = subsample_rows(x_real, max_rows, seed)
    x_synth = subsample_rows(x_synth, max_rows, seed)

    mmd = mmd_rbf(x_real, x_synth)

    x_c2st = np.vstack([x_real, x_synth])
    y_c2st = np.hstack([np.zeros(len(x_real)), np.ones(len(x_synth))])
    x_train, x_test, y_train, y_test = train_test_split(
        x_c2st, y_c2st, test_size=0.3, stratify=y_c2st, random_state=seed
    )
    clf = RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=-1)
    clf.fit(x_train, y_train)
    acc = accuracy_score(y_test, clf.predict(x_test))

    return {
        "mmd_rbf": round_float(mmd),
        "c2st_accuracy": round_float(acc),
    }


def evaluate_sdv_quality(
    train_real: pd.DataFrame,
    synthetic_data: pd.DataFrame,
    metadata: SingleTableMetadata,
) -> dict:
    quality = evaluate_quality(
        real_data=train_real,
        synthetic_data=synthetic_data,
        metadata=metadata,
    )
    score = quality.get_score()
    result = {
        "overall_score": round_float(score),
        "column_shapes_score": None,
        "column_pair_trends_score": None,
    }
    try:
        props = quality.get_properties()
        if hasattr(props, "iterrows"):
            for _, row in props.iterrows():
                prop = str(row.get("Property", row.iloc[0]))
                val = float(row.get("Score", row.iloc[1]))
                if "Column Shapes" in prop:
                    result["column_shapes_score"] = round_float(val)
                elif "Column Pair" in prop:
                    result["column_pair_trends_score"] = round_float(val)
    except Exception:  # noqa: BLE001
        pass
    return result


def evaluate_fidelity_full(
    train_real: pd.DataFrame,
    synthetic_data: pd.DataFrame,
    metadata: SingleTableMetadata,
    label_col: str,
) -> dict:
    """All fidelity metrics from SDV models Cancer notebook."""
    result = {}
    result.update(evaluate_sdv_quality(train_real, synthetic_data, metadata))
    result.update(compute_ks_complement_mean(train_real, synthetic_data, metadata))
    result.update(compute_js_divergence(train_real, synthetic_data))
    result.update(compute_wasserstein(train_real, synthetic_data))
    result.update(compute_gower_similarity(train_real, synthetic_data))

    real_feat, synth_feat = align_feature_frames(train_real, synthetic_data, label_col)
    if not real_feat.empty:
        result.update(compute_mmd_c2st(real_feat, synth_feat))

    return result


def evaluate_all_fidelity(
    train_real: pd.DataFrame,
    synthetic_datasets: dict[str, pd.DataFrame],
    metadata: SingleTableMetadata,
    label_col: str,
) -> dict[str, dict]:
    results = {}
    for name, synth in synthetic_datasets.items():
        try:
            results[name] = evaluate_fidelity_full(
                train_real, synth, metadata, label_col
            )
        except Exception as exc:  # noqa: BLE001
            results[name] = {"error": str(exc)}
    return results
