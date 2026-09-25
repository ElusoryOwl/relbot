import logging
import random

import aiohttp

log = logging.getLogger("relbot.media")

# SFW-only sources. Each tag has a couple of mirrors so one API being
# down doesn't kill the feature.
TAG_SOURCES = {
    "hug": [
        "https://api.waifu.pics/sfw/hug",
        "https://nekos.best/api/v2/hug",
    ],
    "cuddle": [
        "https://api.waifu.pics/sfw/cuddle",
        "https://nekos.best/api/v2/cuddle",
    ],
    "pat": [
        "https://api.waifu.pics/sfw/pat",
        "https://nekos.best/api/v2/pat",
    ],
    "kiss": [
        "https://api.waifu.pics/sfw/kiss",
        "https://nekos.best/api/v2/kiss",
    ],
    "poke": [
        "https://api.waifu.pics/sfw/poke",
        "https://nekos.best/api/v2/poke",
    ],
    "highfive": [
        "https://api.waifu.pics/sfw/highfive",
    ],
    "wave": [
        "https://api.waifu.pics/sfw/wave",
        "https://nekos.best/api/v2/wave",
    ],
}


def _extract_url(data) -> str | None:
    if not isinstance(data, dict):
        return None
    url = data.get("url")
    if not url and isinstance(data.get("results"), list) and data["results"]:
        url = data["results"][0].get("url")
    if isinstance(url, str) and url.startswith("http"):
        return url
    return None


async def fetch_tagged_image(session: aiohttp.ClientSession, tag: str) -> str | None:
    urls = list(TAG_SOURCES.get(tag, []))
    if not urls:
        return None
    random.shuffle(urls)
    timeout = aiohttp.ClientTimeout(total=6)
    for api in urls:
        try:
            async with session.get(api, timeout=timeout) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json(content_type=None)
                url = _extract_url(data)
                if url:
                    return url
        except Exception:
            log.debug("media fetch failed %s", api, exc_info=True)
    return None
