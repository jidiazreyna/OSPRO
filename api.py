# api.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List
import core

app = FastAPI(title="Generador OSPRO")

@app.post("/autocompletar")
async def autocompletar(file: UploadFile = File(...)):
    try:
        datos = core.procesar_sentencia(await file.read(), file.filename)
        return datos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]


@app.post("/chat")
async def chat(req: ChatRequest):
    client = core._get_openai_client()
    kwargs = {"model": "gpt-4o-mini", "messages": [m.model_dump() for m in req.messages]}
    if hasattr(client, "chat"):
        rsp = client.chat.completions.create(**kwargs)  # type: ignore[attr-defined]
        if hasattr(rsp, "model_dump"):
            return rsp.model_dump()
        return rsp
    else:
        rsp = client.ChatCompletion.create(**kwargs)  # type: ignore[attr-defined]
        if hasattr(rsp, "to_dict"):
            return rsp.to_dict()
        return rsp

