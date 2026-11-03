"""Text preprocessing utilities adapted from high-scoring datathon notebook.

Provides text normalization, language detection, and feature extraction
for Bangla/Banglish/English text. Runs on CPU only.
"""

import re
import unicodedata
from difflib import SequenceMatcher


# --- Text Normalization (adapted from datathon notebook) ---

def normalize_text(value: object) -> str:
    """NFKC normalize and clean whitespace. Handles Bangla conjuncts."""
    text = unicodedata.normalize("NFKC", str(value if value is not None else ""))
    # Fix common Bangla Unicode normalization issues
    text = text.replace("ড়", "ড়").replace("ঢ়", "ঢ়")
    return re.sub(r"\s+", " ", text).strip()


def key_text(value: object) -> str:
    """Lowercase, remove punctuation — for matching and dedup."""
    text = normalize_text(value).lower()
    return re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE).strip()


# --- Language Detection ---

# Bangla Unicode range: U+0980 to U+09FF
BANGLA_PATTERN = re.compile(r"[\u0980-\u09FF]")
ENGLISH_PATTERN = re.compile(r"[A-Za-z]")
# Common Banglish markers (Romanized Bangla)
BANGLISH_WORDS = {
    "vai", "bhai", "apnader", "apnar", "koto", "kobe", "ki", "naki",
    "kibhabe", "korbo", "hoy", "pawa", "jay", "korle", "pabo",
    "kothay", "hobe", "bolen", "mane", "ta", "gula", "bolun",
    "dekhen", "please", "ami", "amra", "tumi", "apni", "ache",
    "nai", "hoi", "kor", "din", "kal", "ajke", "sob", "besh",
    "valo", "bhalo", "thik", "asen", "jaben", "khub", "onek",
    "shob", "jodi", "tahole", "kintu", "ba", "ebong", "ar",
}


def detect_language(text: str) -> str:
    """Detect language of a message: bangla, banglish, english, or mixed."""
    bangla_chars = len(BANGLA_PATTERN.findall(text))
    english_chars = len(ENGLISH_PATTERN.findall(text))
    total_chars = bangla_chars + english_chars

    if total_chars == 0:
        return "mixed"

    bangla_ratio = bangla_chars / total_chars if total_chars > 0 else 0
    english_ratio = english_chars / total_chars if total_chars > 0 else 0

    # Check for Banglish: English alphabet but Bangla words
    if english_ratio > 0.7:
        words = set(key_text(text).split())
        banglish_overlap = words & BANGLISH_WORDS
        if len(banglish_overlap) >= 2 or (len(banglish_overlap) >= 1 and len(words) <= 5):
            return "banglish"
        return "english"

    if bangla_ratio > 0.7:
        return "bangla"

    # Mixed content — check for Banglish
    words = set(key_text(text).split())
    banglish_overlap = words & BANGLISH_WORDS
    if len(banglish_overlap) >= 2:
        return "banglish"

    return "mixed"


# --- Text Similarity (from datathon notebook) ---

def token_jaccard(first: str, second: str) -> float:
    """Jaccard similarity between two texts based on word tokens."""
    first_tokens = set(first.split())
    second_tokens = set(second.split())
    if not first_tokens or not second_tokens:
        return 0.0
    return len(first_tokens & second_tokens) / len(first_tokens | second_tokens)


def text_similarity(first: str, second: str) -> float:
    """Combined SequenceMatcher + Jaccard similarity."""
    if not first or not second:
        return 0.0
    if first == second:
        return 1.0
    seq = SequenceMatcher(None, first, second).ratio()
    return max(token_jaccard(first, second), float(seq))


def normalize_phone(phone: str) -> str:
    """Normalize Bangladeshi phone numbers."""
    if not phone or str(phone).lower() in ("nan", "none", ""):
        return ""
    # Remove all non-digit characters
    digits = re.sub(r"\D", "", str(phone))
    # Handle +880 prefix
    if digits.startswith("880") and len(digits) == 13:
        digits = "0" + digits[3:]
    # CSV readers may strip the leading zero from local 11-digit numbers.
    if len(digits) == 10 and not digits.startswith("0"):
        digits = "0" + digits
    return digits
