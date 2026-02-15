@echo off
REM Bloomberg MCP Server - Local Run Script
REM
REM This script runs the MCP server locally on Windows.
REM Requires: Bloomberg Terminal running, blpapi installed
REM
REM Usage:
REM   run_server.bat          - Run with stdio transport (for Claude Code)
REM   run_server.bat --http   - Run with HTTP transport on port 8080
REM   run_server.bat --sse    - Run with SSE transport on port 8080

setlocal

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Set Bloomberg connection (localhost for local Terminal)
set BLOOMBERG_HOST=localhost
set BLOOMBERG_PORT=8194

REM Run the MCP server
python -m bloomberg_mcp.server %*

endlocal
