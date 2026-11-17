import sqlite3
from pathlib import Path
from mcp.server import MCPServer
import re
import time
from typing import Any


DB_PATH = Path(__file__).resolve().parent / "data" / "sales.db"

mcp = MCPServer("sales-analyst")
MAX_ROWS = 200
QUERY_TIMEOUT_SEC = 5
FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|VACUUM)\b",
    re.IGNORECASE,
)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@mcp.tool()
def ping() -> str:
    """Check that the server is running and can read the database."""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    conn.close()
    return f"OK, customers in DB: {count}"


def read_schema() -> str:
    conn = get_connection()
    rows = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL"
    ).fetchall()
    conn.close()
    return "\n\n".join(row["sql"] for row in rows)


@mcp.resource(
    "db://schema",
    name="db_schema",
    description="SQL schema of the sales database",
    mime_type="text/plain",
)
def schema_resource() -> str:
    return read_schema()


@mcp.tool()
def get_schema() -> str:
    """Return the SQL schema (CREATE TABLE statements) of the sales database.
    Call this first to learn table and column names before writing SQL."""
    return read_schema()


@mcp.tool()
def run_readonly_query(sql: str) -> dict[str, Any]:
    """Run a single read-only SQL query (SQLite dialect) on the sales database.
    Only SELECT or WITH queries are allowed. Returns at most 200 rows.
    Dates are stored as 'YYYY-MM-DD' text; use date('now', '-3 months') for relative dates.
    """
    query = sql.strip().rstrip(";").strip()

    if ";" in query:
        return {"error": "Only one SQL statement is allowed."}
    if not query.upper().startswith(("SELECT", "WITH")):
        return {"error": "Only SELECT or WITH queries are allowed."}
    if FORBIDDEN.search(query):
        return {"error": "Query contains a forbidden keyword."}

    conn = get_connection()
    deadline = time.monotonic() + QUERY_TIMEOUT_SEC
    conn.set_progress_handler(lambda: time.monotonic() > deadline, 10_000)
    try:
        rows = conn.execute(query).fetchmany(MAX_ROWS + 1)
    except sqlite3.Error as e:
        return {"error": f"SQL error: {e}"}
    finally:
        conn.close()

    return {
        "rows": [dict(r) for r in rows[:MAX_ROWS]],
        "truncated": len(rows) > MAX_ROWS,
    }


@mcp.tool()
def top_customers(limit: int = 10, days: int = 90) -> list[dict[str, Any]]:
    """Top customers by revenue from completed orders over the last `days` days."""
    limit = max(1, min(limit, 100))
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT c.id, c.name, c.city,
               COUNT(DISTINCT o.id) AS orders,
               ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue
        FROM customers c
        JOIN orders o ON o.customer_id = c.id
        JOIN order_items oi ON oi.order_id = o.id
        WHERE o.status = 'completed'
          AND o.order_date >= date('now', ?)
        GROUP BY c.id
        ORDER BY revenue DESC
        LIMIT ?
        """,
        (f"-{days} days", limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    mcp.run()
