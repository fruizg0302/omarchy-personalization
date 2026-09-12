#!/usr/bin/env python3
"""Check tracked publication files for common secrets and local identity paths."""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
names = subprocess.check_output(["git", "-C", str(root), "ls-files", "-z"], text=True).split('\0')
patterns = [
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
    r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
    r"\bAKIA[A-Z0-9]{16}\b",
    r"\bsk-[A-Za-z0-9_-]{20,}\b",
    r"https?://[^\s/]+:[^\s/]+@",
    r"/home/[A-Za-z0-9_.-]+/",
]
bad = []
for name in filter(None, names):
    path = root / name
    if path.is_symlink():
        bad.append((name, "symlink"))
        continue
    try:
        text = path.read_text()
    except UnicodeDecodeError:
        bad.append((name, "non-text file"))
        continue
    for pattern in patterns:
        if re.search(pattern, text):
            bad.append((name, "sensitive pattern"))
    if any(part in {'.ssh', '.gnupg', '.aws', '.env', 'credentials'} for part in path.relative_to(root).parts):
        bad.append((name, "sensitive filename"))
for name, reason in bad:
    print(f"Review {name}: {reason}")
if not bad:
    print(f"Checked {len(list(filter(None, names)))} tracked text files; no flagged patterns.")
raise SystemExit(bool(bad))
