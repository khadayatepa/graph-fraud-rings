# Fraud-Ring Detection on Oracle 26ai — graph cycles + AI Vector Search

Catch money-laundering rings by combining two signals in Oracle 26ai: **transfer
cycles** (A→B→C→A) found with a recursive query, and **"does this account look like
known fraud?"** answered with AI Vector Search. An LLM then summarises the suspected
ring. Everything is read-only/advisory and reached through the **SQLcl MCP Server**.

```
 transfers ──recursive SQL──> cycles (rings)
 accounts  ──VECTOR_DISTANCE──> similarity to known-fraud profiles
                         └──> rings whose members look like fraud  ──> LLM summary
```

## Two ways to find the rings
- **Recursive SQL** (used here) — runs as any user, no special privilege.
- **SQL Property Graph** — the elegant `GRAPH_TABLE ( MATCH (a)->(b)->(c)->(a) )` form.
  Needs the `CREATE PROPERTY GRAPH` privilege (`GRANT CREATE PROPERTY GRAPH TO debate;`).
  Both queries are in `sql/schema.sql`.

## Setup
```powershell
pip install -r requirements.txt
copy .env.example .env          # OPENAI_API_KEY + ORACLE_MCP_CONNECTION
python src/seed.py              # accounts, transfers, known-fraud profiles (+embeddings)
python src/detect.py            # find cycles, score vs known fraud, summarise top ring
streamlit run src/dashboard.py  # view detected rings
```

## Seeded scenario
Shell Holdings → Quartz Trading → Nimbus LLC → back to Shell Holdings: round-number
sums moving in a closed loop, and all three accounts sit closest to known-fraud
profiles by vector distance. The legitimate businesses (Acme/Bright/Cedar) form no
cycle and sit far away.

> ⚠️ A learning demo on synthetic data — not a real AML system.
