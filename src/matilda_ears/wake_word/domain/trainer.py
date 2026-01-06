from typing import Optional


def normalize_model_name(phrase: str) -> str:
    return phrase.lower().replace(" ", "_").replace("-", "_")


def validate_phrase(phrase: Optional[str]) -> str:
    if not phrase or not phrase.strip():
        raise ValueError("No phrase provided")
    return phrase.strip()
