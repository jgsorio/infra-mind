import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def casos():
    linhas = (ROOT / "eval" / "casos_de_teste.jsonl").read_text(encoding="utf-8").splitlines()
    return {c["id"]: c for c in (json.loads(l) for l in linhas if l.strip())}


@pytest.fixture(scope="session")
def kb():
    from core import rag

    return rag.BaseConhecimento.carregar(incluir_extra=True)
