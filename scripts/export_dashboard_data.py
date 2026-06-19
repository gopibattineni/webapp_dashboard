"""Export TRTR/TSTR Excel results to JSON for static GitHub Pages hosting."""

from __future__ import annotations

import json
import sys
from pathlib import Path

WEBAPP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WEBAPP_ROOT))

from app.pipeline.results_loader import (  # noqa: E402
    list_audit_datasets,
    load_benchmark_overview,
    load_dataset_results,
)

DEFAULT_OUT = WEBAPP_ROOT / "app" / "static" / "data" / "audit"


def export_all(out_dir: Path | None = None) -> Path:
    out = out_dir or DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    ds_out = out / "datasets"
    ds_out.mkdir(parents=True, exist_ok=True)

    datasets = list_audit_datasets()
    (out / "datasets.json").write_text(
        json.dumps(datasets, indent=2), encoding="utf-8"
    )

    overview = load_benchmark_overview()
    (out / "overview.json").write_text(
        json.dumps(overview, indent=2), encoding="utf-8"
    )

    exported = 0
    for meta in datasets:
        if not meta.get("available"):
            print(f"skip (missing file): {meta['id']}")
            continue
        payload = load_dataset_results(meta["id"])
        (ds_out / f"{meta['id']}.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        exported += 1

    print(f"Exported {exported} datasets + overview to {out}")
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    export_all(target)
