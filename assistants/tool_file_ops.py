from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import openai
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from database.db import get_db
from fastapi import Depends
from database.models import Assistant

from utils.logger import logger  # ✅ Import logger

load_dotenv()

router = APIRouter()

with open("/home/obsidian/Github/GPT-API/.openai.key", "r") as f:
    OPENAI_API_KEY = f.read().strip()
    logger.info("🔑 OpenAI API key loaded for assistant update routes.")

openai.base_url = "https://api.openai.com/v1"

class ToolFileUpdate(BaseModel):
    assistant_id: str
    tools: list = []
    file_ids: list = []

@router.post("/update/tools")
async def update_tools(payload: ToolFileUpdate, db: Session = Depends(get_db)):
    logger.info(f"🛠️ Received request to update tools for assistant ID: {payload.assistant_id}")
    logger.debug(f"📦 Tools: {payload.tools}, Files: {payload.file_ids}")

    try:
        assistant = db.query(Assistant).filter_by(id=payload.assistant_id).first()
        if not assistant:
            logger.warning(f"⚠️ Assistant not found in DB: {payload.assistant_id}")
            raise HTTPException(status_code=404, detail="Assistant not found")

        logger.info("📡 Sending update to OpenAI Assistant API...")
        response = openai.beta.assistants.update(
            assistant_id=payload.assistant_id,
            tools=payload.tools,
            file_ids=payload.file_ids
        )

        logger.info(f"✅ Tools updated successfully for assistant: {payload.assistant_id}")
        return {"status": "success", "data": response}

    except Exception as e:
        logger.exception("🔥 Exception occurred during tools update.")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update/files")
async def update_files(payload: ToolFileUpdate, db: Session = Depends(get_db)):
    logger.info(f"🗃️ Received request to update file_ids for assistant ID: {payload.assistant_id}")
    logger.debug(f"📦 Tools: {payload.tools}, Files: {payload.file_ids}")

    try:
        assistant = db.query(Assistant).filter_by(id=payload.assistant_id).first()
        if not assistant:
            logger.warning(f"⚠️ Assistant not found in DB: {payload.assistant_id}")
            raise HTTPException(status_code=404, detail="Assistant not found")

        logger.info("📡 Sending update to OpenAI Assistant API...")
        response = openai.beta.assistants.update(
            assistant_id=payload.assistant_id,
            tools=payload.tools,
            file_ids=payload.file_ids
        )

        logger.info(f"✅ Files updated successfully for assistant: {payload.assistant_id}")
        return {"status": "success", "data": response}

    except Exception as e:
        logger.exception("🔥 Exception occurred during file update.")
        raise HTTPException(status_code=500, detail=str(e))
