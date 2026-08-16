from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

DEST_DIR = Path(__file__).resolve().parent.parent / "openmanus" / "skills" / "python"

RELEASES_API = "https://api.github.com/repos/astral-sh/python-build-standalone/releases"
DOWNLOAD_HOST = "https://github.com/astral-sh/python-build-standalone/releases/download"

VARIANT = "install_only"

def detect_target_triple() -> str:
    plat = sys.platform
    machine = (os.environ.get("PROCESSOR_ARCHITECTURE") or "").lower()
    if plat == "win32":
        return "x86_64-pc-windows-msvc"
    if plat == "darwin":
        if sys.maxsize > 2**32 and os.uname().machine == "arm64":
            return "aarch64-apple-darwin"
        return "x86_64-apple-darwin"
    if sys.maxsize > 2**32:
        return "x86_64-unknown-linux-gnu"
    return "i686-unknown-linux-gnu"

def fetch_latest_release_tag(minor: str) -> str:
    req = urllib.request.Request(
        f"{RELEASES_API}/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "openmanus-bootstrap"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    tag = data.get("tag_name")
    if not tag:
        raise RuntimeError(f"could not determine latest release tag from {RELEASES_API}/latest")
    return tag

def resolve_asset_name(tag: str, minor: str, target: str) -> tuple[str, str]:
    req = urllib.request.Request(
        f"{RELEASES_API}/tags/{tag}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "openmanus-bootstrap"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    assets = [a["name"] for a in data.get("assets", [])]
    suffix = f"-{target}-{VARIANT}.tar.gz"
    prefix = f"cpython-3.{minor}."
    candidates = [n for n in assets if n.startswith(prefix) and n.endswith(suffix)]
    if not candidates:
        raise RuntimeError(
            f"no asset matches cpython-3.{minor}.* + {target} + {VARIANT} in tag {tag}.\n"
            f"available (first 10): {assets[:10]}"
        )
    candidates.sort(reverse=True)
    name = candidates[0]
    url = f"{DOWNLOAD_HOST}/{tag}/{name}"
    return name, url

def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as resp:
        total = int(resp.headers.get("Content-Length", "0"))
        done = 0
        last_pct = -1
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total:
                    pct = int(done * 100 / total)
                    if pct != last_pct and pct % 10 == 0:
                        print(f"  … {pct}% ({done // (1024 * 1024)} MiB)")
                        last_pct = pct
    print(f"  downloaded {dest.name} ({done // (1024 * 1024)} MiB)")

def extract_and_install(archive: Path, target_dir: Path) -> None:
    if target_dir.exists():
        shutil.rmtree(target_dir)
    staging = target_dir.parent / ".staging_python"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    print(f"  extracting {archive.name} …")
    with tarfile.open(archive, "r:gz") as tar:
        try:
            tar.extractall(staging, filter="data")
        except TypeError:
            tar.extractall(staging)
    extracted = staging / "python"
    if not extracted.is_dir():
        dirs = [p for p in staging.iterdir() if p.is_dir()]
        if len(dirs) == 1:
            extracted = dirs[0]
        else:
            raise RuntimeError(
                f"expected a single 'python/' top dir in archive, found: "
                f"{[p.name for p in staging.iterdir()]}"
            )
    shutil.move(str(extracted), str(target_dir))
    shutil.rmtree(staging, ignore_errors=True)

def ensure_python3_alias(install_dir: Path) -> None:
    if sys.platform == "win32":
        py = install_dir / "python.exe"
        py3 = install_dir / "python3.exe"
        if py.is_file() and not py3.is_file():
            shutil.copy2(py, py3)
            print(f"  created alias {py3.name} -> {py.name}")
    else:
        py = install_dir / "bin" / "python3"
        if not py.is_file():
            base = install_dir / "bin" / "python"
            if base.is_file():
                try:
                    py.symlink_to(base.name)
                    print(f"  created symlink {py.name} -> {base.name}")
                except OSError:
                    shutil.copy2(base, py)
                    print(f"  created copy {py.name}")

def already_installed() -> bool:
    if sys.platform == "win32":
        return (DEST_DIR / "python.exe").is_file()
    return (DEST_DIR / "bin" / "python3").is_file()

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--version", default="12", help="CPython minor (e.g. '12' for 3.12)")
    ap.add_argument("--platform", default=None, help="target triple (default: auto-detect)")
    ap.add_argument("--tag", default=None, help="release tag (default: latest)")
    ap.add_argument("--force", action="store_true", help="re-download even if present")
    args = ap.parse_args()

    target = args.platform or detect_target_triple()
    print(f"[bootstrap_python] target = {target}, cpython minor = 3.{args.version}")

    if already_installed() and not args.force:
        print(f"[bootstrap_python] already present at {DEST_DIR} (pass --force to reinstall)")
        return 0

    tag = args.tag or fetch_latest_release_tag(args.version)
    print(f"[bootstrap_python] release tag = {tag}")
    asset, url = resolve_asset_name(tag, args.version, target)
    print(f"[bootstrap_python] asset = {asset}")

    cache = DEST_DIR.parent / ".downloads" / asset
    if cache.is_file() and not args.force:
        print(f"[bootstrap_python] using cached archive {cache}")
    else:
        print(f"[bootstrap_python] downloading {url}")
        download(url, cache)

    print(f"[bootstrap_python] installing into {DEST_DIR}")
    extract_and_install(cache, DEST_DIR)
    ensure_python3_alias(DEST_DIR)

    smoke = (
        DEST_DIR / "python.exe" if sys.platform == "win32" else DEST_DIR / "bin" / "python3"
    )
    print(f"[bootstrap_python] verifying {smoke} …")
    import subprocess

    res = subprocess.run(
        [str(smoke), "-c", "import sys; print(sys.version); print(sys.executable)"],
        capture_output=True, text=True, timeout=30,
    )
    if res.returncode != 0:
        print(f"[bootstrap_python] SMOKE TEST FAILED:\n{res.stderr}", file=sys.stderr)
        return 1
    print(f"[bootstrap_python] ok: {res.stdout.strip().splitlines()[0]}")
    print(f"[bootstrap_python] done → {DEST_DIR}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
