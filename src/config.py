"""Central configuration, loaded from .env."""
from __future__ import annotations
import os
from dotenv import load_dotenv
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
ORACLE_MCP_CONNECTION = os.getenv("ORACLE_MCP_CONNECTION", "DEBATE")
SQLCL_COMMAND = os.getenv("SQLCL_COMMAND", "sql")
