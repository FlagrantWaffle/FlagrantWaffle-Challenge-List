from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from starlette.middleware.sessions import SessionMiddleware

from db import get_connection

from dotenv import load_dotenv

from zoneinfo import ZoneInfo
from datetime import datetime

from psycopg.rows import dict_row
from urllib.parse import urlparse, parse_qs

import os
import uvicorn
import authlib
from discord_oauth import oauth
from fastapi import FastAPI, Request, Form, HTTPException, BackgroundTasks
from discord_bot import send_review_verdict

from pathlib import Path
import markdown
import hashlib


load_dotenv()

app = FastAPI()

SESSION_HTTPS_ONLY = (
    os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true"
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["SESSION_SECRET"],
    https_only=SESSION_HTTPS_ONLY,
    same_site="lax"
)

templates = Jinja2Templates(directory="templates")


css_path = Path(__file__).resolve().parent / "static" / "css" / "styles.css"

css_version = hashlib.sha256(
    css_path.read_bytes()
).hexdigest()[:8]

templates.env.globals["css_version"] = css_version


app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)



def get_current_user(request: Request):
    user_id = request.session.get("user_id")

    if user_id is None:
        return None

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT
                    id,
                    username,
                    is_admin,
                    discord_id,
                    discord_username,
                    discord_display_name,
                    discord_avatar_hash
                FROM users
                WHERE id = %s;
            """, (user_id,))

            return cur.fetchone()


def require_admin(request: Request):
    current_user = get_current_user(request)

    if current_user is None:
        raise HTTPException(
            status_code=401,
            detail="You must be logged in"
        )

    if not current_user["is_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return current_user


# ------------------------------------------
# ENDPOINTS
# ------------------------------------------

@app.get("/health")
def health(request: Request):

    current_user = require_admin(request)

    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")

        db_status = "ok"

    except Exception:
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "error",
        "database": db_status,
        "timestamp": datetime.now(
            ZoneInfo("Europe/London")
        ).strftime("%Y-%m-%d %H:%M:%S %Z")
    }


@app.get("/")
def root(request: Request):

    current_user = get_current_user(request)

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
            SELECT
                submissions.id,
                submissions.status,
                submissions.proof_url,
                submissions.moderator_comment,
                submissions.reviewed_at,
                submitter.username AS submitter_username,

                levels.name AS level_name,
                levels.id AS level_id

            FROM submissions

            JOIN users AS submitter
                ON submitter.id = submissions.user_id

            JOIN levels
                ON levels.id = submissions.level_id

            WHERE submissions.status = 'approved'

            ORDER BY submissions.reviewed_at DESC NULLS LAST, submissions.id DESC

            LIMIT 5;            
            """)

            review_preview = cur.fetchall()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "current_user": current_user,
            "review_preview": review_preview
        }
    )


