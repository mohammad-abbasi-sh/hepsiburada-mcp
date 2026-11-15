"""hepsiburada_mcp — unofficial MCP server for hepsiburada.com.

Read-only tools (search, details, reviews, categories, price stats)
need no login. Account tools (cart, favorites) use the user's own
browser session from HEPSIBURADA_SESSION — local only, never logged
or persisted — and every mutation needs confirm=true.
"""
