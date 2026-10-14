import re
import math
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from PIL import Image, ImageOps, ImageEnhance
from paddleocr import PaddleOCR

# Dedicated native PaddleOCR engine for esports score extraction (Highest tier PP-OCRv4, Single-Threaded)
_esports_ocr = None

def get_esports_ocr():
    global _esports_ocr
    if _esports_ocr is None:
        _esports_ocr = PaddleOCR(
            ocr_version='PP-OCRv4',
            use_angle_cls=False,
            lang='en',
            show_log=False,
            enable_mkldnn=False,
            cpu_threads=1,
            drop_score=0.45,
            det_limit_side_len=1920,
            det_limit_type='max'
        )
    return _esports_ocr

# Comprehensive fallback dictionary for Free Fire stylized fonts
FALLBACK_MAP = {
    'O': 0, 'Q': 0, 'D': 0, 'C': 0, 'U': 0,
    'L': 1, '|': 1, 'T': 1, 'I': 1,
    'Z': 2, '?': 2,
    'E': 3,
    'A': 4, 'H': 4,
    'S': 5,
    'B': 6, 'G': 6,
    'P': 9
}

BASE_REGEX = re.compile(
    r'(.*?)([\s\-.:|]*)(?<![a-zA-Z])(?:[eE][l1I|tT][a-z]*|l[i1]m[a-z]*|[i1]m[a-z]{2,})',
    re.IGNORECASE
)

def extract_kills_from_boxes(
    boxes_with_text: List[Dict[str, Any]],
    crop_y: float = 0.0,
    crop_h: float = 1.0,
    split_x: int = 580,
    height: int = 720
) -> List[Dict[str, Any]]:
    """
    Extracts kill records from bounding boxes using the exact geometric clustering
    and token boundary regex matching from Booyah's esports-ocr engine.
    """
    kill_records = []
    est_width = split_x / 0.55

    for item in boxes_with_text:
        text = item["text"].replace('O', '0').replace('o', '0').replace('l', '1')
        box = item["box"]
        side = item["side"]

        matches = list(BASE_REGEX.finditer(text))
        if matches:
            for match_index, match in enumerate(matches, 1):
                prefix = match.group(1).strip()
                # Strip potential E1 or El prefix
                e1_match = re.match(r'^(.*?)[eE][l1I|tT]$', prefix, re.IGNORECASE)
                if e1_match:
                    prefix = e1_match.group(1).strip()

                tokens = prefix.split()
                if tokens:
                    prefix = tokens[-1]

                col_width = (est_width - split_x) if side == 'right' else split_x
                col_divider = (split_x + col_width * 0.72) if side == 'right' else (col_width * 0.47)
                right_edge = box["x"] + box["w"]
                definitely_col2 = (right_edge > split_x + col_width * 0.85) if side == 'right' else (right_edge > col_width * 0.75)

                if match_index == 2:
                    assign_x = (split_x + (est_width - split_x) * 0.75) if side == 'right' else (split_x * 0.75)
                elif definitely_col2 or match_index > 1:
                    assign_x = (split_x + col_width * 0.75) if side == 'right' else (col_width * 0.75)
                else:
                    is_left_subcol = box["x"] < col_divider
                    base_offset = split_x if side == 'right' else 0
                    assign_x = base_offset + (col_width * 0.25 if is_left_subcol else col_width * 0.75)

                kills = -1
                clean_token = prefix.strip()
                if not clean_token:
                    kill_records.append({"kills": 0, "side": side, "x": assign_x, "y": box["y"], "hasText": True, "rel": 1})
                    continue

                if clean_token.isdigit():
                    kills = int(clean_token)
                    rel = 3
                else:
                    fb = re.sub(r'[^a-zA-Z0-9|?]', '', clean_token)
                    if len(fb) == 1 and fb.upper() in FALLBACK_MAP:
                        kills = FALLBACK_MAP[fb.upper()]
                        rel = 2
                    else:
                        kills = 0
                        rel = 1

                if 0 <= kills <= 48:
                    kill_records.append({"kills": kills, "side": side, "x": assign_x, "y": box["y"], "hasText": True, "rel": rel})
        else:
            # Standalone digit fallback
            clean_str = text.strip()
            if clean_str.isdigit():
                num = int(clean_str)
                if 0 <= num <= 48:
                    col_divider = (split_x + (est_width - split_x) * 0.45) if side == 'right' else (split_x * 0.45)
                    is_col1 = box["x"] < col_divider
                    assign_x = (split_x + (est_width - split_x) * (0.25 if is_col1 else 0.75)) if side == 'right' else (split_x * (0.25 if is_col1 else 0.75))
                    kill_records.append({"kills": num, "side": side, "x": assign_x, "y": box["y"], "hasText": False, "rel": 0})

    return kill_records

