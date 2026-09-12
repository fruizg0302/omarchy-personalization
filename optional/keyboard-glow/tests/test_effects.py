import importlib.util
import math
from pathlib import Path
import struct
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / 'glow.py'
spec = importlib.util.spec_from_file_location('glow', SOURCE)
glow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(glow)


class EffectsTests(unittest.TestCase):
    def test_alert_restores_base_mode_and_brightness(self):
        e = glow.Engine('static', 2)
        e.alert(glow.pulse_sequence(2), 10, 2)
        self.assertEqual(e.level(10.2), 0)
        self.assertEqual(e.level(11), 2)
        self.assertIsNone(e.overlay)
        self.assertEqual(e.mode, 'static')

    def test_off_and_zero_suppress_alerts(self):
        for mode, peak in [('off', 3), ('candle', 0)]:
            e = glow.Engine(mode, peak)
            e.alert(glow.pulse_sequence(2), 10)
            self.assertIsNone(e.overlay)
            self.assertEqual(e.level(10), 0)

    def test_workspace_does_not_interrupt_completion(self):
        e = glow.Engine()
        e.alert(glow.pulse_sequence(3), 10, 2)
        original = e.overlay
        e.alert(glow.pulse_sequence(1), 10.1, 0)
        self.assertIs(e.overlay, original)

    def test_switching_mode_cancels_overlay(self):
        e = glow.Engine()
        e.alert(glow.pulse_sequence(3), 10)
        e.select('typing', 10.2)
        self.assertIsNone(e.overlay)
        self.assertEqual(e.mode, 'typing')

    def test_focus_transitions_and_preserves_previous_mode(self):
        e = glow.Engine('gpu')
        e.select('focus', 0)
        self.assertEqual(e.focus['previous'], 'gpu')
        self.assertIsNone(e.advance_focus(1499))
        self.assertEqual(e.advance_focus(1500), 'break')
        self.assertEqual(e.focus['deadline'], 1800)
        self.assertEqual(e.advance_focus(1800), 'work')

    def test_invalid_focus_and_morse_are_rejected(self):
        for value in (0, -1, 2000, math.nan, math.inf):
            with self.assertRaises(ValueError):
                glow.Engine().start_focus(value, 5, 0)
        for value in ('', 'hello!', 'A' * 81):
            with self.assertRaises(ValueError):
                glow.morse_sequence(value)

    def test_cycling_past_focus_cancels_timer(self):
        e = glow.Engine('gpu')
        e.select('focus', 0)
        e.select('morse', 1)
        self.assertIsNone(e.focus)

    def test_morse_spacing(self):
        self.assertEqual(glow.morse_sequence('E T', unit=1), [(1, 1.), (7, 0.), (3, 1.), (7, 0.)])

    def test_audio_meter_handles_silence_signal_and_nonfinite(self):
        self.assertEqual(glow.audio_level(struct.pack('<4f', 0, 0, 0, 0)), 0)
        self.assertGreater(glow.audio_level(struct.pack('<4f', .2, -.2, .2, -.2)), .5)
        self.assertTrue(math.isfinite(glow.audio_level(struct.pack('<2f', math.nan, math.inf))))

    def test_every_mode_respects_brightness_ceiling(self):
        for mode in glow.MODES:
            for peak in range(4):
                e = glow.Engine(mode, peak)
                e.started = 0
                e.last_activity = 0
                for t in (0, .1, .3, 1, 5, 10, 60):
                    self.assertIn(e.level(t), range(peak + 1), mode)

    def test_output_deduplicates_frames(self):
        d = glow.Daemon.__new__(glow.Daemon)
        d.dbus = Mock(UInt32=int)
        d.session = Mock()
        d.last_level, d.writes = None, 0
        for level in (2, 2, 2, 1, 1):
            d.output(level)
        self.assertEqual(d.session.SetBrightness.call_count, 2)
        self.assertEqual(d.writes, 2)

    def test_inactive_session_never_writes_hardware(self):
        d = glow.Daemon.__new__(glow.Daemon)
        d.engine = glow.Engine()
        d.paused, d.sleeping, d.session_active = True, False, False
        d.stop_audio, d.set_native, d.output = Mock(), Mock(), Mock()
        d.tick()
        d.set_native.assert_not_called()
        d.output.assert_not_called()


if __name__ == '__main__':
    unittest.main()
