#!/usr/bin/env python3
"""Refuse silent source drift before builds and validation."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check():
    manifest = json.loads((ROOT / "SOURCE.json").read_text())
    for repo in manifest["repositories"]:
        path = ROOT / repo["path"]
        sha = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
        if sha != repo["commit"]:
            raise SystemExit(f"Source drift: {repo['name']} at {sha}, expected {repo['commit']}")
        dirty = subprocess.check_output(["git", "-C", str(path), "status", "--porcelain", "--untracked-files=no"], text=True)
        if dirty:
            raise SystemExit(f"Tracked author source changes in {repo['path']}:\n{dirty}")
        print(f"Verified {repo['name']}: {sha}")
    return manifest


if __name__ == "__main__":
    check()

