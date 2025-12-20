# Bloomberg MCP Server Dockerfile
#
# This container runs the Bloomberg MCP server and connects to
# Bloomberg Terminal running on the host via host.docker.internal
#
# Prerequisites:
# - Bloomberg Terminal running on host machine
# - Bloomberg API enabled in Terminal settings

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for building blpapi
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy the C++ SDK (Linux version)
COPY blpapi_cpp/ /opt/blpapi_cpp/

# Set environment for blpapi - libs are in Linux/ subdirectory
ENV BLPAPI_ROOT=/opt/blpapi_cpp
ENV LD_LIBRARY_PATH=/opt/blpapi_cpp/Linux:$LD_LIBRARY_PATH

# Copy the Python blpapi SDK
COPY blpapi_python/ /tmp/blpapi_python/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir mcp pydantic httpx

# Install blpapi Python SDK
WORKDIR /tmp/blpapi_python
RUN pip install --no-cache-dir .

WORKDIR /app

# Copy the bloomberg-mcp package
COPY src/ /app/src/
COPY pyproject.toml /app/

# Install the bloomberg-mcp package
RUN pip install -e .

# Environment variables for Bloomberg connection
ENV BLOOMBERG_HOST=host.docker.internal
ENV BLOOMBERG_PORT=8194

# Expose HTTP port for MCP server
EXPOSE 8080

# Health check - verify server is listening
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('localhost',8080)); s.close()" || exit 1

# Run the MCP server with HTTP transport
CMD ["python", "-m", "bloomberg_mcp.server", "--http", "--port=8080"]
