import re
import logging
from typing import Tuple, Dict, Any, Optional
import numpy as np
from PIL import Image
from paddleocr import PaddleOCR

logger = logging.getLogger(__name__)

# Initialize native PaddleOCR engine matching old app parameters (Highest tier PP-OCRv4, Single-Threaded)
_ocr_engine = PaddleOCR(
    ocr_version='PP-OCRv4',
    use_angle_cls=False,
    lang='en',
    show_log=False,
    enable_mkldnn=False,
    cpu_threads=1,
    drop_score=0.60
)

def compute_dhash(image: Image.Image) -> str:
    """
    Computes an 8x8 difference hash (dHash) to detect screen changes with negligible CPU.
    """
    try:
        # Resize to 9x8 grayscale
        resized = image.convert("L").resize((9, 8), Image.Resampling.BILINEAR)
        get_data_fn = getattr(resized, "get_flattened_data", resized.getdata)
        pixels = list(get_data_fn())
        diff = []
        for row in range(8):
            for col in range(8):
                idx = row * 9 + col
                diff.append(pixels[idx] > pixels[idx + 1])
        # Convert bool array to 16-hex character string
        val = 0
        for b in diff:
            val = (val << 1) | int(b)
        return f"{val:016x}"
    except Exception:
        return ""

def hamming_distance(hash1: str, hash2: str) -> int:
    """Calculates bitwise difference between two hashes"""
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return 999
    try:
        val1 = int(hash1, 16)
        val2 = int(hash2, 16)
        xor_val = val1 ^ val2
        return bin(xor_val).count("1")
    except Exception:
        return 999

