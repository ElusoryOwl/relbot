import logging
import random
import re

import aiohttp

log = logging.getLogger("relbot.media")

TAG_SOURCES = {
    "fuck_slow": [
        "https://nekobot.xyz/api/image?type=hentai",
        "https://nekobot.xyz/api/image?type=pgif",
        "https://api.waifu.pics/nsfw/waifu",
    ],
    "fuck_rough": [
        "https://nekobot.xyz/api/image?type=pgif",
        "https://nekobot.xyz/api/image?type=hentai",
        "https://api.waifu.pics/nsfw/waifu",
    ],
    "degrade": [
        "https://nekobot.xyz/api/image?type=pgif",
        "https://nekobot.xyz/api/image?type=hentai",
        "https://api.waifu.pics/nsfw/trap",
    ],
    "tease": [
        "https://nekobot.xyz/api/image?type=hmidriff",
        "https://nekobot.xyz/api/image?type=pantsu",
        "https://api.waifu.pics/nsfw/neko",
    ],
    "spank": [
        "https://nekobot.xyz/api/image?type=hass",
        "https://nekobot.xyz/api/image?type=hentai",
        "https://api.waifu.pics/nsfw/waifu",
    ],
    "blow": [
        "https://nekobot.xyz/api/image?type=blowjob",
        "https://api.waifu.pics/nsfw/blowjob",
        "https://nekobot.xyz/api/image?type=pgif",
    ],
    "ride": [
        "https://nekobot.xyz/api/image?type=paizuri",
        "https://nekobot.xyz/api/image?type=pgif",
        "https://nekobot.xyz/api/image?type=hentai",
    ],
    "breed": [
        "https://nekobot.xyz/api/image?type=nakadashi",
        "https://nekobot.xyz/api/image?type=pgif",
        "https://nekobot.xyz/api/image?type=hentai",
    ],
    "claim": [
        "https://nekobot.xyz/api/image?type=hentai",
        "https://api.waifu.pics/nsfw/waifu",
    ],
    "leash": [
        "https://nekobot.xyz/api/image?type=hkitsune",
        "https://api.waifu.pics/nsfw/neko",
        "https://nekobot.xyz/api/image?type=hentai",
    ],
    "kiss": [
        "https://api.waifu.pics/sfw/kiss",
        "https://nekobot.xyz/api/image?type=neko",
    ],
    "hug": [
        "https://api.waifu.pics/sfw/hug",
        "https://api.waifu.pics/sfw/cuddle",
    ],
    "aftercare": [
        "https://api.waifu.pics/sfw/cuddle",
        "https://api.waifu.pics/sfw/hug",
        "https://api.waifu.pics/sfw/pat",
    ],
    "doggy": [
        "https://nekobot.xyz/api/image?type=pgif",
        "https://nekobot.xyz/api/image?type=hentai",
        "https://nekobot.xyz/api/image?type=anal",
    ],
    "knees": [
        "https://nekobot.xyz/api/image?type=blowjob",
        "https://api.waifu.pics/nsfw/blowjob",
        "https://nekobot.xyz/api/image?type=pgif",
    ],
    "pin": [
        "https://nekobot.xyz/api/image?type=pgif",
        "https://nekobot.xyz/api/image?type=hentai",
        "https://api.waifu.pics/nsfw/waifu",
    ],
    "scene": [
        "https://nekobot.xyz/api/image?type=pgif",
        "https://nekobot.xyz/api/image?type=hentai",
        "https://api.waifu.pics/nsfw/waifu",
    ],
}

KEYWORD_TAGS = (
    (re.compile(r"throat|blow|knees|down their throat", re.I), "blow"),
    (re.compile(r"spank", re.I), "spank"),
    (re.compile(r"leash|sit\.|stay", re.I), "leash"),
    (re.compile(r"fill them|breed|keep them full", re.I), "breed"),
    (re.compile(r"rides|grinding", re.I), "ride"),
    (re.compile(r"edges|refuses to finish", re.I), "tease"),
    (re.compile(r"kisses", re.I), "kiss"),
    (re.compile(r"hugs|aftercare|cuddle", re.I), "aftercare"),
    (re.compile(r"bends .+ over|doggy", re.I), "doggy"),
    (re.compile(r"on their knees", re.I), "knees"),
    (re.compile(r"pins .+ wrists", re.I), "pin"),
    (re.compile(r"slams into|uses .+ like a toy", re.I), "fuck_rough"),
    (re.compile(r"fucks .+ deep|unhurried", re.I), "fuck_slow"),
    (re.compile(r"marks .+|they're taken", re.I), "claim"),
)


def tag_for(command_key: str, sentence: str, line_tag: str | None = None) -> str:
    if line_tag and line_tag in TAG_SOURCES:
        return line_tag
    for pat, tag in KEYWORD_TAGS:
        if pat.search(sentence or ""):
            return tag
    if command_key in TAG_SOURCES:
        return command_key
    return "scene"


def _extract_url(data) -> str | None:
    if not isinstance(data, dict):
        return None
    url = data.get("url") or data.get("message")
    if isinstance(url, str) and url.startswith("http"):
        return url
    return None


async def fetch_tagged_image(session: aiohttp.ClientSession, tag: str) -> str | None:
    urls = list(TAG_SOURCES.get(tag, TAG_SOURCES["scene"]))
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


async def fetch_for_sentence(
    session: aiohttp.ClientSession,
    command_key: str,
    sentence: str,
    line_tag: str | None = None,
) -> str | None:
    tag = tag_for(command_key, sentence, line_tag)
    return await fetch_tagged_image(session, tag)