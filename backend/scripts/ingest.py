"""Build or refresh the knowledge base.

    python -m scripts.ingest                  # every source
    python -m scripts.ingest --only custom    # just your files in knowledge/custom
    python -m scripts.ingest --refresh        # download the public sources again
"""

import argparse
import asyncio
import logging

from app.rag import sources
from app.rag.ingest import ingest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", choices=list(sources.ALL), help="ingest just these sources")
    ap.add_argument("--refresh", action="store_true", help="ignore cached downloads")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    for name, n in asyncio.run(ingest(args.only, args.refresh)).items():
        print(f"{name}: {n} chunks indexed")


if __name__ == "__main__":
    main()