@app.get("/users")
def get_users(request: Request):

    current_user = require_admin(request)


    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT id, username, is_admin
                FROM users
                ORDER BY id;
            """)

            users = cur.fetchall()

    return users


@app.get("/users/{username}")
def user_profile(request: Request, username: str):
    current_user = get_current_user(request)

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:

            # Get profile user
            cur.execute("""
                SELECT
                    id,
                    username,
                    discord_id,
                    discord_username,
                    discord_display_name,
                    discord_avatar_hash
                FROM users
                WHERE username = %s;
            """, (username,))

            user_info = cur.fetchone()

            if user_info is None:
                raise HTTPException(
                    status_code=404,
                    detail="User not found"
                )


            # User's approved completions
            cur.execute("""
                SELECT
                    levels.id,
                    levels.name,
                    levels.rank,
                    levels.points,
                    completions.completed_at,
                    submissions.moderator_comment

                FROM completions

                JOIN levels
                    ON levels.id = completions.level_id

                JOIN submissions
                    ON submissions.id = completions.submission_id

                WHERE completions.user_id = %s

                ORDER BY levels.rank;
            """, (user_info["id"],))

            completed_levels = cur.fetchall()


            # User's total Waffle Points
            cur.execute("""
                SELECT
                    COALESCE(SUM(levels.points), 0) AS waffle_points

                FROM completions

                JOIN levels
                    ON levels.id = completions.level_id

                WHERE completions.user_id = %s;
            """, (user_info["id"],))

            points_result = cur.fetchone()
            waffle_points = points_result["waffle_points"]


            # private profile information can only be seen by the profile owner or an admin
            can_view_submissions = (
                current_user is not None
                and (
                    current_user["id"] == user_info["id"]
                    or current_user["is_admin"]
                )
            )


            user_submissions = []
            submission_history = []


            if can_view_submissions:

                # pending submissions
                cur.execute("""
                    SELECT
                        submissions.id,
                        submissions.proof_url,
                        submissions.submitted_at,
                        submissions.status,

                        levels.id AS level_id,
                        levels.name,
                        levels.rank

                    FROM submissions

                    JOIN levels
                        ON levels.id = submissions.level_id

                    WHERE submissions.user_id = %s
                    AND submissions.status = 'pending'

                    ORDER BY submissions.submitted_at DESC;
                """, (user_info["id"],))

                user_submissions = cur.fetchall()


                # reviewed submission history
                cur.execute("""
                    SELECT
                        submissions.id,
                        submissions.status,
                        submissions.proof_url,
                        submissions.submitted_at,
                        submissions.reviewed_at,
                        submissions.moderator_comment,

                        levels.id AS level_id,
                        levels.name AS level_name,
                        levels.rank

                    FROM submissions

                    JOIN levels
                        ON levels.id = submissions.level_id

                    LEFT JOIN users AS reviewer
                        ON reviewer.id = submissions.reviewed_by

                    WHERE submissions.user_id = %s
                    AND submissions.status IN ('approved', 'denied')

                    ORDER BY
                        submissions.reviewed_at DESC,
                        submissions.id DESC;
                """, (user_info["id"],))

                submission_history = cur.fetchall()


    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "user_info": user_info,
            "completed_levels": completed_levels,
            "waffle_points": waffle_points,
            "current_user": current_user,
            "user_submissions": user_submissions,
            "submission_history": submission_history,
            "can_view_submissions": can_view_submissions
        }
    )


@app.get("/levels")
def get_levels(request: Request):
    current_user = get_current_user(request)

    user_id = current_user["id"] if current_user else None

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT
                    levels.id,
                    levels.name,
                    levels.gd_id,
                    levels.creator,
                    levels.rank,
                    levels.points,

                    EXISTS (
                        SELECT 1
                        FROM completions
                        WHERE completions.level_id = levels.id
                        AND completions.user_id = %s
                    ) AS completed

                FROM levels

                WHERE levels.active = TRUE

                ORDER BY levels.rank;
            """, (user_id,))

            levels = cur.fetchall()

    return templates.TemplateResponse(
        request=request,
        name="levels.html",
        context={
            "levels": levels,
            "current_user": current_user
        }
    )


@app.get("/login")
def login_page(request: Request):
    current_user = get_current_user(request)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": None,
            "current_user": current_user
        }
    )


@app.get("/logout")
def logout(request: Request):
    request.session.clear()

    return RedirectResponse(
        url="/login",
        status_code=303
    )


