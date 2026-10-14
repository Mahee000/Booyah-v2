import os
import time
import logging
from typing import Dict, Any, Optional, List
from PyQt6.QtCore import QThread, pyqtSignal
from PIL import Image


from src.core.emulator_service import EmulatorService
from src.core.match_detector import compute_dhash, hamming_distance, detect_match_state
from src.core.discord_notifier import send_discord_webhook
from src.core.preset_service import get_rounded_time, get_next_match_time_sec
from src.core.audio_service import play_sound
from src.core.match_database import MatchDatabase
from src.core.config_manager import load_app_settings

logger = logging.getLogger(__name__)

class EmulatorAutomationWorker(QThread):
    """
    Dedicated background worker thread per emulator instance.
    Runs entirely off the main GUI thread to ensure zero UI freezing or lag:
    - Captures screen periodically via ADB
    - Compares dHash to skip static frames & save CPU
    - Detects Match Result screens (Victory/Defeat/Booyah) via PaddleOCR
    - Auto-uploads result screenshot to Discord Webhook asynchronously
    - Auto-taps Return to Lobby coordinate
    - Match Time Scheduler & Auto Room Creation
    - Auto Close Room sequence
    """
    state_changed = pyqtSignal(str, str)             # serial, state ("IDLE", "IN_GAME", "RESULT_SCREEN")
    match_completed = pyqtSignal(str, str)           # serial, match_details
    log_message = pyqtSignal(str, str, str)          # serial, message, level
    frame_ready = pyqtSignal(str, object)            # serial, PIL.Image

    def __init__(self, serial: str, service: EmulatorService, config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.serial = serial
        self.service = service
        self.config = config
        self._is_running = False
        self.last_dhash = ""
        self.current_state = "IDLE"
        self.has_seen_non_result = True
        self.last_log_time = 0.0
        self.last_match_time = 0.0

        # Auto Creation Scheduler tracking
        self.has_run_room_creation = False
        self.last_room_creation_match_sec: Optional[float] = None
        self.last_auto_host_wait_log_time = 0.0
        self.is_executing_sequence = False

    def start(self, priority=QThread.Priority.InheritPriority):
        """Starts worker background thread."""
        self._is_running = True
        super().start(priority)

    def run(self):
        """Background thread execution loop. Completely decouples OCR & ADB from UI."""
        alias = self.config.get("customName") or self.serial
        mode = self.config.get("mode", "BR")
        self.log_message.emit(self.serial, f"Automation worker started for {alias} (Mode: {mode}) [Threaded]", "INFO")

        # Warm up winner OCR engine in background thread so it never freezes when match finishes
        try:
            from src.core.winner_detector import get_winner_ocr
            get_winner_ocr()
        except Exception:
            pass

        while self._is_running:
            try:
                self._step()
            except Exception as e:
                logger.error(f"Error in automation loop for {self.serial}: {e}")
            
            # Polling delay check
            scan_speed = max(300, int(self.config.get("scanSpeed", 1000) or 1000))
            for _ in range(scan_speed // 100):
                if not self._is_running:
                    break
                self.msleep(100)

        alias = self.config.get("customName") or self.serial
        self.log_message.emit(self.serial, f"Automation worker stopped for {alias}", "INFO")

    def stop(self):
        """Stops the background automation thread cleanly without blocking GUI."""
        self._is_running = False

    def wait(self, timeout_ms: int = 1500):
        """Clean cooperative wait for thread termination."""
        self._is_running = False
        super().wait(timeout_ms)


    def _get_cropped_frame(self, image: Image.Image) -> Image.Image:
        """Crops image based on preset relative percentages (cropX, cropY, cropW, cropH)"""
        cx = self.config.get("cropX")
        cy = self.config.get("cropY")
        cw = self.config.get("cropW")
        ch = self.config.get("cropH")
        if cx is None or cy is None or cw is None or ch is None:
            return image

        try:
            w, h = image.size
            left = int(float(cx) * w)
            top = int(float(cy) * h)
            right = min(w, int(left + float(cw) * w))
            bottom = min(h, int(top + float(ch) * h))
            if right > left + 10 and bottom > top + 10:
                return image.crop((left, top, right, bottom))
        except Exception:
            pass
        return image

    def _get_crop2_frame(self, image: Image.Image) -> Image.Image:
        """Crops image based on secondary relative percentages (crop2X, crop2Y, crop2W, crop2H)"""
        c2x = self.config.get("crop2X")
        c2y = self.config.get("crop2Y")
        c2w = self.config.get("crop2W")
        c2h = self.config.get("crop2H")
        if c2x is None or c2y is None or c2w is None or c2h is None:
            return self._get_cropped_frame(image)

        try:
            w, h = image.size
            left = int(float(c2x) * w)
            top = int(float(c2y) * h)
            right = min(w, int(left + float(c2w) * w))
            bottom = min(h, int(top + float(c2h) * h))
            if right > left + 10 and bottom > top + 10:
                return image.crop((left, top, right, bottom))
        except Exception:
            pass
        return image

    def update_config(self, new_config: Dict[str, Any]):
        self.config = new_config

    def _step(self):
        """Single execution cycle running in the background thread."""
        if not self._is_running:
            return

        alias = self.config.get("customName") or self.serial
        mode = self.config.get("mode", "BR")
        log_interval = float(self.config.get("logInterval", 15))

        try:
            # 1. Capture screen
            frame = self.service.capture_screenshot(self.serial)
            if not self._is_running:
                return

            if not frame:
                self.msleep(600)
                return

            self.frame_ready.emit(self.serial, frame)

            # 2. Check perceptual dHash (skip identical screens to save CPU)
            current_hash = compute_dhash(frame)
            h_dist = hamming_distance(self.last_dhash, current_hash)
            self.last_dhash = current_hash

            # If screen is static (Hamming distance <= 2), skip heavy OCR completely!
            if h_dist <= 2 and self.current_state != "IDLE":
                now = time.time()
                if now - self.last_log_time >= log_interval:
                    self.last_log_time = now
                    self.log_message.emit(self.serial, f"Monitoring {alias} (State: {self.current_state})", "SCAN")
                self.msleep(1000)
                return

            # 3. Detect match state via OCR (downscale to max 960px width for fast inference)
            w, h = frame.size
            if w > 960:
                scale = 960.0 / w
                ocr_frame = frame.resize((960, int(h * scale)), Image.Resampling.BILINEAR)
            else:
                ocr_frame = frame

            state, raw_text, details = detect_match_state(ocr_frame, mode)
            if not self._is_running:
                return

            now = time.time()

            if state != self.current_state:
                self.current_state = state
                self.state_changed.emit(self.serial, state)
                self.log_message.emit(self.serial, f"Screen State changed to: {state}", "STATE")
            else:
                if now - self.last_log_time >= log_interval:
                    self.last_log_time = now
                    self.log_message.emit(self.serial, f"Scanning {alias} (State: {state})", "SCAN")

            if state != "RESULT_SCREEN":
                self.has_seen_non_result = True

            # 4. Trigger Result Screen Sequence
            if state == "RESULT_SCREEN":
                if not self.has_seen_non_result or (now - self.last_match_time < 60.0):
                    self.msleep(1500)
                    return

                self.last_match_time = now
                self.has_seen_non_result = False
                play_sound("match_detected")
                self.log_message.emit(self.serial, f"[MATCH] Match completed detected on {alias}!", "MATCH")
                self.state_changed.emit(self.serial, "MATCH")
                self.match_completed.emit(self.serial, raw_text)

                # Wait for settled screenshot
                self.state_changed.emit(self.serial, "WAIT")
                self.log_message.emit(self.serial, "Scoreboard settled. Processing capture...", "WAIT")

                settled_frame = self.service.capture_frame(self.serial)
                if settled_frame is None:
                    settled_frame = frame

                upload_frame = self._get_cropped_frame(settled_frame)

                # Multi-page Scroll Flow if BR
                scroll_count = max(0, int(self.config.get("scrollCount", 0)))
                scroll_frames = []
                if scroll_count > 0 and mode == "BR":
                    self.log_message.emit(self.serial, f"[SCROLL] Initializing Multi-Page Scroll Flow ({scroll_count} swipes)...", "SCROLL")
                    c2x = float(self.config.get("crop2X", 0.03))
                    c2y = float(self.config.get("crop2Y", 0.22))
                    c2w = float(self.config.get("crop2W", 0.93))
                    c2h = float(self.config.get("crop2H", 0.66))

                    swipe_x = c2x + c2w / 2.0
                    swipe_y_start = c2y + c2h * 0.90
                    swipe_y_end = c2y + c2h * 0.15

                    for i in range(scroll_count):
                        self.service.swipe_normalized(self.serial, swipe_x, swipe_y_start, swipe_x + 0.02, swipe_y_end, 400)
                        scrolled_shot = self.service.capture_frame(self.serial)
                        if scrolled_shot:
                            scroll_frames.append(self._get_crop2_frame(scrolled_shot))

                # Extract Winners if Lone Wolf / Clash Squad / Lose To Win
                detected_winners_str = ""
                winner_details: Optional[Dict[str, Any]] = None
                game_mode_label = self.config.get("gameModeType")
                if not game_mode_label:
                    from src.core.preset_service import get_default_game_mode_type_for_preset
                    game_mode_label = get_default_game_mode_type_for_preset(
                        self.config.get("preset", ""),
                        mode=mode
                    )

                if mode in ("LW", "CS") or self.config.get("detectWinners", False):
                    try:
                        from src.core.winner_detector import LoneWolfWinnerDetector
                        detector = LoneWolfWinnerDetector()
                        # Perform winner detection directly on the cropped scoreboard frame
                        winner_details = detector.determine_match_winners(upload_frame, game_mode=game_mode_label)
                        winners_list = winner_details.get("winners", [])
                        if winners_list:
                            detected_winners_str = ", ".join(winners_list)
                            win_tag = "[LTW Losers]" if winner_details.get("is_ltw") else "[Winners]"
                            self.log_message.emit(self.serial, f"{win_tag} Detected: {detected_winners_str} ({game_mode_label})", "MATCH")

                            # Trigger Auto Rewards concurrently in background thread immediately upon match detection
                            if self.config.get("autoRewards", False):
                                master_serial = self.config.get("autoRewardMaster") or self.config.get("autoHostMaster")
                                if master_serial and master_serial != "None":
                                    self.log_message.emit(
                                        self.serial,
                                        f"Initiating Auto Rewards for [{detected_winners_str}] on Master {master_serial} (Concurrent)...",
                                        "REWARD"
                                    )
                                    import threading
                                    def _run_rewards_async(m_ser, w_list, g_lbl, is_ltw_val, l_int, l_off):
                                        try:
                                            from src.core.master_service import MasterCoordinatorService
                                            m_coord = MasterCoordinatorService(self.service)
                                            m_coord.auto_reward_match(
                                                game_serial=self.serial,
                                                master_serial=m_ser,
                                                winners=w_list,
                                                game_mode=g_lbl,
                                                interval_m=l_int,
                                                offset_m=l_off,
                                                is_ltw=is_ltw_val,
                                                log_callback=lambda msg, lvl: self.log_message.emit(self.serial, msg, lvl)
                                            )
                                        except Exception as re:
                                            self.log_message.emit(self.serial, f"Auto Rewards error: {re}", "ERROR")

                                    r_thread = threading.Thread(
                                        target=_run_rewards_async,
                                        args=(
                                            master_serial,
                                            list(winners_list),
                                            game_mode_label,
                                            bool(winner_details.get("is_ltw", False)),
                                            int(self.config.get("logInterval", 15)),
                                            int(self.config.get("logOffset", 0))
                                        ),
                                        daemon=True
                                    )
                                    r_thread.start()
                        else:
                            self.log_message.emit(self.serial, "Scoreboard parsed: No clear winning nicknames identified", "SCAN")
                    except Exception as we:
                        logger.error(f"Winner detection error: {we}")

                # Persist match capture to database
                try:
                    db = MatchDatabase.get()
                    safe_serial = self.serial.replace(":", "_").replace(".", "_")
                    base_ts = int(time.time())
                    filename = f"match_{base_ts}_{safe_serial}.png"
                    save_path = os.path.join(db.get_captures_dir(), filename)
                    upload_frame.save(save_path, format="PNG")
                    db.save_match(self.serial, alias, mode, state, raw_text, save_path, winners=detected_winners_str)

                    for idx, s_frame in enumerate(scroll_frames):
                        s_filename = f"match_{base_ts}_{safe_serial}_scroll{idx + 1}.png"
                        s_path = os.path.join(db.get_captures_dir(), s_filename)
                        s_frame.save(s_path, format="PNG")
                except Exception as e:
                    logger.error(f"Error persisting match capture: {e}")

                # Discord Webhook
                webhook_url = self.config.get("webhook", "").strip()
                if webhook_url:
                    interval_m = int(self.config.get("logInterval", 15))
                    offset_m = int(self.config.get("logOffset", 0))
                    display_time = get_rounded_time(time.time(), interval_m, offset_m)

                    embed_desc = None
                    if self.config.get("esportsMode", False):
                        try:
                            from src.core.esports_calculator import parse_esports_scoreboard
                            kill_pts = int(self.config.get("esportsKillPoints", 1))
                            place_pts = self.config.get("esportsPlacementPoints", [12, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 0])
                            c_y = float(self.config.get("cropY", 0.22) or 0.22)
                            c_h = float(self.config.get("cropH", 0.66) or 0.66)
                            embed_desc = parse_esports_scoreboard(
                                settled_frame,
                                kill_multiplier=kill_pts,
                                placement_points=place_pts,
                                crop_y=c_y,
                                crop_h=c_h
                            )
                        except Exception as pe:
                            logger.error(f"Esports calculation error: {pe}")
                    elif detected_winners_str:
                        w_list = winner_details.get("winners", [])
                        if w_list:
                            embed_desc = "\n".join(f"> `{w}`" for w in w_list)
                        else:
                            embed_desc = f"> `{detected_winners_str}`"

                    msg_extra = f" (+ {len(scroll_frames)} scroll screenshots)" if scroll_frames else ""
                    self.log_message.emit(self.serial, f"Posting match summary ({display_time}){msg_extra} to Discord...", "DISCORD")
                    ok, msg = send_discord_webhook(
                        webhook_url, alias, mode, upload_frame, raw_text,
                        display_time=display_time, additional_images=scroll_frames,
                        description=embed_desc
                    )
                    lvl = "SUCCESS" if ok else "ERROR"
                    self.log_message.emit(self.serial, f"Discord Webhook: {msg}", lvl)

                # Auto-Return to Lobby (Dynamic Coordinates based on Game Mode or Custom Config)
                if self.config.get("autoLobbyReturn", False):
                    # 1. Check custom overrides from node configuration
                    cfg_x = self.config.get("lobbyReturnX")
                    cfg_y = self.config.get("lobbyReturnY")

                    if cfg_x is not None and cfg_y is not None:
                        tap_x, tap_y = float(cfg_x), float(cfg_y)
                        coord_source = "custom preset"
                    elif mode == "CS":
                        # Clash Squad scoreboard Return button position
                        tap_x, tap_y = 0.88, 0.92
                        coord_source = "CS mode preset"
                    elif mode == "LW":
                        # Lone Wolf match conclusion Return button position
                        tap_x, tap_y = 0.85, 0.90
                        coord_source = "LW mode preset"
                    else:
                        # Battle Royale standard scoreboard Return button position
                        tap_x, tap_y = 0.86, 0.91
                        coord_source = "BR standard preset"

                    self.log_message.emit(
                        self.serial,
                        f"Tapping Back to Lobby button at ({tap_x:.2f}, {tap_y:.2f}) [{coord_source}]...",
                        "LOBBY"
                    )
                    self.service.tap_normalized(self.serial, tap_x, tap_y)

                    if self.config.get("autoCloseRoom", False):
                        self.log_message.emit(self.serial, "LOBBY: Waiting 3s for lobby to settle before Auto Close Room...", "LOBBY")
                        self.msleep(3000)
                        self._perform_close_room_flow()

                # Cooldown / Sleep Time
                sleep_min = float(self.config.get("sleepTime", 0))
                if sleep_min > 0:
                    sleep_sec = int(sleep_min * 60.0)
                    self.state_changed.emit(self.serial, "SLEEP")
                    self.log_message.emit(self.serial, f"Post-match cooldown: Pausing scans for {sleep_min} min...", "SLEEP")
                    for _ in range(sleep_sec):
                        if not self._is_running:
                            break
                        self.msleep(1000)
                    return

            # 5. Handle Lobby Screen & Match Schedule Lead Time Trigger
            elif state in ("LOBBY_SCREEN", "CUSTOM_ROOM_SCREEN"):
                is_home = details.get("is_home_lobby", True) if isinstance(details, dict) else True
                auto_room = self.config.get("autoRoomCreation", False)
                actions = self.config.get("autoHostActions", [])

                if state == "CUSTOM_ROOM_SCREEN":
                    if self.config.get("autoCloseRoom", False) and not self.has_run_room_creation:
                        self._handle_custom_room_screen()

                if auto_room and actions and not self.has_run_room_creation and not self.is_executing_sequence:
                    interval_m = int(self.config.get("logInterval", 15) or 15)
                    offset_m = int(self.config.get("logOffset", 0) or 0)
                    next_match_sec = get_next_match_time_sec(now, interval_m, offset_m)
                    time_until_match_sec = next_match_sec - now

                    lead_time_min = int(self.config.get("autoHostLeadTime", 5) or 5)
                    lead_time_sec = lead_time_min * 60.0

                    # Check if next match schedule has changed
                    if self.last_room_creation_match_sec and next_match_sec > self.last_room_creation_match_sec:
                        self.log_message.emit(self.serial, "Previous match time passed. Resetting Auto Host sequence for next match.", "AUTO_HOST")
                        self.has_run_room_creation = False
                        self.last_room_creation_match_sec = None

                    if time_until_match_sec > lead_time_sec:
                        if now - self.last_auto_host_wait_log_time >= 15.0:
                            self.last_auto_host_wait_log_time = now
                            wait_sec = int(time_until_match_sec - lead_time_sec)
                            display_next = get_rounded_time(next_match_sec, interval_m, offset_m)
                            self.log_message.emit(
                                self.serial,
                                f"AUTO_HOST: Next match scheduled for {display_next} ({int(time_until_match_sec // 60)}m away). "
                                f"Lead time is {lead_time_min}m. Waiting {wait_sec // 60}m {wait_sec % 60}s before hosting...",
                                "AUTO_HOST"
                            )
                    else:
                        # Lead time reached! Trigger Room Creation Sequence
                        self.log_message.emit(
                            self.serial,
                            f"AUTO_HOST: Lead time reached ({lead_time_min}m before match). Triggering Room Creation sequence for {alias}...",
                            "AUTO_HOST"
                        )
                        self.has_run_room_creation = True
                        self.last_room_creation_match_sec = next_match_sec
                        self._execute_auto_host_sequence(actions)

        except Exception as e:
            self.log_message.emit(self.serial, f"Worker error: {str(e)}", "ERROR")

    def _execute_auto_host_sequence(self, actions: List[Dict[str, Any]]):
        """Executes room creation step sequence in the background worker thread without blocking GUI."""
        if not actions or self.is_executing_sequence:
            return
        self.is_executing_sequence = True
        try:
            for index, step in enumerate(actions):
                if not self._is_running:
                    break
                step_type = step.get("type", "click")
                delay_sec = float(step.get("delay", 2.0) or 2.0)
                step_num = index + 1
                if step_type == "click":
                    x = float(step.get("x", 0.5) or 0.5)
                    y = float(step.get("y", 0.5) or 0.5)
                    self.log_message.emit(self.serial, f"AUTO_HOST: Step {step_num} - Clicking at [{x * 100:.1f}%, {y * 100:.1f}%]...", "AUTO_HOST")
                    self.service.tap_normalized(self.serial, x, y)
                elif step_type == "slide":
                    sx = float(step.get("startX", 0.5) or 0.5)
                    sy = float(step.get("startY", 0.5) or 0.5)
                    ex = float(step.get("endX", 0.5) or 0.5)
                    ey = float(step.get("endY", 0.5) or 0.5)
                    self.log_message.emit(self.serial, f"AUTO_HOST: Step {step_num} - Sliding from [{sx * 100:.1f}%, {sy * 100:.1f}%] to [{ex * 100:.1f}%, {ey * 100:.1f}%]...", "AUTO_HOST")
                    self.service.swipe_normalized(self.serial, sx, sy, ex, ey, 600)
                elif step_type == "text":
                    # Check if this text step is tagged as the dynamic Room Password
                    if step.get("isPassword") or step.get("role") == "room_password":
                        text = str(self.config.get("autoHostPassword") or step.get("text", "")).strip()
                        self.log_message.emit(self.serial, f"AUTO_HOST: Step {step_num} - Typing dynamic Room Password '{text}'...", "AUTO_HOST")
                    else:
                        text = str(step.get("text", ""))
                        self.log_message.emit(self.serial, f"AUTO_HOST: Step {step_num} - Typing text '{text}'...", "AUTO_HOST")
                    
                    self.service.input_text(self.serial, text)

                wait_sec = max(0.1, delay_sec)
                for _ in range(int(wait_sec * 10)):
                    if not self._is_running:
                        break
                    self.msleep(100)

            if self._is_running:
                self.log_message.emit(self.serial, "AUTO_HOST: Room Creation sequence completed successfully.", "SUCCESS")
                
                # Check if Master Emulator sync is configured
                master_serial = self.config.get("autoHostMaster", "").strip()
                if master_serial and master_serial.lower() != "none":
                    self.log_message.emit(self.serial, f"MASTER_CONNECT: Connecting with Master Emulator [{master_serial}]...", "MASTER")
                    try:
                        from src.core.master_service import MasterCoordinatorService
                        master_svc = MasterCoordinatorService(self.service)
                        
                        # Extract password from config or text step
                        room_pw = self.config.get("autoHostPassword", "")
                        if not room_pw:
                            for step in steps:
                                if step.get("type") == "text":
                                    room_pw = str(step.get("text", "")).strip()
                                    break
                        
                        # Tap Copy Room ID button on the Game Emulator
                        copy_x = self.config.get("autoHostClickX")
                        copy_y = self.config.get("autoHostClickY")
                        if copy_x is not None and copy_y is not None:
                            self.log_message.emit(self.serial, f"AUTO_HOST: Tapping 'Copy Room ID' button at [{float(copy_x)*100:.1f}%, {float(copy_y)*100:.1f}%]...", "AUTO_HOST")
                            for _ in range(2):
                                self.service.tap_normalized(self.serial, float(copy_x), float(copy_y))
                                self.msleep(600)

                        # Read Room ID from clipboard
                        room_id = ""
                        try:
                            from PyQt6.QtWidgets import QApplication
                            cb = QApplication.clipboard()
                            for _ in range(5):
                                if cb:
                                    raw_cb = cb.text().strip()
                                    m = re.search(r'\b\d{5,10}\b', raw_cb)
                                    if m:
                                        room_id = m.group(0)
                                        break
                                self.msleep(400)
                        except Exception:
                            pass
                        
                        if room_id:
                            self.log_message.emit(self.serial, f"AUTO_HOST: Copied Room ID: '{room_id}'", "SUCCESS")
                        else:
                            self.log_message.emit(self.serial, "AUTO_HOST WARN: Could not read Room ID from clipboard.", "WARN")
                        
                        game_mode_label = self.config.get("gameModeType", "Lone Wolf 2V2")
                        interval_m = int(self.config.get("logInterval", 15))
                        offset_m = int(self.config.get("logOffset", 0))

                        master_svc.dispatch_room_credentials(
                            game_serial=self.serial,
                            master_serial=master_serial,
                            room_id=room_id,
                            password=room_pw,
                            game_mode=game_mode_label,
                            interval_m=interval_m,
                            offset_m=offset_m,
                            log_callback=lambda msg, lvl: self.log_message.emit(self.serial, f"MASTER: {msg}", lvl)
                        )
                    except Exception as me:
                        logger.error(f"Failed to synchronize with Master Emulator: {me}")
                        self.log_message.emit(self.serial, f"MASTER ERROR: {me}", "ERROR")
        finally:
            self.is_executing_sequence = False

    def _perform_close_room_flow(self):
        """Executes the room close tap sequence in background thread."""
        if not self._is_running or not self.config.get("autoCloseRoom", False):
            return

        settings = load_app_settings()
        cx = float(settings.get("closeRoomX", 0.982))
        cy = float(settings.get("closeRoomY", 0.046))
        c_delay = float(settings.get("closeRoomDelay", 8.0))

        cfx = float(settings.get("confirmCloseX", 0.873))
        cfy = float(settings.get("confirmCloseY", 0.621))
        cf_delay = float(settings.get("confirmCloseDelay", 4.0))

        ex = float(settings.get("extraCloseX", 0.975))
        ey = float(settings.get("extraCloseY", 0.033))
        e_delay = float(settings.get("extraCloseDelay", 2.0))

        self.log_message.emit(self.serial, f"AUTO_CLOSE: Waiting {c_delay}s before Close Room click...", "AUTO_CLOSE")
        self.msleep(int(c_delay * 1000))
        if not self._is_running:
            return

        self.log_message.emit(self.serial, f"AUTO_CLOSE: Tapping Close Room at [{cx*100:.1f}%, {cy*100:.1f}%]...", "AUTO_CLOSE")
        self.service.tap_normalized(self.serial, cx, cy)
        self.msleep(int(cf_delay * 1000))
        if not self._is_running:
            return

        self.log_message.emit(self.serial, f"AUTO_CLOSE: Tapping Confirm Close at [{cfx*100:.1f}%, {cfy*100:.1f}%]...", "AUTO_CLOSE")
        self.service.tap_normalized(self.serial, cfx, cfy)
        self.msleep(int(e_delay * 1000))
        if not self._is_running:
            return

        self.log_message.emit(self.serial, f"AUTO_CLOSE: Tapping Extra Close at [{ex*100:.1f}%, {ey*100:.1f}%]...", "AUTO_CLOSE")
        self.service.tap_normalized(self.serial, ex, ey)
        self.log_message.emit(self.serial, "AUTO_CLOSE: Room Close sequence finished.", "SUCCESS")

    def _handle_custom_room_screen(self):
        """Backs out from Custom Room Screen using Extra Close button coordinate."""
        settings = load_app_settings()
        ex = float(settings.get("extraCloseX", 0.975))
        ey = float(settings.get("extraCloseY", 0.033))
        e_delay = float(settings.get("extraCloseDelay", 2.0))

        self.log_message.emit(self.serial, f"AUTO_CLOSE: Custom Room Screen detected. Tapping Extra Close in {e_delay}s...", "AUTO_CLOSE")
        self.msleep(int(e_delay * 1000))
        if self._is_running:
            self.service.tap_normalized(self.serial, ex, ey)
