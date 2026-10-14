import re
import math
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from PIL import Image, ImageDraw

def jaro_winkler_similarity(s1: str, s2: str, p: float = 0.1) -> float:
    """
    Exact implementation of Jaro-Winkler distance algorithm from the legacy app.
    """
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0

    match_distance = max(len1, len2) // 2 - 1
    if match_distance < 0:
        match_distance = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2
    matches = 0

    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)
        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    transpositions = 0
    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    transpositions /= 2.0
    jaro = (matches / len1 + matches / len2 + (matches - transpositions) / matches) / 3.0

    prefix = 0
    max_prefix = min(4, min(len1, len2))
    for i in range(max_prefix):
        if s1[i] == s2[i]:
            prefix += 1
        else:
            break

    return jaro + prefix * p * (1.0 - jaro)


def are_names_similar(client_name: str, master_name: str) -> bool:
    """
    Port of `areNamesSimilar` from legacy adb-rewards.js:
    Uses regex cleaning, consecutive letter collapsing (e.g., 'SAAAAD' -> 'SAD'),
    word-level Jaro-Winkler with initial letter constraints, and proportional
    substring coverage.
    """
    def clean(s: str) -> str:
        s_clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', s)
        return re.sub(r'\s+', ' ', s_clean).strip().lower()

    def dedup(s: str) -> str:
        # Collapse consecutive repeated characters: 'SAAAAD' -> 'sad'
        return re.sub(r'(.)\1+', r'\1', s, flags=re.IGNORECASE)

    c_clean = clean(client_name)
    m_clean = clean(master_name)

    if not c_clean:
        c_clean = client_name.strip().lower()
    if not m_clean:
        m_clean = master_name.strip().lower()

    if not c_clean or not m_clean:
        return False
    if c_clean == m_clean:
        return True

    c_dedup = dedup(c_clean)
    m_dedup = dedup(m_clean)
    if c_dedup == m_dedup:
        return True

    c_words = [w for w in c_clean.split(' ') if len(w) > 0]
    m_words = [w for w in m_clean.split(' ') if len(w) > 0]

    for cw in c_words:
        if len(cw) <= 2:
            continue
        for mw in m_words:
            if len(mw) <= 2:
                continue
            if cw == mw:
                return True
            if dedup(cw) == dedup(mw):
                return True

            same_first = cw[0] == mw[0]
            min_jw = 0.88 if (len(cw) <= 5 or len(mw) <= 5) else 0.80
            if same_first:
                jw_score = jaro_winkler_similarity(cw, mw)
                if jw_score >= min_jw:
                    return True
                if jaro_winkler_similarity(dedup(cw), dedup(mw)) >= min_jw:
                    return True

    c_no_space = c_clean.replace(' ', '')
    m_no_space = m_clean.replace(' ', '')
    if c_no_space == m_no_space:
        return True

    c_dedup_no_space = dedup(c_no_space)
    m_dedup_no_space = dedup(m_no_space)
    if c_dedup_no_space == m_dedup_no_space:
        return True

    # 1. Jaro-Winkler Confidence
    jw_score = max(
        jaro_winkler_similarity(c_no_space, m_no_space),
        jaro_winkler_similarity(c_dedup_no_space, m_dedup_no_space)
    )

    # 2. Substring Containment Confidence
    substring_score = 0.0
    if c_no_space in m_no_space and len(m_no_space) > 0:
        substring_score = len(c_no_space) / len(m_no_space)
    elif m_no_space in c_no_space and len(c_no_space) > 0:
        substring_score = len(m_no_space) / len(c_no_space)

    if c_dedup_no_space in m_dedup_no_space and len(m_dedup_no_space) > 0:
        substring_score = max(substring_score, len(c_dedup_no_space) / len(m_dedup_no_space))
    elif m_dedup_no_space in c_dedup_no_space and len(c_dedup_no_space) > 0:
        substring_score = max(substring_score, len(m_dedup_no_space) / len(c_dedup_no_space))

    highest_confidence = max(jw_score, substring_score)

    shortest_len = min(len(c_no_space), len(m_no_space))
    if shortest_len <= 2:
        required_confidence = 0.90
    elif shortest_len <= 4:
        required_confidence = 0.65
    else:
        required_confidence = 0.75

    same_first_char = c_no_space[0] == m_no_space[0] if (c_no_space and m_no_space) else False
    if not same_first_char:
        required_confidence = max(required_confidence, 0.80)

    return highest_confidence >= required_confidence


