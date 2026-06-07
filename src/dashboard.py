"""Streamlit dashboard for fraud-ring detection (reads Oracle via SQLcl MCP).
Run:  streamlit run src/dashboard.py"""
from __future__ import annotations
import asyncio, concurrent.futures, os, sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
sys.path.insert(0, os.path.dirname(__file__))
import streamlit as st
import config
import dashboard_data as dd
from mcp_oracle import open_oracle_mcp

def _load(nonce):
    async def _go():
        async with open_oracle_mcp(config.SQLCL_COMMAND, config.ORACLE_MCP_CONNECTION) as mcp:
            return await dd.list_runs(mcp)
    with concurrent.futures.ThreadPoolExecutor(1) as ex:
        return ex.submit(lambda: asyncio.run(_go())).result()

@st.cache_data(show_spinner="Loading rings from Oracle 26ai via SQLcl MCP…")
def load_all(nonce: int):
    return _load(nonce)

def main():
    st.set_page_config(page_title="Fraud Rings · Oracle 26ai", page_icon="🕸️", layout="wide")
    st.title("🕸️ Fraud-Ring Detection")
    st.caption("Transfer cycles (recursive SQL) confirmed by AI Vector Search · via the SQLcl MCP server")
    with st.sidebar:
        st.header("Controls")
        nonce = st.session_state.setdefault("nonce", 0)
        if st.button("🔄 Refresh from database"):
            st.session_state["nonce"] = nonce + 1; st.cache_data.clear(); st.rerun()
    runs = load_all(st.session_state["nonce"])
    if not runs:
        st.warning("No runs yet. Run `python src/seed.py` then `python src/detect.py`."); return
    with st.sidebar:
        opts = {f"#{r['run_id']} · {r.get('created_at','')}": r for r in runs}
        run = opts[st.selectbox("Run", list(opts.keys()))]
    c1, c2, c3 = st.columns(3)
    c1.metric("Ring size", f"{run.get('member_count')} accounts")
    c2.metric("Avg fraud distance", run.get("avg_fraud_dist"))
    c3.metric("Cycled amount", f"${run.get('total_amount'):,.0f}")
    st.markdown(f"### 🚩 {run.get('ring')}")
    st.error(run.get("summary") or "—")

if __name__ == "__main__":
    main()
else:
    main()
