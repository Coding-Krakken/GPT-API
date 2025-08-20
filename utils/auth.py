# utils/auth.py
from fastapi import Request, HTTPException
from dotenv import load_dotenv
import os

load_dotenv()

def verify_key(request: Request):
    key = request.headers.get("x-api-key")
    if key != os.getenv("API_KEY"):
        raise HTTPException(status_code=403, detail="Invalid API key")
    else:
        return True
