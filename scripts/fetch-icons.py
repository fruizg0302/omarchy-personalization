#!/usr/bin/env python3
"""Download the original public app icons into an explicitly chosen directory."""
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("destination")
args = parser.parse_args()
destination = Path(args.destination)
destination.mkdir(parents=True, exist_ok=True)
sources = json.loads((Path(__file__).resolve().parents[1] / "icons/sources.json").read_text())
failed = False
for name, url in sources.items():
    target = destination / name
    if target.exists():
        print(f"Keeping {name}")
        continue
    try:
        with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20) as response:
            data = response.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise ValueError("Icon exceeds 2 MiB limit")
        if not (data.startswith(b'\x89PNG\r\n\x1a\n') or (name.endswith('.svg') and b'<svg' in data[:4096])):
            raise ValueError("Response is not the expected image format")
        target.write_bytes(data)
        print(f"Downloaded {name}")
    except Exception as error:
        failed = True
        print(f"Could not download {name}: {error}")
raise SystemExit(1 if failed else 0)
