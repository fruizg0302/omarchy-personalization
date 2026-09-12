import importlib.util
import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import time

spec = importlib.util.spec_from_file_location('glow', Path(__file__).resolve().parents[1] / 'glow.py')
glow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(glow)
master, slave = pty.openpty()
full = '--full' in sys.argv
shell = subprocess.Popen(['/usr/bin/bash', '--noprofile'] + ([] if full else ['--norc']) + ['-i'], stdin=slave, stdout=slave, stderr=slave,
                         start_new_session=True, env={**os.environ, 'PS1': 'GLOWTEST> '})
os.close(slave)
chunks = []
def read_for(seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        ready, _, _ = select.select([master], [], [], .05)
        if ready:
            try:
                chunks.append(os.read(master, 65536))
            except OSError:
                break
try:
    read_for(2 if full else .2)
    before = glow.request({'command': 'status'})['completion_events']
    commands = ([] if full else ["_capture_status() { printf 'GLOW_RC=%s\\n' \"$?\"; }; PROMPT_COMMAND=(_capture_status)"]) + [
        'source ~/.config/keyboard-glow/shell.bash',
        'source ~/.config/keyboard-glow/shell.bash',
        'KEYBOARD_GLOW_MIN_SECONDS=1',
        'sleep 1.2 && false',
    ]
    for command in commands:
        os.write(master, (command + '\n').encode())
        read_for(1.5 if 'sleep' in command else .2)
    current = glow.request({'command': 'status'})
    transcript = b''.join(chunks).decode(errors='replace')
    assert current['completion_events'] == before + 1, (current, transcript)
    if not full:
        assert 'GLOW_RC=1\r\n' in transcript, transcript
    os.write(master, b"_glow_hook_count=0; for _glow_entry in \"${PROMPT_COMMAND[@]}\"; do [[ $_glow_entry == _keyboard_glow_complete ]] && ((_glow_hook_count+=1)); done; printf 'GLOW_HOOK_COUNT=%s\\n' \"$_glow_hook_count\"\n")
    read_for(.2)
    transcript = b''.join(chunks).decode(errors='replace')
    assert 'GLOW_HOOK_COUNT=1\r\n' in transcript, transcript
    print('PASS:', 'Full user Bash startup' if full else 'Isolated Bash', 'emits one completion alert; repeated sourcing installs only one hook; failure status preserved in isolated Bash.')
finally:
    if shell.poll() is None:
        shell.kill()
    shell.wait(timeout=3)
    os.close(master)
