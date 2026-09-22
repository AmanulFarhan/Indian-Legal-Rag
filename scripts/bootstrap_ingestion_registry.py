"""One-time registry bootstrap for the historical Indian legal corpus.

Run manually from the repository root. This script only hashes files and
writes the local ingestion registry; it does not perform Pinecone operations.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag import (  # noqa: E402
    INGESTION_REGISTRY,
    RAW,
    load_ingestion_registry,
    pdf_content_hash,
    save_ingestion_registry,
)


HISTORICAL_DOCUMENTS = {
    "bns.pdf": 114,
    "bnss.pdf": 280,
    "bsa.pdf": 54,
    "constitution.pdf": 400,
    "contract.pdf": 57,
    "cpa.pdf": 41,
    "rta.pdf": 24,
}


def bootstrap_historical_registry(
    raw_directory: Path = RAW,
    registry_path: Path = INGESTION_REGISTRY,
):
    """Register known historical corpus hashes without processing any vectors."""

    paths = {filename: raw_directory / filename for filename in HISTORICAL_DOCUMENTS}
    missing = [filename for filename, path in paths.items() if not path.is_file()]

    if missing:
        raise FileNotFoundError(
            "Bootstrap stopped; missing required historical PDFs: "
            + ", ".join(missing)
        )

    hashes = {filename: pdf_content_hash(path) for filename, path in paths.items()}

    print("Existing historical corpus:")
    for filename in HISTORICAL_DOCUMENTS:
        print(f"{filename:<20} SHA-256: {hashes[filename]}")
    print("No Pinecone operations will be performed.")

    registry = load_ingestion_registry(registry_path)
    documents = registry["documents"]
    source_hashes = {}
    for content_hash, entry in documents.items():
        if isinstance(entry, dict) and entry.get("source"):
            source_hashes.setdefault(entry["source"], set()).add(content_hash)

    conflicts = [
        filename
        for filename, content_hash in hashes.items()
        if filename in source_hashes and content_hash not in source_hashes[filename]
    ]
    if conflicts:
        raise RuntimeError(
            "Bootstrap stopped; existing registry entries use a different hash "
            "for: " + ", ".join(conflicts)
        )

    additions = {
        content_hash: {
            "source": filename,
            "chunk_count": HISTORICAL_DOCUMENTS[filename],
            "historical_bootstrap": True,
        }
        for filename, content_hash in hashes.items()
        if content_hash not in documents
    }

    if not additions:
        print("Registry already contains all historical document hashes; no changes made.")
        return registry

    documents.update(additions)
    save_ingestion_registry(registry, registry_path)
    print(f"Registered {len(additions)} historical document hash(es) in {registry_path}.")
    return registry


if __name__ == "__main__":
    bootstrap_historical_registry()