@app.get("/leaderboard")
def leaderboard_page(request: Request):
    current_user = get_current_user(request)

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT
                    users.id,
                    users.username,
                    COALESCE(SUM(levels.points), 0) AS waffle_points
                FROM users

                LEFT JOIN completions
                    ON completions.user_id = users.id

                LEFT JOIN levels
                    ON levels.id = completions.level_id

                GROUP BY
                    users.id,
                    users.username

                ORDER BY
                    waffle_points DESC,
                    users.username ASC;
            """)

            leaderboard = cur.fetchall()

    return templates.TemplateResponse(
        request=request,
        name="leaderboard.html",
        context={
            "leaderboard": leaderboard,
            "current_user": current_user
        }
    )


@app.post("/levels/{level_id}/submit")
def submit_completion(
    request: Request,
    level_id: int,
    proof_url: str = Form(...)
):
    current_user = get_current_user(request)

    if current_user is None:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    with get_connection() as conn:
        with conn.cursor() as cur:

            # check whether the user has already completed this level
            cur.execute("""
                SELECT 1
                FROM completions
                WHERE user_id = %s
                AND level_id = %s;
            """, (
                current_user["id"],
                level_id
            ))

            already_completed = cur.fetchone() is not None

            if already_completed:
                raise HTTPException(
                    status_code=409,
                    detail="You have already completed this level"
                )


            # check whether the user already has a pending submission
            cur.execute("""
                SELECT 1
                FROM submissions
                WHERE user_id = %s
                AND level_id = %s
                AND status = 'pending';
            """, (
                current_user["id"],
                level_id
            ))

            already_pending = cur.fetchone() is not None

            if already_pending:
                raise HTTPException(
                    status_code=409,
                    detail="You already have a pending submission for this level"
                )


            # create the new submission
            cur.execute("""
                INSERT INTO submissions (
                    user_id,
                    level_id,
                    proof_url
                )
                VALUES (%s, %s, %s);
            """, (
                current_user["id"],
                level_id,
                proof_url
            ))

            # i

    request.session["flash_message"] = (
        "Submission sent successfully!"
    )

    return RedirectResponse(
        url=f"/levels/{level_id}",
        status_code=303
    )


@app.get("/levels/{level_id}")
def level_page(request: Request, level_id: int):

    current_user = get_current_user(request)

    flash_message = request.session.pop(
        "flash_message",
        None
    )

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:

            # get level
            cur.execute("""
                SELECT
                    id,
                    name,
                    creator,
                    gd_id,
                    rank,
                    points,
                    verification_url
                FROM levels
                WHERE id = %s;
            """, (level_id,))

            level = cur.fetchone()

            if level is None:
                raise HTTPException(
                    status_code=404,
                    detail="Level not found"
                )


            # check if user already has a pending submission
            pending_submission = False

            if current_user:

                cur.execute("""
                    SELECT 1
                    FROM submissions
                    WHERE user_id = %s
                    AND level_id = %s
                    AND status = 'pending';
                """, (
                    current_user["id"],
                    level["id"]
                ))

                pending_submission = (
                    cur.fetchone() is not None
                )


            # get level victors
            cur.execute("""
                SELECT
                    users.id,
                    users.username,
                    completions.completed_at,
                    completions.proof_url
                FROM completions

                JOIN users
                    ON users.id = completions.user_id

                WHERE completions.level_id = %s

                ORDER BY completions.completed_at ASC;
            """, (level_id,))

            victors = cur.fetchall()


            # check if current user has completed the level
            user_completion = False

            if current_user:

                user_completion = any(
                    victor["id"] == current_user["id"]
                    for victor in victors
                )


    video_id = None

    if level["verification_url"]:

        parsed_url = urlparse(
            level["verification_url"]
        )

        query = parse_qs(
            parsed_url.query
        )

        video_id = query.get(
            "v",
            [None]
        )[0]


    if video_id:

        level["embed_url"] = (
            f"https://www.youtube.com/embed/{video_id}"
        )

    else:

        level["embed_url"] = None


    return templates.TemplateResponse(
        request=request,
        name="level.html",
        context={
            "level": level,
            "current_user": current_user,
            "flash_message": flash_message,
            "victors": victors,
            "user_completion": user_completion,
            "pending_submission": pending_submission
        }
    )


@app.get("/admin")
def admin_page(
    request: Request,
    history_page: int = 1):

    current_user = require_admin(request)

    page_size = 20

    if history_page < 1:
        history_page = 1

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # list admin users
            cur.execute("""
                SELECT username, levels_reviewed FROM users
                WHERE is_admin = TRUE;                   
            """)

            site_admin = cur.fetchall()

            # get number of reviewed submissions
            cur.execute("""
                SELECT COUNT(*) AS total_reviews
                FROM submissions
                WHERE status IN ('approved', 'denied');
            """)

            total_reviews = cur.fetchone()["total_reviews"]
            total_pages = max(1, (total_reviews + page_size - 1) // page_size)

            if history_page > total_pages:
                history_page = total_pages

            offset = (history_page - 1) * page_size

            # pull review history
            cur.execute("""
                SELECT
                    submissions.id,
                    submissions.status,
                    submissions.proof_url,
                    submissions.submitted_at,
                    submissions.moderator_comment,
                    submissions.reviewed_at,

                    submitter.username AS submitter_username,

                    levels.id AS level_id,
                    levels.name AS level_name,

                    reviewer.username AS reviewer_username

                FROM submissions

                JOIN users AS submitter
                    ON submitter.id = submissions.user_id

                JOIN levels
                    ON levels.id = submissions.level_id

                JOIN users AS reviewer
                    ON reviewer.id = submissions.reviewed_by

                WHERE submissions.status IN ('approved', 'denied')

                ORDER BY submissions.reviewed_at DESC, submissions.id DESC
                LIMIT %s
                OFFSET %s;
            """, (page_size, offset,))

            review_history = cur.fetchall()


    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "current_user": current_user,
            "site_admin": site_admin,
            "review_history": review_history,
            "history_page": history_page,
            "total_pages": total_pages,
            "total_reviews": total_reviews
        }
    )


@app.get("/admin/submissions")
def admin_submissions(request: Request):
    current_user = require_admin(request)

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:

            cur.execute("""
                SELECT
                    submissions.id,
                    submissions.proof_url,
                    submissions.submitted_at,
                    submissions.status,

                    users.id AS user_id,
                    users.username,

                    levels.id AS level_id,
                    levels.name AS level_name,
                    levels.rank

                FROM submissions

                JOIN users
                    ON users.id = submissions.user_id

                JOIN levels
                    ON levels.id = submissions.level_id

                WHERE submissions.status = 'pending'

                ORDER BY submissions.submitted_at ASC;
            """)

            submissions = cur.fetchall()


    return templates.TemplateResponse(
        request=request,
        name="admin-submissions.html",
        context={
            "submissions": submissions,
            "current_user": current_user
        }
    )


@app.get("/admin/submissions/{submission_id}/approve")
def approve_submission(
    request: Request,
    submission_id: int):

    current_user = require_admin(request)

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT
                    submissions.id,
                    submissions.proof_url,
                    submissions.submitted_at,
                    submissions.status,

                    users.username,

                    levels.id AS level_id,
                    levels.name AS level_name

                FROM submissions

                JOIN users
                    ON users.id = submissions.user_id

                JOIN levels
                    ON levels.id = submissions.level_id

                WHERE submissions.id = %s
                AND submissions.status = 'pending';
            """, (submission_id,))

            submission = cur.fetchone()

    if submission is None:
        raise HTTPException(
            status_code=404,
            detail="Submission not found"
        )

    return templates.TemplateResponse(
        request=request,
        name="admin-approve.html",
        context={
            "current_user": current_user,
            "submission": submission
        }
    )


