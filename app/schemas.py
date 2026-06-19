"""Pydantic request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoadRequest(BaseModel):
    uci_id: int | None = Field(None, ge=1, description="UCI ML Repository dataset ID")
    preset_id: str | None = Field(None, description="Known dataset preset (overrides uci_id when set)")


class PreprocessRequest(BaseModel):
    session_id: str
    target_col: str | None = None
    n_subsample: int = Field(1000, ge=100, le=100000)
    test_size: float = Field(0.2, gt=0, lt=0.5)
    seed: int = 42
    drop_columns: list[str] = Field(default_factory=list)


class ExperimentRequest(BaseModel):
    session_id: str
    n_synthetic: int = Field(1000, ge=100, le=50000)
    seed: int = 42
    run_fidelity: bool = True
    run_privacy: bool = True
    run_utility: bool = True
    generators: list[str] | None = None
    fast_mode: bool = Field(
        False,
        description="Quick run: GaussianCopula only, skip CTAB-GAN/WGAN",
    )
