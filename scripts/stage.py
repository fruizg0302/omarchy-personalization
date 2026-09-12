#!/usr/bin/env python3
"""Render a reviewable home-directory tree; never write to the real home."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def stage(destination, target_home):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Choose a new staging directory; existing paths are not overwritten.")
    target_home = str(Path(target_home))
    if not target_home.startswith("/") or any(c in target_home for c in '\n\r"`$\\%'):
        raise ValueError("Target home must be an absolute path without desktop-entry escape characters.")
    destination.mkdir(parents=True)
    shutil.copytree(ROOT / "config", destination / ".config")
    shutil.copytree(ROOT / "plugins", destination / ".config/omarchy/plugins")
    shutil.copytree(ROOT / "bin", destination / ".local/bin")
    applications = destination / ".local/share/applications"
    applications.mkdir(parents=True)
    for source in sorted((ROOT / "applications").glob("*.desktop.in")):
        text = source.read_text().replace("@HOME@", target_home)
        (applications / source.name.removesuffix(".in")).write_text(text)
    for script in (destination / ".local/bin").iterdir():
        script.chmod(0o755)
    print(f"Staged in {destination}. No active configuration was changed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination")
    parser.add_argument("--home", default=str(Path.home()), help="Home path to embed in launcher icons")
    args = parser.parse_args()
    try:
        stage(args.destination, args.home)
    except ValueError as error:
        parser.error(str(error))
