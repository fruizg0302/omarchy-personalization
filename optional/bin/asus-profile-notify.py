#!/usr/bin/env python3
"""Show ASUS profile changes without changing power-management settings."""
from pathlib import Path
import subprocess
import time

PROFILE = Path('/sys/firmware/acpi/platform_profile')
LABELS = {'quiet': 'Quiet (power saver)', 'low-power': 'Quiet (power saver)',
          'balanced': 'Balanced', 'performance': 'Performance'}


def watch():
    previous = candidate = PROFILE.read_text().strip()
    while True:
        time.sleep(0.5)
        current = PROFILE.read_text().strip()
        # Wait for two matching samples to avoid intermediate profile changes.
        if current != candidate:
            candidate = current
            continue
        if not current or current == previous:
            continue
        result = subprocess.run([
            '/usr/bin/notify-send', '--app-name=omarchy-action',
            '--icon=preferences-system-power', '--expire-time=3000',
            'Power profile', LABELS.get(current, current.replace('-', ' ').title()),
        ], timeout=5, check=False)
        if result.returncode == 0:
            print(f'Power profile: {previous} -> {current}', flush=True)
            previous = current


if __name__ == '__main__':
    watch()
