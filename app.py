import hmac
import io
import re
from pathlib import Path

import streamlit as st
from groq import Groq
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import storage

MODEL = "openai/gpt-oss-120b"
KNOWLEDGE_PDF = Path(__file__).parent / "docs" / "base_conhecimento_infra.pdf"
AUTH_USER, AUTH_PASS = "admin", "admin"
TOP_K = 4

SYSTEM_PROMPT = """Você é o InfraMind, um assistente de troubleshooting de infraestrutura e sistemas operacionais.
Responda SEMPRE em português, usando APENAS o contexto da documentação fornecido.
- Informe o ID do caso (ex.: INC-001) usado como base.
- Apresente: causa provável, comandos de diagnóstico e passos da solução, de forma objetiva.
- Se o contexto não contiver a resposta, diga claramente que a documentação não cobre o problema e não invente.
- Lembre o usuário de validar comandos antes de executar em produção."""


def extract_chunks(file) -> list[dict]:
    """Extrai o texto do PDF e divide em chunks (um por caso/seção, subdividindo os longos)."""
    noise = re.compile(r"^(InfraMind - Base de Conhecimento.*|Documento fictício - uso interno|Página \d+)$")
    text, marks = "", []  # marks: (posição no texto, página)
    for page_no, page in enumerate(PdfReader(file).pages, 1):
        lines = [l for l in (page.extract_text() or "").splitlines() if not noise.match(l.strip())]
        marks.append((len(text), page_no))
        text += "\n".join(lines) + "\n"

    def page_at(pos):
        return [p for start, p in marks if start <= pos][-1]

    chunks, size = [], 1800
    starts = [m.start() for m in re.finditer(r"^INC-\d{3} - .+$", text, re.M)]
    bounds = ([0] if not starts or starts[0] > 0 else []) + starts + [len(text)]
    for a, b in zip(bounds, bounds[1:]):
        body = text[a:b].strip()
        header = body.splitlines()[0] if re.match(r"INC-\d{3} - ", body) else ""
        for i in range(0, len(body), size):
            piece = body[i:i + size].strip()
            if i and header:
                piece = f"{header} (continuação)\n{piece}"
            if len(piece) > 40:
                chunks.append({"page": page_at(a + i), "text": piece})
    return chunks


@st.cache_resource(show_spinner="Indexando base de conhecimento...")
def build_index():
    chunks = extract_chunks(io.BytesIO(KNOWLEDGE_PDF.read_bytes()))
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, strip_accents="unicode", lowercase=True)
    matrix = vec.fit_transform([c["text"] for c in chunks])
    return chunks, vec, matrix


def retrieve(query, chunks, vec, matrix, k=TOP_K):
    scores = cosine_similarity(vec.transform([query]), matrix).ravel()
    best = scores.argsort()[::-1][:k]
    return [(chunks[i], float(scores[i])) for i in best if scores[i] > 0]


def ask_llm(question, history, hits):
    context = "\n\n---\n\n".join(f"[Página {c['page']}]\n{c['text']}" for c, _ in hits)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += history[-6:]
    messages.append({"role": "user", "content": f"Contexto da documentação:\n{context}\n\nPergunta: {question}"})
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    stream = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.2, stream=True)
    for chunk in stream:
        yield chunk.choices[0].delta.content or ""


def login_screen():
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.title("🧠 InfraMind")
        st.caption("Your AI Copilot for Infrastructure Troubleshooting")
        with st.form("login"):
            user = st.text_input("Usuário")
            pwd = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", use_container_width=True, type="primary"):
                ok = hmac.compare_digest(user.encode(), AUTH_USER.encode()) & hmac.compare_digest(pwd.encode(), AUTH_PASS.encode())
                if ok:
                    st.session_state.user = user
                    st.rerun()
                st.error("Usuário ou senha inválidos.")


def sidebar(user):
    with st.sidebar:
        st.markdown(f"👤 **{user}**")
        if st.button("Sair", use_container_width=True):
            for k in ("user", "conv_id", "messages"):
                st.session_state.pop(k, None)
            st.rerun()
        st.divider()
        if st.button("➕ Nova conversa", use_container_width=True, type="primary"):
            st.session_state.conv_id, st.session_state.messages = None, []
            st.rerun()
        st.subheader("Conversas recentes")
        convs = storage.list_conversations(user)
        if not convs:
            st.caption("Nenhuma conversa ainda.")
        for cid, title in convs:
            c1, c2 = st.columns([5, 1])
            active = cid == st.session_state.get("conv_id")
            if c1.button(title, key=f"open{cid}", use_container_width=True, type="primary" if active else "secondary"):
                st.session_state.conv_id = cid
                st.session_state.messages = storage.get_messages(cid, user)
                st.rerun()
            if c2.button("🗑", key=f"del{cid}", help="Excluir conversa"):
                storage.delete_conversation(cid, user)
                if active:
                    st.session_state.conv_id, st.session_state.messages = None, []
                st.rerun()
        if convs:
            st.divider()
            if st.button("Excluir todas", use_container_width=True):
                st.session_state.confirm_all = True
            if st.session_state.get("confirm_all"):
                st.warning("Excluir TODO o histórico?")
                a, b = st.columns(2)
                if a.button("Sim"):
                    storage.delete_all(user)
                    st.session_state.conv_id, st.session_state.messages, st.session_state.confirm_all = None, [], False
                    st.rerun()
                if b.button("Não"):
                    st.session_state.confirm_all = False
                    st.rerun()


def chat(user):
    chunks, vec, matrix = build_index()
    st.title("🧠 InfraMind")
    st.caption("Your AI Copilot for Infrastructure Troubleshooting")
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("conv_id", None)

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    question = st.chat_input("Descreva o problema (ex.: disco cheio no Linux)")
    if not question:
        return
    if st.session_state.conv_id is None:
        st.session_state.conv_id = storage.create_conversation(user, question)
    cid = st.session_state.conv_id
    history = list(st.session_state.messages)
    st.session_state.messages.append({"role": "user", "content": question})
    storage.add_message(cid, "user", question)
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        hits = retrieve(question, chunks, vec, matrix)
        if not hits:
            answer = "Não encontrei nada na documentação relacionado a essa pergunta."
            st.markdown(answer)
        else:
            try:
                answer = st.write_stream(ask_llm(question, history, hits))
            except Exception as e:
                answer = f"Erro ao consultar a Groq: {e}"
                st.error(answer)
            with st.expander("📚 Trechos utilizados"):
                for c, s in hits:
                    st.markdown(f"**Página {c['page']}** · similaridade {s:.2f}")
                    st.text(c["text"][:400] + "...")
    st.session_state.messages.append({"role": "assistant", "content": answer})
    storage.add_message(cid, "assistant", answer)
    st.rerun()  # atualiza a barra lateral com a nova conversa


st.set_page_config(page_title="InfraMind", page_icon="🧠")
if "user" not in st.session_state:
    login_screen()
else:
    sidebar(st.session_state.user)
    chat(st.session_state.user)
