from fastapi import HTTPException
from urllib.parse import urlparse


def validate_proof_url(proof_url: str):
    proof_url = proof_url.strip()

    if not proof_url:
        raise HTTPException(
            status_code=400,
            detail="Proof URL cannot be empty"
        )

    if len(proof_url) > 500:
        raise HTTPException(
            status_code=400,
            detail="Proof URL is too long"
        )

    if any(character.isspace() for character in proof_url):
        raise HTTPException(
            status_code=400,
            detail="Proof URL cannot contain spaces"
        )

    parsed_url = urlparse(proof_url)

    if parsed_url.scheme != "https" or not parsed_url.hostname:
        raise HTTPException(
            status_code=400,
            detail="Proof URL must be a valid HTTPS URL"
        )

    return proof_url


def validate_new_level(
    name: str,
    creator: str,
    gd_id: int,
    rank: int
):
    name = name.strip()
    creator = creator.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Level name cannot be empty"
        )

    if not creator:
        raise HTTPException(
            status_code=400,
            detail="Creator cannot be empty"
        )

    if gd_id <= 0:
        raise HTTPException(
            status_code=400,
            detail="Geometry Dash ID must be positive"
        )

    if rank <= 0:
        raise HTTPException(
            status_code=400,
            detail="Rank must be positive"
        )

    return name, creator