@app.post("/admin/submissions/{submission_id}/approve")
def process_approval(
    request: Request,
    submission_id: int,
    background_tasks: BackgroundTasks,
    moderator_comment: str = Form(...)
    ):

    current_user = require_admin(request)

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:

            # get the submission being approved
            cur.execute("""
                SELECT
                    submissions.user_id,
                    submissions.level_id,
                    submissions.proof_url,
                    submissions.submitted_at,

                    users.username,
                    users.discord_id,

                    levels.name AS level_name

                FROM submissions

                JOIN users
                    ON users.id = submissions.user_id

                JOIN levels
                    ON levels.id = submissions.level_id

                WHERE submissions.id = %s
                AND submissions.status = 'pending';
            """, (submission_id,))

            submission = cur.fetchone()

            if submission is None:
                raise HTTPException(
                    status_code=404,
                    detail="Pending submission not found"
                )

            if submission["discord_id"]:

                background_tasks.add_task(
                    send_review_verdict,
                    discord_id=submission["discord_id"],
                    username=submission["username"],
                    level_name=submission["level_name"],
                    approved=True,
                    moderator_comment=moderator_comment,
                    proof_url=submission["proof_url"]
                )


            # mark the submission as approved
            cur.execute("""
                UPDATE submissions
                SET
                    status = 'approved',
                    moderator_comment = %s,
                    reviewed_at = NOW(),
                    reviewed_by = %s
                WHERE id = %s;
            """, (
                moderator_comment,
                current_user["id"],
                submission_id
            ))


            # create the approved completion
            cur.execute("""
                INSERT INTO completions (
                    user_id,
                    level_id,
                    submission_id,
                    proof_url,
                    completed_at
                )
                VALUES (%s, %s, %s, %s, %s);
            """, (
                submission["user_id"],
                submission["level_id"],
                submission_id,
                submission["proof_url"],
                submission["submitted_at"]
            ))

            # increment the admin's review count
            cur.execute("""
                UPDATE users
                SET levels_reviewed = levels_reviewed + 1
                WHERE id = %s
                AND is_admin = TRUE;
            """, (current_user["id"],))

            return RedirectResponse(
                url="/admin/submissions",
                status_code=303
            )


