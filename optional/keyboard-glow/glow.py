#!/usr/bin/python3
"""Whole-keyboard effects for the ASUS FA401EA, using the active login session."""
import argparse
import collections
import json
import math
import os
from pathlib import Path
import random
import signal
import socket
import struct
import subprocess
import sys
import time
import uuid

MODES = ('static', 'breathe', 'heartbeat', 'candle', 'gpu', 'music',
         'battery', 'temperature', 'typing', 'focus', 'morse', 'off')
LABELS = {'static': 'Steady', 'breathe': 'Breathe', 'heartbeat': 'Heartbeat',
          'candle': 'Candlelight', 'gpu': 'GPU heartbeat', 'music': 'Music',
          'battery': 'Battery', 'temperature': 'Temperature', 'typing': 'Typing glow',
          'focus': 'Focus timer', 'morse': 'Morse: HELLO', 'off': 'Off'}
MORSE = dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
    '.- -... -.-. -.. . ..-. --. .... .. .--- -.- .-.. -- -. --- .--. --.- .-. ... - ..- ...- .-- -..- -.-- --.. ----- .---- ..--- ...-- ....- ..... -.... --... ---.. ----.'.split()))
DATA = Path.home() / '.local/share/keyboard-glow'
STATE = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'keyboard-glow/state.json'
RUNTIME = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')) / 'keyboard-glow'
SOCKET = RUNTIME / 'control.sock'
LED = Path('/sys/class/leds/asus::kbd_backlight/brightness')


def pulse_sequence(count, on=0.18, gap=0.22):
    return [(duration, level) for _ in range(count) for duration, level in ((on, 1.), (gap, 0.))]


def morse_sequence(message, unit=0.16):
    words = message.upper().split()
    if not words or len(message) > 80 or any(c not in MORSE for w in words for c in w):
        raise ValueError('Use 1–80 letters, digits, or spaces for Morse.')
    seq = []
    for wi, word in enumerate(words):
        for ci, char in enumerate(word):
            for si, symbol in enumerate(MORSE[char]):
                seq.append((unit * (3 if symbol == '-' else 1), 1.))
                if si < len(MORSE[char]) - 1:
                    seq.append((unit, 0.))
            if ci < len(word) - 1:
                seq.append((unit * 3, 0.))
        if wi < len(words) - 1:
            seq.append((unit * 7, 0.))
    seq.append((unit * 7, 0.))
    return seq


def sequence_level(seq, elapsed):
    for duration, level in seq:
        if elapsed < duration:
            return level
        elapsed -= duration
    return None


def heartbeat(phase):
    phase %= 1.
    return 1. if phase < .10 else .65 if .20 <= phase < .30 else 0.


def quantize(value, peak):
    return max(0, min(peak, int(max(0., min(1., value)) * peak + .5)))


def audio_level(data):
    size = len(data) // 4
    if not size:
        return 0.
    samples = struct.unpack('<' + 'f' * size, data[:size * 4])
    rms = math.sqrt(sum(min(1., x * x) for x in samples if math.isfinite(x)) / size)
    return max(0., min(1., (20 * math.log10(max(rms, 1e-8)) + 48) / 36))


def read_number(path, default=0):
    try:
        return float(path.read_text().strip())
    except (OSError, ValueError):
        return default


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value) + '\n')
    tmp.replace(path)


def request(payload, wait=True):
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
        reply = RUNTIME / f'client-{os.getpid()}-{uuid.uuid4().hex[:8]}'
        try:
            if wait:
                sock.bind(str(reply))
                os.chmod(reply, 0o600)
                sock.settimeout(3)
            sock.sendto(json.dumps(payload).encode(), str(SOCKET))
            if wait:
                answer = json.loads(sock.recv(16384))
                if not answer.get('ok'):
                    raise ValueError(answer.get('error', 'Request failed'))
                return answer
        finally:
            if wait:
                reply.unlink(missing_ok=True)


