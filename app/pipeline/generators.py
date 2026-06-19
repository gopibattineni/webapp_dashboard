"""Synthetic data generators — exact experimental setup from cancer.py / notebooks."""

from __future__ import annotations

import random
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sdv.metadata import SingleTableMetadata
from sdv.single_table import (
    CTGANSynthesizer,
    CopulaGANSynthesizer,
    GaussianCopulaSynthesizer,
    TVAESynthesizer,
)

from app.pipeline.ctabgan_helpers import (
    align_to_train_schema,
    encode_online_shopping_ctabgan,
    get_ctabgan_config,
    prepare_ctabgan_train_df,
    sanitize_ctabgan_sample,
)
from app.pipeline.preprocessor import sanitize_synthetic_target

WEBAPP_ROOT = Path(__file__).resolve().parents[2]
CTAB_REPO = WEBAPP_ROOT / "data" / "CTAB-GAN-Plus"

# Exact order from forest_cover.ipynb / cancer.ipynb utility evaluation
GENERATOR_ORDER = [
    "CTGAN",
    "CopulaGAN",
    "TVAE",
    "GaussianCopula",
    "WGAN_GP",
    "CTABGAN",
]

SDV_MODEL_CLASSES = {
    "CTGAN": CTGANSynthesizer,
    "CopulaGAN": CopulaGANSynthesizer,
    "TVAE": TVAESynthesizer,
    "GaussianCopula": GaussianCopulaSynthesizer,
}


def _ensure_ctabgan():
    if not CTAB_REPO.is_dir():
        CTAB_REPO.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "https://github.com/Team-TUD/CTAB-GAN-Plus"],
            cwd=CTAB_REPO.parent,
            check=True,
        )
    if str(CTAB_REPO) not in sys.path:
        sys.path.insert(0, str(CTAB_REPO))


