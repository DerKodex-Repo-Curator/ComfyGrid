import asyncio

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from comfygrid.services import llm_service

router = APIRouter()


class TranslateRequest(BaseModel):
    text: str
    target_lang: str = "en"
    model: str | None = None
    system: str | None = None


@router.get("/llm/status")
def get_llm_status():
    models = llm_service.get_ollama_model_details()
    return {
        "available": bool(models),
        "models": [model["name"] for model in models],
        "model_sizes": {model["name"]: model["size"] for model in models},
    }


@router.post("/llm/translate")
async def translate_text(req: TranslateRequest, request: Request):
    async def wait_for_disconnect():
        while not await request.is_disconnected():
            await asyncio.sleep(0.1)

    translation = asyncio.create_task(llm_service.translate_text(req.model, req.text, req.system))
    disconnected = asyncio.create_task(wait_for_disconnect())
    try:
        await asyncio.wait({translation, disconnected}, return_when=asyncio.FIRST_COMPLETED)
        if disconnected.done():
            raise HTTPException(status_code=499, detail="Translation cancelled.")
        return {"ok": True, "translated_text": await translation}
    finally:
        translation.cancel()
        disconnected.cancel()
        await asyncio.gather(translation, disconnected, return_exceptions=True)
