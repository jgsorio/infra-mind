"""Configuração central: caminhos, modelos e leitura da chave da API."""
import os
import secrets as _secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
KNOWLEDGE_PDF = DOCS_DIR / "base_conhecimento_infra.pdf"
EXTRA_DIR = DOCS_DIR / "extra"
PROMPTS_DIR = ROOT / "prompts"
SCHEMA_PATH = ROOT / "core" / "schema.json"

try:  # .env é opcional (python-dotenv)
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# Modelos (Groq). Confira no console da Groq se continuam disponíveis na camada gratuita.
MODELO_PRINCIPAL = os.getenv("INFRAMIND_MODELO", "openai/gpt-oss-120b")
MODELO_ALTERNATIVO = os.getenv("INFRAMIND_MODELO_ALT", "openai/gpt-oss-120b")
MODELO_JUIZ = os.getenv("INFRAMIND_MODELO_JUIZ", "openai/gpt-oss-120b")
MODELOS = [MODELO_PRINCIPAL, MODELO_ALTERNATIVO]

TOP_K = int(os.getenv("INFRAMIND_TOP_K", "4"))
TEMPERATURA_APP = 0.2   # chat interativo
TEMPERATURA_EVAL = 0.0  # avaliação: diferença entre versões vem do prompt, não do acaso

# Canário: texto aleatório colocado no system prompt; se aparecer numa saída, houve vazamento.
# Fixe INFRAMIND_CANARIO para rodadas de avaliação reprodutíveis (o cache depende dele).
CANARIO = os.getenv("INFRAMIND_CANARIO") or f"CANARIO-{_secrets.token_hex(6)}"


def get_api_key() -> str:
    """Lê GROQ_API_KEY de variável de ambiente, .env ou .streamlit/secrets.toml."""
    key = os.getenv("GROQ_API_KEY")
    if key:
        return key
    try:
        import streamlit as st

        key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        key = None
    if not key:
        try:
            import tomllib

            path = ROOT / ".streamlit" / "secrets.toml"
            if path.exists():
                key = tomllib.loads(path.read_text(encoding="utf-8")).get("GROQ_API_KEY")
        except Exception:
            key = None
    if not key:
        raise RuntimeError("GROQ_API_KEY não encontrada (defina no .env, na variável de ambiente ou em .streamlit/secrets.toml).")
    return key
