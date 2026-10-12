import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from comfygrid.services import llm_service

router = APIRouter()
logger = logging.getLogger(__name__)
TRANSLATION_TIMEOUT_SECONDS = 120.0


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
        done, _ = await asyncio.wait({translation, disconnected}, timeout=TRANSLATION_TIMEOUT_SECONDS, return_when=asyncio.FIRST_COMPLETED)
        if not done:
            logger.warning("Ollama translation timed out.")
            raise HTTPException(status_code=504, detail="Translation timed out.")
        if disconnected.done():
            raise HTTPException(status_code=499, detail="Translation cancelled.")
        return {"ok": True, "translated_text": await translation}
    except ValueError as exc:
        logger.warning("Invalid translation request: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.warning("Ollama translation failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        translation.cancel()
        disconnected.cancel()
        await asyncio.gather(translation, disconnected, return_exceptions=True)
