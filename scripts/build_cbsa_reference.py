from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

INP = ROOT / "data" / "geo" / "cbsa_reference" / "list1_2023.xlsx"
OUT = ROOT / "data" / "geo" / "cbsa_reference" / "cbsa_reference.csv"
META = ROOT / "data" / "geo" / "cbsa_reference" / "cbsa_reference.meta.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_meta() -> dict:
    if not META.exists():
        return {}
    try:
        return json.loads(META.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_meta(meta: dict) -> None:
    META.parent.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")


def build() -> None:
    if not INP.exists():
        raise FileNotFoundError(f"Missing input: {INP}")

    inp_hash = sha256_file(INP)
    meta = load_meta()

    if OUT.exists() and meta.get("input_sha256") == inp_hash and meta.get("status") == "ok":
        print(f"OK (up-to-date): {OUT} rows={meta.get('rows')} input_sha256={inp_hash[:12]}...")
        return

    # Census file has title rows; real headers are on row 3 => header=2 (0-indexed)
    df = pd.read_excel(INP, header=2, usecols=["CBSA Code", "CBSA Title"]).dropna()

    # Deduplicate: one CBSA appears multiple times (one per county). We want one row per CBSA code.
    df["CBSA Code"] = df["CBSA Code"].astype(int).astype(str)
    df["CBSA Title"] = df["CBSA Title"].astype(str).str.strip()

    df = df.drop_duplicates(subset=["CBSA Code"]).sort_values("CBSA Code")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)

    new_meta = {
        "status": "ok",
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_path": str(INP),
        "output_path": str(OUT),
        "input_sha256": inp_hash,
        "rows": int(len(df)),
        "columns": ["CBSA Code", "CBSA Title"],
    }
    write_meta(new_meta)

    # Sanity check: file should re-load and have the same row count
    df2 = pd.read_csv(OUT)
    if len(df2) != len(df):
        raise RuntimeError("Post-write validation failed: row count mismatch after CSV write/read")

    print(f"BUILT: {OUT} rows={len(df)} input_sha256={inp_hash[:12]}...")


if __name__ == "__main__":
    build()