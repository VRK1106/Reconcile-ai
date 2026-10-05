"""
Root Application Entrypoint for native Python cloud deployments (no Docker needed).
Runs FastAPI on $PORT or default 8000.
"""
import os
import uvicorn
from backend.api.server import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.api.server:app", host="0.0.0.0", port=port)
