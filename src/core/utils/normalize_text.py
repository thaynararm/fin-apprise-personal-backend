import re
import unicodedata


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFD", text)

    text = "".join(char for char in text if unicodedata.category(char) != "Mn")

    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)

    text = re.sub(r"\s+", " ", text).strip()

    text = text.replace(" ", "_")

    return text.lower()


def normalize_display_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[^\w\sÀ-ÿ]", "", text)
    text = text.replace("_", " ")
    return text.title()
