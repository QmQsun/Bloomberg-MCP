# Bloomberg MCP Server - PowerShell Run Script
#
# This script runs the MCP server locally on Windows.
# Requires: Bloomberg Terminal running, blpapi installed
#
# Usage:
#   .\run_server.ps1            - Run with stdio transport (for Claude Code)
#   .\run_server.ps1 --http     - Run with HTTP transport on port 8080
#   .\run_server.ps1 --sse      - Run with SSE transport on port 8080

param(
    [switch]$http,
    [switch]$sse,
    [int]$port = 8080
)

# Activate virtual environment if it exists
if (Test-Path "venv\Scripts\Activate.ps1") {
    . .\venv\Scripts\Activate.ps1
}

# Set Bloomberg connection (localhost for local Terminal)
$env:BLOOMBERG_HOST = "localhost"
$env:BLOOMBERG_PORT = "8194"

# Build arguments
$args = @()
if ($http) {
    $args += "--http"
    $args += "--port=$port"
} elseif ($sse) {
    $args += "--sse"
    $args += "--port=$port"
}

# Run the MCP server
Write-Host "Starting Bloomberg MCP Server..."
Write-Host "Bloomberg Host: $env:BLOOMBERG_HOST"
Write-Host "Bloomberg Port: $env:BLOOMBERG_PORT"

if ($args.Count -gt 0) {
    Write-Host "Transport: HTTP/SSE on port $port"
    python -m bloomberg_mcp.server @args
} else {
    Write-Host "Transport: stdio"
    python -m bloomberg_mcp.server
}