def deduplicate_and_assign_kills(
    kill_records: List[Dict[str, Any]],
    placement_points: List[int],
    kill_multiplier: int = 1,
    crop_y: float = 0.0,
    crop_h: float = 1.0,
    split_x: int = 580,
    height: int = 720
) -> str:
    """
    Deduplicates kills by player zone, clusters them into 12 teams,
    calculates placement + kill points, and outputs ASCII leaderboard tables.
    """
    est_width = split_x / 0.55
    left_kills = []
    right_kills = []

    for item in kill_records:
        target_list = left_kills if item["side"] == 'left' else right_kills
        existing_idx = -1
        for idx, k in enumerate(target_list):
            if abs(k["y"] - item["y"]) < height * 0.03 and abs(k["x"] - item["x"]) < est_width * 0.08:
                existing_idx = idx
                break

        if existing_idx != -1:
            existing = target_list[existing_idx]
            if item["hasText"] and not existing["hasText"]:
                target_list[existing_idx] = item
            elif item["hasText"] == existing["hasText"]:
                if item["rel"] > existing["rel"]:
                    target_list[existing_idx] = item
                elif item["rel"] == existing["rel"] and item["kills"] > existing["kills"]:
                    target_list[existing_idx] = item
        else:
            target_list.push(item) if hasattr(target_list, "push") else target_list.append(item)

    max_teams = max(12, len(placement_points))
    pts_table = list(placement_points) + [0] * max(0, max_teams - len(placement_points))

    def assign_to_teams(kills: List[Dict[str, Any]], num_teams: int, side: str) -> List[int]:
        result = [0] * num_teams
        if not kills:
            return result
        start_y = height * crop_y
        end_y = height * (crop_y + crop_h)
        avail_h = max(1.0, end_y - start_y)
        visible_slots = 5 if side == 'left' else 7
        slot_h = avail_h / max(1, visible_slots)

        for k in kills:
            adj_y = k["y"] - start_y
            if adj_y < 0:
                continue
            slot = int(adj_y / slot_h)
            if 0 <= slot < num_teams:
                result[slot] += k["kills"]
        return result

    left_count = 5
    right_count = max_teams - left_count
    left_team_kills = assign_to_teams(left_kills, left_count, 'left')
    right_team_kills = assign_to_teams(right_kills, right_count, 'right')
    team_kills = left_team_kills + right_team_kills
    while len(team_kills) < max_teams:
        team_kills.append(0)

    team_results = []
    for i in range(max_teams):
        place_pts = pts_table[i] if i < len(pts_table) else 0
        actual_kills = team_kills[i]
        k_pts = actual_kills * kill_multiplier
        total = place_pts + k_pts
        team_results.append({
            "rank": i + 1,
            "place_pts": place_pts,
            "kills": actual_kills,
            "k_pts": k_pts,
            "total": total
        })

    # Build ASCII tables matching the original Booyah esports output
    output = "# **MATCH STATISTICS**\n```\n"
    output += "+--------+-----------+-------+--------+\n"
    output += "| Team   | Placement | Kills | Points |\n"
    output += "+--------+-----------+-------+--------+\n"

    for t in team_results:
        team_str = f"TOP {t['rank']}".ljust(6)
        place_str = str(t['place_pts']).ljust(9)
        kills_str = str(t['kills']).ljust(5)
        pts_str = str(t['total']).ljust(6)
        output += f"| {team_str} | {place_str} | {kills_str} | {pts_str} |\n"
        output += "+--------+-----------+-------+--------+\n"
    output += "```\n\n"

    output += "# **FINAL STANDINGS**\n```\n"
    output += "+-------+--------+--------+\n"
    output += "| Rank  | Team   | Points |\n"
    output += "+-------+--------+--------+\n"

    sorted_teams = sorted(team_results, key=lambda x: x["total"], reverse=True)
    suffixes = ["1st", "2nd", "3rd", "4th"]
    for i in range(min(4, len(sorted_teams))):
        st = sorted_teams[i]
        sfx = suffixes[i].ljust(5)
        team_str = f"TOP {st['rank']}".ljust(6)
        pts_str = str(st['total']).ljust(6)
        output += f"| {sfx} | {team_str} | {pts_str} |\n"
        output += "+-------+--------+--------+\n"
    output += "```"

    return output

