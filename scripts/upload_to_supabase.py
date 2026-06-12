"""Upload combined_data.csv to Supabase Storage as gzip.

Usage (from project root):
    python scripts/upload_to_supabase.py

Requires .env with SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.
"""

from __future__ import annotations

import gzip
import io
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "output" / "combined_data.csv"
BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "sales-data")
OBJECT_NAME = os.getenv("SUPABASE_DATA_FILE", "combined_data.csv.gz")


def gzip_bytes(csv_path: Path) -> bytes:
    buf = io.BytesIO()
    with open(csv_path, "rb") as src, gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        while chunk := src.read(8 * 1024 * 1024):
            gz.write(chunk)
    return buf.getvalue()


def main() -> int:
    load_dotenv(ROOT / ".env")

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env", file=sys.stderr)
        return 1

    csv_path = Path(os.getenv("LOCAL_CSV_PATH", DEFAULT_CSV))
    if not csv_path.is_file():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 1

    print(f"Compressing {csv_path.name}…")
    payload = gzip_bytes(csv_path)
    print(f"Uploading {len(payload) / 1024 / 1024:.1f} MB to {BUCKET}/{OBJECT_NAME}…")

    from supabase import create_client

    client = create_client(url, key)
    client.storage.from_(BUCKET).upload(
        OBJECT_NAME,
        payload,
        file_options={
            "content-type": "application/gzip",
            "upsert": "true",
            "cache-control": "3600",
        },
    )

    public_url = client.storage.from_(BUCKET).get_public_url(OBJECT_NAME)
    print("Upload complete.")
    print(f"Public URL: {public_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
