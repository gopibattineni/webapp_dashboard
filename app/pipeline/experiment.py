"""Experiment orchestration — ties together the full FORGE pipeline."""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from app.pipeline.datasets import load_dataset
from app.pipeline.fidelity import evaluate_all_fidelity
from app.pipeline.generators import run_all_generators
from app.pipeline.preprocessor import preprocess_pipeline, sanitize_synthetic_target
from app.pipeline.privacy import evaluate_all_privacy
from app.pipeline.task_type import detect_task_type
from app.pipeline.utility import run_utility_evaluation

WEBAPP_ROOT = Path(__file__).resolve().parents[2]
SESSIONS_DIR = WEBAPP_ROOT / "data" / "sessions"


class ExperimentStore:
    """In-memory + disk session store for experiments."""

    def __init__(self):
        self._sessions: dict[str, dict] = {}
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    def create(self) -> str:
        sid = str(uuid.uuid4())
        self._sessions[sid] = {
            "id": sid,
            "status": "created",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "raw_data": None,
            "metadata": None,
            "preprocessed": None,
            "results": None,
            "progress": [],
            "error": None,
        }
        return sid

    def get(self, sid: str) -> dict | None:
        return self._sessions.get(sid)

    def _log(self, sid: str, message: str):
        session = self._sessions[sid]
        session["progress"].append(message)

    def load_dataset(
        self,
        sid: str,
        uci_id: int | None = None,
        preset_id: str | None = None,
    ) -> dict:
        session = self._sessions[sid]
        session["status"] = "loading"
        label = preset_id or f"UCI {uci_id}"
        self._log(sid, f"Loading dataset ({label})...")

        data, metadata = load_dataset(uci_id=uci_id, preset_id=preset_id)
        session["raw_data"] = data
        session["metadata"] = metadata
        session["status"] = "loaded"
        self._log(sid, f"Loaded {metadata['name']} ({len(data)} rows, {data.shape[1]} columns)")

        preview = data.head(10).to_dict(orient="records")
        dtypes = {col: str(dtype) for col, dtype in data.dtypes.items()}
        missing = {col: int(data[col].isna().sum()) for col in data.columns}
        task_type = metadata.get("task_type") or detect_task_type(
            data,
            metadata["target_cols"][0] if metadata.get("target_cols") else data.columns[-1],
            uci_id=metadata.get("uci_id"),
            preset_id=metadata.get("preset_id"),
        )

        return _json_safe({
            "session_id": sid,
            "metadata": metadata,
            "shape": list(data.shape),
            "preview": preview,
            "dtypes": dtypes,
            "missing_counts": missing,
            "task_type": task_type,
            "suggested_target": (
                metadata["target_cols"][0]
                if metadata.get("target_cols")
                else data.columns[-1]
            ),
        })

    def load_uci(self, sid: str, uci_id: int) -> dict:
        return self.load_dataset(sid, uci_id=uci_id)

    def preprocess(
        self,
        sid: str,
        target_col: str | None = None,
        n_subsample: int = 1000,
        test_size: float = 0.2,
        seed: int = 42,
        drop_columns: list[str] | None = None,
    ) -> dict:
        session = self._sessions[sid]
        if session["raw_data"] is None:
            raise ValueError("Load a dataset first")

        session["status"] = "preprocessing"
        self._log(sid, "Handling missing values and encoding categoricals...")

        result = preprocess_pipeline(
            session["raw_data"],
            target_col=target_col,
            n_subsample=n_subsample,
            test_size=test_size,
            seed=seed,
            drop_columns=drop_columns,
            uci_id=session["metadata"].get("uci_id") if session.get("metadata") else None,
            preset_id=session["metadata"].get("preset_id") if session.get("metadata") else None,
        )
        result["task_type"] = detect_task_type(
            result["data"],
            result["target_col"],
            uci_id=session["metadata"].get("uci_id") if session.get("metadata") else None,
            preset_id=session["metadata"].get("preset_id") if session.get("metadata") else None,
        )

        session["preprocessed"] = result
        session["status"] = "preprocessed"
        self._log(
            sid,
            f"Split: {result['n_train']} train ({result['train_fraction']*100:.0f}%) "
            f"/ {result['n_test']} holdout ({result['test_fraction']*100:.0f}%)",
        )

        return _json_safe({
            "session_id": sid,
            "target_col": result["target_col"],
            "n_total": result["n_total"],
            "n_train": result["n_train"],
            "n_test": result["n_test"],
            "train_fraction": result["train_fraction"],
            "test_fraction": result["test_fraction"],
            "missing_stats": result["missing_stats"],
            "task_type": result["task_type"],
            "downstream_models": 10,
            "evaluation_seeds": 10,
            "train_preview": result["train_real"].head(5).to_dict(orient="records"),
            "test_preview": result["test_real"].head(5).to_dict(orient="records"),
        })

    def run_experiment(
        self,
        sid: str,
        n_synthetic: int = 1000,
        seed: int = 42,
        run_fidelity: bool = True,
        run_privacy: bool = True,
        run_utility: bool = True,
        generators: list[str] | None = None,
        fast_mode: bool = False,
    ) -> dict:
        session = self._sessions[sid]
        if session["preprocessed"] is None:
            raise ValueError("Preprocess the dataset first")

        session["status"] = "running"
        prep = session["preprocessed"]
        train_real = prep["train_real"]
        test_real = prep["test_real"]
        target_col = prep["target_col"]
        test_size = prep["test_fraction"]

        work_dir = SESSIONS_DIR / sid
        work_dir.mkdir(parents=True, exist_ok=True)

        results: dict = {
            "fidelity": None,
            "privacy": None,
            "utility": None,
            "generators_run": [],
            "generator_errors": {},
        }

        self._log(sid, "Training 6 generators on 80% real data (no leakage)...")
        synthetic, errors, metadata = run_all_generators(
            train_real=train_real,
            target_col=target_col,
            n_samples=n_synthetic,
            seed=seed,
            work_dir=work_dir,
            generators=generators,
            fast_mode=fast_mode,
            on_progress=lambda msg: self._log(sid, msg),
            task_type=prep.get("task_type", "classification"),
            preset_id=session["metadata"].get("preset_id") if session.get("metadata") else None,
            train_real_ctab=prep.get("train_real_ctab"),
        )
        results["generators_run"] = list(synthetic.keys())
        results["generator_errors"] = errors
        results["generators_expected"] = (
            ["GaussianCopula"] if fast_mode else [
                "CTGAN", "CopulaGAN", "TVAE", "GaussianCopula", "WGAN_GP", "CTABGAN"
            ]
        )

        for name, df in synthetic.items():
            df.to_csv(work_dir / f"synthetic_{name}.csv", index=False)

        self._log(sid, f"Generated synthetic data from: {', '.join(synthetic.keys())}")

        if run_fidelity and synthetic:
            self._log(sid, "Running fidelity (SDV, KS, JS, Wasserstein, Gower, MMD, C2ST)...")
            results["fidelity"] = evaluate_all_fidelity(
                train_real, synthetic, metadata, target_col
            )

        if run_privacy and synthetic:
            self._log(sid, "Running privacy (NN, DCR, Mahalanobis, Hungarian, MIA)...")
            results["privacy"] = evaluate_all_privacy(
                train_real, test_real, synthetic, target_col
            )

        if run_utility and synthetic:
            task_type = prep.get("task_type", "classification")
            self._log(
                sid,
                f"Running utility (TRTR vs TSTR): 6 generators × 10 "
                f"{'regressors' if task_type == 'regression' else 'classifiers'} × 10 seeds...",
            )
            results["utility"] = run_utility_evaluation(
                train_real,
                test_real,
                synthetic,
                target_col,
                task_type=task_type,
                test_size=test_size,
            )

        session["results"] = results
        session["status"] = "completed"
        self._log(sid, "Experiment completed.")

        results_path = work_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(_json_safe(results), f, indent=2)

        return results

    def status(self, sid: str) -> dict:
        session = self._sessions[sid]
        return {
            "session_id": sid,
            "status": session["status"],
            "progress": session["progress"],
            "error": session["error"],
            "has_results": session["results"] is not None,
        }

    def results(self, sid: str) -> dict | None:
        session = self._sessions[sid]
        results = session.get("results")
        return _json_safe(results) if results is not None else None


def _json_safe(obj):
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, pd.DataFrame):
        return _json_safe(obj.to_dict(orient="records"))
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (np.floating, np.integer, np.bool_)):
        val = obj.item()
        return _json_safe(val)
    if isinstance(obj, np.ndarray):
        return _json_safe(obj.tolist())
    if obj is pd.NA:
        return None
    if hasattr(obj, "item") and not isinstance(obj, (bytes, str)):
        try:
            return _json_safe(obj.item())
        except (ValueError, AttributeError):
            pass
    return obj


store = ExperimentStore()
