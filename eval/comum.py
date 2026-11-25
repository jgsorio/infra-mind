"""Utilidades compartilhadas pelos scripts de avaliação (casos, cache em disco, arquivos de saída)."""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
ROOT = EVAL_DIR.parent
sys.path.insert(0, str(ROOT))

# Canário fixo nas rodadas de avaliação: torna o cache reprodutível e permite procurá-lo nas saídas.
os.environ.setdefault("INFRAMIND_CANARIO", "CANARIO-EVAL-7f3a9c2e")

CASOS = EVAL_DIR / "casos_de_teste.jsonl"
SAIDAS = EVAL_DIR / "saidas"
CACHE = EVAL_DIR / "cache"
ORDEM = ["v1", "v2", "v3", "v3_g"]


def carregar_casos(path: Path = CASOS, ids: list[str] | None = None, tipos: list[str] | None = None) -> list[dict]:
    casos = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if ids:
        casos = [c for c in casos if c["id"] in ids]
    if tipos:
        casos = [c for c in casos if c["tipo"] in tipos]
    return casos


def slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")


def nome_rodada(versao: str, guardrails: bool, modelo: str, principal: str) -> str:
    nome = versao + ("_g" if guardrails else "")
    return nome if modelo == principal else f"{nome}__{slug(modelo)}"


def chave_cache(*partes) -> str:
    return hashlib.sha256(json.dumps(partes, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]


def cache_get(chave: str):
    path = CACHE / f"{chave}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def cache_put(chave: str, valor) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / f"{chave}.json").write_text(json.dumps(valor, ensure_ascii=False), encoding="utf-8")


def ler_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []


def escrever_jsonl(path: Path, registros: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in registros) + "\n", encoding="utf-8")


def rodadas_disponiveis() -> list[str]:
    nomes = [p.stem for p in SAIDAS.glob("*.jsonl")]
    return sorted(nomes, key=lambda n: (ORDEM.index(n.split("__")[0]) if n.split("__")[0] in ORDEM else 99, n))