_winner_paddle_ocr = None

def get_winner_ocr():
    global _winner_paddle_ocr
    try:
        from src.core.resource_governor import ResourceGovernor
        return ResourceGovernor.get().get_shared_ocr()
    except Exception:
        if _winner_paddle_ocr is None:
            from paddleocr import PaddleOCR
            _winner_paddle_ocr = PaddleOCR(
                ocr_version='PP-OCRv4',
                use_angle_cls=False,
                lang='en',
                show_log=False,
                enable_mkldnn=False,
                cpu_threads=1,
                drop_score=0.45,
                det_limit_side_len=960,
                det_limit_type='max'
            )
        return _winner_paddle_ocr


class LoneWolfWinnerDetector:
    """
    Lone Wolf / Clash Squad Scoreboard Winner Detection Engine.
    Uses PaddleOCR with blackout masking, vertical midpoint bisection
    (top1 vs top2), and horizontal slot separation.
    """
    def __init__(self, ocr_engine=None):
        self._custom_ocr = ocr_engine

    @property
    def _ocr(self):
        if self._custom_ocr is not None:
            return self._custom_ocr
        return get_winner_ocr()

    def extract_winners_and_losers(self, image: Image.Image) -> Dict[str, Any]:
        """
        Parses scoreboard to extract Top 1 (Winners) and Top 2 (Losers).
        Returns:
            {
                "top1": ["Player 1", "Player 2"],
                "top2": ["Player 3", "Player 4"],
                "top1_count": 2,
                "top2_count": 2,
                "active_slots": 4
            }
        """
        img = image.convert("RGB")
        width, height = img.size

        # If full screen 16:9 (e.g. 1280x720 or 1920x1080), crop to standard LW scoreboard first
        is_already_cropped = (height < 650 or width < 1000)
        if is_already_cropped:
            crop_img = img.copy()
            crop_w, crop_h = width, height
        else:
            crop_left = int(width * 0.02)
            crop_top = int(height * 0.20)
            crop_w = int(width * 0.54)
            crop_h = int(height * 0.26)
            crop_img = img.crop((crop_left, crop_top, crop_left + crop_w, crop_top + crop_h))

        cw, ch = crop_img.size

        # Standardized Calibrated Slot Grids (matching Clash Squad architecture)
        # Vertical Heights:
        # Top 1 Row: y = 8% to 48% (perfectly centered within Row 1 banner)
        # Top 2 Row: y = 56% to 94% (perfectly centered within Row 2 banner)
        # Horizontal Widths:
        # Player Slot 1 (Left):  x = 16% to 38% (width = 22%, perfectly framed between badge and eliminations)
        # Player Slot 2 (Right): x = 58% to 80% (width = 22%, perfectly matching Slot 1 width and row alignment)
        slot_definitions = {
            "top1_p1": (int(cw * 0.16), int(ch * 0.08), int(cw * 0.38), int(ch * 0.48)),
            "top1_p2": (int(cw * 0.58), int(ch * 0.08), int(cw * 0.80), int(ch * 0.48)),
            "top2_p1": (int(cw * 0.16), int(ch * 0.56), int(cw * 0.38), int(ch * 0.94)),
            "top2_p2": (int(cw * 0.58), int(ch * 0.56), int(cw * 0.80), int(ch * 0.94)),
        }

        def extract_slot_name(box_coords: Tuple[int, int, int, int]) -> Optional[str]:
            x1, y1, x2, y2 = box_coords
            slot_card = crop_img.crop((x1, y1, x2, y2))
            np_slot = np.array(slot_card)
            try:
                from src.core.resource_governor import ResourceGovernor
                ocr_out = ResourceGovernor.get().run_inference_guarded(self._ocr.ocr, np_slot, cls=False)
            except Exception:
                try:
                    ocr_out = self._ocr.ocr(np_slot, cls=False)
                except Exception:
                    ocr_out = None

            if not ocr_out or not ocr_out[0]:
                return None

            tokens = []
            for item in ocr_out[0]:
                if not item or len(item) < 2:
                    continue
                t = item[1][0] if isinstance(item[1], (list, tuple)) else str(item[1])
                t = t.strip()
                if not t:
                    continue
                # Ignore noise and accidental stats bleed
                if re.search(r'liminat', t, re.IGNORECASE) or re.match(r'^(FREE|FIRE|ELIMINATIONS)$', t, re.IGNORECASE):
                    continue
                # Sort token by x coordinate for accurate left-to-right name assembly
                bx = min(p[0] for p in item[0])
                tokens.append((bx, t))

            if not tokens:
                return None

            tokens.sort(key=lambda x: x[0])
            assembled_name = " ".join(t[1] for t in tokens)
            return assembled_name if len(assembled_name) >= 2 else None

        # Extract calibrated slots
        top1_p1 = extract_slot_name(slot_definitions["top1_p1"])
        top1_p2 = extract_slot_name(slot_definitions["top1_p2"])
        top2_p1 = extract_slot_name(slot_definitions["top2_p1"])
        top2_p2 = extract_slot_name(slot_definitions["top2_p2"])

        top1_names = [name for name in (top1_p1, top1_p2) if name]
        top2_names = [name for name in (top2_p1, top2_p2) if name]

        active_slots = len(top1_names) + len(top2_names)

        return {
            "top1": top1_names,
            "top2": top2_names,
            "top1_count": len(top1_names),
            "top2_count": len(top2_names),
            "active_slots": active_slots
        }

    def extract_clash_squad_winners(self, image: Image.Image) -> Dict[str, Any]:
        """
        Parses Clash Squad 4v4 end-of-match screen.
        Winners are located on the Left Column (Team 1, e.g. Howlers).
        Extracts all 4 player nicknames using calibrated slot vision boxes
        while masking out avatars and K/D/A/Damage statistics.
        """
        img = image.convert("RGB")
        width, height = img.size

        # If full 16:9 screen (e.g. 1280x720 or 1920x1080)
        # Left Winning Column sits between:
        # x: 2.5% to 49.0%
        # y: 44.0% to 77.0%
        col_x1 = int(width * 0.025)
        col_x2 = int(width * 0.490)
        col_y1 = int(height * 0.440)
        col_y2 = int(height * 0.770)

        cs_left = img.crop((col_x1, col_y1, col_x2, col_y2))
        cw, ch = cs_left.size
        card_h = ch / 4.0

        av_w = int(cw * 0.18)
        st_start = int(cw * 0.54)

        winners_list: List[str] = []

        # Iterate over each of the 4 vertical player slots
        for i in range(4):
            y_start = int(i * card_h)
            y_end = int((i + 1) * card_h)
            box_x1 = av_w
            box_x2 = st_start

            # Crop the designated nickname vision box for this slot
            slot_box = cs_left.crop((box_x1, y_start, box_x2, y_end))
            np_slot = np.array(slot_box)

            try:
                from src.core.resource_governor import ResourceGovernor
                ocr_out = ResourceGovernor.get().run_inference_guarded(self._ocr.ocr, np_slot, cls=False)
            except Exception:
                try:
                    ocr_out = self._ocr.ocr(np_slot, cls=False)
                except Exception:
                    ocr_out = None

            if ocr_out and ocr_out[0]:
                # Collect lines found in this slot box
                raw_lines = []
                for item in ocr_out[0]:
                    if item and len(item) >= 2:
                        t = item[1][0] if isinstance(item[1], (list, tuple)) else str(item[1])
                        t = t.strip()
                        if t and len(t) >= 2 and not re.match(r'^(FREE|FIRE|ELIMINATIONS)$', t, re.IGNORECASE):
                            raw_lines.append(t)

                if raw_lines:
                    # In Clash Squad player cards, the top line is the player's true In-Game Name (IGN),
                    # while subsequent lines (if any) are guild tag subtitles (e.g., TeamArmySq, NEKULB CITY).
                    ign = raw_lines[0]
                    winners_list.append(ign)

        # Right Column (Runners-up / Losers)
        # x: 50.8% to 97.5%
        # y: 44.0% to 77.0%
        r_col_x1 = int(width * 0.508)
        r_col_x2 = int(width * 0.975)
        cs_right = img.crop((r_col_x1, col_y1, r_col_x2, col_y2))
        rcw, rch = cs_right.size
        rcard_h = rch / 4.0
        rav_w = int(rcw * 0.18)
        rst_start = int(rcw * 0.54)

        losers_list: List[str] = []
        for i in range(4):
            y_start = int(i * rcard_h)
            y_end = int((i + 1) * rcard_h)
            r_slot_box = cs_right.crop((rav_w, y_start, rst_start, y_end))
            np_rslot = np.array(r_slot_box)

            try:
                from src.core.resource_governor import ResourceGovernor
                r_ocr_out = ResourceGovernor.get().run_inference_guarded(self._ocr.ocr, np_rslot, cls=False)
            except Exception:
                try:
                    r_ocr_out = self._ocr.ocr(np_rslot, cls=False)
                except Exception:
                    r_ocr_out = None

            if r_ocr_out and r_ocr_out[0]:
                r_raw_lines = []
                for item in r_ocr_out[0]:
                    if item and len(item) >= 2:
                        t = item[1][0] if isinstance(item[1], (list, tuple)) else str(item[1])
                        t = t.strip()
                        if t and len(t) >= 2 and not re.match(r'^(FREE|FIRE|ELIMINATIONS)$', t, re.IGNORECASE):
                            r_raw_lines.append(t)
                if r_raw_lines:
                    losers_list.append(r_raw_lines[0])

        return {
            "top1": winners_list,
            "top2": losers_list,
            "top1_count": len(winners_list),
            "top2_count": len(losers_list),
            "active_slots": len(winners_list) + len(losers_list)
        }

    def determine_match_winners(
        self,
        image: Image.Image,
        game_mode: str = "Lone Wolf"
    ) -> Dict[str, Any]:
        """
        Determines the true winning players based on game mode:
        - Clash Squad (CS): Left column 4v4 slot vision boxes
        - Normal Lone Wolf: Top row 1v1 / 2v2 winners
        - Lose To Win (LTW): Inverted winners (losing team receives awards)
        """
        is_cs = "clash" in game_mode.lower() or "cs" in game_mode.lower()

        if is_cs:
            ocr_result = self.extract_clash_squad_winners(image)
        else:
            ocr_result = self.extract_winners_and_losers(image)

        is_ltw = "lose" in game_mode.lower() or "ltw" in game_mode.lower()

        if is_ltw:
            # In Lose-To-Win, winners are top2 (the losing team)
            target_winners = ocr_result["top2"] if ocr_result["top2"] else []
        else:
            target_winners = ocr_result["top1"] if ocr_result["top1"] else []

        return {
            "winners": target_winners,
            "is_ltw": is_ltw,
            "top1": ocr_result["top1"],
            "top2": ocr_result["top2"],
            "active_slots": ocr_result["active_slots"]
        }
