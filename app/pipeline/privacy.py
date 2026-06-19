"""Privacy evaluation — distance metrics, Hungarian matching, MIA."""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.linalg import LinAlgError, inv
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from app.pipeline.metrics_common import numeric_matrix, round_float, subsample_rows


def fit_mahalanobis_params(real_matrix: np.ndarray, reg: float = 1e-6):
    mu = np.mean(real_matrix, axis=0)
    cov = np.cov(real_matrix, rowvar=False)
    if cov.ndim == 0:
        cov = np.array([[cov]])
    p = cov.shape[0]
    try:
        inv_cov = inv(cov + reg * np.eye(p))
    except LinAlgError:
        inv_cov = np.linalg.pinv(cov + reg * np.eye(p))
    return mu, inv_cov


def mahalanobis_distances_to_distribution(
    synth_matrix: np.ndarray, mu: np.ndarray, inv_cov: np.ndarray
) -> np.ndarray:
    delta = synth_matrix - mu
    d2 = np.einsum("ij,jk,ik->i", delta, inv_cov, delta)
    return np.sqrt(np.maximum(d2, 0.0))


def nearest_neighbor_privacy(
    train_real: pd.DataFrame,
    synthetic_data: pd.DataFrame,
    label_col: str,
) -> dict:
    x_real = numeric_matrix(train_real, label_col)
    x_synth = numeric_matrix(synthetic_data, label_col)

    scaler = StandardScaler()
    x_real_scaled = scaler.fit_transform(x_real)
    x_synth_scaled = scaler.transform(x_synth)

    nn = NearestNeighbors(n_neighbors=1).fit(x_real_scaled)
    distances, _ = nn.kneighbors(x_synth_scaled)
    distances = distances.flatten()

    return {
        "mean_nn_distance": round_float(np.mean(distances)),
        "min_nn_distance": round_float(np.min(distances)),
        "p5_nn_distance": round_float(np.percentile(distances, 5)),
        "p95_nn_distance": round_float(np.percentile(distances, 95)),
    }


def distance_to_closest_record(
    train_real: pd.DataFrame,
    synthetic_data: pd.DataFrame,
    label_col: str,
) -> dict:
    """DCR — distance from each synthetic row to nearest real training record."""
    return nearest_neighbor_privacy(train_real, synthetic_data, label_col)


def mahalanobis_privacy(
    train_real: pd.DataFrame,
    synthetic_data: pd.DataFrame,
    label_col: str,
) -> dict:
    real_matrix = numeric_matrix(train_real, label_col)
    synth_matrix = numeric_matrix(synthetic_data, label_col)

    mu, inv_cov = fit_mahalanobis_params(real_matrix)
    distances = mahalanobis_distances_to_distribution(synth_matrix, mu, inv_cov)

    return {
        "mean_mahalanobis": round_float(np.mean(distances)),
        "min_mahalanobis": round_float(np.min(distances)),
        "p5_mahalanobis": round_float(np.percentile(distances, 5)),
        "p95_mahalanobis": round_float(np.percentile(distances, 95)),
    }


def hungarian_matching_score(
    train_real: pd.DataFrame,
    synthetic_data: pd.DataFrame,
    label_col: str,
    metric: str = "cosine",
    max_rows: int = 500,
) -> dict:
    real_matrix = numeric_matrix(train_real, label_col)
    synth_matrix = numeric_matrix(synthetic_data, label_col)

    n = min(len(real_matrix), len(synth_matrix), max_rows)
    real_matrix = real_matrix[:n]
    synth_matrix = synth_matrix[:n]

    if metric == "mahalanobis":
        mu, inv_cov = fit_mahalanobis_params(real_matrix)
        d = cdist(synth_matrix, real_matrix, metric="mahalanobis", VI=inv_cov)
    else:
        d = cdist(synth_matrix, real_matrix, metric="cosine")

    row_ind, col_ind = linear_sum_assignment(d)
    matched_distances = d[row_ind, col_ind]

    return {
        "metric": metric,
        "mean_matched_distance": round_float(np.mean(matched_distances)),
        "min_matched_distance": round_float(np.min(matched_distances)),
        "max_matched_distance": round_float(np.max(matched_distances)),
    }


def membership_inference_attack(
    train_real: pd.DataFrame,
    test_real: pd.DataFrame,
    synthetic_data: pd.DataFrame,
    label_col: str,
    max_train: int = 2000,
    seed: int = 42,
) -> dict:
    """
    Classifier-based MIA: train RF to distinguish generator training members
    (train_real) vs holdout non-members (test_real). Evaluate leakage via
  attack AUC and fraction of synthetic rows classified as members.
    """
    x_member = train_real.drop(columns=[label_col])
    x_nonmember = test_real.drop(columns=[label_col])
    x_synth = synthetic_data.drop(columns=[label_col])

    scaler = StandardScaler()
    xm = scaler.fit_transform(x_member)
    xn = scaler.transform(x_nonmember)
    xs = scaler.transform(x_synth)

    xm = subsample_rows(xm, max_train, seed)
    xn = subsample_rows(xn, max_train, seed + 1)

    x = np.vstack([xm, xn])
    y = np.array([1] * len(xm) + [0] * len(xn))

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.3, stratify=y, random_state=seed
    )

    clf = RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=-1)
    clf.fit(x_train, y_train)

    proba = clf.predict_proba(x_test)[:, 1]
    preds = clf.predict(x_test)
    synth_preds = clf.predict(xs)
    synth_proba = clf.predict_proba(xs)[:, 1]

    try:
        attack_auc = float(roc_auc_score(y_test, proba))
    except ValueError:
        attack_auc = float("nan")

    return {
        "attack_auc": round_float(attack_auc),
        "attack_accuracy": round_float(accuracy_score(y_test, preds)),
        "attack_advantage": round_float(abs(attack_auc - 0.5) * 2),
        "synthetic_member_rate": round_float(float(np.mean(synth_preds))),
        "synthetic_member_proba_mean": round_float(float(np.mean(synth_proba))),
        "interpretation": (
            "Lower attack AUC/advantage and synthetic member rate indicate better privacy."
        ),
    }


def evaluate_privacy_full(
    train_real: pd.DataFrame,
    test_real: pd.DataFrame,
    synthetic_data: pd.DataFrame,
    label_col: str,
) -> dict:
    return {
        "nearest_neighbor": nearest_neighbor_privacy(train_real, synthetic_data, label_col),
        "dcr": distance_to_closest_record(train_real, synthetic_data, label_col),
        "mahalanobis": mahalanobis_privacy(train_real, synthetic_data, label_col),
        "hungarian_cosine": hungarian_matching_score(
            train_real, synthetic_data, label_col, metric="cosine"
        ),
        "hungarian_mahalanobis": hungarian_matching_score(
            train_real, synthetic_data, label_col, metric="mahalanobis"
        ),
        "mia": membership_inference_attack(
            train_real, test_real, synthetic_data, label_col
        ),
    }


def evaluate_all_privacy(
    train_real: pd.DataFrame,
    test_real: pd.DataFrame,
    synthetic_datasets: dict[str, pd.DataFrame],
    label_col: str,
) -> dict[str, dict]:
    results = {}
    for name, synth in synthetic_datasets.items():
        try:
            results[name] = evaluate_privacy_full(
                train_real, test_real, synth, label_col
            )
        except Exception as exc:  # noqa: BLE001
            results[name] = {"error": str(exc)}
    return results
