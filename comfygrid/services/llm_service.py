import asyncio
import json
import logging
import urllib.request
from typing import TypedDict

import httpx

from comfygrid.domain import state

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://127.0.0.1:11434"


def is_ollama_available() -> bool:
    """Check if ollama service is available and responding with models."""
    try:
        models = get_ollama_models()
        return len(models) > 0
    except Exception:
        return False


class OllamaModel(TypedDict):
    name: str
    size: int | None


def get_ollama_model_details() -> list[OllamaModel]:
    """Get available Ollama models, deduplicated by name, with sizes in bytes."""
    try:
        ollama_base_url = state.opts.data.get("ComfyGrid.ollama.url", OLLAMA_BASE_URL)
        req = urllib.request.Request(f"{ollama_base_url}/api/tags", headers={"User-Agent": "ComfyGrid"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            if resp.status != 200:
                return []
            data = json.loads(resp.read().decode("utf-8"))
            if not isinstance(data, dict):
                return []
            models: dict[str, OllamaModel] = {}
            for item in data.get("models", []):
                name = item.get("name")
                if not name:
                    continue
                size = item.get("size")
                if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                    size = None
                if name not in models or models[name]["size"] is None:
                    models[name] = {"name": name, "size": size}
            return list(models.values())
    except Exception as e:
        logger.warning("Failed to fetch Ollama models: %s", e)
        return []


def get_ollama_models() -> list[str]:
    """Get names of available Ollama models."""
    return [model["name"] for model in get_ollama_model_details()]


async def translate_text(model: str | None, prompt: str, system: str | None = None) -> str:
    """Translate text using local Ollama LLM."""
    if not prompt.strip():
        return prompt

    models = await asyncio.to_thread(get_ollama_models)
    if not models:
        logger.warning("Ollama is not available for translation.")
        raise RuntimeError("Ollama is not available.")

    if model is None:
        raise ValueError("Ollama model is not specified.")

    if model not in models:
        logger.warning("Ollama model not found: %s", model)
        raise ValueError(f"Ollama model {model} not found.")

    system_prompt = system if system is not None else state.opts.data.get("ComfyGrid.ollama.system")

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": 0.3,
        }
    }

    if system_prompt:
        payload["system"] = system_prompt

    try:
        ollama_base_url = state.opts.data.get("ComfyGrid.ollama.url", OLLAMA_BASE_URL)
        parts: list[str] = []
        completed = False
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=3.0)) as client:
            async with client.stream(
                "POST",
                f"{ollama_base_url}/api/generate",
                json=payload,
                headers={"User-Agent": "ComfyGrid"},
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("error"):
                        raise RuntimeError(data["error"])
                    parts.append(data.get("response", ""))
                    if data.get("done"):
                        completed = True
                        break
        if not completed:
            raise RuntimeError("Ollama translation stream ended before completion.")
        translated = "".join(parts).strip()
        if not translated:
            raise RuntimeError("Ollama returned empty translation response.")
        return translated
    except Exception as e:
        logger.error("Ollama translation failed: %s", e)
        raise RuntimeError(f"Ollama translation failed: {e}")
