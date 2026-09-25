def fill_line(template: str, a: str, b: str) -> str:
    return (
        template.replace("{a}", "\x00A\x00")
        .replace("{b}", "\x00B\x00")
        .replace("\x00A\x00", a)
        .replace("\x00B\x00", b)
    )


def clip(text: str, limit: int = 1020) -> str:
    text = text or "—"
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


# Each line is (text, media_tag)
LINES = {
    "fuck": {
        "vanilla": [
            ("{a} fucks {b} deep and unhurried, making them feel every inch.", "fuck_slow"),
        ],
        "rough": [
            ("{a} slams into {b} until it's sloppy and loud.", "fuck_rough"),
        ],
        "degrading": [
            ("{a} uses {b} like a toy and tells them exactly what they are.", "degrade"),
        ],
    },
    "tease": [
        ("{a} edges {b} and refuses to finish them.", "tease"),
    ],
    "spank": [
        ("{a} spanks {b} until they're hot and twitching.", "spank"),
    ],
    "blow": [
        ("{a} takes {b} down their throat and doesn't come up clean.", "blow"),
    ],
    "ride": [
        ("{a} rides {b} messy, grinding down to break their pace.", "ride"),
    ],
    "breed": [
        ("{a} fucks {b} to fill them and keep them full.", "breed"),
    ],
    "claim": [
        ("{a} marks {b} and tells the room they're taken.", "claim"),
    ],
    "leash": [
        ("{a} clips a leash on {b}. Sit. Stay. Earn it.", "leash"),
    ],
    "kiss": [
        ("{a} kisses {b} filthy.", "kiss"),
    ],
    "scene": [
        ("{a} bends {b} over and doesn't ask twice.", "doggy"),
        ("{a} puts {b} on their knees in front of anyone watching.", "knees"),
        ("{a} pins {b}'s wrists and whispers how they're getting used.", "pin"),
    ],
}