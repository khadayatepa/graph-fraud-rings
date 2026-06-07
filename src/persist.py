"""Persist detected rings to Oracle (via MCP). Table prefix `fraud_`."""
from __future__ import annotations

from mcp_oracle import OracleMCP


def _cre(ddl: str) -> str:
    body = ddl.replace("'", "''")
    return ("BEGIN EXECUTE IMMEDIATE '" + body + "'; "
            "EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF; END;")


DDL = [
    _cre("CREATE TABLE fraud_runs (run_id NUMBER PRIMARY KEY, created_at TIMESTAMP DEFAULT SYSTIMESTAMP, "
         "ring VARCHAR2(400), member_count NUMBER, avg_fraud_dist NUMBER, total_amount NUMBER, summary CLOB)"),
    "CREATE OR REPLACE VIEW v_fraud_feed AS SELECT run_id, created_at, ring, member_count, "
    "avg_fraud_dist, total_amount, summary FROM fraud_runs",
]


def _q(t: str) -> str:
    t = (t or "").replace("'", "''").replace("&", "'||CHR(38)||'")
    t = t.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "'||CHR(10)||'")
    return "'" + t + "'"


def _clob(t: str, n: int = 1500) -> str:
    raw = t or ""
    parts = [raw[i:i + n] for i in range(0, len(raw), n)] or [""]
    return "||".join("TO_CLOB(" + _q(p) + ")" for p in parts)


async def _exec(mcp: OracleMCP, sql: str, what: str) -> None:
    out = await mcp.run_sql(sql)
    if "ORA-" in out or "Error" in out or "cancelled" in out:
        raise RuntimeError(f"persist {what} FAILED: " + next((l for l in out.splitlines() if 'ORA-' in l), out[:300]))


async def ensure_tables(mcp: OracleMCP) -> None:
    for s in DDL:
        await mcp.run_sql(s)


async def save(mcp: OracleMCP, *, run_id: int, ring: str, member_count: int,
               avg_fraud_dist: float, total_amount: float, summary: str) -> None:
    await _exec(mcp,
        "INSERT INTO fraud_runs (run_id, ring, member_count, avg_fraud_dist, total_amount, summary) VALUES "
        f"({run_id}, {_q(ring)}, {member_count}, {avg_fraud_dist}, {total_amount}, {_clob(summary)})", "run")
    await _exec(mcp, "COMMIT", "commit")
