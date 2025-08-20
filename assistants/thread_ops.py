from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid
import psycopg2
import httpx

from utils.logger import logger  # ✅ Import logger

router = APIRouter()

with open("/home/obsidian/Github/GPT-API/.openai.key", "r") as f:
    OPENAI_API_KEY = f.read().strip()
    logger.info("🔑 OpenAI API key loaded.")

headers = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json",
    "OpenAI-Beta": "assistants=v2"
}

class ThreadCreateRequest(BaseModel):
    assistant_id: Optional[str] = None

class MessageCreateRequest(BaseModel):
    thread_id: str
    role: str
    content: str

class RunRequest(BaseModel):
    thread_id: str
    assistant_id: str
    input_data: str

@router.post("/thread/create")
def create_thread(data: ThreadCreateRequest):
    logger.info("📩 Received request to create a new thread.")
    logger.debug(f"🧾 Assistant ID provided: {data.assistant_id}")
    try:
        payload = {}
        with httpx.Client() as client:
            response = client.post("https://api.openai.com/v1/threads", headers=headers, json=payload)
        logger.debug(f"📡 OpenAI thread creation status: {response.status_code}")
        if response.status_code not in [200, 201]:
            logger.error(f"❌ OpenAI thread creation failed: {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.text)

        openai_thread_id = response.json()["id"]
        logger.info(f"✅ Thread created on OpenAI with ID: {openai_thread_id}")

        logger.debug("🗃️ Saving thread metadata to local database...")
        conn = psycopg2.connect(dbname="gpt_system", user="obsidian", password="postgres", host="localhost")
        cur = conn.cursor()
        if data.assistant_id:
            cur.execute("INSERT INTO threads (id, assistant_id) VALUES (%s, %s)", (openai_thread_id, data.assistant_id))
        else:
            cur.execute("INSERT INTO threads (id) VALUES (%s)", (openai_thread_id,))
        conn.commit()
        cur.close()
        conn.close()
        logger.info("📦 Thread info stored in local DB.")

        return response.json()
    except Exception as e:
        logger.exception("🔥 Exception while creating thread.")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/thread/message")
def post_message(data: MessageCreateRequest):
    logger.info(f"✉️ Posting message to thread {data.thread_id} as role: {data.role}")
    try:
        logger.debug("🗃️ Inserting message into local DB...")
        conn = psycopg2.connect(dbname="gpt_system", user="obsidian", password="postgres", host="localhost")
        cur = conn.cursor()
        cur.execute("INSERT INTO messages (thread_id, role, content) VALUES (%s, %s, %s)", (data.thread_id, data.role, data.content))
        conn.commit()
        cur.close()
        conn.close()
        logger.info("🧾 Message metadata stored locally.")

        payload = {"role": data.role, "content": data.content}
        with httpx.Client() as client:
            response = client.post(f"https://api.openai.com/v1/threads/{data.thread_id}/messages", headers=headers, json=payload)
        logger.debug(f"📡 OpenAI message post status: {response.status_code}")
        if response.status_code not in [200, 201]:
            logger.error(f"❌ Failed to post message to OpenAI: {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.text)

        logger.info(f"✅ Message posted successfully to OpenAI thread {data.thread_id}")
        return response.json()
    except Exception as e:
        logger.exception("🔥 Exception while posting message.")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/thread/run")
def run_assistant(data: RunRequest):
    run_id = str(uuid.uuid4())
    logger.info(f"🏃 Initiating assistant run. Local Run ID: {run_id}")
    logger.debug(f"📎 Thread: {data.thread_id}, Assistant: {data.assistant_id}")

    try:
        logger.debug("🗃️ Inserting run metadata into local DB...")
        conn = psycopg2.connect(dbname="gpt_system", user="obsidian", password="postgres", host="localhost")
        cur = conn.cursor()
        cur.execute("INSERT INTO runs (id, thread_id, input_data) VALUES (%s, %s, %s)", (run_id, data.thread_id, data.input_data))
        conn.commit()
        cur.close()
        conn.close()
        logger.info("✅ Run metadata saved to local database.")

        payload = {
            "assistant_id": data.assistant_id,
            "instructions": data.input_data
        }
        with httpx.Client() as client:
            response = client.post(
                f"https://api.openai.com/v1/threads/{data.thread_id}/runs",
                headers=headers,
                json=payload
            )
        logger.debug(f"📡 OpenAI run trigger status: {response.status_code}")
        if response.status_code not in [200, 201]:
            logger.error(f"❌ OpenAI run initiation failed: {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.text)

        run_info = response.json()
        run_info["local_run_id"] = run_id
        run_info["thread_id"] = data.thread_id
        logger.info(f"✅ Assistant run started on OpenAI. OpenAI Run ID: {run_info.get('id')}")

        return run_info

    except Exception as e:
        logger.exception("🔥 Exception during assistant run.")
        raise HTTPException(status_code=500, detail=str(e))
