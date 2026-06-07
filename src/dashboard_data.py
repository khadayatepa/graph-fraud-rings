"""Read detected rings back out of Oracle through the SQLcl MCP server (as JSON)."""
from __future__ import annotations
import csv, io, json
from typing import Any
from mcp_oracle import OracleMCP

RUNS_SQL = """
SELECT JSON_ARRAYAGG(JSON_OBJECT('run_id' VALUE run_id, 'ring' VALUE ring,
       'member_count' VALUE member_count, 'avg_fraud_dist' VALUE avg_fraud_dist,
       'total_amount' VALUE total_amount,
       'created_at' VALUE TO_CHAR(created_at,'YYYY-MM-DD HH24:MI'), 'summary' VALUE summary RETURNING CLOB)
       ORDER BY created_at DESC RETURNING CLOB) AS data FROM fraud_runs
""".strip()

def _extract(out: str) -> Any:
    for row in list(csv.reader(io.StringIO(out)))[1:]:
        for cell in row:
            cell = cell.strip()
            if cell and cell[0] in "[{":
                return json.loads(cell)
    return None

async def list_runs(mcp: OracleMCP) -> list[dict]:
    return _extract(await mcp.run_sql(RUNS_SQL)) or []
