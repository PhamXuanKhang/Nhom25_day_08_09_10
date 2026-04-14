from __future__ import annotations

import os
import sys

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
except ImportError:
    print(
        "fastapi chưa được cài. Để dùng HTTP server (bonus):\n"
        "pip install fastapi uvicorn httpx",
        file=sys.stderr,
    )
    raise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_server import dispatch_tool, list_tools, TOOL_SCHEMAS  # noqa: E402


app = FastAPI(
    title="Day 09 MCP Server",
    version="1.0.0",
    description="HTTP bridge for MCP tool calls (retrieval + ticket + access + create_ticket).",
)


class ToolCallRequest(BaseModel):
    name: str
    input: dict | None = None


@app.get("/")
def health():
    return {
        "status": "ok",
        "tools": list(TOOL_SCHEMAS.keys()),
        "protocol": "mcp/1.0 (http bridge)",
    }


@app.get("/tools/list")
def tools_list():
    """MCP tools/list — trả về danh sách tool schemas."""
    return {"tools": list_tools()}


@app.post("/tools/call")
def tools_call(req: ToolCallRequest):
    """MCP tools/call — dispatch tool với input."""
    if req.name not in TOOL_SCHEMAS:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Tool '{req.name}' không tồn tại.", "available": list(TOOL_SCHEMAS.keys())},
        )

    result = dispatch_tool(req.name, req.input or {})
    if isinstance(result, dict) and result.get("error"):
        # Trả 200 + error payload để worker parse dễ (không raise HTTP 500)
        return JSONResponse(status_code=200, content=result)
    return result


if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        print("❌ uvicorn chưa cài. pip install uvicorn", file=sys.stderr)
        sys.exit(1)

    port = int(os.getenv("MCP_SERVER_PORT", "8080"))
    print(f"🚀 MCP HTTP server starting on http://localhost:{port}")
    print(f"   GET  /tools/list")
    print(f"   POST /tools/call  {{'name': ..., 'input': ...}}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
