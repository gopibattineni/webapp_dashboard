"""SYNTH Audit Web Application — FastAPI entry point."""

from __future__ import annotations

import asyncio
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.pipeline.datasets import DATASET_PRESETS
from app.pipeline.experiment import store
from app.pipeline.results_loader import (
    list_audit_datasets,
    load_benchmark_overview,
    load_dataset_results,
)
from app.schemas import ExperimentRequest, LoadRequest, PreprocessRequest

app = FastAPI(
    title="SYNTH Data Audit",
    description="Synthetic data fidelity, privacy, and utility evaluation (FORGE experimental setup)",
    version="1.0.0",
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Long-running ML jobs run off the event loop so the UI stays responsive.
_experiment_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="synth-exp")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html")


@app.get("/dashboard")
async def dashboard():
    return FileResponse(STATIC_DIR / "dashboard.html", media_type="text/html")


@app.get("/api/results/datasets")
async def audit_datasets(task_type: str | None = None):
    """List pre-computed TRTR/TSTR result datasets from audit Excel exports."""
    return list_audit_datasets(task_type=task_type)


@app.get("/api/results/datasets/{dataset_id}")
async def audit_dataset_results(dataset_id: str):
    try:
        return load_dataset_results(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/results/overview")
async def audit_benchmark_overview():
    """Cross-dataset summary for publication heatmaps and generator rankings."""
    return load_benchmark_overview()


@app.post("/api/session")
async def create_session():
    sid = store.create()
    return {"session_id": sid}


@app.post("/api/load")
async def load_dataset_endpoint(req: LoadRequest):
    if not req.preset_id and not req.uci_id:
        raise HTTPException(status_code=400, detail="Provide a UCI ID or dataset preset")
    sid = store.create()
    try:
        result = store.load_dataset(
            sid,
            uci_id=req.uci_id,
            preset_id=req.preset_id,
        )
        return result
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/preprocess")
async def preprocess(req: PreprocessRequest):
    if not store.get(req.session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        return store.preprocess(
            req.session_id,
            target_col=req.target_col,
            n_subsample=req.n_subsample,
            test_size=req.test_size,
            seed=req.seed,
            drop_columns=req.drop_columns or None,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _run_experiment_task(req: ExperimentRequest):
    try:
        store.run_experiment(
            req.session_id,
            n_synthetic=req.n_synthetic,
            seed=req.seed,
            run_fidelity=req.run_fidelity,
            run_privacy=req.run_privacy,
            run_utility=req.run_utility,
            generators=req.generators,
            fast_mode=req.fast_mode,
        )
    except Exception as exc:  # noqa: BLE001
        session = store.get(req.session_id)
        if session:
            session["status"] = "failed"
            session["error"] = str(exc)
            session["progress"].append(f"Error: {exc}")
            session["progress"].append(traceback.format_exc())


@app.post("/api/experiment")
async def start_experiment(req: ExperimentRequest):
    if not store.get(req.session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    session = store.get(req.session_id)
    if session["preprocessed"] is None:
        raise HTTPException(status_code=400, detail="Preprocess the dataset first")

    session["status"] = "queued"
    loop = asyncio.get_running_loop()
    loop.run_in_executor(_experiment_executor, _run_experiment_task, req)
    return {"session_id": req.session_id, "status": "queued"}


@app.get("/api/experiment/{session_id}/status")
async def experiment_status(session_id: str):
    if not store.get(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return store.status(session_id)


@app.get("/api/experiment/{session_id}/results")
async def experiment_results(session_id: str):
    if not store.get(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    results = store.results(session_id)
    if results is None:
        raise HTTPException(status_code=404, detail="Results not ready yet")
    return results


@app.get("/api/datasets/presets")
async def dataset_presets(task_type: str | None = None):
    """Known datasets from the experimental setup, optionally filtered by task type."""
    presets = DATASET_PRESETS
    if task_type in ("classification", "regression"):
        presets = [p for p in presets if p["task_type"] == task_type]
    return presets
