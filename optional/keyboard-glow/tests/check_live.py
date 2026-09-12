"""Short, reversible checks against the user's running lighting service."""
import importlib.util
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import time

spec = importlib.util.spec_from_file_location('glow', Path(__file__).resolve().parents[1] / 'glow.py')
glow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(glow)


def call(command, **kwargs):
    return glow.request({'command': command, 'quiet': True, **kwargs})


def status():
    return call('status')


original = status()
try:
    call('brightness', value='2')
    for mode in glow.MODES:
        current = call('mode', mode=mode)
        time.sleep(.4)
        current = status()
        assert current['mode'] == mode and not current['hardware_error'], current
        assert 0 <= current['output'] <= 2, current
        if mode == 'music':
            assert current['audio_running'] and not current['audio_error'], current
        else:
            assert not current['audio_running'], current
    print('PASS: all 12 modes accepted; music monitor starts and stops with Music mode.', flush=True)

    call('focus', action='stop')
    call('mode', mode='static')
    call('alert', kind='success')
    assert status()['overlay']
    time.sleep(1.2)
    restored = status()
    assert not restored['overlay'] and restored['mode'] == 'static' and restored['output'] == 2, restored
    call('brightness', value='0')
    call('alert', kind='failure')
    assert status()['output'] == 0 and not status()['overlay']
    call('brightness', value='2')
    print('PASS: completion alerts restore the base effect; brightness zero suppresses alerts.', flush=True)

    call('focus', action='start', work=.005, rest=.02)
    time.sleep(.6)
    assert status()['focus']['phase'] == 'break', status()
    call('focus', action='stop')
    call('mode', mode='static')
    call('morse', text='OK')
    assert status()['overlay']
    call('mode', mode='typing')
    before = status()['typing_events']
    subprocess.run(['hyprctl', 'dispatch', 'hl.dsp.event("keyboard-glow,typing")'], check=True, stdout=subprocess.DEVNULL)
    time.sleep(.15)
    assert status()['typing_events'] > before, status()
    print('PASS: focus timer advances, Morse overlays work, and Hyprland activity reaches the daemon.', flush=True)

    result = subprocess.run([str(Path.home() / '.local/bin/glow'), 'run', '--', '/usr/bin/bash', '-c', 'exit 7'])
    assert result.returncode == 7
    call('mode', mode='static')

    # A clean interactive Bash verifies PS0 timing, prompt status, and idempotency.
    master, slave = pty.openpty()
    shell = subprocess.Popen(['/usr/bin/bash', '--noprofile', '--norc', '-i'], stdin=slave, stdout=slave, stderr=slave,
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
        read_for(.2)
        commands = [
            "_capture_status() { printf 'GLOW_RC=%s\\n' \"$?\"; }; PROMPT_COMMAND=(_capture_status)",
            'source ~/.config/keyboard-glow/shell.bash',
            'source ~/.config/keyboard-glow/shell.bash',
            'KEYBOARD_GLOW_MIN_SECONDS=1',
            'sleep 1.2 && false',
        ]
        for command in commands:
            os.write(master, (command + '\n').encode())
            read_for(1.5 if 'sleep' in command else .2)
        assert status()['overlay'], (status(), b''.join(chunks).decode(errors='replace'))
        os.write(master, b"printf 'HOOKS=%s\\n' \"${#PROMPT_COMMAND[@]}\"\n")
        read_for(.2)
        os.write(master, b'exit\n')
        read_for(.2)
        transcript = b''.join(chunks).decode(errors='replace')
        assert 'GLOW_RC=1\r\n' in transcript, transcript
        assert 'HOOKS=2\r\n' in transcript, transcript
        assert 'Read-only' not in transcript and 'syntax error' not in transcript, transcript
        print('PASS: wrapped commands retain exit code 7; automatic Bash completion retains failure status and installs once.', flush=True)
    finally:
        if shell.poll() is None:
            shell.kill()
        shell.wait(timeout=3)
        os.close(master)
finally:
    call('focus', action='stop')
    call('mode', mode=original['mode'])
    call('brightness', value=str(original['brightness']))
print(json.dumps(status(), indent=2))
