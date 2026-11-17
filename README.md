# AI-Analytics

An AI sales analyst built on the [Model Context Protocol (MCP)](https://modelcontextprotocol.io).

The project exposes a SQLite sales database to an LLM through a small, read-only MCP server. Connected to an MCP host such as Cursor, the model can answer business questions in plain language — for example, *"Which customers stopped buying in the last 3 months?"* — by inspecting the schema, writing SQL, and querying the data on its own.

## Features

- **MCP tools** — schema discovery, ad-hoc read-only SQL, and a ready-made analytics query.
- **MCP resource** — the database schema published as `db://schema`.
- **Defense in depth** — the database is read-only at the driver level, and queries are additionally validated, time-limited, and row-limited.
- **Self-correcting queries** — SQL errors are returned to the model as text, so it can fix its query and retry.
- **Reproducible demo data** — a seeded generator creates customers, products, and orders, including a known set of churned customers.

## Architecture

```
Cursor (MCP host + client)  ⇄  stdio  ⇄  server.py (MCP server)  →  data/sales.db (SQLite, read-only)
```

The host launches `server.py` as a subprocess and communicates with it over stdin/stdout. No network ports are opened.

## Tech stack

- Python 3.14
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) 2.x (`MCPServer`)
- SQLite (standard library `sqlite3`)
- [uv](https://docs.astral.sh/uv/) for dependency management

## Project structure

```
AI-Analytics/
├── .cursor/mcp.json      # MCP server registration for Cursor
├── data/sales.db         # generated database (git-ignored)
├── scripts/seed_db.py    # demo data generator
├── server.py             # MCP server: tools and resources
├── pyproject.toml
└── uv.lock
```

## Data model

| Table         | Description                                                |
|---------------|------------------------------------------------------------|
| `customers`   | `id`, `name`, `email`, `city`, `created_at`                |
| `products`    | `id`, `name`, `category`, `price`                          |
| `orders`      | `id`, `customer_id`, `order_date`, `status`                |
| `order_items` | `id`, `order_id`, `product_id`, `quantity`, `unit_price`   |

The generator creates 80 customers, 25 products across 4 categories, and roughly 1,200 orders over the past year. Ten customers are deliberately "churned": their last order is 100–200 days old. Dates are relative to the current day, and the random seed is fixed, so the data stays realistic and reproducible.

## MCP capabilities

### Tools

| Tool                       | Purpose                                                                      |
|----------------------------|------------------------------------------------------------------------------|
| `get_schema()`             | Returns the `CREATE TABLE` statements so the model can learn the structure.  |
| `run_readonly_query(sql)`  | Executes a single read-only `SELECT`/`WITH` query. Returns up to 200 rows.   |
| `top_customers(limit, days)` | Top customers by revenue from completed orders over the last `days` days.  |
| `ping()`                   | Health check: verifies the server can read the database.                     |

### Resources

| URI           | Content                                  |
|---------------|------------------------------------------|
| `db://schema` | SQL schema of the sales database (text). |

## Security

`run_readonly_query` accepts arbitrary SQL from the model, so it is protected by several independent layers:

1. **Read-only connection.** The database is opened with `mode=ro`; SQLite rejects any write regardless of the query. This is the primary safeguard.
2. **Statement allow-list.** Only queries starting with `SELECT` or `WITH` are accepted.
3. **Single statement.** Queries containing `;` (multiple statements) are rejected.
4. **Keyword deny-list.** `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `ATTACH`, `DETACH`, `PRAGMA`, and `VACUUM` are blocked. This catches cases like `WITH x AS (SELECT 1) DELETE ...`.
5. **Timeout.** Queries are interrupted after 5 seconds.
6. **Row limit.** At most 200 rows are returned; a `truncated` flag tells the model when more data exists.

`top_customers` uses a fixed, parameterized query, so the model only supplies numeric arguments, which are clamped to safe ranges.

## Getting started

### Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js (only for MCP Inspector)

### Installation

```bash
git clone <repository-url>
cd AI-Analytics
uv sync
uv run python scripts/seed_db.py
```

The seed script prints the IDs of the churned customers, which you can use to verify the model's answers.

### Testing with MCP Inspector

```bash
uv run mcp dev server.py
```

This opens MCP Inspector in the browser, where you can connect to the server, list its tools and resources, and call them manually.

### Connecting to Cursor

The server is registered in `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "sales-analyst": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/AI-Analytics", "python", "server.py"]
    }
  }
}
```

Update the path to match your machine, then enable `sales-analyst` in Cursor's MCP settings. A green indicator with 4 tools and 1 resource means the server is connected. If you change `server.py`, toggle the server off and on to reload it.

## Example questions

Ask these in a Cursor chat in **Agent** mode:

- *Which customers stopped buying in the last 3 months?* — the model calls `get_schema`, then writes its own SQL with `run_readonly_query`.
- *Show the top 5 customers by revenue over the last 90 days.* — the model uses the dedicated `top_customers` tool.
- *Which product category generates the most revenue?* — an ad-hoc query joining three tables.
- *Delete all customers from Moscow.* — the server rejects the request.

## Limitations

- The keyword filter is intentionally conservative: queries containing `;` inside string literals are rejected.
- The path in `.cursor/mcp.json` is absolute and must be adjusted per machine.
- This is a learning and demo project, not a production analytics system.
