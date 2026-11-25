"""Orquestração: responder(pergunta, versao) — guardrail de entrada → RAG → LLM → guardrail de saída.

Versões (prompts/vN.md):
- v1: persona + trechos + texto livre (linha de base);
- v2: + few-shot, JSON Schema, fonte obrigatória por passo;
- v3: + cadeia de 2 chamadas (triagem → resposta), delimitadores, campo analise, regras de
      "não sei", documento mais recente e documento adulterado.

Os guardrails (detecção de ataque na entrada + validação da saída) são uma camada independente
da versão do prompt, ligada/desligada por `guardrails=`, para medir o efeito de cada um em separado.
O mascaramento de PII é sempre aplicado (LGPD): nada com e-mail, CPF ou telefone vai ao modelo ou ao log.
"""
import json
import time
from dataclasses import asdict, dataclass, field

from core import config, guardrails, llm, prompts, rag


@dataclass
class Resposta:
    versao: str
    modelo: str
    guardrails: bool
    pergunta_mascarada: str
    pii_mascarada: list[str] = field(default_factory=list)
    ataque_detectado: list[str] = field(default_factory=list)
    triagem: dict | None = None
    consulta_busca: str = ""
    hits: list[dict] = field(default_factory=list)
    texto_bruto: str = ""          # saída do modelo, sem filtro
    texto: str = ""                # o que vai para a tela (após guardrail, se ligado)
    dados: dict | None = None      # JSON (v2/v3) após guardrail, se ligado
    dados_brutos: dict | None = None
    json_valido: bool | None = None  # None na v1
    erros_schema: list[str] = field(default_factory=list)
    problemas_saida: list[str] = field(default_factory=list)
    bloqueado: bool = False
    chamadas: int = 0
    latencia_s: float = 0.0
    canario: str = config.CANARIO

    @property
    def ids_recuperados(self) -> list[str]:
        return list(dict.fromkeys(h["id"] for h in self.hits))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ids_recuperados"] = self.ids_recuperados
        d["hits"] = [{k: h[k] for k in ("id", "titulo", "score", "atualizado_em", "origem")} for h in self.hits]
        d["documentos"] = rag.formatar_documentos(self.hits)
        return d


def _historico_texto(historico: list[dict] | None, n: int = 4) -> str:
    if not historico:
        return "(vazio)"
    linhas = [f"{m['role']}: {guardrails.mascarar_pii(m['content'])[0][:500]}" for m in historico[-n:]]
    return "\n".join(linhas)


def triagem(pergunta: str, modelo: str, temperatura: float) -> tuple[dict, float]:
    """1ª chamada da cadeia (v3): extrai serviço, sintoma, erros e consulta de busca."""
    p = prompts.carregar("v3")
    msgs = [{"role": "system", "content": p["triagem_system"]},
            {"role": "user", "content": prompts.preencher(p["triagem_user"], pergunta=pergunta)}]
    texto, lat = llm.chat(msgs, modelo, temperatura, json_mode=True)
    return llm.extrair_json(texto) or {}, lat


def consulta_expandida(pergunta: str, tri: dict) -> str:
    """Consulta reescrita pela triagem + texto original (mantém mensagens de erro literais)."""
    partes = [tri.get("consulta", ""), tri.get("servico", ""), " ".join(tri.get("mensagens_erro") or []), pergunta]
    return "\n".join(p for p in partes if p)


