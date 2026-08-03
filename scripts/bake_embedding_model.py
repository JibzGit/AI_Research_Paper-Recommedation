"""Bakes the pinned BAAI/bge-base-en-v1.5 revision into a local directory at
Docker build time, so the Cloud Run container never downloads the model at
request time -- no network dependency, no first-request latency spike, no
risk of a mid-request Hugging Face Hub outage. Writes a small, non-secret
JSON manifest alongside the saved model recording exactly what was baked.

Deliberately does NOT import research_platform.config -- that module reads
DATABASE_URL eagerly at import time (os.environ["DATABASE_URL"]), which has
no reason to exist in a Docker build environment. MODEL_NAME/MODEL_REVISION
below are literal constants that MUST be kept in sync with config.py's
EMBEDDING_MODEL_NAME / EMBEDDING_MODEL_REVISION defaults -- a comment in
config.py points back here, and this file points back at config.py.

Usage:
    python3 scripts/bake_embedding_model.py [--output-dir PATH]

Requires network access (a real Hugging Face Hub download) and
sentence-transformers to already be installed -- run this after installing
requirements-prod.txt + torch, not before.
"""
import argparse
import json
import sys
from datetime import datetime, timezone

# Must match research_platform.config.EMBEDDING_MODEL_NAME /
# EMBEDDING_MODEL_REVISION / EMBEDDING_DIMENSION exactly. MODEL_REVISION is
# the exact immutable Hugging Face commit sha for BAAI/bge-base-en-v1.5 --
# see config.py for how/when it was resolved and cross-checked. Never a
# mutable ref like "main".
MODEL_NAME = "BAAI/bge-base-en-v1.5"
MODEL_REVISION = "a5beb1e3e68b9ab74eb54cfd186867f64f240e1a"
EXPECTED_EMBEDDING_DIMENSION = 768

DEFAULT_OUTPUT_DIR = "/opt/models/bge-base-en-v1.5"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to save the baked model into (default: {DEFAULT_OUTPUT_DIR})",
    )
    args = parser.parse_args()

    from sentence_transformers import SentenceTransformer

    print(f"Downloading {MODEL_NAME}@{MODEL_REVISION} ...", flush=True)
    model = SentenceTransformer(MODEL_NAME, revision=MODEL_REVISION, device="cpu")

    actual_dimension = model.get_sentence_embedding_dimension()
    if actual_dimension != EXPECTED_EMBEDDING_DIMENSION:
        print(
            f"FATAL: downloaded model reports embedding dimension {actual_dimension}, "
            f"expected {EXPECTED_EMBEDDING_DIMENSION} -- refusing to bake a mismatched model "
            "(paper_embeddings.embedding is a fixed VECTOR(768) column).",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Saving to {args.output_dir} ...", flush=True)
    model.save(args.output_dir)

    manifest = {
        "model_name": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "embedding_dimension": actual_dimension,
        "baked_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = f"{args.output_dir}/BAKE_MANIFEST.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"Baked model manifest written to {manifest_path}")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
