"""
Find money-laundering rings in Oracle 26ai: detect transfer cycles with recursive
SQL, confirm the members look like known fraud with AI Vector Search, and have an
LLM summarise the suspected ring (advisory only — nothing is changed).

Run:  python src/detect.py
"""
from __future__ import annotations

import asyncio
import csv
import io
import sys
import textwrap

from openai import AsyncOpenAI

import config
import persist
from mcp_oracle import open_oracle_mcp, OracleMCP

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

# Recursive cycle detection — find transfer paths that return to their start.
CYCLE_SQL = """
WITH paths (start_acct, cur_acct, depth, pth) AS (
  SELECT from_acct, to_acct, 1, '-'||from_acct||'-'||to_acct||'-' FROM transfers
  UNION ALL
  SELECT p.start_acct, t.to_acct, p.depth+1, p.pth||t.to_acct||'-'
  FROM paths p JOIN transfers t ON t.from_acct = p.cur_acct
  WHERE p.depth < 5 AND (t.to_acct = p.start_acct OR INSTR(p.pth, '-'||t.to_acct||'-') = 0))
SELECT pth FROM paths WHERE cur_acct = start_acct AND depth BETWEEN 2 AND 5
""".strip()

FRAUD_SQL = """
SELECT a.account_id, a.name,
  ROUND((SELECT MIN(VECTOR_DISTANCE(a.embedding, k.embedding, COSINE)) FROM known_fraud k),3) AS fraud_dist
FROM accounts a
""".strip()


def _rows(out: str) -> list[list[str]]:
    r = list(csv.reader(io.StringIO(out)))
    return [x for x in r[1:] if x and x[0].strip() and "rows selected" not in x[0]]


def _wrap(t: str) -> str:
    return "\n".join(textwrap.fill(p, 92, initial_indent="   ", subsequent_indent="   ") if p.strip() else "" for p in t.splitlines())


async def main() -> None:
    client = AsyncOpenAI(api_key=config.OPENAI_API_KEY or None)
    print("\n=== Fraud-ring detection on Oracle 26ai ===\n")

    async with open_oracle_mcp(config.SQLCL_COMMAND, config.ORACLE_MCP_CONNECTION) as mcp:
        print("1) Detecting transfer cycles with recursive SQL...")
        cyc = _rows(await mcp.run_sql(CYCLE_SQL))
        rings: dict[frozenset, list[int]] = {}
        for row in cyc:
            ids = [int(x) for x in row[0].strip("-").split("-") if x]
            members = ids[:-1] if ids and ids[0] == ids[-1] else ids
            key = frozenset(members)
            if key and key not in rings:
                rings[key] = members
        print(f"   found {len(rings)} unique ring(s)")

        print("2) Scoring accounts against known fraud with AI Vector Search...")
        fr = {int(r[0]): {"name": r[1], "dist": float(r[2])} for r in _rows(await mcp.run_sql(FRAUD_SQL))}
        amounts = {(int(r[0]), int(r[1])): float(r[2]) for r in
                   _rows(await mcp.run_sql("SELECT from_acct, to_acct, amount FROM transfers"))}

        # rank rings by how fraud-like their members are (lower avg distance = worse)
        ranked = []
        for members in rings.values():
            avg = sum(fr[m]["dist"] for m in members) / len(members)
            # total flowing around the cycle
            total = 0.0
            seq = members + [members[0]]
            for a, b in zip(seq, seq[1:]):
                total += amounts.get((a, b), 0.0)
            ranked.append({"members": members, "avg_dist": round(avg, 3), "total": total})
        ranked.sort(key=lambda r: r["avg_dist"])

        for r in ranked:
            names = " → ".join(fr[m]["name"] for m in r["members"]) + f" → {fr[r['members'][0]]['name']}"
            print(f"   ring: {names}  | avg fraud-dist {r['avg_dist']} | ${r['total']:,.0f} cycled")

        top = ranked[0]
        names = [fr[m]["name"] for m in top["members"]]
        print("\n3) Asking the LLM to summarise the top suspected ring...")
        resp = await client.chat.completions.create(
            model=config.OPENAI_MODEL, temperature=0.3,
            messages=[
                {"role": "system", "content": "You are a financial-crime analyst. In 3-4 sentences, summarise this "
                 "suspected money-laundering ring: explain the circular flow, why the members look like known fraud, "
                 "and recommend ONE next investigative step. This is advisory only — recommend, do not act."},
                {"role": "user", "content":
                    f"Accounts in the cycle: {', '.join(names)}.\n"
                    f"They transfer money in a closed loop totalling about ${top['total']:,.0f} in round-number sums.\n"
                    f"Each account's cosine distance to known-fraud profiles (lower = more similar): "
                    + ", ".join(f"{fr[m]['name']}={fr[m]['dist']}" for m in top['members'])},
            ])
        summary = (resp.choices[0].message.content or "").strip()
        ring_str = " → ".join(names) + f" → {names[0]}"
        print(f"\n🚩 Top suspected ring: {ring_str}\n" + _wrap(summary) + "\n")

        await persist.ensure_tables(mcp)
        import time
        await persist.save(mcp, run_id=int(time.time()), ring=ring_str, member_count=len(names),
                           avg_fraud_dist=top["avg_dist"], total_amount=top["total"], summary=summary)
        print("💾 Saved to fraud_runs (view: v_fraud_feed).")


if __name__ == "__main__":
    asyncio.run(main())
