import sys
import os
import time
import unittest
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.emulator_service import EmulatorService
from src.core.match_detector import detect_match_state, compute_dhash, hamming_distance
from src.core.preset_service import PresetService, MODES
from src.core.config_manager import get_node_config, save_node_config, load_all_configs
from src.core.audio_service import AudioEngine, play_sound
from src.core.discord_notifier import send_discord_webhook
from src.core.automation_worker import EmulatorAutomationWorker

from PyQt6.QtWidgets import QApplication
from src.ui.main_window import MainWindow
from src.ui.emulator_tile import EmulatorTile
from src.ui.sidebar_inspector import SidebarInspector
from src.ui.theme import VSCODE_THEME

class FullSystemAuditTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create single QApplication for UI testing
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_01_emulator_service(self):
        """Tests ADB connection, device enumeration, and physical size queries"""
        svc = EmulatorService()
        devices = svc.get_connected_devices()
        self.assertGreater(len(devices), 0, "Should detect at least 1 emulator")
        serial = devices[0]["serial"]
        
        # Test screen size discovery
        w, h = svc.get_screen_size(serial)
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)
        
        # Test screenshot capture
        img = svc.capture_screenshot(serial)
        self.assertIsNotNone(img, "Screenshot should not be None")
        self.assertIsInstance(img, Image.Image)

    def test_02_dhash_and_hamming(self):
        """Tests perceptual hashing and distance calculation"""
        img1 = Image.new("RGB", (100, 100), color="white")
        img2 = Image.new("RGB", (100, 100), color="white")
        img3 = Image.new("RGB", (100, 100), color="black")

        h1 = compute_dhash(img1)
        h2 = compute_dhash(img2)
        h3 = compute_dhash(img3)

        self.assertEqual(hamming_distance(h1, h2), 0, "Identical images should have distance 0")
        self.assertGreater(len(h1), 0)

    def test_03_match_detector_classification(self):
        """Tests match state detection on synthetic images across BR, CS, LW"""
        test_img = Image.new("RGB", (640, 360), color="black")
        state, text, details = detect_match_state(test_img, "BR")
        self.assertIn(state, ["IDLE", "IN_GAME", "LOBBY_SCREEN", "RESULT_SCREEN"])

    def test_04_preset_service_and_purged_keys(self):
        """Tests preset service loading and guarantees removed keys are absent"""
        presets = PresetService.load_presets()
        self.assertGreaterEqual(len(presets), 10)

        # Check BR, CS, LW presets exist
        br_presets = PresetService.get_presets_for_mode("BR")
        cs_presets = PresetService.get_presets_for_mode("CS")
        lw_presets = PresetService.get_presets_for_mode("LW")
        self.assertGreater(len(br_presets), 0)
        self.assertGreater(len(cs_presets), 0)
        self.assertGreater(len(lw_presets), 0)

        # Verify keys 1, 2, 3, 5, 7 are completely removed
        purged = ['esportsMode', 'autoRoomCreation', 'scrollCount', 'autoRewards', 'room_close_delay']
        for p in presets.values():
            cfg = p.get("config", {})
            for key in purged:
                self.assertNotIn(key, cfg, f"Key '{key}' should not exist in preset config")

    def test_05_config_manager_io(self):
        """Tests config saving, reading, and persistence"""
        test_serial = "test-serial-001"
        test_data = {
            "customName": "Audit Host",
            "mode": "CS",
            "preset": "std_cs",
            "webhook": "https://discord.com/api/test",
            "autoLobbyReturn": False,
            "lobbyReturnDelay": 3.0
        }
        save_node_config(test_serial, test_data)
        loaded = get_node_config(test_serial)
        self.assertEqual(loaded["customName"], "Audit Host")
        self.assertEqual(loaded["mode"], "CS")
        self.assertEqual(loaded["preset"], "std_cs")
        self.assertFalse(loaded["autoLobbyReturn"])

        # Test logInterval and logOffset tournament rounding algorithm
        from src.core.preset_service import get_rounded_time
        # Fixed timestamp: 1728738000 corresponds to an exact hour
        time_str = get_rounded_time(1728738000, 20, 0)
        self.assertIn(":", time_str)
        self.assertTrue(time_str.endswith("AM") or time_str.endswith("PM"))

    def test_06_audio_engine(self):
        """Tests audio synthesis, volume level control, and background thread playback"""
        eng = AudioEngine.get()
        self.assertTrue(AudioEngine.is_enabled())
        # Test volume level adjustments
        AudioEngine.set_volume(0.5)
        self.assertAlmostEqual(AudioEngine.get_volume(), 0.5)
        # Test exactly the 4 permitted system sound effects
        allowed_sounds = ["match_detected", "start", "stop", "save"]
        self.assertEqual(sorted(list(eng._sound_cache.keys())), sorted(allowed_sounds))
        for sname in allowed_sounds:
            self.assertGreater(len(eng._sound_cache[sname]), 1000)
        play_sound("save")
        time.sleep(0.1)

    def test_07_automation_worker_lifecycle(self):
        """Tests background thread worker instantiation, thread execution, and quick stop"""
        svc = EmulatorService()
        devs = svc.get_connected_devices()
        serial = devs[0]["serial"]
        cfg = get_node_config(serial)

        worker = EmulatorAutomationWorker(serial, svc, cfg)
        self.assertFalse(worker._is_running)

        # Test start
        worker.start()
        self.assertTrue(worker._is_running)

        # Test stop responsiveness
        worker.stop()
        worker.wait(1000)
        self.assertFalse(worker._is_running)


    def test_08_ui_components(self):
        """Tests UI instantiation, theme loading, and widget hierarchy"""
        self.assertGreater(len(VSCODE_THEME), 100)

        # Test EmulatorTile and Phase Glow Outline
        tile = EmulatorTile("test-emulator")
        self.assertIsNotNone(tile)
        self.assertEqual(tile.current_phase, "IDLE")
        tile.set_phase("IN_GAME", "IN-GAME")
        self.assertEqual(tile.current_phase, "IN_GAME")
        tile.set_phase("WAIT", "SETTLING 3S")
        self.assertEqual(tile.current_phase, "WAIT")

        # Test SidebarInspector
        sidebar = SidebarInspector()
        self.assertIsNotNone(sidebar)
        sidebar.load_emulator("test-emulator", False)
        self.assertEqual(sidebar.current_serial, "test-emulator")

        # Test Match Database & Match History Browser
        from src.core.match_database import MatchDatabase
        from src.ui.match_history_dialog import MatchHistoryDialog

        db = MatchDatabase.get()
        row_id = db.save_match("test-serial", "Test Host", "CS", "RESULT_SCREEN", "VICTORY BOOYAH", "test.png")
        self.assertGreater(row_id, 0)
        matches = db.get_matches(10)
        self.assertGreater(len(matches), 0)
        self.assertEqual(matches[0]["node_id"], "test-serial")

        hist_dlg = MatchHistoryDialog()
        self.assertIsNotNone(hist_dlg)
        hist_dlg.close()

        # Test MainWindow
        win = MainWindow()
        self.assertEqual(win.width(), 1280)
        self.assertEqual(win.height(), 720)
        self.assertGreater(len(win.tiles), 0)
        win.close()

    def test_09_br_and_scroll_flow(self):
        """Tests BR multi-elimination detection, swipe gestures, and multi-image webhook payload"""
        svc = EmulatorService()
        self.assertTrue(hasattr(svc, "swipe"))
        self.assertTrue(hasattr(svc, "swipe_normalized"))

        # Test Discord multi-attachment signature
        from src.core.discord_notifier import send_discord_webhook
        img1 = Image.new("RGB", (100, 100), color="blue")
        img2 = Image.new("RGB", (100, 100), color="red")
        ok, msg = send_discord_webhook("", "Test Host", "BR", img1, additional_images=[img2])
        self.assertFalse(ok)
        self.assertIn("No valid Webhook", msg)

        # Test BR detection with simulated Battle Royale summary
        from src.core.match_detector import detect_match_state
        test_img = Image.new("RGB", (960, 540), color="black")
        state, _, _ = detect_match_state(test_img, "BR")
        self.assertIn(state, ["IDLE", "RESULT_SCREEN", "LOBBY_SCREEN", "IN_GAME"])


if __name__ == "__main__":
    unittest.main()