@app.get("/admin/submissions/{submission_id}/deny")
def deny_submission(
    request: Request,
    submission_id: int):

    current_user = require_admin(request)

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT
                    submissions.id,
                    submissions.proof_url,
                    submissions.submitted_at,
                    submissions.status,

                    users.username,

                    levels.id AS level_id,
                    levels.name AS level_name

                FROM submissions

                JOIN users
                    ON users.id = submissions.user_id

                JOIN levels
                    ON levels.id = submissions.level_id

                WHERE submissions.id = %s
                AND submissions.status = 'pending';
            """, (submission_id,))

            submission = cur.fetchone()

    if submission is None:
        raise HTTPException(
            status_code=404,
            detail="Submission not found"
        )

    return templates.TemplateResponse(
        request=request,
        name="admin-deny.html",
        context={
            "current_user": current_user,
            "submission": submission
        }
    )


@app.post("/admin/submissions/{submission_id}/deny")
def process_denial(
    request: Request,
    submission_id: int,
    background_tasks: BackgroundTasks,
    moderator_comment: str = Form(...)):

    current_user = require_admin(request)

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:

            # get the submission being denied
            cur.execute("""
                SELECT
                    submissions.user_id,
                    submissions.level_id,
                    submissions.proof_url,
                    submissions.submitted_at,

                    users.username,
                    users.discord_id,

                    levels.name AS level_name

                FROM submissions

                JOIN users
                    ON users.id = submissions.user_id

                JOIN levels
                    ON levels.id = submissions.level_id

                WHERE submissions.id = %s
                AND submissions.status = 'pending';
            """, (submission_id,))

            submission = cur.fetchone()

            if submission is None:
                raise HTTPException(
                    status_code=404,
                    detail="Pending submission not found"
                )

            if submission["discord_id"]:

                background_tasks.add_task(
                    send_review_verdict,
                    discord_id=submission["discord_id"],
                    username=submission["username"],
                    level_name=submission["level_name"],
                    approved=False,
                    moderator_comment=moderator_comment,
                    proof_url=submission["proof_url"]
                )

            # mark the submission as denied
            cur.execute("""
                UPDATE submissions
                SET
                    status = 'denied',
                    moderator_comment = %s,
                    reviewed_at = NOW(),
                    reviewed_by = %s
                WHERE id = %s
            """, (
                moderator_comment,
                current_user["id"],
                submission_id
            ))

            # increment the admin's review count
            cur.execute("""
                UPDATE users
                SET levels_reviewed = levels_reviewed + 1
                WHERE id = %s
                AND is_admin = TRUE;
            """, (current_user["id"],))


        return RedirectResponse(
            url="/admin/submissions",
            status_code=303
        )


@app.get("/privacy")
def privacy_policy(request: Request):

    current_user = get_current_user(request)

    markdown_text = Path(
        "legal/privacy.md"
    ).read_text(encoding="utf-8")

    legal_html = markdown.markdown(
        markdown_text,
        extensions=["extra"]
    )

    return templates.TemplateResponse(
        request=request,
        name="legal.html",
        context={
            "current_user": current_user,
            "page_title": "Privacy Policy",
            "legal_html": legal_html
        }
    )


@app.get("/terms")
def terms_of_service(request: Request):

    current_user = get_current_user(request)

    markdown_text = Path(
        "legal/terms.md"
    ).read_text(encoding="utf-8")

    legal_html = markdown.markdown(
        markdown_text,
        extensions=["extra"]
    )

    return templates.TemplateResponse(
        request=request,
        name="legal.html",
        context={
            "current_user": current_user,
            "page_title": "Terms of Service",
            "legal_html": legal_html
        }
    )


@app.get("/rules")
def terms_of_service(request: Request):

    current_user = get_current_user(request)

    markdown_text = Path(
        "legal/rules.md"
    ).read_text(encoding="utf-8")

    legal_html = markdown.markdown(
        markdown_text,
        extensions=["extra"]
    )

    return templates.TemplateResponse(
        request=request,
        name="legal.html",
        context={
            "current_user": current_user,
            "page_title": "Rules of Submission",
            "legal_html": legal_html
        }
    )





@app.get("/login/discord")
async def login_discord(request: Request):
    redirect_uri = os.getenv("DISCORD_REDIRECT_URI")

    return await oauth.discord.authorize_redirect(
        request,
        redirect_uri
    )


@app.get("/auth/discord/callback")
async def discord_callback(request: Request):
    token = await oauth.discord.authorize_access_token(request)

    response = await oauth.discord.get(
        "users/@me",
        token=token
    )

    response.raise_for_status()

    discord_user = response.json()

    discord_id = discord_user["id"]
    discord_username = discord_user["username"]
    discord_display_name = discord_user.get("global_name")
    discord_avatar_hash = discord_user.get("avatar")

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:

            # does this discord account already have a site account?
            cur.execute("""
                SELECT
                    id,
                    username,
                    is_admin
                FROM users
                WHERE discord_id = %s;
            """, (discord_id,))

            user = cur.fetchone()


            # new Discord user = create a site account
            if user is None:

                site_username = discord_username

                # protect against a legacy site account already using the same username

                cur.execute("""
                    SELECT 1
                    FROM users
                    WHERE username = %s;
                """, (site_username,))

                username_taken = cur.fetchone() is not None

                if username_taken:
                    site_username = f"{discord_username}_{discord_id}"

                cur.execute("""
                    INSERT INTO users (
                        username,
                        password_hash,
                        discord_id,
                        discord_username,
                        discord_display_name,
                        discord_avatar_hash
                    )
                    VALUES (%s, NULL, %s, %s, %s, %s)
                    RETURNING
                        id,
                        username,
                        is_admin;
                """, (
                    site_username,
                    discord_id,
                    discord_username,
                    discord_display_name,
                    discord_avatar_hash
                ))

                user = cur.fetchone()


            # existing discord user = refresh changeable discord data
            else:
                cur.execute("""
                    UPDATE users
                    SET
                        discord_username = %s,
                        discord_display_name = %s,
                        discord_avatar_hash = %s
                    WHERE id = %s;
                """, (
                    discord_username,
                    discord_display_name,
                    discord_avatar_hash,
                    user["id"]
                ))


    request.session.clear()
    request.session["user_id"] = user["id"]

    return RedirectResponse(
        url="/levels",
        status_code=303
    )


if __name__ == "__main__":
    host = "localhost"
    port = 8000

    print(f"http://{host}:{port}/levels")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True
    )