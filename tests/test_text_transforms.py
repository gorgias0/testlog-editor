import base64

import pytest

from text_transforms import (
    TransformError,
    ascii_email_name,
    decode_base64_text,
    decode_url_component,
    encode_url_component,
)


def test_base64_accepts_line_wrapped_input():
    text = "Ett långt meddelande " * 10
    encoded = base64.encodebytes(text.encode("utf-8")).decode("ascii")
    assert "\n" in encoded.strip()

    assert decode_base64_text(encoded) == text


def test_base64_accepts_url_safe_input_without_padding():
    data = "åäö?>~".encode("utf-8")
    encoded = base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

    assert decode_base64_text(encoded) == "åäö?>~"


def test_base64_reports_invalid_and_non_text_input_differently():
    with pytest.raises(TransformError, match="Invalid Base64"):
        decode_base64_text("not base64!")
    with pytest.raises(TransformError, match="not UTF-8"):
        decode_base64_text(base64.b64encode(b"\xff\xfe\x00").decode("ascii"))


def test_url_encoding_encodes_reserved_characters():
    assert encode_url_component("a/b?c=d&e f") == "a%2Fb%3Fc%3Dd%26e%20f"
    assert encode_url_component("åäö") == "%C3%A5%C3%A4%C3%B6"


def test_url_decoding_treats_plus_as_space_and_rejects_broken_sequences():
    assert decode_url_component("a+b%20c%2B") == "a b c+"
    with pytest.raises(TransformError):
        decode_url_component("%E4")


def test_url_round_trip():
    text = "a+b/c?d=e&f g åäö"

    assert decode_url_component(encode_url_component(text)) == text


@pytest.mark.parametrize(
    "name, expected",
    [("Søren Ærø", "sorenaero"), ("Þórður", "thordur"), ("Åsa Öberg", "asaoberg"), ("Strauß", "strauss"), ("José", "jose")],
)
def test_email_names_keep_letters_as_ascii(name, expected):
    assert ascii_email_name(name) == expected
