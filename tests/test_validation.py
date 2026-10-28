import pytest
from fastapi import HTTPException

from validation import validate_proof_url


def test_valid_proof_url():
    result = validate_proof_url("https://youtube.com/watch?v=123")

    assert result == "https://youtube.com/watch?v=123"


def test_proof_url_is_stripped():
    result = validate_proof_url("  https://youtube.com/watch?v=123  ")

    assert result == "https://youtube.com/watch?v=123"


def test_empty_proof_url_rejected():
    with pytest.raises(HTTPException) as error:
        validate_proof_url("")

    assert error.value.status_code == 400


def test_http_proof_url_rejected():
    with pytest.raises(HTTPException) as error:
        validate_proof_url("http://youtube.com/watch?v=123")

    assert error.value.status_code == 400


def test_proof_url_with_spaces_rejected():
    with pytest.raises(HTTPException) as error:
        validate_proof_url("https://example.com/my proof")

    assert error.value.status_code == 400