def detect_match_state(image: Image.Image, target_mode: str = "AUTO") -> Tuple[str, str, Dict[str, Any]]:
    """
    Analyzes an emulator screenshot to classify current screen state:
    Returns: (state, detected_text, details)
    - RESULT_SCREEN: Match finished (Victory, Defeat, Booyah, Eliminations, Scoreboard)
    - IN_GAME: Match actively in progress (HP bar, match clock, Alive count)
    - LOBBY_SCREEN: In game lobby / room
    - IDLE: Menu or transitional screen
    """
    try:
        img_np = np.array(image.convert("RGB"))
        ocr_out = _ocr_engine.ocr(img_np, cls=False)
    except Exception as e:
        return "IDLE", "", {"error": str(e)}

    if not ocr_out or not ocr_out[0]:
        return "IDLE", "", {}

    # PaddleOCR returns [ [ [ [x,y]... ], (text, confidence) ], ... ]
    raw_lines = []
    for line in ocr_out[0]:
        if line and len(line) >= 2 and line[1]:
            text = line[1][0] if isinstance(line[1], (list, tuple)) else str(line[1])
            if text:
                raw_lines.append(text.upper())

    raw_text = " ".join(raw_lines)
    clean_text = re.sub(r'[^A-Z0-9]', '', raw_text)

    # Word boundary checker on raw text
    def matches_word(target: str) -> bool:
        escaped = re.escape(target)
        return bool(re.search(r'\b' + escaped + r'\b', raw_text, re.IGNORECASE))

    def matches(target: str) -> bool:
        return target in clean_text

    # 1. In-Game HUD Signal Detection (exact parity with parseIngameSignals from old app)
    has_hpep = bool(re.search(r'\b(HP|EP)\s*\d+\/\d+\b', raw_text, re.IGNORECASE))
    has_hp_bar = bool(re.search(r'\b(HP|EP)\s*\d+', raw_text, re.IGNORECASE)) or bool(re.search(r'\b\d{3}\/\d{3}\b', raw_text))
    has_distance = bool(re.search(r'(?:^|\s)\d{2,}\s*[mM]\b', raw_text)) or matches("METER") or matches("METERS")
    has_objective = bool(re.search(r'objecti', raw_text, re.IGNORECASE))
    has_game_timer = bool(re.search(r'\b0\d:\d{2}\b', raw_text))

    is_ingame_strong = (
        matches("OBJECTIVE") or matches("SPECTATING") or matches("SPECTAT") or matches("5PECTAT") or
        matches("SPECTATOR") or matches("SURVIVE") or matches("ALIVE") or matches("AL1VE") or
        matches("SAFEZONE") or matches("S4FE") or matches("ZONE") or matches("Z0NE") or matches("SHRINKING") or
        has_hpep or has_hp_bar or has_game_timer or has_objective or
        matches("ARMOR") or matches("MEDKIT") or matches("BACKPACK") or
        matches("FOLLOWING") or matches("WATCHING") or matches("NEARBY") or matches("KNOCKED") or
        has_distance
    )
    is_ingame_definitive = has_objective or has_hp_bar or has_game_timer or matches("NEARBY") or matches("SPECTATING")

    # 2. Custom Room Screen & Lobby detection
    has_custom_word = matches_word("CUSTOM") or matches_word("CUST0M")
    has_casual = matches_word("CASUAL") or matches_word("CASU4L")
    has_league = matches_word("LEAGUE") or matches_word("LEAG")
    has_craftland = matches_word("CRAFTLAND") or matches_word("CRAFT")
    has_create = matches_word("CREATE") or matches_word("CRE4TE")
    has_quick_join = matches_word("QUICKJOIN") or (matches_word("QUICK") and matches_word("JOIN"))
    custom_room_evidence = sum([has_casual, has_league, has_craftland, has_create, has_quick_join])

    has_status_header = (
        matches("VICTORY") or matches("V1CTORY") or matches("VICT0RY") or
        matches("DEFEAT") or matches("MATCHOVER") or matches("SCOREBOARD") or
        (("BOOYA" in clean_text or "B00YA" in clean_text or "BOOFAH" in clean_text or "BOOAYH" in clean_text)
         and not any(p in clean_text for p in ["PASS", "P4SS", "PA5S"]))
    )

    if has_custom_word and custom_room_evidence >= 2 and not has_status_header:
        return "CUSTOM_ROOM_SCREEN", raw_text, {"clean_text": clean_text, "custom_room_evidence": custom_room_evidence}

    has_start = any(matches_word(w) for w in ["START", "STARI", "8TART", "S1ART"])
    is_lobby_signal = any(matches_word(w) for w in [
        "STORE", "MISSIONS", "EVENTS", "VAULT", "INVITE", "ROOM", "CUSTOMIZED",
        "CASUAL", "SPECTATOR", "ADVANCED", "PROFILE", "TACTICS", "DETAILS", "GUILD"
    ]) or matches("INVITEFRIEND") or matches("BATTLEROYALECLASSIC") or matches("BOOYAHPASS")

    has_room_id = bool(re.search(r'(ID|1D)\d{6,10}', clean_text))
    home_signals = sum([
        matches("STORE") or matches("ST0RE"),
        matches("MISSION") or matches("M1SSION"),
        matches("EVENT") or matches("EV3NT"),
        matches("VAULT"),
        matches("WEAPON") or matches("W3APON"),
        has_start
    ])
    is_home_lobby = (home_signals >= 2 or (has_start and not has_room_id)) and not has_room_id and not matches("SPECTATORLIST")

    if (has_start or is_lobby_signal) and not has_status_header:
        return "LOBBY_SCREEN", raw_text, {"clean_text": clean_text, "is_home_lobby": is_home_lobby}

    # 3. Result Screen Detection per Mode
    is_cs = (target_mode == "CS")
    is_lw = (target_mode == "LW")
    is_br = (target_mode == "BR" or (not is_cs and not is_lw))

    # Shared Button & Data signals: Require exact token for BACK to prevent matching player names
    has_back = matches_word("BACK") or matches_word("LOBBY") or matches("8ACK") or matches("B4CK") or matches("L0BBY") or matches("EXIT") or matches("RETURN")
    has_elim = bool(re.search(r'E[L1IU]?[I1L]?M[I1L]?N', clean_text)) or matches("SUMMARY") or matches("KDA")

    if is_br:
        has_status = has_status_header
        is_definitive = has_status or has_elim
        has_br_header = (
            has_status or matches("SUMMARY") or matches("PERFORMANCE") or
            (matches("BATTLE") and matches("ROYALE")) or (matches("FREE") and matches("FIRE")) or
            matches("BATTLEROYALE") or matches("FREEFIRE") or matches("FREEF") or matches("FIPE")
        )
        has_data = has_elim or matches("RANKUP") or matches("RANKPOINT") or matches("DMG")
        evidence_count = sum([has_br_header, has_data, has_back])

        elim_matches = re.findall(r'E[L1IU]?[I1L]?M[I1L]?N', clean_text)
        has_multiple_elims = len(elim_matches) >= 2

        br_state = "IDLE"
        if has_back:
            if is_definitive or (evidence_count >= 2 and has_data):
                br_state = "RESULT_SCREEN"
        elif has_status:
            if evidence_count >= 2 or has_multiple_elims:
                br_state = "RESULT_SCREEN"
        elif has_multiple_elims and has_br_header and (not is_ingame_strong or len(elim_matches) >= 8):
            br_state = "RESULT_SCREEN"
        elif len(elim_matches) >= 4 and (not is_ingame_strong or len(elim_matches) >= 8):
            br_state = "RESULT_SCREEN"
        elif evidence_count >= 3 and (not is_ingame_strong or len(elim_matches) >= 8):
            br_state = "RESULT_SCREEN"

        # Validate BR result state against in-game suppression
        if br_state == "RESULT_SCREEN":
            has_identity = has_status or has_br_header or matches("RANKUP") or (has_elim and matches("ELIMINATIONS"))
            if not has_identity and not has_status and not has_multiple_elims:
                br_state = "IDLE"

            # When a definitive match win header (BOOYAH, VICTORY, MATCHOVER, DEFEAT) is visible,
            # never allow residual background HUD text to cancel the victory screen!
            if not has_status:
                if is_ingame_definitive:
                    br_state = "IDLE"
                elif is_ingame_strong and not has_back and len(elim_matches) < 4:
                    br_state = "IDLE"
                elif is_ingame_strong and not has_back:
                    br_state = "IDLE"

        if br_state == "RESULT_SCREEN":
            return "RESULT_SCREEN", raw_text, {"mode": "BR", "evidence": evidence_count}

    if is_cs:
        matches_kda = any(matches(k) for k in ["KDA", "KDIA", "K0A", "K0IA", "KD7A"])
        matches_dmg = any(matches(d) for d in ["DMG", "OMG", "OMS", "OM6", "DNIG", "DWG", "DNG", "DMC", "DM9"])
        has_howlers = any(matches(h) for h in ["HOWLER", "HOWLERS", "H0WLER"])
        has_warbringers = any(matches(w) for w in ["WARBRINGER", "WARBRINGERS", "WARBR1NGER"])
        has_name = matches("NAME") or matches("NANE") or matches("N4ME")
        has_vs = matches("VS") or matches("V5")
        has_clash = any(matches(c) for c in ["CLASH", "GLASH", "CLASS"])
        has_squad = any(matches(s) for s in ["SQUAD", "SOUAD", "SQUAO"])
        has_clash_squad = has_clash and has_squad

        is_cs_definitive = (
            has_status_header or has_howlers or has_warbringers or
            (has_name and matches_dmg) or (has_vs and matches_dmg) or (matches_kda and matches_dmg)
        )

        has_cs_header = (
            has_status_header or matches("SCOREBOARD") or matches("SUMMARY") or matches("SCORE") or
            matches("ROUND") or has_clash_squad or has_howlers or has_warbringers
        )
        has_cs_data = (has_elim and not is_ingame_definitive) or matches_dmg or matches_kda or matches("RANK")
        cs_evidence = sum([has_cs_header, has_cs_data, has_back])

        cs_state = "IDLE"
        if has_back:
            if is_cs_definitive or (cs_evidence >= 2 and has_cs_data):
                cs_state = "RESULT_SCREEN"
        elif has_status_header and (cs_evidence >= 2 or (matches_kda and matches_dmg)):
            cs_state = "RESULT_SCREEN"
        elif is_cs_definitive and cs_evidence >= 2:
            cs_state = "RESULT_SCREEN"

        # Suppress CS false positives if match is actively in progress
        if cs_state == "RESULT_SCREEN":
            has_cs_result_header = (
                matches("SCOREBOARD") or has_clash_squad or has_howlers or has_warbringers or
                matches("FREEFIRE") or (matches_kda and matches_dmg) or (has_name and matches_dmg) or (has_vs and matches_dmg)
            )
            if not has_status_header and not has_cs_result_header and not matches("BOOYA") and not matches("B00YA"):
                cs_state = "IDLE"

            if is_ingame_definitive or (is_ingame_strong and not has_status_header):
                cs_state = "IDLE"

        if cs_state == "RESULT_SCREEN":
            return "RESULT_SCREEN", raw_text, {"mode": "CS", "evidence": cs_evidence}

    if is_lw:
        has_lw_header = has_status_header or matches("LONEWOLF") or matches("LONE") or matches("WOLF") or matches("ROUND")
        has_lw_data = has_elim or matches("DMG") or matches("KDA") or matches("SCORE")
        lw_evidence = sum([has_lw_header, has_lw_data, has_back])

        lw_state = "IDLE"
        if (has_back or has_status_header) and (has_status_header or lw_evidence >= 2):
            lw_state = "RESULT_SCREEN"

        if lw_state == "RESULT_SCREEN" and (is_ingame_definitive or (is_ingame_strong and not has_status_header)):
            lw_state = "IDLE"

        if lw_state == "RESULT_SCREEN":
            return "RESULT_SCREEN", raw_text, {"mode": "LW", "evidence": lw_evidence}

    # 4. In-Game state fallback
    if is_ingame_strong or is_ingame_definitive:
        return "IN_GAME", raw_text, {"clean_text": clean_text}

    return "IDLE", raw_text, {"clean_text": clean_text}
