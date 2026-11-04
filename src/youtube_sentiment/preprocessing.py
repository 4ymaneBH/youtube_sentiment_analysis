import re
import unicodedata

URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
MENTION = re.compile(r"(?<!\w)@[\w.-]+")
SYMBOL = re.compile(r"[^\w\s'!?]+")
EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower().replace("’", "'")
    text = URL.sub(" ", text)
    text = MENTION.sub(" ", text)
    text = EMOJI.sub(lambda match: f" {unicodedata.name(match[0], '').lower()} ", text)
    text = " ".join(SYMBOL.sub(" ", text).split())
    return text if any(char.isalnum() for char in text) else ""


def clean_comments(texts: list[str]) -> list[str]:
    return [clean_text(text) for text in texts]
