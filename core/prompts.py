"""Carrega os prompts da biblioteca versionada (prompts/*.md).

A biblioteca é a fonte única: o texto que roda no app e na avaliação é exatamente o que está
nos blocos ```prompt:<nome>``` de cada ficha. Placeholders usam {{nome}} (não colidem com o JSON
dos exemplos few-shot).
"""
import re
from functools import lru_cache

from core import config

VERSOES = ["v1", "v2", "v3"]
_BLOCO = re.compile(r"```prompt:(\w+)\n(.*?)\n```", re.S)


@lru_cache(maxsize=None)
def carregar(nome: str) -> dict[str, str]:
    """Retorna {bloco: texto} da ficha prompts/<nome>.md (ex.: carregar('v3')['system'])."""
    raw = (config.PROMPTS_DIR / f"{nome}.md").read_text(encoding="utf-8")
    blocos = dict(_BLOCO.findall(raw))
    if "system" not in blocos:
        raise ValueError(f"prompts/{nome}.md não tem bloco ```prompt:system```")
    return blocos


def preencher(template: str, **valores) -> str:
    for chave, valor in valores.items():
        template = template.replace("{{" + chave + "}}", str(valor))
    return template
