"""Utility evaluation — TRTR vs TSTR (10 models × 10 seeds, leak-safe holdout)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import (
    AdaBoostClassifier,
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import (
    ElasticNet,
    Lasso,
    LinearRegression,
    LogisticRegression,
    Ridge,
)
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from app.pipeline.generators import GENERATOR_ORDER

EVAL_SEEDS = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]
N_MODELS = 10
N_SEEDS = len(EVAL_SEEDS)


def _safe_stratify(y):
    y = pd.Series(y).reset_index(drop=True)
    if y.nunique() < 2 or y.value_counts().min() < 2:
        return None
    return y


def _std(values):
    return float(np.std(values, ddof=1)) if len(values) > 1 else 0.0


def get_classifiers() -> dict:
    """Ten downstream classifiers from the experimental setup."""
    return {
        "LogReg": LogisticRegression(max_iter=5000, solver="lbfgs", random_state=42),
        "SVM-RBF": SVC(kernel="rbf", probability=True, random_state=42),
        "KNN": KNeighborsClassifier(),
        "NaiveBayes": GaussianNB(),
        "DecisionTree": DecisionTreeClassifier(random_state=42),
        "RandomForest": RandomForestClassifier(random_state=42),
        "ExtraTrees": ExtraTreesClassifier(random_state=42),
        "GradientBoost": GradientBoostingClassifier(random_state=42),
        "AdaBoost": AdaBoostClassifier(random_state=42),
        "MLP": MLPClassifier(max_iter=2000, random_state=42),
    }


def get_regressors() -> dict:
    """Ten downstream regressors from metro_interstate.ipynb."""
    return {
        "LinearRegression": LinearRegression(),
        "Ridge": Ridge(alpha=1.0),
        "Lasso": Lasso(alpha=0.001, max_iter=5000),
        "ElasticNet": ElasticNet(alpha=0.001, l1_ratio=0.5, max_iter=5000),
        "SVR_RBF": SVR(kernel="rbf", C=1.0, epsilon=0.1),
        "KNN": KNeighborsRegressor(n_neighbors=5),
        "DecisionTree": DecisionTreeRegressor(random_state=42),
        "RandomForest": RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1),
        "ExtraTrees": ExtraTreesRegressor(n_estimators=100, random_state=42, n_jobs=-1),
        "GradientBoost": GradientBoostingRegressor(random_state=42),
    }


def _metric_kwargs(y_true):
    n_classes = pd.Series(y_true).nunique()
    if n_classes <= 2:
        return {"average": "binary", "zero_division": 0}
    return {"average": "weighted", "zero_division": 0}


def evaluate_classification_models(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    label_col: str,
    models: dict | None = None,
    test_size: float = 0.2,
    seeds: list[int] | None = None,
    use_holdout: bool = True,
) -> pd.DataFrame:
    if models is None:
        models = get_classifiers()
    if seeds is None:
        seeds = EVAL_SEEDS

    results = []

    for name, model in models.items():
        accuracy_scores, f1_scores, precision_scores, recall_scores = [], [], [], []
        model_error = None

        for seed in seeds:
            x_train_full = train_df.drop(columns=[label_col])
            y_train_full = train_df[label_col]
            x_test = test_df.drop(columns=[label_col])
            y_test = test_df[label_col]

            if use_holdout:
                x_train, _, y_train, _ = train_test_split(
                    x_train_full,
                    y_train_full,
                    test_size=test_size,
                    random_state=seed,
                    stratify=_safe_stratify(y_train_full),
                )
            else:
                x_train, _, y_train, _ = train_test_split(
                    x_train_full,
                    y_train_full,
                    test_size=test_size,
                    random_state=seed,
                    stratify=_safe_stratify(y_train_full),
                )
                _, x_test, _, y_test = train_test_split(
                    x_test,
                    y_test,
                    test_size=test_size,
                    random_state=seed,
                    stratify=_safe_stratify(y_test),
                )

            try:
                clf = clone(model)
                if "random_state" in clf.get_params():
                    clf.set_params(random_state=seed)
                if hasattr(clf, "n_jobs"):
                    clf.set_params(n_jobs=-1)

                clf.fit(x_train, y_train)
                y_pred = clf.predict(x_test)
                mk = _metric_kwargs(y_test)

                accuracy_scores.append(accuracy_score(y_test, y_pred))
                f1_scores.append(f1_score(y_test, y_pred, **mk))
                precision_scores.append(precision_score(y_test, y_pred, **mk))
                recall_scores.append(recall_score(y_test, y_pred, **mk))
            except Exception as exc:  # noqa: BLE001
                model_error = str(exc)
                break

        if model_error or not accuracy_scores:
            results.append({"Model": name, "Error": model_error or "No scores"})
            continue

        results.append({
            "Model": name,
            "Accuracy Mean": float(np.mean(accuracy_scores)),
            "Accuracy Std": _std(accuracy_scores),
            "F1 Mean": float(np.mean(f1_scores)),
            "F1 Std": _std(f1_scores),
            "Precision Mean": float(np.mean(precision_scores)),
            "Precision Std": _std(precision_scores),
            "Recall Mean": float(np.mean(recall_scores)),
            "Recall Std": _std(recall_scores),
        })

    return pd.DataFrame(results).sort_values(by="Accuracy Mean", ascending=False)


def evaluate_regression_models(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    label_col: str,
    models: dict | None = None,
    test_size: float = 0.2,
    seeds: list[int] | None = None,
    use_holdout: bool = True,
) -> pd.DataFrame:
    if models is None:
        models = get_regressors()
    if seeds is None:
        seeds = EVAL_SEEDS

    results = []

    for name, model in models.items():
        r2_scores, mse_scores, rmse_scores, mae_scores = [], [], [], []
        model_error = None

        for seed in seeds:
            x_train_full = train_df.drop(columns=[label_col])
            y_train_full = train_df[label_col]
            x_test = test_df.drop(columns=[label_col])
            y_test = test_df[label_col]

            if use_holdout:
                x_train, _, y_train, _ = train_test_split(
                    x_train_full,
                    y_train_full,
                    test_size=test_size,
                    random_state=seed,
                )
            else:
                x_train, _, y_train, _ = train_test_split(
                    x_train_full,
                    y_train_full,
                    test_size=test_size,
                    random_state=seed,
                )
                _, x_test, _, y_test = train_test_split(
                    x_test,
                    y_test,
                    test_size=test_size,
                    random_state=seed,
                )

            try:
                reg = clone(model)
                if "random_state" in reg.get_params():
                    reg.set_params(random_state=seed)
                if hasattr(reg, "n_jobs"):
                    reg.set_params(n_jobs=-1)

                reg.fit(x_train, y_train)
                y_pred = reg.predict(x_test)

                mse = mean_squared_error(y_test, y_pred)
                r2_scores.append(r2_score(y_test, y_pred))
                mse_scores.append(mse)
                rmse_scores.append(float(np.sqrt(mse)))
                mae_scores.append(mean_absolute_error(y_test, y_pred))
            except Exception as exc:  # noqa: BLE001
                model_error = str(exc)
                break

        if model_error or not r2_scores:
            results.append({"Model": name, "Error": model_error or "No scores"})
            continue

        results.append({
            "Model": name,
            "R2 Mean": float(np.mean(r2_scores)),
            "R2 Std": _std(r2_scores),
            "MSE Mean": float(np.mean(mse_scores)),
            "MSE Std": _std(mse_scores),
            "RMSE Mean": float(np.mean(rmse_scores)),
            "RMSE Std": _std(rmse_scores),
            "MAE Mean": float(np.mean(mae_scores)),
            "MAE Std": _std(mae_scores),
        })

    return pd.DataFrame(results).sort_values(by="R2 Mean", ascending=False)


def run_utility_evaluation(
    train_real: pd.DataFrame,
    test_real: pd.DataFrame,
    synthetic_datasets: dict[str, pd.DataFrame],
    label_col: str,
    task_type: str = "classification",
    test_size: float = 0.2,
    seeds: list[int] | None = None,
) -> dict:
    """TRTR on real data, TSTR per generator — all 6 generators, 10 models, 10 seeds."""
    if seeds is None:
        seeds = EVAL_SEEDS

    is_regression = task_type == "regression"
    model_order = [g for g in GENERATOR_ORDER if g in synthetic_datasets]

    if is_regression:
        trtr = evaluate_regression_models(
            train_real,
            test_real,
            label_col,
            test_size=test_size,
            seeds=seeds,
            use_holdout=True,
        )
    else:
        trtr = evaluate_classification_models(
            train_real,
            test_real,
            label_col,
            test_size=test_size,
            seeds=seeds,
            use_holdout=True,
        )

    all_comparisons = []
    per_generator = {}

    for synth_name in model_order:
        if is_regression:
            tstr = evaluate_regression_models(
                synthetic_datasets[synth_name],
                test_real,
                label_col,
                test_size=test_size,
                seeds=seeds,
                use_holdout=True,
            )
            comparison = trtr.merge(tstr, on="Model", suffixes=("_TRTR", "_TSTR"))
            comparison["R2_Drop"] = (
                comparison["R2 Mean_TRTR"] - comparison["R2 Mean_TSTR"]
            )
            comparison["MSE_Increase"] = (
                comparison["MSE Mean_TSTR"] - comparison["MSE Mean_TRTR"]
            )
            comparison["RMSE_Increase"] = (
                comparison["RMSE Mean_TSTR"] - comparison["RMSE Mean_TRTR"]
            )
            comparison["MAE_Increase"] = (
                comparison["MAE Mean_TSTR"] - comparison["MAE Mean_TRTR"]
            )
        else:
            tstr = evaluate_classification_models(
                synthetic_datasets[synth_name],
                test_real,
                label_col,
                test_size=test_size,
                seeds=seeds,
                use_holdout=True,
            )
            comparison = trtr.merge(tstr, on="Model", suffixes=("_TRTR", "_TSTR"))
            comparison["Accuracy_Drop"] = (
                comparison["Accuracy Mean_TRTR"] - comparison["Accuracy Mean_TSTR"]
            )
            comparison["F1_Drop"] = comparison["F1 Mean_TRTR"] - comparison["F1 Mean_TSTR"]
            comparison["Precision_Drop"] = (
                comparison["Precision Mean_TRTR"] - comparison["Precision Mean_TSTR"]
            )
            comparison["Recall_Drop"] = (
                comparison["Recall Mean_TRTR"] - comparison["Recall Mean_TSTR"]
            )

        comparison["Synthetic_Model"] = synth_name
        per_generator[synth_name] = comparison.to_dict(orient="records")
        all_comparisons.append(comparison)

    combined = pd.concat(all_comparisons, ignore_index=True) if all_comparisons else pd.DataFrame()

    if is_regression and not combined.empty:
        summary = (
            combined.groupby("Synthetic_Model", as_index=False)[
                ["R2_Drop", "MSE_Increase", "RMSE_Increase", "MAE_Increase"]
            ]
            .mean()
            .sort_values("R2_Drop")
        )
    elif not combined.empty:
        summary = (
            combined.groupby("Synthetic_Model", as_index=False)[
                ["Accuracy_Drop", "F1_Drop", "Precision_Drop", "Recall_Drop"]
            ]
            .mean()
            .sort_values("Accuracy_Drop")
        )
    else:
        summary = pd.DataFrame()

    return {
        "task_type": task_type,
        "n_models": N_MODELS,
        "n_seeds": len(seeds),
        "generators_evaluated": model_order,
        "trtr": trtr.to_dict(orient="records"),
        "per_generator": per_generator,
        "summary": summary.to_dict(orient="records"),
    }
