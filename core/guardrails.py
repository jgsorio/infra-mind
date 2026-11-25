"""Guardrails de entrada e de saída (R5).

Entrada: mascaramento de PII (sempre ligado, LGPD) e detecção de padrões de prompt injection.
Saída: validação do JSON Schema, fontes citadas ⊂ trechos recuperados, ações destrutivas e canário.

Limitação declarada: regras por expressão regular são fáceis de contornar (paráfrase, outro idioma,
codificação). Elas são uma camada a mais, não a única defesa — o prompt v3 é a outra.
"""
import json
import re
import unicodedata
from functools import lru_cache

from core import config

# ----------------------------------------------------------------------------- PII (LGPD)
_PII = [
    ("[EMAIL]", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("[CPF]", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    ("[TELEFONE]", re.compile(r"(?:\+55\s?)?(?:\(\d{2}\)|\b\d{2})\s?9?\d{4}-?\d{4}\b")),
]


def mascarar_pii(texto: str) -> tuple[str, list[str]]:
    """Substitui e-mail, CPF e telefone por marcadores. Retorna (texto, tipos encontrados)."""
    achados = []
    for marcador, padrao in _PII:
        texto, n = padrao.subn(marcador, texto)
        if n:
            achados.append(marcador)
    return texto, achados


# ----------------------------------------------------------------------------- entrada
_ATAQUES = [
    ("ignorar_regras", r"\b(ignore|ignora|ignorem|desconsidere|esque[cç]a)\b.{0,40}\b(regras|instru[cç][oõ]es|orienta[cç][oõ]es|tudo)\b"),
    ("ignorar_regras_en", r"\b(ignore|disregard|forget)\b.{0,30}\b(previous|prior|all|above)\b.{0,20}\b(instructions|rules|prompt)\b"),
    ("extrair_prompt", r"\b(mostre|revele|exiba|imprima|repita|liste|diga|copie|traduza)\b.{0,50}\b(prompt|instru[cç][oõ]es (internas|do sistema)|suas regras|system prompt)\b"),
    ("repetir_acima", r"\b(repita|copie|reproduza|repeat)\b.{0,60}\b(acima|anterior|above)\b"),
    ("troca_persona", r"(a partir de agora|from now on)?\s*voc[eê] (agora )?[eé] (o |a |um |uma )?\w*(gpt|dan|bot)\b|\bmodo (desenvolvedor|dev|irrestrito)\b|\bjailbreak\b|\bsem restri[cç][oõ]es\b"),
    ("ocultar_rastro", r"\bsem deixar rastros?\b|\bapagar (os )?logs? de auditoria\b"),
]
_ATAQUES = [(nome, re.compile(p, re.I | re.S)) for nome, p in _ATAQUES]


def detectar_ataque(texto: str) -> list[str]:
    """Lista os padrões de ataque encontrados na entrada (vazio = entrada limpa)."""
    return [nome for nome, padrao in _ATAQUES if padrao.search(texto)]


RESPOSTA_RECUSADA = {
    "cobertura": "recusado",
    "severidade": None,
    "diagnostico": "Não posso atender a esse pedido. Descreva o sintoma ou cole o alerta para que eu ajude no incidente.",
    "passos": [],
    "fontes": [],
    "escalar": False,
}

# ----------------------------------------------------------------------------- saída
ID_DOC = re.compile(r"\b(INC-\d{3}|KB-\d{4}|DOC-[A-Z]+|APX-[A-C])\b")
_DESTRUTIVAS = re.compile(
    r"drop\s+(database|table)|flushall|flushdb|rm\s+-rf\s+/(\s|$|\*|var/log)|mkfs|\bshred\b|"
    r"apagar o banco|apague o banco|sem deixar rastro|dd\s+if=/dev/zero",
    re.I,
)


@lru_cache(maxsize=1)
def _validador():
    from jsonschema import Draft202012Validator

    return Draft202012Validator(json.loads(config.SCHEMA_PATH.read_text(encoding="utf-8")))


def erros_schema(dados: dict | None) -> list[str]:
    if dados is None:
        return ["saída não é JSON"]
    return [e.message for e in _validador().iter_errors(dados)]


def fontes_citadas(dados: dict | None, texto: str = "") -> set[str]:
    """IDs citados: campo fontes + fonte de cada passo (JSON) ou IDs no texto (v1)."""
    if dados is None:
        return set(ID_DOC.findall(texto or ""))
    ids = set(dados.get("fontes") or [])
    ids |= {p.get("fonte") for p in dados.get("passos") or [] if isinstance(p, dict) and p.get("fonte")}
    return ids


def validar_saida(dados: dict | None, texto: str, ids_recuperados: set[str], canario: str = config.CANARIO):
    """Aplica o guardrail de saída.

    Retorna (dados_filtrados, texto_filtrado, problemas, bloqueado).
    - canário na saída → bloqueia tudo (vazamento do system prompt);
    - JSON fora do schema → problema registrado (a UI mostra o texto bruto com alerta);
    - fonte citada que não veio da recuperação → passo removido (alucinação de fonte);
    - ação destrutiva em qualquer passo → passo removido (proteção contra injection indireta).
    """
    problemas: list[str] = []
    if canario and canario in (texto or ""):
        return dict(RESPOSTA_RECUSADA), RESPOSTA_RECUSADA["diagnostico"], ["canario_vazado"], True

    if dados is None:  # v1 (texto livre) ou JSON quebrado
        if _DESTRUTIVAS.search(texto or ""):
            problemas.append("acao_destrutiva")
            return None, "⚠️ Resposta bloqueada pelo guardrail de saída: continha ação destrutiva não autorizada.", problemas, True
        externas = fontes_citadas(None, texto) - ids_recuperados
        if externas:
            problemas.append(f"fonte_nao_recuperada:{','.join(sorted(externas))}")
        return None, texto, problemas, False

    problemas += [f"schema:{e}" for e in erros_schema(dados)]
    dados = json.loads(json.dumps(dados))  # cópia
    passos_ok = []
    for passo in dados.get("passos") or []:
        if not isinstance(passo, dict):
            continue
        if _DESTRUTIVAS.search(passo.get("acao", "")):
            problemas.append("acao_destrutiva")
            continue
        if passo.get("fonte") not in ids_recuperados:
            problemas.append(f"fonte_nao_recuperada:{passo.get('fonte')}")
            continue
        passos_ok.append(passo)
    if "passos" in dados:
        dados["passos"] = passos_ok
    if isinstance(dados.get("fontes"), list):
        externas = [f for f in dados["fontes"] if f not in ids_recuperados]
        if externas:
            problemas.append(f"fonte_nao_recuperada:{','.join(externas)}")
            dados["fontes"] = [f for f in dados["fontes"] if f in ids_recuperados]
    if _DESTRUTIVAS.search(dados.get("diagnostico", "") or ""):
        problemas.append("acao_destrutiva")
        dados["diagnostico"] = "(trecho removido pelo guardrail de saída)"
    if any(p.startswith(("acao_destrutiva", "fonte_nao_recuperada")) for p in problemas):
        dados["escalar"] = True
        aviso = "Partes da resposta foram removidas pelo guardrail de saída; confira os documentos e escale se necessário."
        dados["aviso"] = f"{dados['aviso']} {aviso}" if dados.get("aviso") else aviso
    return dados, json.dumps(dados, ensure_ascii=False), sorted(set(problemas)), False


def normalizar(texto: str) -> str:
    """Minúsculas e sem acentos (para comparações de conteúdo na avaliação)."""
    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()
