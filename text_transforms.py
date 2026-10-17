import base64
import binascii
import re
import unicodedata
from urllib.parse import quote, unquote_plus


class TransformError(ValueError):
    pass


def decode_base64_text(text):
    # Accept line-wrapped (MIME style) and URL-safe input, and tell "not Base64" apart from
    # "Base64, but not text".
    compact = re.sub(r"\s+", "", text or "").replace("-", "+").replace("_", "/")
    compact += "=" * (-len(compact) % 4)
    try:
        data = base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError) as error:
        raise TransformError("Invalid Base64") from error
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TransformError("Base64 decodes to data that is not UTF-8 text") from error


def encode_url_component(text):
    # Like JavaScript's encodeURIComponent: "/", "?", "&" and similar are encoded too.
    return quote(text or "", safe="-_.!~*'()")


def decode_url_component(text):
    # "+" means a space in query strings; broken %-sequences are reported instead of being
    # turned into replacement characters.
    try:
        return unquote_plus(text or "", errors="strict")
    except UnicodeDecodeError as error:
        raise TransformError("Invalid URL encoding") from error


EMAIL_LETTER_REPLACEMENTS = str.maketrans({"æ": "ae", "ø": "o", "þ": "th", "ð": "d", "ß": "ss", "œ": "oe", "ł": "l"})


def ascii_email_name(text):
    # "Søren Ærø" -> "sorenaero": map letters without an ASCII decomposition first, then
    # strip accents (å, ä, ö, é ...) instead of dropping the letters.
    lowered = (text or "").lower().translate(EMAIL_LETTER_REPLACEMENTS)
    stripped = "".join(
        character for character in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", "", stripped)
