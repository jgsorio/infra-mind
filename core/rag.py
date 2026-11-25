"""RAG: extração da base (PDF + Markdown), chunking por documento e busca TF-IDF.

Cada chunk carrega metadados: id (INC-xxx ou DOC-/APX-), título, categoria, severidade,
data de atualização, origem e página. O id é o que a resposta cita e o que o guardrail
de saída confere contra a lista de trechos recuperados.
"""
import io
import re
from pathlib import Path

from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from core import config

PDF_ATUALIZADO_EM = "2026-11-18"  # "Versão 2.0 · 18/11/2026" na capa do PDF
CHUNK_SIZE = 1800

_NOISE = re.compile(
    r"^\s*(InfraMind - Base de Conhecimento.*|Documento fictício - uso interno.*|Página \d+|5\.\d+\s+\S.*)\s*$"
)
_INC = re.compile(r"^[ \t]*(INC-\d{3}) - (.+)$", re.M)
_SECAO = re.compile(
    r"^[ \t]*\d\.\s+(Como usar este documento|Política de severidade|Metodologia geral|Índice de incidentes|Apêndice ([A-C]))[^\n]*$",
    re.M,
)
_META = re.compile(r"Categoria:\s*(.+?)\s*\|\s*Severidade:\s*([^\s|]+)")
_SECAO_IDS = {
    "Como usar este documento": "DOC-USO",
    "Política de severidade": "DOC-SEVERIDADE",
    "Metodologia geral": "DOC-METODOLOGIA",
    "Índice de incidentes": "DOC-INDICE",
}
# Fora do índice de busca: a capa e o índice listam títulos de todos os casos e "roubam" as consultas.
_NAO_INDEXAR = {"DOC-CAPA", "DOC-INDICE"}


def _pdf_text(source) -> tuple[str, list[tuple[int, int]]]:
    text, marks = "", []  # marks: (posição no texto, página)
    for page_no, page in enumerate(PdfReader(source).pages, 1):
        lines = [l for l in (page.extract_text() or "").splitlines() if not _NOISE.match(l)]
        marks.append((len(text), page_no))
        text += "\n".join(lines) + "\n"
    return text, marks


def _split(doc: dict, body: str) -> list[dict]:
    """Divide um documento longo em pedaços, repetindo id e título em cada um."""
    header = f"{doc['id']} - {doc['titulo']}"
    pieces = []
    for i in range(0, len(body), CHUNK_SIZE):
        piece = body[i:i + CHUNK_SIZE].strip()
        if i:
            piece = f"{header} (continuação)\n{piece}"
        if len(piece) > 40:
            pieces.append({**doc, "parte": len(pieces) + 1, "text": piece})
    return pieces


def chunks_do_pdf(source=None) -> list[dict]:
    source = source or io.BytesIO(config.KNOWLEDGE_PDF.read_bytes())
    text, marks = _pdf_text(source)

    def page_at(pos):
        return [p for start, p in marks if start <= pos][-1]

    bounds = [(0, "DOC-CAPA", "Capa")]
    for m in _SECAO.finditer(text):
        nome = m.group(1)
        doc_id = f"APX-{m.group(2)}" if m.group(2) else _SECAO_IDS[nome]
        bounds.append((m.start(), doc_id, m.group(0).strip()))
    for m in _INC.finditer(text):
        bounds.append((m.start(), m.group(1), m.group(2).strip()))
    bounds.sort()

    chunks = []
    for (start, doc_id, titulo), nxt in zip(bounds, bounds[1:] + [(len(text), None, None)]):
        body = text[start:nxt[0]].strip()
        if not body:
            continue
        meta = _META.search(body)
        doc = {
            "id": doc_id,
            "titulo": titulo,
            "categoria": meta.group(1) if meta else "",
            "severidade": meta.group(2) if meta else "",
            "atualizado_em": PDF_ATUALIZADO_EM,
            "origem": config.KNOWLEDGE_PDF.name,
            "pagina": page_at(start),
        }
        chunks.extend(_split(doc, body))
    return chunks


def _front_matter(raw: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.S)
    if not m:
        return {}, raw
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, raw[m.end():]


def chunks_do_markdown(folder: Path | None = None) -> list[dict]:
    """Documentos extras em docs/extra/*.md com front matter (id, titulo, categoria, severidade, atualizado_em)."""
    folder = folder or config.EXTRA_DIR
    chunks = []
    for path in sorted(Path(folder).glob("*.md")):
        meta, body = _front_matter(path.read_text(encoding="utf-8"))
        body = re.sub(r"<!--.*?-->", "", body, flags=re.S)  # notas para humanos não vão ao índice
        if not meta.get("id"):
            continue
        doc = {
            "id": meta["id"],
            "titulo": meta.get("titulo", path.stem),
            "categoria": meta.get("categoria", ""),
            "severidade": meta.get("severidade", ""),
            "atualizado_em": meta.get("atualizado_em", ""),
            "origem": f"extra/{path.name}",
            "pagina": None,
        }
        header = f"{doc['id']} - {doc['titulo']}\nCategoria: {doc['categoria']} | Severidade: {doc['severidade']}\n"
        chunks.extend(_split(doc, header + body.strip()))
    return chunks


class BaseConhecimento:
    """Índice TF-IDF (n-gramas de caracteres) sobre os chunks indexáveis."""

    def __init__(self, chunks: list[dict]):
        self.todos = chunks
        self.chunks = [c for c in chunks if c["id"] not in _NAO_INDEXAR]
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True,
                                   strip_accents="unicode", lowercase=True)
        self.matrix = self.vec.fit_transform([c["text"] for c in self.chunks])

    @classmethod
    def carregar(cls, incluir_extra: bool = True) -> "BaseConhecimento":
        chunks = chunks_do_pdf()
        if incluir_extra:
            chunks += chunks_do_markdown()
        return cls(chunks)

    @property
    def ids(self) -> set[str]:
        return {c["id"] for c in self.chunks}

    def buscar(self, consulta: str, k: int = config.TOP_K) -> list[dict]:
        """Retorna os k chunks mais parecidos: [{**chunk, "score": float}]."""
        scores = cosine_similarity(self.vec.transform([consulta]), self.matrix).ravel()
        best = scores.argsort()[::-1][:k]
        return [{**self.chunks[i], "score": float(scores[i])} for i in best if scores[i] > 0]


def formatar_documentos(hits: list[dict], estilo: str = "xml") -> str:
    """Monta o bloco de contexto. 'simples' é o formato da v1; 'xml' delimita cada documento (v2/v3)."""
    if estilo == "simples":
        return "\n\n---\n\n".join(f"[{h['id']} · página {h['pagina'] or '-'}]\n{h['text']}" for h in hits)
    return "\n".join(
        f'<documento id="{h["id"]}" atualizado_em="{h["atualizado_em"]}" origem="{h["origem"]}">\n{h["text"]}\n</documento>'
        for h in hits
    )
