from fastapi import APIRouter, HTTPException
import psycopg2
import httpx
from utils.logger import logger  # ✅ Import logger

router = APIRouter()

with open("/home/obsidian/Github/GPT-API/.openai.key", "r") as f:
    OPENAI_API_KEY = f.read().strip()
    logger.info("🔑 OpenAI API key loaded for assistant listing routes.")

# Relay to OpenAI API
headers = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json",
    "OpenAI-Beta": "assistants=v2"
}

@router.get("/list")
def list_assistants():
    logger.info("📋 Request received to list all assistants from OpenAI.")
    try:
        with httpx.Client() as client:
            response = client.get("https://api.openai.com/v1/assistants", headers=headers)
        logger.debug(f"📡 OpenAI response status: {response.status_code}")
        if response.status_code != 200:
            logger.error(f"❌ Failed to list assistants: {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.text)

        logger.info("✅ Successfully retrieved assistant list.")
        return response.json()
    except Exception as e:
        logger.exception("🔥 Exception while listing assistants.")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{assistant_id}/threads")
def get_threads(assistant_id: str):
    logger.info(f"🔍 Fetching threads for assistant: {assistant_id}")
    try:
        conn = psycopg2.connect(dbname="gpt_system", user="obsidian", password="ABC123def.", host="localhost")
        cur = conn.cursor()
        cur.execute("SELECT * FROM threads WHERE assistant_id = %s", (assistant_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        logger.info(f"✅ Retrieved {len(rows)} threads for assistant {assistant_id}")
        return [{"id": r[0], "assistant_id": r[1]} for r in rows]
    except Exception as e:
        logger.exception(f"🔥 Exception while fetching threads for assistant {assistant_id}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/thread/{thread_id}/messages")
def get_messages(thread_id: str):
    logger.info(f"📨 Request to get messages for thread: {thread_id}")
    try:
        with httpx.Client() as client:
            response = client.get(f"https://api.openai.com/v1/threads/{thread_id}/messages", headers=headers)
        logger.debug(f"📡 OpenAI message fetch status: {response.status_code}")
        if response.status_code != 200:
            logger.error(f"❌ Failed to get messages: {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.text)

        logger.info(f"✅ Successfully retrieved messages for thread {thread_id}")
        return response.json()
    except Exception as e:
        logger.exception(f"🔥 Exception while fetching messages for thread {thread_id}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/thread/{thread_id}/runs")
def get_runs(thread_id: str):
    logger.info(f"🏃 Request to get runs for thread: {thread_id}")
    try:
        with httpx.Client() as client:
            response = client.get(f"https://api.openai.com/v1/threads/{thread_id}/runs", headers=headers)
        logger.debug(f"📡 OpenAI run fetch status: {response.status_code}")
        if response.status_code != 200:
            logger.error(f"❌ Failed to get runs: {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.text)

        logger.info(f"✅ Successfully retrieved runs for thread {thread_id}")
        return response.json()
    except Exception as e:
        logger.exception(f"🔥 Exception while fetching runs for thread {thread_id}")
        raise HTTPException(status_code=500, detail=str(e))
