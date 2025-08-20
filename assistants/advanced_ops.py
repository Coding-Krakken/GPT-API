import json
import requests
import openai
import os
import uuid
import psycopg2
from fastapi import APIRouter, Request, HTTPException
from dotenv import load_dotenv
from pydantic import BaseModel

from utils.logger import logger  # ✅ Import logger

load_dotenv()

router = APIRouter()

with open("/home/obsidian/Github/GPT-API/.openai.key", "r") as f:
    OPENAI_API_KEY = f.read().strip()

openai.api_key = OPENAI_API_KEY
logger.info("🔑 OpenAI API key loaded and set.")

# Relay to OpenAI API
headers = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json",
    "OpenAI-Beta": "assistants=v2"
}

class RunStatusRequest(BaseModel):
    run_id: str

@router.get("/thread/{thread_id}/runs/{run_id}")
def get_run_status(thread_id: str, run_id: str):
    logger.debug(f"🔍 Checking run status for Thread ID: {thread_id}, Run ID: {run_id}")
    try:
        url = f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}"
        response = requests.get(url, headers=headers)
        logger.debug(f"📡 OpenAI GET response status: {response.status_code}")

        if response.status_code == 404:
            logger.warning(f"⚠️ Run not found: {run_id}")
            raise HTTPException(status_code=404, detail="Run not found")
        elif response.status_code >= 400:
            logger.error(f"❌ OpenAI returned error: {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.text)

        logger.info(f"✅ Run status retrieved successfully for Run ID: {run_id}")
        return response.json()

    except Exception as e:
        logger.exception("🔥 Exception while checking run status.")
        raise HTTPException(status_code=500, detail=str(e))


class ToolInvocationRequest(BaseModel):
    tool_call_id: str
    output: str

@router.post("/advanced_ops/tools/invoke")
def simulate_tool_execution(data: ToolInvocationRequest):
    logger.info(f"🛠️ Simulating tool execution: {data.tool_call_id} -> {data.output}")
    return {"message": f"Simulated execution for tool_call_id: {data.tool_call_id} with output: {data.output}"}

@router.post("/advanced_ops/files/upload")
def upload_file(request: Request):
    logger.info("📤 Simulating file upload.")
    return {"message": "File upload simulation complete."}

@router.get("/advanced_ops/files/download")
def download_file():
    logger.info("📥 Simulating file download.")
    return {"message": "File download simulation complete."}

@router.get("/advanced_ops/search")
def search_assistants():
    logger.debug("🔎 Searching for assistants in the database.")
    try:
        conn = psycopg2.connect(dbname="gpt_system", user="obsidian", password="ABC123def.", host="localhost")
        cur = conn.cursor()
        cur.execute("SELECT * FROM assistants")
        rows = cur.fetchall()
        logger.info(f"📋 Retrieved {len(rows)} assistant records from DB.")
        cur.close()
        conn.close()
        return {"assistants": rows}
    except Exception as e:
        logger.exception("🔥 Exception while querying assistants.")
        return {"error": str(e)}
