def calculate_waffle_points(rank: int, level_count: int) -> int:
    if level_count <= 0:
        return 0

    if level_count == 1:
        return 500

    points = 1 + 499 * (
        (level_count - rank) / (level_count - 1)
    ) ** 1.5

    return round(points)


def recalculate_waffle_points(cur):
    cur.execute("""
        SELECT id, rank
        FROM levels
        WHERE active = TRUE
        ORDER BY rank;
    """)

    levels = cur.fetchall()
    level_count = len(levels)

    for level in levels:
        points = calculate_waffle_points(
            level["rank"],
            level_count
        )

        cur.execute("""
            UPDATE levels
            SET points = %s
            WHERE id = %s;
        """, (
            points,
            level["id"]
        ))