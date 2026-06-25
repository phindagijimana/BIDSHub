"""
Build a tiny synthetic BIDS dataset under ``assets/sample_bids/``.

This is what powers the "Try with sample data" button on the home page —
it lets a researcher who just cloned the repo see a real dataset wired
through Browse Subjects, QC, and the viewer without configuring any
remote credentials.

The dataset is intentionally minimal:
  * 2 subjects (sub-01, sub-02)
  * 1-2 sessions per subject (ses-01, ses-02)
  * Each session has one anat T1w; sub-01/ses-01 also has a func bold
  * All NIfTI volumes are 4x4x4 (or 4x4x4x5 for bold) — valid NIfTI-1,
    a few hundred bytes each gzipped

Re-run after editing this script and commit the result:

    python scripts/build_sample_bids.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import nibabel as nib
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "assets" / "sample_bids"

# Deterministic noise so re-running produces a clean diff (or none)
RNG = np.random.default_rng(seed=42)


def _phantom(shape: tuple[int, ...]) -> np.ndarray:
    """A simple brain-like phantom so the viewer shows an actual image.

    An ellipsoidal "head" with a brighter interior (white-matter-like), a
    darker central "ventricle", and mild texture — recognisable in the NIfTI
    viewer rather than the random static a noise volume produces.
    """
    if len(shape) == 4:
        vol = _phantom(shape[:3])
        # repeat across time with slight per-frame variation (resting bold)
        frames = [np.clip(vol + RNG.normal(0, 30, size=vol.shape), 0, 4095)
                  for _ in range(shape[3])]
        return np.stack(frames, axis=-1).astype(np.int16)

    nx, ny, nz = shape
    ax0, ax1, ax2 = np.mgrid[0:nx, 0:ny, 0:nz].astype(float)
    cx, cy, cz = (nx - 1) / 2, (ny - 1) / 2, (nz - 1) / 2
    r = (((ax0 - cx) / (nx * 0.42)) ** 2
         + ((ax1 - cy) / (ny * 0.46)) ** 2
         + ((ax2 - cz) / (nz * 0.46)) ** 2)
    data = np.zeros(shape, dtype=float)
    head = r <= 1.0
    data[head] = 1700                      # gray-matter shell
    data[r <= 0.6] = 2500                  # brighter interior (white matter)
    vent = (((ax0 - cx) / (nx * 0.13)) ** 2
            + ((ax1 - cy) / (ny * 0.2)) ** 2
            + ((ax2 - cz) / (nz * 0.2)) ** 2) <= 1.0
    data[vent] = 500                       # dark central ventricle
    data[head] += RNG.normal(0, 70, size=data.shape)[head]
    data[~head] = 0
    return np.clip(data, 0, 4095).astype(np.int16)


# A real, CC0-licensed T1w from OpenNeuro ds000003 — so "Try with sample data"
# shows an actual brain in the viewer rather than synthetic data.
REAL_T1_URL = "https://s3.amazonaws.com/openneuro.org/ds000003/sub-01/anat/sub-01_T1w.nii.gz"
_REAL_BRAIN = None
_REAL_TRIED = False


def _downsample(vol: np.ndarray, max_dim: int) -> np.ndarray:
    f = max(1, max(vol.shape[:3]) // max_dim)
    return vol[::f, ::f, ::f]


def _get_real_brain():
    """Fetch + downsample the real OpenNeuro T1w once; None if offline."""
    global _REAL_BRAIN, _REAL_TRIED
    if _REAL_TRIED:
        return _REAL_BRAIN
    _REAL_TRIED = True
    try:
        import os, tempfile, requests
        print(f"Fetching real CC0 T1w from OpenNeuro: {REAL_T1_URL}")
        resp = requests.get(REAL_T1_URL, timeout=120)
        resp.raise_for_status()
        # Write to a .nii.gz temp file so nibabel handles the gzip transparently.
        tf = tempfile.NamedTemporaryFile(suffix=".nii.gz", delete=False)
        tf.write(resp.content)
        tf.close()
        img = nib.load(tf.name)
        d = np.asarray(img.dataobj, dtype=np.float32)
        os.unlink(tf.name)
        d = _downsample(d, 96)
        d = d - d.min()
        if d.max() > 0:
            d = d / d.max() * 4000.0
        _REAL_BRAIN = d.astype(np.int16)
        print(f"  real brain {_REAL_BRAIN.shape} downsampled OK")
    except Exception as exc:
        print(f"  real-brain fetch failed ({exc}); using synthetic phantom")
        _REAL_BRAIN = None
    return _REAL_BRAIN


def _write_nii(path: Path, shape: tuple[int, ...]) -> None:
    """Write a valid NIfTI-1 .nii.gz at ``path`` (real brain if available)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    real = _get_real_brain()
    if len(shape) == 4:  # func/bold: a small 4D series from the real brain
        if real is not None:
            vol = _downsample(real, 48)
            frames = [np.clip(vol + RNG.normal(0, 30, vol.shape), 0, 4095)
                      for _ in range(shape[3])]
            data = np.stack(frames, axis=-1).astype(np.int16)
        else:
            data = _phantom(shape)
    else:  # anat: the real downsampled T1w (phantom only if offline)
        data = real if real is not None else _phantom(shape)
    affine = np.eye(4)
    img = nib.Nifti1Image(data, affine)
    if data.ndim == 4:
        img.header.set_zooms((1.0, 1.0, 1.0, 2.0))
    nib.save(img, str(path))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def build() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    # ----- top-level BIDS metadata -----
    _write_json(
        OUT_DIR / "dataset_description.json",
        {
            "Name": "BIDSHub Sample Dataset",
            "BIDSVersion": "1.6.0",
            "DatasetType": "raw",
            "Authors": ["BIDSHub demo"],
            "License": "CC0",
        },
    )

    (OUT_DIR / "README").write_text(
        "BIDSHub sample dataset.\n\n"
        "Two subjects. Anatomical volumes are a downsampled, CC0-licensed real\n"
        "T1w from OpenNeuro ds000003 (so the viewer shows an actual brain);\n"
        "metadata is illustrative. Generated by scripts/build_sample_bids.py.\n"
        "Safe to delete; the 'Try with sample data' button in BIDSHub points here.\n"
    )

    participants_tsv = (
        "participant_id\tage\tsex\tdiagnosis\tsite\n"
        "sub-01\t28\tM\tcontrol\tdemo-site-A\n"
        "sub-02\t34\tF\tTBI\tdemo-site-B\n"
    )
    (OUT_DIR / "participants.tsv").write_text(participants_tsv)

    _write_json(
        OUT_DIR / "participants.json",
        {
            "age": {"Description": "Age at scan (years)", "Units": "year"},
            "sex": {
                "Description": "Biological sex",
                "Levels": {"M": "male", "F": "female"},
            },
            "diagnosis": {
                "Description": "Primary diagnosis",
                "Levels": {"control": "healthy control", "TBI": "traumatic brain injury"},
            },
            "site": {"Description": "Acquisition site"},
        },
    )

    # ----- subjects -----
    # sub-01: two sessions, anat in both, func only in ses-01
    # Viewable resolution (48^3 anat, 32^3 bold) so the phantom is recognisable
    # in the NIfTI viewer; still only a few hundred KB gzipped.
    plan = {
        "sub-01": {
            "ses-01": [("anat", "T1w", (48, 48, 48)),
                       ("func", "task-rest_bold", (32, 32, 32, 5))],
            "ses-02": [("anat", "T1w", (48, 48, 48))],
        },
        "sub-02": {
            "ses-01": [("anat", "T1w", (48, 48, 48))],
        },
    }

    for sub, sessions in plan.items():
        for ses, scans in sessions.items():
            for modality, suffix, shape in scans:
                stem = f"{sub}_{ses}_{suffix}"
                base = OUT_DIR / sub / ses / modality / stem
                _write_nii(base.with_suffix(".nii.gz"), shape)

                sidecar = {
                    "EchoTime": 0.0025,
                    "RepetitionTime": 2.0 if "bold" in suffix else 2.3,
                    "Manufacturer": "Synthetic",
                    "MagneticFieldStrength": 3,
                }
                if "bold" in suffix:
                    sidecar["TaskName"] = "rest"
                _write_json(base.with_suffix(".json"), sidecar)

    # Count what we wrote so the build output is verifiable at a glance
    nii_count = sum(1 for _ in OUT_DIR.rglob("*.nii.gz"))
    json_count = sum(1 for _ in OUT_DIR.rglob("*.json"))
    print(f"wrote {nii_count} .nii.gz, {json_count} .json under {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    build()