def set_seeds(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def build_metadata(train_real: pd.DataFrame) -> SingleTableMetadata:
    meta = SingleTableMetadata()
    meta.detect_from_dataframe(train_real)
    return meta


def generate_ctabgan(
    train_real: pd.DataFrame,
    target_col: str,
    n_samples: int,
    work_dir: Path,
    task_type: str = "classification",
    preset_id: str | None = None,
    train_real_ctab: pd.DataFrame | None = None,
    seed: int = 42,
    fast_mode: bool = False,
) -> pd.DataFrame:
    _ensure_ctabgan()
    from model.ctabgan import CTABGAN  # noqa: WPS433

    work_dir.mkdir(parents=True, exist_ok=True)
    csv_path = work_dir / "train.csv"

    config = get_ctabgan_config(preset_id, target_col)
    is_regression = task_type == "regression" and config is not None and train_real_ctab is not None

    if is_regression:
        ctab_train = prepare_ctabgan_train_df(
            train_real_ctab,
            config["categorical_columns"],
            config["numeric_columns"],
            target_col,
        )
        ctab_train.to_csv(csv_path, index=False)
        ctabgan = CTABGAN(
            raw_csv_path=str(csv_path),
            test_ratio=0.01,
            categorical_columns=config["categorical_columns"],
            log_columns=[],
            mixed_columns=config["mixed_columns"],
            general_columns=config["general_columns"],
            integer_columns=config["integer_columns"],
            problem_type=config["problem_type"],
        )
        ctabgan.synthesizer.epochs = 5 if fast_mode else 150
        ctabgan.fit()
        raw_sample = ctabgan.synthesizer.sample(n_samples)
        if preset_id == "online_shopping":
            raw_sample = sanitize_ctabgan_sample(
                raw_sample,
                ctabgan.data_prep,
                ctab_train,
                config["numeric_columns"],
                seed=seed,
            )
        synthetic_raw = ctabgan.data_prep.inverse_prep(raw_sample)
        if preset_id == "online_shopping":
            return encode_online_shopping_ctabgan(
                synthetic_raw,
                train_real,
                train_real_ctab,
                target_col,
                seed=seed,
            )
        return align_to_train_schema(synthetic_raw, train_real, target_col)

    train_real.to_csv(csv_path, index=False)
    ctabgan = CTABGAN(
        raw_csv_path=str(csv_path),
        categorical_columns=[target_col],
        log_columns=[],
        mixed_columns={},
        integer_columns=[],
        problem_type={"Classification": target_col},
    )
    ctabgan.synthesizer.epochs = 5 if fast_mode else 150
    ctabgan.fit()
    return ctabgan.data_prep.inverse_prep(ctabgan.synthesizer.sample(n_samples))


def generate_wgan_gp(
    train_real: pd.DataFrame,
    target_col: str,
    n_samples: int,
    seed: int,
    fast_mode: bool = False,
) -> pd.DataFrame:
    set_seeds(seed)
    data_wgan = train_real.copy()

    encoder = LabelEncoder()
    data_wgan[target_col] = encoder.fit_transform(data_wgan[target_col].astype(str))

    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(data_wgan)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    real_tensor = torch.tensor(scaled_data, dtype=torch.float32)

    batch_size = 64
    latent_dim = 64
    data_dim = real_tensor.shape[1]
    n_epochs = 20 if fast_mode else 100
    n_critic = 5

    loader = torch.utils.data.DataLoader(
        real_tensor, batch_size=batch_size, shuffle=True, drop_last=False
    )

    class Generator(nn.Module):
        def __init__(self):
            super().__init__()
            self.model = nn.Sequential(
                nn.Linear(latent_dim, 128),
                nn.LayerNorm(128),
                nn.LeakyReLU(0.2),
                nn.Linear(128, 256),
                nn.LayerNorm(256),
                nn.LeakyReLU(0.2),
                nn.Linear(256, data_dim),
            )

        def forward(self, z):
            return self.model(z)

    class Critic(nn.Module):
        def __init__(self):
            super().__init__()
            self.model = nn.Sequential(
                nn.Linear(data_dim, 256),
                nn.LeakyReLU(0.2),
                nn.Linear(256, 128),
                nn.LeakyReLU(0.2),
                nn.Linear(128, 1),
            )

        def forward(self, x):
            return self.model(x)

    def gradient_penalty(critic, real_samples, fake_samples):
        alpha = torch.rand(real_samples.size(0), 1, device=device).expand_as(real_samples)
        interpolates = (alpha * real_samples + (1 - alpha) * fake_samples).requires_grad_(True)
        critic_interpolates = critic(interpolates)
        gradients = torch.autograd.grad(
            outputs=critic_interpolates,
            inputs=interpolates,
            grad_outputs=torch.ones_like(critic_interpolates),
            create_graph=True,
            retain_graph=True,
        )[0]
        gradients = gradients.view(gradients.size(0), -1)
        return ((gradients.norm(2, dim=1) - 1) ** 2).mean()

    generator = Generator().to(device)
    critic = Critic().to(device)
    optimizer_g = optim.Adam(generator.parameters(), lr=0.0001, betas=(0.5, 0.9))
    optimizer_c = optim.Adam(critic.parameters(), lr=0.0001, betas=(0.5, 0.9))

    for _ in range(n_epochs):
        for real_batch in loader:
            real_batch = real_batch.to(device)
            for _ in range(n_critic):
                z = torch.randn(real_batch.size(0), latent_dim, device=device)
                fake_batch = generator(z).detach()
                critic_real = critic(real_batch).mean()
                critic_fake = critic(fake_batch).mean()
                gp = gradient_penalty(critic, real_batch, fake_batch)
                critic_loss = critic_fake - critic_real + 10 * gp
                optimizer_c.zero_grad()
                critic_loss.backward()
                optimizer_c.step()

            z = torch.randn(real_batch.size(0), latent_dim, device=device)
            generator_loss = -critic(generator(z)).mean()
            optimizer_g.zero_grad()
            generator_loss.backward()
            optimizer_g.step()

    generator.eval()
    with torch.no_grad():
        z = torch.randn(n_samples, latent_dim, device=device)
        synthetic_scaled = generator(z).cpu().numpy()

    synthetic = scaler.inverse_transform(synthetic_scaled)
    synthetic_df = pd.DataFrame(synthetic, columns=data_wgan.columns)

    n_classes = len(encoder.classes_)
    synthetic_df[target_col] = (
        synthetic_df[target_col].round().clip(0, n_classes - 1).astype(int)
    )
    synthetic_df[target_col] = encoder.inverse_transform(synthetic_df[target_col])

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return synthetic_df


def generate_sdv_model(
    name: str,
    train_real: pd.DataFrame,
    metadata: SingleTableMetadata,
    n_samples: int,
) -> pd.DataFrame:
    model_cls = SDV_MODEL_CLASSES[name]
    model = model_cls(metadata=metadata)
    model.fit(train_real)
    return model.sample(n_samples)


def run_all_generators(
    train_real: pd.DataFrame,
    target_col: str,
    n_samples: int,
    seed: int,
    work_dir: Path,
    generators: list[str] | None = None,
    fast_mode: bool = False,
    on_progress: Callable[[str], None] | None = None,
    task_type: str = "classification",
    preset_id: str | None = None,
    train_real_ctab: pd.DataFrame | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, str], SingleTableMetadata]:
    """Run all six generators independently so one failure does not block others."""
    set_seeds(seed)
    metadata = build_metadata(train_real)
    selected = generators or GENERATOR_ORDER

    if fast_mode:
        selected = ["GaussianCopula"]

    synthetic: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}

    def _progress(msg: str):
        if on_progress:
            on_progress(msg)

    for gen_name in GENERATOR_ORDER:
        if gen_name not in selected:
            continue

        _progress(f"Training generator: {gen_name}...")

        try:
            if gen_name == "CTABGAN":
                synthetic[gen_name] = generate_ctabgan(
                    train_real,
                    target_col,
                    n_samples,
                    work_dir / "ctabgan",
                    task_type=task_type,
                    preset_id=preset_id,
                    train_real_ctab=train_real_ctab,
                    seed=seed,
                    fast_mode=fast_mode,
                )
            elif gen_name == "WGAN_GP":
                synthetic[gen_name] = generate_wgan_gp(
                    train_real, target_col, n_samples, seed, fast_mode=fast_mode
                )
            elif gen_name in SDV_MODEL_CLASSES:
                synthetic[gen_name] = generate_sdv_model(
                    gen_name, train_real, metadata, n_samples
                )
            else:
                errors[gen_name] = f"Unknown generator: {gen_name}"
                continue

            synthetic[gen_name] = sanitize_synthetic_target(
                synthetic[gen_name], train_real, target_col
            )
            _progress(f"Completed {gen_name} ({len(synthetic[gen_name])} synthetic rows)")
        except Exception as exc:  # noqa: BLE001
            errors[gen_name] = str(exc)
            _progress(f"{gen_name} failed: {exc}")

    # Return in fixed notebook order
    ordered = {k: synthetic[k] for k in GENERATOR_ORDER if k in synthetic}
    return ordered, errors, metadata
