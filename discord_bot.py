import os

import httpx
from dotenv import load_dotenv


load_dotenv()


DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_REVIEW_CHANNEL_ID = os.getenv("DISCORD_REVIEW_CHANNEL_ID")
DISCORD_CHANGELOG_CHANNEL_ID = os.getenv("DISCORD_CHANGELOG_CHANNEL_ID")

async def send_discord_message(content: str):

    url = (
        f"https://discord.com/api/v10/channels/"
        f"{DISCORD_REVIEW_CHANNEL_ID}/messages"
    )

    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}"
    }

    data = {
        "content": content
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers=headers,
            json=data
        )

        response.raise_for_status()

        return response.json()


async def send_review_verdict(
    discord_id: str,
    username: str,
    level_name: str,
    approved: bool,
    moderator_comment: str,
    proof_url: str
):

    url = (
        f"https://discord.com/api/v10/channels/"
        f"{DISCORD_REVIEW_CHANNEL_ID}/messages"
    )

    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}"
    }

    verdict = "Approved" if approved else "Denied"
    colour = 0x57F287 if approved else 0xED4245

    data = {
        "content": f"<@{discord_id}>",
        "allowed_mentions": {
            "users": [discord_id]
        },
        "embeds": [
            {
                "title": f"Submission {verdict}",
                "color": colour,
                "fields": [
                    {
                        "name": "User",
                        "value": username,
                        "inline": True
                    },
                    {
                        "name": "Level",
                        "value": level_name,
                        "inline": True
                    },
                    {
                        "name": "Moderator Comment",
                        "value": moderator_comment,
                        "inline": False
                    },
                    {
                        "name": "Proof",
                        "value": f"[View submitted proof]({proof_url})",
                        "inline": False
                    }
                ]
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers=headers,
            json=data
        )

        response.raise_for_status()

        return response.json()


async def send_ranking_changelog(changes: list[dict]):

    if not changes:
        return

    url = (
        f"https://discord.com/api/v10/channels/"
        f"{DISCORD_CHANGELOG_CHANNEL_ID}/messages"
    )

    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}"
    }

    description = "\n".join(
        (
            f"**{change['level_name']}**: "
            f"#{change['old_rank']} → #{change['new_rank']}"
        )
        for change in changes
    )

    data = {
        "embeds": [
            {
                "title": "Ranking Update",
                "description": description,
                "color": 0x3B98D3
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers=headers,
            json=data
        )

        response.raise_for_status()

        return response.json()


async def send_new_placement(
    level_name: str,
    rank: int,
    verification_url: str
):
    if None in (level_name, rank, verification_url):
        return

    url = (
        f"https://discord.com/api/v10/channels/"
        f"{DISCORD_CHANGELOG_CHANNEL_ID}/messages"
    )

    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}"
    }

    description = (
        f"**{level_name}** has been added and placed at #{rank}"
    )

    data = {
        "embeds": [
            {
                "title": "New Level Placement",
                "description": description,
                "color": 0x3B98D3
            }
        ]
    }

    async with httpx.AsyncClient() as client:

        # placement message
        response = await client.post(
            url,
            headers=headers,
            json=data
        )

        response.raise_for_status()

        # verification video
        response = await client.post(
            url,
            headers=headers,
            json={
                "content": verification_url
            }
        )

        response.raise_for_status()