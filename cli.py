# cli.py
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("API_HOST", "127.0.0.1")
port = int(os.getenv("API_PORT", "8000"))

if __name__ == "__main__":
    print(f"🔧 Starting API at http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=False)