def parse_esports_scoreboard(
    image: Image.Image,
    kill_multiplier: int = 1,
    placement_points: Optional[List[int]] = None,
    crop_y: float = 0.22,
    crop_h: float = 0.66
) -> str:
    """
    Parses a Free Fire BR scoreboard screenshot using multi-pass OCR
    and mathematical coordinate extraction, generating the full Esports
    match statistics and final standings tables.
    """
    if placement_points is None:
        placement_points = [12, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 0]

    img = image.convert("RGB")
    width, height = img.size

    # Ensure width >= 1920 for accurate tiny digit OCR recognition
    if width < 1920:
        scale = 1920.0 / width
        width = 1920
        height = int(height * scale)
        img = img.resize((width, height), Image.Resampling.LANCZOS)

    split_x = int(width * 0.55)
    right_width = width - split_x

    # Split into left and right columns
    left_img = img.crop((0, 0, split_x, height))
    right_img = img.crop((split_x, 0, width, height))

    # Perform multi-pass OCR (Raw + Enhanced Contrast)
    boxes_with_text: List[Dict[str, Any]] = []

    def run_pass(crop_part: Image.Image, side: str, x_offset: int):
        np_arr = np.array(crop_part)
        try:
            engine = get_esports_ocr()
            ocr_out = engine.ocr(np_arr, cls=False)
        except Exception:
            ocr_out = None

        if ocr_out and ocr_out[0]:
            for item in ocr_out[0]:
                if not item or len(item) < 2:
                    continue
                box_coords = item[0]  # [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
                text_info = item[1]
                text = text_info[0] if isinstance(text_info, (list, tuple)) else str(text_info)
                if not text:
                    continue

                xs = [p[0] for p in box_coords]
                ys = [p[1] for p in box_coords]
                bx = min(xs) + x_offset
                by = min(ys)
                bw = max(xs) - min(xs)
                bh = max(ys) - min(ys)
                boxes_with_text.append({
                    "text": text,
                    "side": side,
                    "box": {"x": bx, "y": by, "w": bw, "h": bh}
                })

    # Pass 1: Raw Left and Right
    run_pass(left_img, 'left', 0)
    run_pass(right_img, 'right', split_x)

    # Pass 2: Enhanced Contrast Left and Right
    enh_left = ImageEnhance.Contrast(left_img).enhance(1.4)
    enh_right = ImageEnhance.Contrast(right_img).enhance(1.4)
    run_pass(enh_left, 'left', 0)
    run_pass(enh_right, 'right', split_x)

    # Extract kills and format tables
    kill_records = extract_kills_from_boxes(boxes_with_text, crop_y, crop_h, split_x, height)
    return deduplicate_and_assign_kills(
        kill_records,
        placement_points,
        kill_multiplier,
        crop_y,
        crop_h,
        split_x,
        height
    )
