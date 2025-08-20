from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Union, Literal
import json
import psycopg2
import httpx
from utils.logger import logger  # ✅ Import logger

router = APIRouter()

with open("/home/obsidian/Github/GPT-API/.openai.key", "r") as f:
    OPENAI_API_KEY = f.read().strip()
    logger.debug("🔑 Loaded OpenAI API key from file.")

headers = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json",
    "OpenAI-Beta": "assistants=v2"
}

class FunctionDefinition(BaseModel):
    name: str
    description: str
    parameters: dict

class FunctionTool(BaseModel):
    type: Literal["function"]
    function: FunctionDefinition

class SimpleTool(BaseModel):
    type: Literal["code_interpreter", "file_search"]

Tool = Union[SimpleTool, FunctionTool]

class AssistantCreateRequest(BaseModel):
    name: str
    instructions: str
    model: str
    tools: list[Tool] = []
    file_ids: list[str] = []

@router.post("/")
def create_assistant(data: AssistantCreateRequest):
    logger.info("📩 Received request to create assistant.")
    logger.debug(f"📝 Request payload: {data.json()}")

    try:
        # 🔧 Inject tools from multiple JSON files
        tools_paths = [
            "/home/obsidian/Github/GPT-API/Gpt-Config/tools/assistants.json",
            "/home/obsidian/Github/GPT-API/Gpt-Config/tools/archlinux.json"
        ]

        loaded_tools = []
        for path in tools_paths:
            logger.info(f"🧰 Loading tools from {path}")
            with open(path, "r") as tf:
                tools = json.load(tf)
                logger.debug(f"📦 Loaded tools from {path}: {json.dumps(tools, indent=2)}")
                loaded_tools.extend(tools)

        payload = data.dict()
        payload["tools"] = loaded_tools  # 🔧 Inject merged tools
        payload.pop("file_ids", None)

        logger.debug(f"📤 Payload to OpenAI (file_ids excluded): {payload}")

        with httpx.Client() as client:
            logger.info("📡 Sending assistant creation request to OpenAI API...")
            response = client.post("https://api.openai.com/v1/assistants", headers=headers, json=payload)

        logger.debug(f"📨 OpenAI response status: {response.status_code}")
        logger.debug(f"📨 OpenAI response body: {response.text}")

        if response.status_code not in [200, 201]:
            logger.error(f"❌ OpenAI request failed: {response.status_code} - {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.text)

        response_json = response.json()
        assistant_id = response_json.get("id")

        if not assistant_id:
            logger.error("❌ No assistant ID returned in OpenAI response.")
            raise HTTPException(status_code=500, detail="OpenAI response did not include an assistant ID.")

        logger.info(f"✅ Assistant successfully created with ID: {assistant_id}")

        logger.info("🧾 Storing assistant metadata in PostgreSQL database...")
        logger.debug(f"""
        Metadata being stored:
            id: {assistant_id}
            name: {data.name}
            instructions: {data.instructions}
            model: {data.model}
            tools: {loaded_tools}
            file_ids: {data.file_ids}
        """)

        conn = psycopg2.connect(dbname="gpt_system", user="obsidian", password="postgres", host="localhost")
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO assistants (id, name, instructions, model, tools, file_ids)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            assistant_id,
            data.name,
            data.instructions,
            data.model,
            json.dumps(loaded_tools),
            data.file_ids
        ))
        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"📦 Assistant metadata stored successfully for ID: {assistant_id}")

        return response_json

    except Exception as e:
        logger.exception("🔥 Exception occurred during assistant creation.")
        raise HTTPException(status_code=500, detail=str(e))
