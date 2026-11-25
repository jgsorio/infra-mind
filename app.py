"""InfraMind — interface Streamlit (login, chat, histórico, seletor de versão do prompt)."""
import hmac

import streamlit as st

import storage
from core import config, guardrails, prompts, rag
from core.chain import para_markdown, responder

AUTH_USER, AUTH_PASS = "admin", "admin"


@st.cache_resource(show_spinner="Indexando base de conhecimento...")
def build_index():
    return rag.BaseConhecimento.carregar(incluir_extra=True)


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
            for k in ("user", "conv_id", "messages", "last_r"):
                st.session_state.pop(k, None)
            st.rerun()

        st.divider()
        st.subheader("⚙️ Configuração")
        st.selectbox("Versão do prompt", prompts.VERSOES, index=len(prompts.VERSOES) - 1, key="versao",
                     help="v1: texto livre · v2: few-shot + JSON · v3: cadeia + delimitadores + análise")
        st.toggle("Guardrails ativos", value=True, key="guardrails",
                  help="Bloqueia padrões de ataque na entrada e valida fontes, ações e vazamento na saída.")
        st.selectbox("Modelo", config.MODELOS, key="modelo")

        st.divider()
        if st.button("➕ Nova conversa", use_container_width=True, type="primary"):
            st.session_state.conv_id, st.session_state.messages = None, []
            st.session_state.pop("last_r", None)
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
                st.session_state.pop("last_r", None)
                st.rerun()
            if c2.button("🗑", key=f"del{cid}", help="Excluir conversa"):
                storage.delete_conversation(cid, user)
                if active:
                    st.session_state.conv_id, st.session_state.messages = None, []
                    st.session_state.pop("last_r", None)
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


def detalhes(r):
    """Painéis de transparência: trechos usados, triagem/análise e guardrails."""
    if r.hits:
        with st.expander(f"📚 Trechos utilizados ({len(r.hits)})"):
            for h in r.hits:
                pagina = f" · página {h['pagina']}" if h.get("pagina") else ""
                st.markdown(f"**{h['id']}** — {h['titulo']}{pagina} · atualizado em {h['atualizado_em']} · similaridade {h['score']:.2f}")
                st.text(h["text"][:400] + "...")
    if r.triagem or (r.dados and r.dados.get("analise")):
        with st.expander("🧩 Triagem e análise (v3)"):
            if r.triagem:
                st.json(r.triagem)
            if r.dados and r.dados.get("analise"):
                st.markdown(f"**Análise:** {r.dados['analise']}")
    if r.pii_mascarada or r.ataque_detectado or r.problemas_saida:
        with st.expander("🛡️ Guardrails"):
            if r.pii_mascarada:
                st.markdown(f"Dados pessoais mascarados antes do modelo e do histórico: {', '.join(r.pii_mascarada)}")
            if r.ataque_detectado:
                st.markdown(f"Padrões de ataque na entrada: `{', '.join(r.ataque_detectado)}`")
            if r.problemas_saida:
                st.markdown(f"Ocorrências na saída: `{', '.join(r.problemas_saida)}`")
    st.caption(f"{r.versao} · {r.modelo} · guardrails {'on' if r.guardrails else 'off'} · "
               f"{r.chamadas} chamada(s) · {r.latencia_s:.1f}s")


def chat(user):
    kb = build_index()
    st.title("🧠 InfraMind")
    st.caption("Your AI Copilot for Infrastructure Troubleshooting")
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("conv_id", None)

    msgs = st.session_state.messages
    for i, m in enumerate(msgs):
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if i == len(msgs) - 1 and m["role"] == "assistant" and st.session_state.get("last_r"):
                detalhes(st.session_state.last_r)

    question = st.chat_input("Descreva o problema ou cole o alerta (ex.: disco cheio no Linux)")
    if not question:
        return
    # LGPD: o que é gravado e exibido é a versão mascarada.
    masked, _ = guardrails.mascarar_pii(question)
    if st.session_state.conv_id is None:
        st.session_state.conv_id = storage.create_conversation(user, masked)
    cid = st.session_state.conv_id
    history = list(st.session_state.messages)
    st.session_state.messages.append({"role": "user", "content": masked})
    storage.add_message(cid, "user", masked)
    with st.chat_message("user"):
        st.markdown(masked)
    with st.chat_message("assistant"):
        versao = st.session_state.get("versao", "v3")
        try:
            with st.spinner("Consultando a base e o modelo..."):
                r = responder(question, versao, kb, modelo=st.session_state.get("modelo", config.MODELO_PRINCIPAL),
                              guardrails_on=st.session_state.get("guardrails", True), historico=history,
                              stream_cb=st.write_stream if versao == "v1" else None)
            answer = para_markdown(r)
            st.session_state.last_r = r  # detalhes exibidos abaixo da última resposta após o rerun
        except Exception as e:
            answer = f"Erro ao consultar o modelo: {e}"
            st.session_state.pop("last_r", None)
            st.error(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
    storage.add_message(cid, "assistant", answer)
    st.rerun()  # atualiza a barra lateral com a nova conversa


st.set_page_config(page_title="InfraMind", page_icon="🧠")
if "user" not in st.session_state:
    login_screen()
else:
    sidebar(st.session_state.user)
    chat(st.session_state.user)