class Engine:
    """Effect composition; the daemon supplies hardware and event inputs."""
    def __init__(self, mode='candle', peak=2):
        self.mode = mode if mode in MODES else 'candle'
        self.peak = max(0, min(3, int(peak)))
        self.last_mode = 'candle'
        self.started = time.monotonic()
        self.overlay = None
        self.last_activity = -100.
        self.activity_count = 0
        self.workspace_count = 0
        self.completion_count = 0
        self.gpu = 0.
        self.temperature = 40.
        self.charge = 100.
        self.charging = False
        self.music = 0.
        self.candle = .6
        self.candle_until = 0.
        self.focus = None
        self.morse = morse_sequence('HELLO')
        self.workspace_alerts = True
        self.battery_alerts = True

    def select(self, mode, now):
        if mode not in MODES:
            raise ValueError('Unknown mode')
        if mode == 'off' and self.mode != 'off':
            self.last_mode = self.mode
        if self.mode == 'focus' and mode != 'focus':
            self.focus = None
        if mode == 'focus' and not self.focus:
            self.start_focus(25, 5, now)
        self.mode, self.started, self.overlay = mode, now, None

    def start_focus(self, work, rest, now):
        if not .001 <= work <= 1440 or not .001 <= rest <= 1440:
            raise ValueError('Focus durations must be between .001 and 1440 minutes')
        previous = self.mode if self.mode != 'focus' else self.last_mode
        self.focus = {'phase': 'work', 'deadline': now + work * 60,
                      'work': work, 'break': rest, 'previous': previous}
        self.mode, self.started = 'focus', now

    def advance_focus(self, now):
        if not self.focus or now < self.focus['deadline']:
            return None
        phase = 'break' if self.focus['phase'] == 'work' else 'work'
        self.focus['phase'] = phase
        self.focus['deadline'] = now + self.focus[phase] * 60
        self.alert(pulse_sequence(3, .3, .3), now, 3)
        return phase

    def alert(self, seq, now, priority=1):
        if self.mode == 'off' or not self.peak:
            return
        if self.overlay and now < self.overlay['end'] and priority < self.overlay['priority']:
            return
        self.overlay = {'seq': seq, 'start': now, 'end': now + sum(d for d, _ in seq), 'priority': priority}

    def level(self, now):
        if self.mode == 'off' or self.peak == 0:
            return 0
        if self.overlay:
            value = sequence_level(self.overlay['seq'], now - self.overlay['start'])
            if value is not None:
                return quantize(value, self.peak)
            self.overlay = None
        elapsed = now - self.started
        if self.mode in ('static', 'breathe'):
            value = 1.
        elif self.mode == 'heartbeat':
            value = heartbeat(elapsed / 2.)
        elif self.mode == 'gpu':
            value = heartbeat(elapsed / (2.8 - 2.0 * max(0., min(100., self.gpu)) / 100))
        elif self.mode == 'candle':
            if now >= self.candle_until:
                self.candle = random.choice((.4, .6, .6, .8, 1.))
                self.candle_until = now + random.uniform(.2, .7)
            value = self.candle
        elif self.mode == 'music':
            value = self.music
        elif self.mode == 'battery':
            value = max(.25, self.charge / 100)
            if self.charging:
                value *= .4 + .6 * (1 - math.cos(elapsed * math.tau / 4)) / 2
        elif self.mode == 'temperature':
            value = .25 if self.temperature < 50 else .65 if self.temperature < 70 else 1.
        elif self.mode == 'typing':
            value = max(.2, 1 - max(0., now - self.last_activity - .5) / 3)
        elif self.mode == 'focus':
            value = .3 if self.focus and self.focus['phase'] == 'work' else .4 + .6 * heartbeat(elapsed / 3)
        elif self.mode == 'morse':
            value = sequence_level(self.morse, elapsed % sum(d for d, _ in self.morse)) or 0.
        else:
            value = 1.
        return quantize(value, self.peak)


