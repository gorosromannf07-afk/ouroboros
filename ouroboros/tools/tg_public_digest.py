
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import httpx

TG_CH_RE = re.compile(r"(?:https?://t\.me/)(s/)?([A-Za-z0-9_]{5,})", re.IGNORECASE)

def _strip_tags(html: str) -> str:
    html = re.sub(r"<br\s*/?>", "\n", html)
    html = re.sub(r"<.*?>", "", html, flags=re.DOTALL)
    html = (html.replace("&nbsp;", " ")
                 .replace("&amp;", "&")
                 .replace("&lt;", "<")
                 .replace("&gt;", ">"))
    return re.sub(r"\s+", " ", html).strip()

async def tg_public_digest(channel_url: str, day: str = "yesterday", tz: str = "Europe/Amsterdam", limit: int = 30):
    """
    PUBLIC Telegram web feed reader: https://t.me/s/<channel>
    Accepts channel_url like https://t.me/<name> or https://t.me/s/<name>.
    day: "yesterday" | "today"
    tz: IANA timezone string
    """
    m = TG_CH_RE.search((channel_url or "").strip())
    if not m:
        return {"error": "bad_channel_url", "channel_url": channel_url}

    username = m.group(2)
    feed_url = f"https://t.me/s/{username}"

    Z = ZoneInfo(tz)
    now_local = datetime.now(Z)
    if day == "today":
        start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    else:
        end = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=1)

    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as c:
        r = await c.get(feed_url)
        r.raise_for_status()
        html = r.text

    blocks = re.split(r'<div class="tgme_widget_message_wrap', html)
    items = []
    for b in blocks[1:]:
        post_m = re.search(r'data-post="([^"]+)"', b)
        post = post_m.group(1) if post_m else None
        link = f"https://t.me/{post}" if post else feed_url

        tm = re.search(r'<time[^>]+datetime="([^"]+)"', b)
        if not tm:
            continue
        dt_raw = tm.group(1)

        try:
            dt = datetime.fromisoformat(dt_raw.replace("Z","+00:00"))
        except Exception:
            continue

        dt_local = dt.astimezone(Z) if dt.tzinfo else dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(Z)
        if not (start <= dt_local < end):
            continue

        text_m = re.search(r'<div class="tgme_widget_message_text[^"]*">(.*?)</div>', b, re.DOTALL)
        raw_text = text_m.group(1) if text_m else ""
        text = _strip_tags(raw_text) if raw_text.strip() else "(без текста)"
        preview = text if len(text) <= 240 else text[:240] + "…"

        items.append({"datetime_local": dt_local.isoformat(timespec="minutes"), "preview": preview, "url": link})

    items.sort(key=lambda x: x["datetime_local"])
    items = items[:max(1, int(limit))]

    return {"channel": username, "feed_url": feed_url, "tz": tz, "day": day, "count": len(items), "items": items}
