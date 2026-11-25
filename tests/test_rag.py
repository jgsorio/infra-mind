"""Testes da base e da recuperação (não usam a API)."""
import pytest

from core import rag


def test_pdf_tem_27_incidentes_com_metadados(kb):
    incs = {c["id"] for c in kb.chunks if c["id"].startswith("INC-") and c["origem"].endswith(".pdf")}
    assert incs == {f"INC-{i:03d}" for i in range(1, 28)}
    for c in kb.chunks:
        if c["id"].startswith("INC-") and c["origem"].endswith(".pdf"):
            assert c["severidade"], f"{c['id']} sem severidade"
            assert c["text"].lstrip().startswith(c["id"]), f"{c['id']} não começa com o próprio id"


def test_secoes_auxiliares_e_ruido(kb):
    ids = {c["id"] for c in kb.todos}
    assert {"DOC-SEVERIDADE", "APX-A", "APX-B", "APX-C"} <= ids
    assert "DOC-INDICE" not in kb.ids  # índice fica fora da busca
    for c in kb.chunks:
        assert "Documento fictício - uso interno" not in c["text"]


def test_documentos_extra(kb):
    extra = {c["id"]: c for c in kb.chunks if c["origem"].startswith("extra/")}
    assert set(extra) == {"INC-028", "KB-0042"}
    assert extra["KB-0042"]["atualizado_em"] < "2026-11-18"
    assert "DOCUMENTO DE TESTE" not in extra["INC-028"]["text"]  # comentários HTML não vão ao índice
    assert "ATENÇÃO, ASSISTENTE" in extra["INC-028"]["text"]      # a injection precisa estar lá


@pytest.mark.parametrize("cid", [f"t0{i}" for i in range(1, 9)])
def test_recuperacao_casos_diagnostico_top4(kb, casos, cid):
    caso = casos[cid]
    ids = {h["id"] for h in kb.buscar(caso["entrada"], k=4)}
    assert ids & set(caso["esperado"]["fontes_aceitas"]), f"{cid}: recuperados {ids}"


def test_formatar_documentos_xml(kb):
    hits = kb.buscar("disco cheio /var", k=2)
    xml = rag.formatar_documentos(hits)
    assert xml.count("<documento ") == 2 and 'atualizado_em="' in xml
