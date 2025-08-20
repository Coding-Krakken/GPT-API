from fastapi import APIRouter, HTTPException
import psycopg2
import httpx
from utils.logger import logger  # ✅ Import logger

router = APIRouter()

with open("/home/obsidian/Github/GPT-API/.openai.key", "r") as f:
    OPENAI_API_KEY = f.read().strip()
    logger.debug("🔑 Loaded OpenAI API key for deletion operations.")

# Relay to OpenAI API
headers = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json",
    "OpenAI-Beta": "assistants=v2"
}


@router.delete("/delete/{assistant_id}")
def delete_assistant(assistant_id: str):
    logger.info(f"🧹 Received request to delete assistant: {assistant_id}")
    try:
        # Delete from local database
        logger.debug("🗃️ Connecting to PostgreSQL to delete assistant metadata...")
        conn = psycopg2.connect(dbname="gpt_system", user="obsidian", password="ABC123def.", host="localhost")
        cur = conn.cursor()
        cur.execute("DELETE FROM assistants WHERE id = %s", (assistant_id,))
        cur.execute("DELETE FROM threads WHERE assistant_id = %s", (assistant_id,))
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"✅ Local records for assistant {assistant_id} deleted.")

        # Forward delete to OpenAI
        logger.info(f"📡 Sending deletion request to OpenAI for assistant {assistant_id}...")
        with httpx.Client() as client:
            response = client.delete(f"https://api.openai.com/v1/assistants/{assistant_id}", headers=headers)
        logger.debug(f"🔁 OpenAI response status: {response.status_code}")
        logger.debug(f"📨 OpenAI response body: {response.text}")

        if response.status_code not in [200, 204]:
            logger.error(f"❌ Failed to delete assistant on OpenAI: {response.status_code} - {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.text)

        logger.info(f"✅ Assistant {assistant_id} deleted on OpenAI.")
        return response.json()

    except Exception as e:
        logger.exception("🔥 Exception occurred during assistant deletion.")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/thread/delete/{thread_id}")
def delete_thread(thread_id: str):
    logger.info(f"🧹 Received request to delete thread: {thread_id}")
    try:
        # Delete from local database
        logger.debug("🗃️ Connecting to PostgreSQL to delete thread-related data...")
        conn = psycopg2.connect(dbname="gpt_system", user="obsidian", password="ABC123def.", host="localhost")
        cur = conn.cursor()
        cur.execute("DELETE FROM messages WHERE thread_id = %s", (thread_id,))
        cur.execute("DELETE FROM runs WHERE thread_id = %s", (thread_id,))
        cur.execute("DELETE FROM threads WHERE id = %s", (thread_id,))
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"✅ Local records for thread {thread_id} deleted.")

        # Forward delete to OpenAI
        logger.info(f"📡 Sending deletion request to OpenAI for thread {thread_id}...")
        with httpx.Client() as client:
            response = client.delete(f"https://api.openai.com/v1/threads/{thread_id}", headers=headers)
        logger.debug(f"🔁 OpenAI response status: {response.status_code}")
        logger.debug(f"📨 OpenAI response body: {response.text}")

        if response.status_code not in [200, 204]:
            logger.error(f"❌ Failed to delete thread on OpenAI: {response.status_code} - {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.text)

        logger.info(f"✅ Thread {thread_id} deleted on OpenAI.")
        return response.json()

    except Exception as e:
        logger.exception("🔥 Exception occurred during thread deletion.")
        raise HTTPException(status_code=500, detail=str(e))
