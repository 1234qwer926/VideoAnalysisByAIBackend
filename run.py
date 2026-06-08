import os
import uvicorn

if __name__ == "__main__":
    # Render and other cloud platforms set PORT env var dynamically
    port = int(os.environ.get("PORT", 8000))
    # reload=False for production (Render, etc.)
    # reload=True only for local development
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