def responder(pergunta: str, versao: str, kb: rag.BaseConhecimento, *, modelo: str = config.MODELO_PRINCIPAL,
              k: int = config.TOP_K, guardrails_on: bool = True, historico: list[dict] | None = None,
              temperatura: float = config.TEMPERATURA_APP, stream_cb=None) -> Resposta:
    """Responde uma pergunta com a versão de prompt escolhida.

    stream_cb: função opcional que recebe um gerador de texto (usada pela UI na v1 para streaming)
    e devolve o texto completo.
    """
    if versao not in prompts.VERSOES:
        raise ValueError(f"versão desconhecida: {versao}")
    mascarada, pii = guardrails.mascarar_pii(pergunta)
    r = Resposta(versao=versao, modelo=modelo, guardrails=guardrails_on, pergunta_mascarada=mascarada, pii_mascarada=pii)

    # Guardrail de entrada: ataque conhecido nem chega ao modelo.
    r.ataque_detectado = guardrails.detectar_ataque(mascarada)
    if guardrails_on and r.ataque_detectado:
        r.dados = r.dados_brutos = dict(guardrails.RESPOSTA_RECUSADA)
        r.texto = r.texto_bruto = json.dumps(r.dados, ensure_ascii=False) if versao != "v1" else r.dados["diagnostico"]
        r.json_valido = True if versao != "v1" else None
        r.problemas_saida = ["entrada_bloqueada"]
        return r

    p = prompts.carregar(versao)
    inicio = time.perf_counter()

    # Recuperação (na v3, com a consulta reescrita pela triagem).
    r.consulta_busca = mascarada
    if versao == "v3":
        r.triagem, _ = triagem(mascarada, modelo, temperatura)
        r.chamadas += 1
        r.consulta_busca = consulta_expandida(mascarada, r.triagem)
    r.hits = kb.buscar(r.consulta_busca, k=k)

    sistema = prompts.preencher(p["system"], canario=r.canario)
    if versao == "v1":
        msgs = [{"role": "system", "content": sistema}]
        msgs += [{"role": m["role"], "content": guardrails.mascarar_pii(m["content"])[0]} for m in (historico or [])[-6:]]
        msgs.append({"role": "user", "content": prompts.preencher(
            p["user"], documentos=rag.formatar_documentos(r.hits, "simples"), pergunta=mascarada)})
        if stream_cb:
            r.texto_bruto = stream_cb(llm.chat_stream(msgs, modelo, temperatura))
        else:
            r.texto_bruto, _ = llm.chat(msgs, modelo, temperatura)
    else:
        user = prompts.preencher(
            p["user"], documentos=rag.formatar_documentos(r.hits), pergunta=mascarada,
            historico=_historico_texto(historico),
            triagem=json.dumps(r.triagem or {}, ensure_ascii=False))
        msgs = [{"role": "system", "content": sistema}, {"role": "user", "content": user}]
        r.texto_bruto, _ = llm.chat(msgs, modelo, temperatura, json_mode=True)
        r.dados_brutos = llm.extrair_json(r.texto_bruto)
        r.erros_schema = guardrails.erros_schema(r.dados_brutos)
        r.json_valido = not r.erros_schema
    r.chamadas += 1
    r.latencia_s = time.perf_counter() - inicio

    # Guardrail de saída.
    r.texto, r.dados = r.texto_bruto, r.dados_brutos
    if guardrails_on:
        r.dados, r.texto, problemas, r.bloqueado = guardrails.validar_saida(
            r.dados_brutos, r.texto_bruto, set(r.ids_recuperados), r.canario)
        r.problemas_saida += problemas
    return r


def para_markdown(r: Resposta) -> str:
    """Renderiza a resposta para a tela e para o histórico."""
    if r.versao == "v1" or r.dados is None:
        aviso = ""
        if r.versao != "v1":
            aviso = "⚠️ A resposta não veio no formato esperado (JSON). Texto bruto:\n\n"
        return aviso + (r.texto or "")
    d = r.dados
    rotulo = {"coberto": "✅ Coberto pela base", "fora_da_base": "❓ Fora da base — escale",
              "recusado": "⛔ Pedido recusado"}.get(d.get("cobertura"), d.get("cobertura"))
    linhas = [f"**{rotulo}**" + (f" · severidade **{d['severidade']}**" if d.get("severidade") else "")]
    if d.get("diagnostico"):
        linhas.append(f"\n**Diagnóstico:** {d['diagnostico']}")
    if d.get("passos"):
        linhas.append("\n**Passos:**")
        linhas += [f"{i}. {p['acao']} `[{p['fonte']}]`" for i, p in enumerate(d["passos"], 1)]
    if d.get("aviso"):
        linhas.append(f"\n> ⚠️ {d['aviso']}")
    if d.get("escalar"):
        linhas.append("\n🚨 **Escale** conforme a política de severidade.")
    if d.get("fontes"):
        linhas.append(f"\n_Fontes: {', '.join(d['fontes'])}_")
    if d.get("cobertura") == "coberto":
        linhas.append("\n_Valide os comandos antes de executar em produção._")
    return "\n".join(linhas)
