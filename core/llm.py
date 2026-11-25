"""Cliente fino da Groq com modo JSON, streaming, retry em limite de taxa e medição de latência."""
import json
import re
import time
from functools import lru_cache

from core import config


@lru_cache(maxsize=1)
def _client():
    from groq import Groq

    return Groq(api_key=config.get_api_key())


def chat(messages: list[dict], modelo: str, temperatura: float, json_mode: bool = False,
         tentativas: int = 4) -> tuple[str, float]:
    """Chamada sem streaming. Retorna (texto, latência em segundos)."""
    import groq

    kwargs = {"model": modelo, "messages": messages, "temperature": temperatura}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    espera = 5.0
    for tentativa in range(tentativas):
        inicio = time.perf_counter()
        try:
            resp = _client().chat.completions.create(**kwargs)
            return resp.choices[0].message.content or "", time.perf_counter() - inicio
        except groq.RateLimitError:
            if tentativa == tentativas - 1:
                raise
            time.sleep(espera)
            espera *= 2
        except groq.BadRequestError as e:
            # Alguns modelos rejeitam o modo JSON ou devolvem json_validate_failed: tenta sem ele.
            if json_mode and "response_format" in kwargs:
                kwargs.pop("response_format")
                continue
            raise e
    raise RuntimeError("falha ao chamar o modelo")


def chat_stream(messages: list[dict], modelo: str, temperatura: float):
    """Gera os pedaços de texto (usado na v1, que responde em texto livre)."""
    stream = _client().chat.completions.create(model=modelo, messages=messages, temperature=temperatura, stream=True)
    for chunk in stream:
        yield chunk.choices[0].delta.content or ""


def extrair_json(texto: str) -> dict | None:
    """Extrai o primeiro objeto JSON do texto (tolera cercas ```json e texto em volta)."""
    if not texto:
        return None
    limpo = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip())
    for candidato in (limpo, limpo[limpo.find("{"): limpo.rfind("}") + 1]):
        try:
            dado = json.loads(candidato)
            return dado if isinstance(dado, dict) else None
        except (json.JSONDecodeError, ValueError):
            continue
    return None
