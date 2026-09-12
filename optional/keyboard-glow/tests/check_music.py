"""Play a short quiet tone, verify output metering, and restore lighting."""
import importlib.util
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import time
import wave

spec = importlib.util.spec_from_file_location('glow', Path(__file__).resolve().parents[1] / 'glow.py')
glow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(glow)
original = glow.request({'command': 'status'})
try:
    glow.request({'command': 'mode', 'mode': 'music', 'quiet': True})
    time.sleep(.5)
    with tempfile.TemporaryDirectory(prefix='keyboard-glow-audio-') as directory:
        tone = Path(directory) / 'quiet-test.wav'
        with wave.open(str(tone), 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            wav.writeframes(b''.join(struct.pack('<h', int(900 * math.sin(i * math.tau * 440 / 8000))) for i in range(8000)))
        player = subprocess.Popen(['paplay', str(tone)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        levels = []
        for _ in range(25):
            levels.append(glow.request({'command': 'status'})['audio_level'])
            time.sleep(.06)
        player.wait(timeout=3)
        assert max(levels) > .1, levels
        print(f'PASS: output monitor detected the test tone (meter peak {max(levels):.2f}).')
finally:
    glow.request({'command': 'mode', 'mode': original['mode'], 'quiet': True})
assert not glow.request({'command': 'status'})['audio_running']
print('PASS: audio capture stopped after restoring the original non-music mode.')
