import io
import time
import requests
from typing import Optional, Tuple, List
from PIL import Image

def send_discord_webhook(
    webhook_url: str,
    emulator_name: str,
    mode: str,
    screenshot: Optional[Image.Image] = None,
    detected_text: str = "",
    display_time: Optional[str] = None,
    additional_images: Optional[List[Image.Image]] = None,
    description: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Constructs and sends a multipart/form-data payload to the Discord Webhook,
    attaching the match summary screenshot and optional scroll screenshots as
    embedded images in the same message.
    """
    if not webhook_url or not webhook_url.startswith("http"):
        return False, "No valid Webhook URL provided"

    timestamp_str = display_time if display_time else time.strftime("%I:%M:%S %p")

    main_embed = {
        "author": {
            "name": f"Time: {timestamp_str}"
        },
        "url": "https://discord.com",
        "color": 0x000000,
        "image": {"url": "attachment://result.png"} if screenshot else {},
        "footer": {
            "text": "Booyah | Developed By Etherious",
            "icon_url": "https://raw.githubusercontent.com/Mahee000/Booyah-SS/main/src/renderer/logo.png"
        }
    }
    if description:
        main_embed["description"] = description

    embeds = [main_embed]

    files = {}
    if screenshot:
        buf = io.BytesIO()
        screenshot.save(buf, format="PNG")
        buf.seek(0)
        files["file1"] = ("result.png", buf, "image/png")

    if additional_images:
        for idx, add_img in enumerate(additional_images):
            fname = f"scroll{idx + 1}.png"
            embeds.append({
                "url": "https://discord.com",
                "color": 0x000000,
                "image": {"url": f"attachment://{fname}"}
            })
            add_buf = io.BytesIO()
            add_img.save(add_buf, format="PNG")
            add_buf.seek(0)
            files[f"file{idx + 2}"] = (fname, add_buf, "image/png")

    payload = {
        "username": "Booyah",
        "avatar_url": "https://raw.githubusercontent.com/Mahee000/Booyah-SS/main/src/renderer/logo.png",
        "embeds": embeds
    }

    try:
        if files:
            res = requests.post(
                webhook_url,
                data={"payload_json": requests.models.complexjson.dumps(payload)},
                files=files,
                timeout=12
            )
        else:
            res = requests.post(webhook_url, json=payload, timeout=10)

        if res.status_code in (200, 204):
            return True, "Webhook sent successfully"
        else:
            return False, f"Discord error HTTP {res.status_code}: {res.text}"
    except Exception as e:
        return False, f"Webhook request exception: {str(e)}"
