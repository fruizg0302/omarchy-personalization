#!/usr/bin/env python3
"""Apply a reviewed customization to a matching, clean upstream plugin checkout."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATCHES = {"rosakodu.dock": "dock", "piyush.omaswitch": "omaswitch"}


def patch_plugin(plugin_id, checkout):
    checkout = Path(checkout).resolve()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(checkout), *args], text=True).strip()
    locked = next(p for p in json.loads((ROOT / "plugins.lock.json").read_text()) if p["id"] == plugin_id)
    if git("rev-parse", "HEAD") != locked["commit"]:
        raise ValueError("Plugin revision differs from plugins.lock.json; review/rebase the patch first.")
    patch = ROOT / PATCHES[plugin_id] / "customizations.patch"
    # Idempotent only if the tracked patch and any added file are both present.
    reverse = subprocess.run(["git", "-C", str(checkout), "apply", "--reverse", "--check", str(patch)], capture_output=True)
    extra = ROOT / "dock/DockTooltip.qml" if plugin_id == "rosakodu.dock" else None
    if reverse.returncode == 0:
        if extra and (not (checkout / extra.name).exists() or (checkout / extra.name).read_bytes() != extra.read_bytes()):
            raise ValueError("Tracked patch exists, but the tooltip file differs or is missing.")
        print("Patch already applied.")
        return
    if git("status", "--porcelain"):
        raise ValueError("Checkout has local changes; refusing to overwrite them.")
    subprocess.run(["git", "-C", str(checkout), "apply", "--check", str(patch)], check=True)
    subprocess.run(["git", "-C", str(checkout), "apply", str(patch)], check=True)
    if extra:
        shutil.copyfile(extra, checkout / extra.name)
    print(f"Applied {plugin_id} customizations.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin_id", choices=PATCHES)
    parser.add_argument("checkout")
    args = parser.parse_args()
    try:
        patch_plugin(args.plugin_id, args.checkout)
    except ValueError as error:
        parser.error(str(error))
