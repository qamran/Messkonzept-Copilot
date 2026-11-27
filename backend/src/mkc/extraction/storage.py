"""Where fetched PDFs live (MKC-21, decision 63).

Production and every shared run: Supabase Storage, through `mkc.harness.storage`. A local
run without Storage settings caches blobs in `LOCAL_CACHE_DIR` instead; `.cache/` is
gitignored and kept out of the image's build context, so no PDF reaches the repo or an image.
"""

from pathlib import Path

LOCAL_CACHE_DIR = Path(__file__).resolve().parents[3] / ".cache" / "blobs"
