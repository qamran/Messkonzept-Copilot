"""MKC-22 (MKC-12 review finding 11): `is_valid_code` answers False, never raises, for text
that `str.isdigit` calls digits but that is no ASCII digit. `extract_text` parses stated LBS
codes from PDF text, where superscripts (`²`, a footnote mark) and other Unicode digits occur.
"""

import pytest

from mkc.reference.lbs import is_valid_code


@pytest.mark.parametrize(
    "code",
    [
        "999200000013²",  # superscript two as the check digit: int("²") raises
        "99920000001²3",  # superscript in the payload
        "\uff19\uff19\uff19\uff12000000133",  # full-width digits: int() reads them
        "999200000013\u0663",  # Arabic-Indic three, a decimal digit to int()
    ],
)
def test_is_valid_code_refuses_non_ascii_digits(code: str) -> None:
    assert is_valid_code(code) is False


def test_is_valid_code_still_accepts_a_valid_code() -> None:
    assert is_valid_code("9992000000133") is True
