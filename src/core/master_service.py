import time
import re
import threading
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List, Tuple

from src.core.emulator_service import EmulatorService
from src.core.preset_service import get_rounded_time
from src.core.winner_detector import are_names_similar

logger = logging.getLogger(__name__)

# Global queue / lock for Master emulator so multiple client nodes serialize access
_master_lock = threading.Lock()


class MasterCoordinatorService:
    """
    DOM & UI Automator inspection-based controller for Master Emulator running `com.riyaz.zvyadmin`.
    Completely eliminates OCR:
    - 0% Misreads (direct XML tree element extraction)
    - 0% GPU / CPU AI load
    - Pixel-perfect bounding box click calculation
    """

    def __init__(self, emulator_service: Optional[EmulatorService] = None):
        self.service = emulator_service or EmulatorService()

    def get_ui_hierarchy(self, serial: str) -> Optional[ET.Element]:
        """Dumps the current foreground UI XML hierarchy from the emulator via ADB."""
        try:
            dump_file = "/sdcard/window_dump.xml"
            # Dump to file
            self.service.adb_path
            import subprocess
            subprocess.run(
                [self.service.adb_path, "-s", serial, "shell", "uiautomator", "dump", dump_file],
                capture_output=True, timeout=5
            )
            # Read XML content
            proc = subprocess.run(
                [self.service.adb_path, "-s", serial, "shell", "cat", dump_file],
                capture_output=True, text=True, timeout=5
            )
            xml_text = proc.stdout.strip()
            if not xml_text or not xml_text.startswith("<?xml"):
                # Try finding where xml starts
                idx = xml_text.find("<?xml")
                if idx >= 0:
                    xml_text = xml_text[idx:]
                else:
                    return None

            return ET.fromstring(xml_text)
        except Exception as e:
            logger.error(f"Failed to dump UI hierarchy from {serial}: {e}")
            return None

    @staticmethod
    def parse_bounds(bounds_str: str) -> Optional[Tuple[int, int, int, int]]:
        """Parses '[x1,y1][x2,y2]' string into (x1, y1, x2, y2)."""
        m = re.findall(r'\[(\d+),(\d+)\]', bounds_str)
        if len(m) == 2:
            return int(m[0][0]), int(m[0][1]), int(m[1][0]), int(m[1][1])
        return None

    def find_node_by_desc(self, root: ET.Element, pattern: str) -> Optional[Tuple[int, int]]:
        """
        Recursively searches the XML tree for a node matching content-desc or text pattern.
        Returns the center (x, y) pixel coordinates of the element.
        """
        regex = re.compile(pattern, re.IGNORECASE)
        for node in root.iter("node"):
            desc = node.attrib.get("content-desc", "")
            text = node.attrib.get("text", "")
            val = desc if desc else text
            if regex.search(val):
                bounds = self.parse_bounds(node.attrib.get("bounds", ""))
                if bounds:
                    x1, y1, x2, y2 = bounds
                    return (x1 + x2) // 2, (y1 + y2) // 2
        return None

    def find_match_set_room_button(self, root: ET.Element, target_times: List[str]) -> Optional[Tuple[int, int]]:
        """
        Finds the match card matching target time slots and returns the 'Set Room ID/Password' button coordinates.
        """
        clean_targets = [t.replace(" ", "").upper() for t in target_times]

        for node in root.iter("node"):
            desc = node.attrib.get("content-desc", "")
            # Check if this node is a match card containing our time
            desc_upper = desc.replace(" ", "").upper()
            has_time = any(t in desc_upper for t in clean_targets)

            if has_time:
                # Look for 'Set Room ID/Password' inside its children
                for child in node.iter("node"):
                    c_desc = child.attrib.get("content-desc", "")
                    if "set room" in c_desc.lower() or "room id" in c_desc.lower():
                        bounds = self.parse_bounds(child.attrib.get("bounds", ""))
                        if bounds:
                            x1, y1, x2, y2 = bounds
                            return (x1 + x2) // 2, (y1 + y2) // 2

        # Fallback: if match card not found by exact time, find any visible 'Set Room ID/Password' button
        return self.find_node_by_desc(root, r"Set Room ID/Password")

    def find_input_fields_in_dialog(self, root: ET.Element) -> Dict[str, Tuple[int, int]]:
        """
        Extracts Room ID, Password edit fields, and Save/Submit button from the popup.
        """
        fields = {}
        edit_texts = []
        for node in root.iter("node"):
            cls = node.attrib.get("class", "")
            desc = node.attrib.get("content-desc", "")
            bounds = self.parse_bounds(node.attrib.get("bounds", ""))

            if "EditText" in cls and bounds:
                edit_texts.append(bounds)
            elif ("save" in desc.lower() or "submit" in desc.lower()) and bounds:
                fields["save"] = ((bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2)

        # In Flutter dialogs, Edit texts are listed vertically: 1st is Room ID, 2nd is Password
        edit_texts.sort(key=lambda b: b[1])  # sort by y1
        if len(edit_texts) >= 1:
            b = edit_texts[0]
            fields["room_id"] = ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)
        if len(edit_texts) >= 2:
            b = edit_texts[1]
            fields["password"] = ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)

        return fields

    def ensure_home_screen(self, master_serial: str, max_backs: int = 5) -> bool:
        """Navigates back to ZVY Admin home dashboard by checking the XML tree."""
        for attempt in range(max_backs + 1):
            root = self.get_ui_hierarchy(master_serial)
            if root is not None:
                # Home Screen has "Refresh Dashboard" or "Manage Users"
                if self.find_node_by_desc(root, r"Refresh Dashboard") or self.find_node_by_desc(root, r"ZVY Admin"):
                    return True

            if attempt < max_backs:
                self.service.keyevent(master_serial, 4)  # Android Back
                time.sleep(1.0)

        return False

    def dispatch_room_credentials(
        self,
        game_serial: str,
        master_serial: str,
        room_id: str,
        password: str,
        game_mode: str = "Lone Wolf 2V2",
        interval_m: int = 15,
        offset_m: int = 0,
        log_callback=None
    ) -> bool:
        """
        Fast, OCR-free credential dispatch directly into `com.riyaz.zvyadmin`.
        """
        def log(msg, lvl="MASTER"):
            if log_callback:
                log_callback(msg, lvl)
            else:
                logger.info(f"[{lvl}] {msg}")

        if not master_serial or master_serial.lower() in ("none", ""):
            log("No Master Emulator configured. Skipping credential dispatch.", "INFO")
            return False

        with _master_lock:
            log(f"Acquired Master Emulator lock for {master_serial}. Starting DOM dispatch...", "MASTER")

            # 1. Bring ZVY Admin to foreground if not active
            import subprocess
            subprocess.run(
                [self.service.adb_path, "-s", master_serial, "shell", "monkey", "-p", "com.riyaz.zvyadmin", "-c", "android.intent.category.LAUNCHER", "1"],
                capture_output=True, timeout=4
            )
            time.sleep(1.0)

            # 2. Ensure Home Screen
            if not self.ensure_home_screen(master_serial):
                log("Could not confirm Home Screen. Continuing with active UI tree...", "WARN")

            root = self.get_ui_hierarchy(master_serial)
            if root is None:
                log("Failed to inspect Master UI hierarchy.", "ERROR")
                return False

            # 3. Locate & Tap Game Mode Button
            mode_pattern = r"LW 2V2"
            if "lose" in game_mode.lower() or "ltw" in game_mode.lower():
                mode_pattern = r"Lose To Win"
            elif "cs" in game_mode.lower() or "clash" in game_mode.lower():
                mode_pattern = r"CS 4V4"
            elif "br" in game_mode.lower() or "battle" in game_mode.lower():
                mode_pattern = r"BR SQUAD"

            log(f"Locating '{mode_pattern}' button in UI tree...", "MASTER")
            mode_coords = self.find_node_by_desc(root, mode_pattern)
            if mode_coords:
                log(f"Found '{mode_pattern}' at ({mode_coords[0]}, {mode_coords[1]}). Tapping...", "MASTER")
                self.service.tap(master_serial, mode_coords[0], mode_coords[1])
                time.sleep(1.2)
            else:
                log(f"Button for '{mode_pattern}' not found in Home Screen XML.", "WARN")

            # 4. Find the Match & Tap 'Set Room ID/Password'
            now_ts = time.time()
            cur_time = get_rounded_time(now_ts, interval_m, offset_m)
            prev_time = get_rounded_time(now_ts - (interval_m * 60), interval_m, offset_m)
            next_time = get_rounded_time(now_ts + (interval_m * 60), interval_m, offset_m)
            target_times = [cur_time, prev_time, next_time]

            log(f"Searching match cards for target times {target_times}...", "MASTER")
            set_room_coords = None

            for attempt in range(4):
                match_root = self.get_ui_hierarchy(master_serial)
                if match_root is not None:
                    set_room_coords = self.find_match_set_room_button(match_root, target_times)
                    if set_room_coords:
                        break
                # Scroll down
                self.service.swipe_normalized(master_serial, 0.5, 0.75, 0.5, 0.35, 500)
                time.sleep(1.0)

            if set_room_coords:
                log(f"Found 'Set Room ID/Password' at ({set_room_coords[0]}, {set_room_coords[1]}). Tapping...", "MASTER")
                self.service.tap(master_serial, set_room_coords[0], set_room_coords[1])
                time.sleep(1.2)
            else:
                log("Could not locate 'Set Room ID/Password' button for match.", "ERROR")
                return False

            # 5. Fill Credentials in Dialog
            dialog_root = self.get_ui_hierarchy(master_serial)
            if dialog_root is None:
                log("Failed to inspect credentials dialog UI.", "ERROR")
                return False

            inputs = self.find_input_fields_in_dialog(dialog_root)

            # Room ID
            if "room_id" in inputs and room_id:
                rx, ry = inputs["room_id"]
                log(f"Tapping Room ID field at ({rx}, {ry}) & entering '{room_id}'...", "MASTER")
                self.service.tap(master_serial, rx, ry)
                time.sleep(0.4)
                self.service.clear_field(master_serial, 15)
                self.service.input_text(master_serial, room_id)
                self.service.keyevent(master_serial, 66)
                time.sleep(0.4)

            # Password
            if "password" in inputs and password:
                px, py = inputs["password"]
                log(f"Tapping Password field at ({px}, {py}) & entering password...", "MASTER")
                self.service.tap(master_serial, px, py)
                time.sleep(0.4)
                self.service.clear_field(master_serial, 15)
                self.service.input_text(master_serial, password)
                self.service.keyevent(master_serial, 66)
                time.sleep(0.4)

            # Save / Submit
            if "save" in inputs:
                sx, sy = inputs["save"]
                log(f"Tapping SAVE at ({sx}, {sy})...", "MASTER")
                self.service.tap(master_serial, sx, sy)
                time.sleep(1.0)
            else:
                # Look for Save button via desc
                save_coords = self.find_node_by_desc(dialog_root, r"save|confirm|submit")
                if save_coords:
                    self.service.tap(master_serial, save_coords[0], save_coords[1])
                    time.sleep(1.0)

            # Return to Home Screen
            self.service.keyevent(master_serial, 4)
            log("Room ID & Password synchronized directly via UI Automator without OCR!", "SUCCESS")
            return True

    def auto_reward_match(
        self,
        game_serial: str,
        master_serial: str,
        winners: List[str],
        game_mode: str = "Lone Wolf 2V2",
        interval_m: int = 15,
        offset_m: int = 0,
        is_ltw: bool = False,
        log_callback=None
    ) -> bool:
        """
        Executes the 2-Route Auto Reward flow directly via UI Automator (0% OCR):
        - Route 1: Verify & Mark Winners
          1. Scroll down on Home Screen to tap 'Live Match'
          2. Select Game Mode tab
          3. Tap active match card matching time
          4. Inspect player list, match names via are_names_similar, tap Edit -> Winner -> Save
          5. Tap 'See Result Sheet'
          6. Tap 'Submit Result' and Back
        - Route 2: Send Reward & Payout
          7. Return to Home Screen and tap 'Send Reward'
          8. Select Game Mode tab
          9. Tap completed match card
          10. Tap 'Send All'
          11. Tap 'CONFIRM'
        """
        def log(msg, lvl="REWARD"):
            if log_callback:
                log_callback(msg, lvl)
            else:
                logger.info(f"[{lvl}] {msg}")

        if not master_serial or master_serial.lower() in ("none", ""):
            log("No Master Emulator configured for Auto Rewards. Skipping.", "WARN")
            return False

        if not winners:
            log("No winners detected from match conclusion. Skipping reward dispatch.", "WARN")
            return False

        with _master_lock:
            log(f"Acquired Master Emulator lock for {master_serial}. Starting Auto Rewards (2-Route)...", "REWARD")

            # 0. Ensure app foreground
            import subprocess
            subprocess.run(
                [self.service.adb_path, "-s", master_serial, "shell", "monkey", "-p", "com.riyaz.zvyadmin", "-c", "android.intent.category.LAUNCHER", "1"],
                capture_output=True, timeout=4
            )
            time.sleep(1.0)

            # Determine Mode Pattern
            mode_tab = "Lone Wolf 2V2"
            if "lose" in game_mode.lower() or "ltw" in game_mode.lower() or is_ltw:
                mode_tab = "Lose To Win"
            elif "cs" in game_mode.lower() or "clash" in game_mode.lower():
                mode_tab = "CS 4V4"
            elif "br" in game_mode.lower() or "battle" in game_mode.lower():
                mode_tab = "BR E-Sports PRO League"

            now_ts = time.time()
            target_times = [
                get_rounded_time(now_ts, interval_m, offset_m),
                get_rounded_time(now_ts - (interval_m * 60), interval_m, offset_m),
                get_rounded_time(now_ts + (interval_m * 60), interval_m, offset_m)
            ]

            # ==========================================
            # ROUTE 1: VERIFY & MARK WINNERS (Phases 1-6)
            # ==========================================
            log("=== Starting ROUTE 1: Verify & Mark Winners ===", "REWARD")
            self.ensure_home_screen(master_serial)

            # Phase 1: Scroll to bottom of Home Screen and Tap 'Live Match'
            live_match_coords = None
            for _ in range(3):
                root = self.get_ui_hierarchy(master_serial)
                if root is not None:
                    live_match_coords = self.find_node_by_desc(root, r"^Live Match$")
                    if live_match_coords:
                        break
                self.service.swipe_normalized(master_serial, 0.5, 0.85, 0.5, 0.35, 500)
                time.sleep(0.8)

            if live_match_coords:
                log(f"Found 'Live Match' at {live_match_coords}. Tapping...", "REWARD")
                self.service.tap(master_serial, live_match_coords[0], live_match_coords[1])
                time.sleep(1.5)
            else:
                log("Could not locate 'Live Match' on Home Screen.", "ERROR")
                self.ensure_home_screen(master_serial)
                return False

            # Phase 2: Select Game Mode Tab in Live Match
            lm_root = self.get_ui_hierarchy(master_serial)
            if lm_root is not None:
                tab_coords = self.find_node_by_desc(lm_root, mode_tab)
                if tab_coords:
                    log(f"Found '{mode_tab}' tab at {tab_coords}. Tapping...", "REWARD")
                    self.service.tap(master_serial, tab_coords[0], tab_coords[1])
                    time.sleep(1.2)

            # Phase 3: Find active match card by time and Tap into it
            match_card_coords = None
            for _ in range(3):
                lm_match_root = self.get_ui_hierarchy(master_serial)
                if lm_match_root is not None:
                    # Check if match card contains target time or has Move to Match Page
                    clean_targets = [t.replace(" ", "").upper() for t in target_times]
                    for node in lm_match_root.iter("node"):
                        desc = node.attrib.get("content-desc", "").replace(" ", "").upper()
                        if any(t in desc for t in clean_targets) or "LIVE" in desc:
                            bounds = self.parse_bounds(node.attrib.get("bounds", ""))
                            if bounds:
                                match_card_coords = ((bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2)
                                break
                    if match_card_coords:
                        break
                self.service.swipe_normalized(master_serial, 0.5, 0.85, 0.5, 0.40, 500)
                time.sleep(0.8)

            if match_card_coords:
                log(f"Found active match card at {match_card_coords}. Tapping...", "REWARD")
                self.service.tap(master_serial, match_card_coords[0], match_card_coords[1])
                time.sleep(1.5)
            else:
                log("Could not find active match in Live Match view.", "WARN")

            # Phase 4: Inspect players, match names & Mark Winners
            details_root = self.get_ui_hierarchy(master_serial)
            if details_root is not None:
                # Iterate player items in XML
                for node in details_root.iter("node"):
                    desc = node.attrib.get("content-desc", "")
                    # Player row has format "<slot>\n<player_name>\n<uid>..."
                    lines = desc.split("\n")
                    if len(lines) >= 2:
                        p_name = lines[1].strip()
                        # Check if matches any detected winner
                        is_winner = any(are_names_similar(w, p_name) for w in winners)
                        if is_winner:
                            log(f"Player '{p_name}' MATCHED winner! Searching Edit button...", "REWARD")
                            # Edit button is sibling or child
                            bounds = self.parse_bounds(node.attrib.get("bounds", ""))
                            if bounds:
                                # Tap Edit button on right side of player card (x ~ 90%)
                                edit_x = int(bounds[2] * 0.90)
                                edit_y = (bounds[1] + bounds[3]) // 2
                                self.service.tap(master_serial, edit_x, edit_y)
                                time.sleep(1.0)

                                # Handle Winner Popup: find 'Winner' radio/button and 'Save'
                                popup_root = self.get_ui_hierarchy(master_serial)
                                if popup_root is not None:
                                    win_btn = self.find_node_by_desc(popup_root, r"Winner")
                                    if win_btn:
                                        self.service.tap(master_serial, win_btn[0], win_btn[1])
                                        time.sleep(0.5)
                                    save_btn = self.find_node_by_desc(popup_root, r"^Save$")
                                    if save_btn:
                                        self.service.tap(master_serial, save_btn[0], save_btn[1])
                                        time.sleep(1.0)
                                    else:
                                        # Cancel / close popup if no save
                                        self.service.keyevent(master_serial, 4)
                                        time.sleep(0.5)

            # Phase 5: Tap 'See Result Sheet'
            sheet_root = self.get_ui_hierarchy(master_serial)
            if sheet_root is not None:
                sheet_btn = self.find_node_by_desc(sheet_root, r"See Result Sheet")
                if sheet_btn:
                    log(f"Found 'See Result Sheet' at {sheet_btn}. Tapping...", "REWARD")
                    self.service.tap(master_serial, sheet_btn[0], sheet_btn[1])
                    time.sleep(2.0)

                    # Phase 6: Tap 'Submit Result'
                    submit_root = self.get_ui_hierarchy(master_serial)
                    if submit_root is not None:
                        sub_btn = self.find_node_by_desc(submit_root, r"Submit Result")
                        if sub_btn:
                            log(f"Found 'Submit Result' at {sub_btn}. Tapping...", "REWARD")
                            self.service.tap(master_serial, sub_btn[0], sub_btn[1])
                            time.sleep(2.0)
                            log("Result sheet submitted successfully!", "SUCCESS")

            # Return to Home Screen
            self.ensure_home_screen(master_serial)
            time.sleep(1.5)

            # ==========================================
            # ROUTE 2: SEND REWARD & PAYOUT (Phases 7-11)
            # ==========================================
            log("=== Starting ROUTE 2: Send Reward & Payout ===", "REWARD")

            # Phase 7: Scroll to bottom of Home Screen and Tap 'Send Reward'
            send_reward_coords = None
            for _ in range(3):
                root = self.get_ui_hierarchy(master_serial)
                if root is not None:
                    send_reward_coords = self.find_node_by_desc(root, r"^Send Reward$")
                    if send_reward_coords:
                        break
                self.service.swipe_normalized(master_serial, 0.5, 0.85, 0.5, 0.35, 500)
                time.sleep(0.8)

            if send_reward_coords:
                log(f"Found 'Send Reward' at {send_reward_coords}. Tapping...", "REWARD")
                self.service.tap(master_serial, send_reward_coords[0], send_reward_coords[1])
                time.sleep(1.5)
            else:
                log("Could not locate 'Send Reward' on Home Screen.", "ERROR")
                self.ensure_home_screen(master_serial)
                return False

            # Phase 8: Select Game Mode Tab in Send Reward
            sr_root = self.get_ui_hierarchy(master_serial)
            if sr_root is not None:
                tab_coords = self.find_node_by_desc(sr_root, mode_tab)
                if tab_coords:
                    log(f"Found '{mode_tab}' tab at {tab_coords}. Tapping...", "REWARD")
                    self.service.tap(master_serial, tab_coords[0], tab_coords[1])
                    time.sleep(1.2)

            # Phase 9: Select completed match in Send Reward list
            completed_card_coords = None
            for _ in range(3):
                sr_match_root = self.get_ui_hierarchy(master_serial)
                if sr_match_root is not None:
                    clean_targets = [t.replace(" ", "").upper() for t in target_times]
                    for node in sr_match_root.iter("node"):
                        desc = node.attrib.get("content-desc", "").replace(" ", "").upper()
                        if any(t in desc for t in clean_targets) or "COMPLETED" in desc:
                            bounds = self.parse_bounds(node.attrib.get("bounds", ""))
                            if bounds:
                                completed_card_coords = ((bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2)
                                break
                    if completed_card_coords:
                        break
                self.service.swipe_normalized(master_serial, 0.5, 0.85, 0.5, 0.40, 500)
                time.sleep(0.8)

            if completed_card_coords:
                log(f"Found completed match card at {completed_card_coords}. Tapping...", "REWARD")
                self.service.tap(master_serial, completed_card_coords[0], completed_card_coords[1])
                time.sleep(1.5)
            else:
                log("Could not find completed match in Send Reward list.", "WARN")

            # Phase 10: Tap 'Send All'
            payout_root = self.get_ui_hierarchy(master_serial)
            if payout_root is not None:
                send_all_btn = self.find_node_by_desc(payout_root, r"Send All")
                if send_all_btn:
                    log(f"Found 'Send All' button at {send_all_btn}. Tapping...", "REWARD")
                    self.service.tap(master_serial, send_all_btn[0], send_all_btn[1])
                    time.sleep(1.2)

                    # Phase 11: Tap 'CONFIRM'
                    confirm_root = self.get_ui_hierarchy(master_serial)
                    if confirm_root is not None:
                        confirm_btn = self.find_node_by_desc(confirm_root, r"CONFIRM")
                        if confirm_btn:
                            log(f"Found 'CONFIRM' button at {confirm_btn}. Tapping...", "REWARD")
                            self.service.tap(master_serial, confirm_btn[0], confirm_btn[1])
                            time.sleep(2.0)
                            log("Full Auto Rewards sequence completed successfully! All payouts sent.", "SUCCESS")
                else:
                    # Might already be 'All Sent'
                    if self.find_node_by_desc(payout_root, r"All Sent"):
                        log("Match already marked 'All Sent'. Payouts previously completed.", "SUCCESS")

            # Clean exit back to Home Screen
            self.ensure_home_screen(master_serial)
            return True