class Daemon:
    def __init__(self):
        import dbus
        from dbus.mainloop.glib import DBusGMainLoop
        from gi.repository import GLib, GLibUnix
        self.dbus, self.GLib = dbus, GLib
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        self.aura = dbus.Interface(self.bus.get_object('xyz.ljones.Asusd', '/xyz/ljones/aura/tuf'),
                                   'org.freedesktop.DBus.Properties')
        self.session = dbus.Interface(self.bus.get_object('org.freedesktop.login1', '/org/freedesktop/login1/session/auto'),
                                      'org.freedesktop.login1.Session')
        props = self.bus.get_object('org.freedesktop.login1', '/org/freedesktop/login1/session/auto')
        self.session_props = dbus.Interface(props, 'org.freedesktop.DBus.Properties')
        self.original_effect = int(self.aura.Get('xyz.ljones.Aura', 'LedMode', timeout=2))
        self.original_brightness = int(read_number(LED, 1))
        self.native = self.original_effect
        self.last_level = None
        self.writes = 0
        self.last_error = ''
        self.last_error_time = 0.
        self.paused = False
        self.session_active = True
        self.sleeping = False
        self.lock_signal = False
        self.audio = None
        self.audio_watch = None
        self.audio_retry = 0.
        self.audio_seen = 0.
        self.audio_buffer = b''
        self.audio_error = ''
        self.audio_sink = ''
        self.audio_check = 0.
        self.hypr = None
        self.hypr_buffer = b''
        self.hypr_watch = None
        self.hypr_retry = 0.
        self.last_battery = None
        self.low_battery = False
        try:
            saved = json.loads(STATE.read_text())
        except (OSError, ValueError):
            saved = {}
        self.engine = Engine(saved.get('mode', 'candle'), saved.get('brightness', 2))
        self.engine.workspace_alerts = bool(saved.get('workspace_alerts', True))
        self.engine.battery_alerts = bool(saved.get('battery_alerts', True))
        if self.engine.mode == 'focus':
            self.engine.start_focus(25, 5, time.monotonic())
        self.gpu_path = next(iter(Path('/sys/class/drm').glob('card*/device/gpu_busy_percent')), None)
        self.temp_path = next(iter(self.gpu_path.parent.glob('hwmon/hwmon*/temp1_input')), None) if self.gpu_path else None
        self.battery_path = next((p for p in Path('/sys/class/power_supply').iterdir() if (p / 'capacity').exists()), None)
        RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
        # A lock is held by main(); an old socket can only belong to a dead instance.
        SOCKET.unlink(missing_ok=True)
        self.control = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.control.bind(str(SOCKET))
        os.chmod(SOCKET, 0o600)
        self.control.setblocking(False)
        GLib.io_add_watch(self.control.fileno(), GLib.IO_IN, self.on_control)
        self.bus.add_signal_receiver(self.on_sleep, 'PrepareForSleep', 'org.freedesktop.login1.Manager')
        self.bus.add_signal_receiver(self.on_lock, 'Lock', 'org.freedesktop.login1.Session')
        self.bus.add_signal_receiver(self.on_unlock, 'Unlock', 'org.freedesktop.login1.Session')
        self.loop = GLib.MainLoop()
        self.poll()
        GLib.timeout_add(100, self.tick)
        GLib.timeout_add_seconds(1, self.poll)
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.stop)
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.stop)

    def persist(self):
        e = self.engine
        save_json(STATE, {'mode': e.mode, 'brightness': e.peak,
                         'workspace_alerts': e.workspace_alerts, 'battery_alerts': e.battery_alerts})

    def notify(self, title, body):
        subprocess.Popen(['notify-send', '--app-name=Keyboard Glow', '--icon=input-keyboard',
                          '--expire-time=3000', '--hint=string:x-dunst-stack-tag:keyboard-glow', title, body],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def set_native(self, mode):
        if self.native != mode:
            self.aura.Set('xyz.ljones.Aura', 'LedMode', self.dbus.UInt32(mode), timeout=2)
            self.native = mode
            self.last_level = None

    def output(self, level):
        if level != self.last_level:
            self.session.SetBrightness('leds', 'asus::kbd_backlight', self.dbus.UInt32(level), timeout=2)
            self.last_level = level
            self.writes += 1

    def error(self, exc):
        message = str(exc)
        if message != self.last_error or time.monotonic() - self.last_error_time > 60:
            print(message, file=sys.stderr, flush=True)
            self.last_error_time = time.monotonic()
        self.last_error = message

    def on_lock(self):
        self.lock_signal = True
        self.paused = True

    def on_unlock(self):
        self.lock_signal = False
        self.last_level = None

    def on_sleep(self, sleeping):
        self.sleeping = bool(sleeping)
        self.last_level = None
        self.native = None
        if sleeping:
            self.engine.overlay = None
            self.stop_audio()

    def poll(self):
        now = time.monotonic()
        e = self.engine
        try:
            props = self.session_props.GetAll('org.freedesktop.login1.Session', timeout=2)
            self.session_active = bool(props['Active'])
            self.paused = not self.session_active or bool(props['LockedHint']) or self.lock_signal or self.sleeping
        except Exception as exc:
            self.session_active = False
            self.paused = True
            self.error(exc)
        if self.gpu_path:
            e.gpu = read_number(self.gpu_path)
        if self.temp_path:
            e.temperature = read_number(self.temp_path, 40000) / 1000
        if self.battery_path:
            e.charge = read_number(self.battery_path / 'capacity', 100)
            try:
                status = (self.battery_path / 'status').read_text().strip()
                e.charging = status == 'Charging'
                connected = status in ('Charging', 'Full', 'Not charging')
                if self.last_battery is not None and connected != self.last_battery and e.battery_alerts and not self.paused:
                    e.alert(pulse_sequence(2 if connected else 1, .3, .3), now, 1)
                self.last_battery = connected
                low = e.charge <= 15 and not connected
                if low and not self.low_battery and e.battery_alerts and not self.paused:
                    e.alert(pulse_sequence(3, .4, .5), now, 2)
                self.low_battery = low
            except OSError:
                pass
        if self.hypr is None and now >= self.hypr_retry:
            self.connect_hypr()
        if self.audio is not None and now - self.audio_check > 5:
            self.audio_check = now
            try:
                sink = subprocess.check_output(['pactl', 'get-default-sink'], text=True, timeout=1).strip()
                if sink != self.audio_sink:
                    self.stop_audio()
            except (OSError, subprocess.SubprocessError):
                pass
        # Reap notify-send/OSD children without retaining zombie processes.
        subprocess._cleanup()
        return True

    def tick(self):
        now = time.monotonic()
        e = self.engine
        phase = e.advance_focus(now)
        if phase:
            self.notify('Focus timer', 'Time for a break.' if phase == 'break' else 'Back to focus.')
        if self.paused or self.sleeping:
            e.overlay = None
            self.stop_audio()
            # Hold steady while locked; no animation follows password activity.
            if not self.sleeping and self.session_active:
                try:
                    self.set_native(0)
                    self.output(0 if e.mode == 'off' else e.peak)
                except Exception as exc:
                    self.error(exc)
            return True
        music_needed = e.mode == 'music' and e.peak > 0
        if music_needed and self.audio is None and now >= self.audio_retry:
            self.start_audio()
        elif not music_needed:
            self.stop_audio()
        if now - self.audio_seen > .4:
            e.music = 0.
        try:
            level = e.level(now)
            # Native breathing runs in the controller. Software modes use Static;
            # frame updates go through logind and never rewrite asusd/firmware settings.
            self.set_native(1 if e.mode == 'breathe' and not e.overlay and e.peak else 0)
            self.output(level)
            self.last_error = ''
        except Exception as exc:
            self.error(exc)
        return True

    def start_audio(self):
        self.audio_retry = time.monotonic() + 10
        try:
            self.audio_sink = subprocess.check_output(['pactl', 'get-default-sink'], text=True, timeout=1).strip()
            self.audio = subprocess.Popen(['parec', '--device=' + self.audio_sink + '.monitor',
                '--format=float32le', '--rate=8000', '--channels=1', '--latency-msec=60',
                '--raw', '--client-name=Keyboard Glow', '--stream-name=Music brightness'],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            os.set_blocking(self.audio.stdout.fileno(), False)
            self.audio_buffer = b''
            self.audio_watch = self.GLib.io_add_watch(self.audio.stdout.fileno(),
                self.GLib.IO_IN | self.GLib.IO_HUP | self.GLib.IO_ERR, self.on_audio)
            self.audio_error = ''
            self.audio_check = time.monotonic()
        except (OSError, subprocess.SubprocessError) as exc:
            self.audio_error = str(exc)
            self.stop_audio()

    def on_audio(self, fd, condition):
        try:
            data = os.read(fd, 8192)
            if not data:
                self.audio_error = 'Audio monitor stopped; retrying in 10 seconds.'
                self.audio_watch = None
                self.stop_audio()
                return False
            data = self.audio_buffer + data
            count = len(data) // 4 * 4
            self.audio_buffer = data[count:]
            self.engine.music = max(audio_level(data[:count]), self.engine.music * .7)
            self.audio_seen = time.monotonic()
        except BlockingIOError:
            pass
        return True

    def stop_audio(self):
        if self.audio_watch is not None:
            self.GLib.source_remove(self.audio_watch)
            self.audio_watch = None
        if self.audio:
            self.audio.terminate()
            try:
                self.audio.wait(timeout=.5)
            except subprocess.TimeoutExpired:
                self.audio.kill()
                self.audio.wait(timeout=.5)
            self.audio.stdout.close()
            self.audio = None
        self.engine.music = 0.

    def connect_hypr(self):
        self.hypr_retry = time.monotonic() + 5
        signature = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE', '')
        candidates = [RUNTIME.parent / 'hypr' / signature / '.socket2.sock'] if signature else []
        candidates += sorted((RUNTIME.parent / 'hypr').glob('*/.socket2.sock'), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in dict.fromkeys(candidates):
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.settimeout(.2)
                sock.connect(str(path))
                sock.setblocking(False)
                self.hypr = sock
                self.hypr_buffer = b''
                self.hypr_watch = self.GLib.io_add_watch(sock.fileno(),
                    self.GLib.IO_IN | self.GLib.IO_HUP | self.GLib.IO_ERR, self.on_hypr)
                return
            except OSError:
                sock.close()

    def on_hypr(self, fd, condition):
        try:
            data = self.hypr.recv(65536)
            if not data:
                self.hypr.close()
                self.hypr = None
                self.hypr_watch = None
                return False
            self.hypr_buffer += data
            lines = self.hypr_buffer.split(b'\n')
            self.hypr_buffer = lines.pop()[-8192:]
            now = time.monotonic()
            for line in lines:
                event = line.decode(errors='replace')
                if event == 'custom>>keyboard-glow,typing' or event == 'custom_event>>keyboard-glow,typing':
                    if not self.paused:
                        self.engine.last_activity = now
                        self.engine.activity_count += 1
                elif event.startswith('workspacev2>>'):
                    self.engine.workspace_count += 1
                    try:
                        number = int(event.split('>>', 1)[1].split(',', 1)[0])
                        if self.engine.workspace_alerts and not self.paused and number > 0:
                            self.engine.alert(pulse_sequence(min(number, 10), .12, .18), now, 0)
                    except ValueError:
                        pass
        except BlockingIOError:
            pass
        return True

    def status(self):
        e = self.engine
        return {'mode': e.mode, 'brightness': e.peak, 'output': self.last_level,
                'overlay': bool(e.overlay), 'paused': self.paused, 'gpu_percent': e.gpu,
                'temperature_c': e.temperature, 'battery_percent': e.charge,
                'charging': e.charging, 'workspace_alerts': e.workspace_alerts,
                'battery_alerts': e.battery_alerts, 'hyprland_connected': self.hypr is not None,
                'typing_events': e.activity_count, 'workspace_events': e.workspace_count,
                'completion_events': e.completion_count,
                'audio_running': self.audio is not None, 'audio_level': e.music,
                'audio_error': self.audio_error, 'hardware_error': self.last_error,
                'brightness_writes': self.writes,
                'focus': None if not e.focus else {'phase': e.focus['phase'],
                    'remaining_seconds': max(0, int(e.focus['deadline'] - time.monotonic()))}}

    def handle(self, msg):
        e, now = self.engine, time.monotonic()
        cmd = msg['command']
        if cmd == 'status':
            return self.status()
        if cmd == 'mode':
            mode = msg['mode']
            if mode in ('next', 'prev'):
                mode = MODES[(MODES.index(e.mode) + (1 if mode == 'next' else -1)) % len(MODES)]
            e.select(mode, now)
            self.persist()
            if not msg.get('quiet'):
                self.notify('Keyboard lighting', LABELS[e.mode])
        elif cmd == 'brightness':
            action = str(msg['value'])
            level = {'up': min(3, e.peak + 1), 'down': max(0, e.peak - 1), 'cycle': (e.peak + 1) % 4}.get(action)
            if level is None:
                level = int(action)
            if level not in range(4):
                raise ValueError('Brightness must be 0, 1, 2, or 3')
            e.peak, e.overlay = level, None
            if e.mode == 'off' and level > 0:
                e.select(e.last_mode, now)
            self.persist()
            subprocess.Popen(['omarchy', 'osd', '-i', 'keyboard', '-p', str(level * 100 // 3)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif cmd == 'alert':
            kind = msg['kind']
            if kind not in ('success', 'failure', 'done'):
                raise ValueError('Unknown alert')
            e.completion_count += 1
            if not self.paused:
                e.alert(pulse_sequence(3 if kind == 'failure' else 2, .35 if kind == 'failure' else .18, .25), now, 2)
        elif cmd == 'morse':
            seq = morse_sequence(msg['text'])
            if not self.paused:
                e.alert(seq, now, 3)
        elif cmd == 'focus':
            if msg['action'] == 'stop':
                previous = e.focus['previous'] if e.focus else 'candle'
                e.focus = None
                if e.mode == 'focus':
                    e.select(previous, now)
            else:
                e.start_focus(float(msg.get('work', 25)), float(msg.get('rest', 5)), now)
            self.persist()
            if not msg.get('quiet'):
                self.notify('Focus timer', 'Stopped' if not e.focus else f"{e.focus['work']:g} minutes work / {e.focus['break']:g} minutes break")
        elif cmd == 'events':
            if msg['event'] not in ('workspace', 'battery') or msg['value'] not in ('on', 'off'):
                raise ValueError('Use events workspace|battery on|off')
            setattr(e, msg['event'] + '_alerts', msg['value'] == 'on')
            self.persist()
        else:
            raise ValueError('Unknown command')
        self.tick()
        return self.status()

    def on_control(self, fd, condition):
        try:
            data, address = self.control.recvfrom(8192)
        except BlockingIOError:
            return True
        try:
            result = self.handle(json.loads(data))
            response = {'ok': True, **result}
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            response = {'ok': False, 'error': str(exc)}
        except Exception as exc:
            self.error(exc)
            response = {'ok': False, 'error': str(exc)}
        if address:
            try:
                self.control.sendto(json.dumps(response).encode(), address)
            except OSError:
                pass
        return True

    def stop(self):
        self.stop_audio()
        try:
            self.set_native(self.original_effect)
            self.output(self.original_brightness)
        except Exception as exc:
            self.error(exc)
        self.control.close()
        SOCKET.unlink(missing_ok=True)
        self.loop.quit()
        return False


def main():
    parser = argparse.ArgumentParser(description='Keyboard lighting, ambient modes, and activity alerts.')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('daemon')
    sub.add_parser('list')
    sub.add_parser('menu', help='Choose a lighting mode interactively.')
    sub.add_parser('status')
    mode = sub.add_parser('mode')
    mode.add_argument('mode', choices=MODES + ('next', 'prev'))
    mode.add_argument('--quiet', action='store_true')
    bright = sub.add_parser('brightness')
    bright.add_argument('value', choices=('up', 'down', 'cycle', '0', '1', '2', '3'))
    bright.add_argument('--quiet', action='store_true')
    alert = sub.add_parser('alert')
    alert.add_argument('kind', choices=('success', 'failure', 'done'))
    alert.add_argument('--quiet', action='store_true')
    alert.add_argument('--no-wait', action='store_true')
    morse = sub.add_parser('morse')
    morse.add_argument('text')
    focus = sub.add_parser('focus')
    focus.add_argument('action', choices=('start', 'stop'))
    focus.add_argument('--work', type=float, default=25)
    focus.add_argument('--rest', type=float, default=5)
    focus.add_argument('--quiet', action='store_true')
    events = sub.add_parser('events')
    events.add_argument('event', choices=('workspace', 'battery'))
    events.add_argument('value', choices=('on', 'off'))
    run = sub.add_parser('run', help='Run a command and signal its exit status.')
    run.add_argument('args', nargs=argparse.REMAINDER)
    args = parser.parse_args(sys.argv[1:] or (['menu'] if sys.stdin.isatty() else ['status']))
    if args.command == 'menu':
        choices = [f'{name:12} {LABELS[name]}' for name in MODES]
        result = subprocess.run(['gum', 'choose', '--header=Keyboard lighting', *choices], text=True, stdout=subprocess.PIPE)
        if result.returncode:
            return result.returncode
        selected = result.stdout.strip().split()[0]
        try:
            request({'command': 'mode', 'mode': selected})
        except (OSError, ValueError) as exc:
            print(f'Keyboard Glow: {exc}', file=sys.stderr)
            return 1
        return 0
    if args.command == 'list':
        for name in MODES:
            print(f'{name:12} {LABELS[name]}')
        return 0
    if args.command == 'daemon':
        import fcntl
        RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (RUNTIME / 'daemon.lock').open('w') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                parser.error('Keyboard Glow is already running')
            daemon = Daemon()
            daemon.loop.run()
        return 0
    if args.command == 'run':
        command = args.args[1:] if args.args[:1] == ['--'] else args.args
        if not command:
            parser.error('Supply a command after run --')
        # Suppress a duplicate automatic completion alert in the parent shell.
        marker = RUNTIME / f'shell-{os.getppid()}'
        if marker.exists():
            marker.write_text('handled\n')
        try:
            result = subprocess.run(command)
            rc = result.returncode if result.returncode >= 0 else 128 - result.returncode
        except KeyboardInterrupt:
            rc = 130
        except OSError as exc:
            print(exc, file=sys.stderr)
            rc = 127
        if rc not in (130, 143):
            try:
                request({'command': 'alert', 'kind': 'success' if rc == 0 else 'failure'}, wait=False)
            except OSError:
                pass
        return rc
    try:
        result = request(vars(args), wait=not getattr(args, 'no_wait', False))
        if args.command == 'status':
            print(json.dumps(result, indent=2))
        elif not getattr(args, 'quiet', False) and result:
            print(f"{LABELS[result['mode']]} · brightness {result['brightness']}/3")
    except (OSError, ValueError) as exc:
        if not getattr(args, 'quiet', False):
            print(f'Keyboard Glow: {exc}. Check systemctl --user status keyboard-glow.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
