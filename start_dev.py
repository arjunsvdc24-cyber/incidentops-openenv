#!/usr/bin/env python3
import os

# Set env vars FIRST, before any other imports
os.environ['JWT_SECRET'] = 'dev-secret-key-12345'
os.environ['OPENAI_API_KEY'] = 'sk-dummy-key-for-dev'

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "server.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
