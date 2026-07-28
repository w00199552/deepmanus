"""Generate 50 DiceBear "adventurer" avatar presets offline into backend/seed/avatars/.

This is a DEVELOPMENT-TIME tool, run once by a maintainer who has network
access to api.dicebear.com. The generated SVGs are bundled with the app
(via backend/seed/avatars/) and served at runtime from /avatar-presets,
so end users never need to reach dicebear.

Idempotent: re-running overwrites the files with identical content (the
seed->face mapping is deterministic on dicebear's side).

Usage:
    cd backend
    uv run python scripts/gen_avatar_presets.py            # default count=50
    uv run python scripts/gen_avatar_presets.py --count 80  # custom count
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

# Resolve backend/seed/avatars/ relative to this file (script lives in
# backend/scripts/, so ../../seed/avatars). Matches the AVATARS_SEED_DIR
# constant in src/openmanus/agent_loader.py.
SEED_AVATARS_DIR = (
    Path(__file__).resolve().parent.parent / "seed" / "avatars"
)

API = "https://api.dicebear.com/9.x/adventurer/svg"
# Light/tan skin tones only — kept in sync with the old save_avatar skin logic
# and frontend avatar.jsx skinForSeed() so preset faces match the original palette.
SKIN_TONES = ["ffdfba", "f5d0b0"]

SEED_PREFIX = "openmanus-avatar"


def build_url(seed: str, skin: str) -> str:
    """Build the dicebear URL. Params identical to old save_avatar + avatar.jsx."""
    return (
        f"{API}?seed={seed}"
        f"&backgroundColor=transparent&radius=50&skinColor={skin}"
    )


def fetch_svg(client: httpx.Client, seed: str, skin: str) -> str:
    url = build_url(seed, skin)
    resp = client.get(url, timeout=15.0)
    resp.raise_for_status()
    svg = resp.text.strip()
    if not svg.startswith("<svg"):
        raise ValueError(f"unexpected payload for seed={seed}: {svg[:80]!r}")
    return svg


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--count", type=int, default=50,
        help="number of presets to generate (default: 50)",
    )
    args = parser.parse_args()
    count = max(1, args.count)

    SEED_AVATARS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[gen_avatar_presets] target dir: {SEED_AVATARS_DIR}")
    print(f"[gen_avatar_presets] generating {count} presets from {API}")

    presets = []
    # Reuse one client with keep-alive; small retry for transient 5xx.
    with httpx.Client(headers={"Accept": "image/svg+xml"}) as client:
        for i in range(1, count + 1):
            preset_id = f"{i:02d}"
            seed = f"{SEED_PREFIX}-{preset_id}"
            # Alternate skin tones deterministically — mirrors the hash-based
            # pick the old code used, but as a stable per-index alternation
            # so the palette stays balanced across the preset pool.
            skin = SKIN_TONES[i % len(SKIN_TONES)]
            for attempt in range(3):
                try:
                    svg = fetch_svg(client, seed, skin)
                    break
                except Exception as e:  # noqa: BLE001
                    if attempt == 2:
                        raise
                    print(f"  retry {attempt+1}/3 for {preset_id}: {e}")
                    time.sleep(1.0)
            out_path = SEED_AVATARS_DIR / f"{preset_id}.svg"
            out_path.write_text(svg, encoding="utf-8")
            presets.append({
                "id": preset_id,
                "file": f"{preset_id}.svg",
                "seed": seed,
            })
            print(f"  [{i}/{count}] wrote {preset_id}.svg ({len(svg)} bytes)")

    manifest = {
        "style": "dicebear-adventurer-9.x",
        "count": count,
        "params": {
            "backgroundColor": "transparent",
            "radius": 50,
            "skinTones": SKIN_TONES,
        },
        "presets": presets,
    }
    manifest_path = SEED_AVATARS_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[gen_avatar_presets] wrote manifest.json ({count} presets)")
    print("[gen_avatar_presets] done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
