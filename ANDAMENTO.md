# InfraMind — Andamento do Trabalho Final (Advanced Generative AI)

> Arquivo vivo: registra o estado do projeto frente ao guia do trabalho
> (`../Trabalho Final Advanced Generative AI — Proposta e passo a passo.pdf`).
> Atualize as caixas `[ ]` → `[x]` conforme avançar. Última revisão: **24/11/2026**.

**Entrega:** início do encontro de **25/11/2026** (canal indicado pelo professor).
**Prazo restante:** menos de 1 dia → seguir a ordem de prioridade da seção 4.

---

## 1. Como o projeto está hoje (diagnóstico)

O InfraMind é a nossa versão do tema "Copiloto de Plantão" do guia. O que já existe:

| Item | Estado atual | Arquivo |
|---|---|---|
| Interface Streamlit (login, chat, streaming, histórico, "Trechos utilizados") | ✅ Pronto | `app.py` |
| Persistência de conversas por usuário (SQLite) | ✅ Pronto | `storage.py` |
| Base de conhecimento sintética (27 incidentes INC-001..INC-027, política de severidade, cheat sheet, checklist, glossário) | ✅ Pronto (fictícia) | `docs/base_conhecimento_infra.pdf` |
| RAG: chunking por incidente (máx. 1800 chars) + TF-IDF de n-gramas de caracteres + top-4 por cosseno | ✅ Pronto (versão única) | `app.py` (`extract_chunks`, `build_index`, `retrieve`) |
| LLM: Groq `openai/gpt-oss-120b`, temperatura 0.2, histórico das últimas 6 mensagens | ✅ Pronto | `app.py` (`ask_llm`) |
| System prompt com persona, "use só o contexto", citar INC, "não invente" | ✅ Equivale à **v1** do guia | `app.py` (`SYSTEM_PROMPT`) |
| Chave de API fora do código (`.streamlit/secrets.toml` no `.gitignore`) | ✅ Pronto | `.gitignore` |
| README com instalação e uso | 🟡 Parcial (falta avaliação, decisões, limitações) | `README.md` |
| Dev Container (Codespaces) | ✅ Pronto | `.devcontainer/` |

### Mapeamento contra os requisitos (R1–R5) e a rubrica

| Critério (peso) | Mínimo exigido | Situação | Gap |
|---|---|---|---|
| R1 Problema e valor (10%) | Usuário-alvo, dor, por que IA generativa, métrica | 🟡 Só no README, informal | Escrever no relatório com as metas numéricas |
| Arquitetura e modelo (15%) | Decisões justificadas sobre o diagrama de referência | 🟡 Arquitetura existe, sem justificativa nem comparação | Diagrama de 7 blocos + tabela API vs. modelo alternativo (acerto, JSON válido, latência) |
| R2 Prompt engineering (25%) | ≥3 técnicas, v1→v2→v3 comparadas | 🔴 Só 1 prompt, sem versionamento | Criar `prompts/v1.md, v2.md, v3.md`, seletor de versão, few-shot, JSON Schema, chaining, delimitadores, campo `analise` |
| R3 Personalização (20%) | RAG/FT/multimodal com justificativa | 🟡 RAG funciona, sem experimento | Experimento hit@k (k=2,4,6, com/sem consulta reescrita); justificar TF-IDF vs. embeddings; metadados por chunk (id, categoria, severidade) |
| R4 Avaliação (15%) | ≥15 casos, métrica ou LLM-as-judge, evolução entre versões | 🔴 Inexistente | `eval/casos_de_teste.jsonl` (✅ criado), `run_eval.py`, `judge.py`, `placar.md` |
| R5 Segurança e ética (5%) | Injection direta/indireta, vazamento, alucinação, viés, LGPD | 🔴 Sem guardrails | Guardrail de entrada (padrões + máscara de PII), canário, guardrail de saída (schema + fontes ⊂ recuperadas), doc envenenado |
| Pitch e demo (10%) | 7 min + 3 min perguntas, vídeo plano B | 🔴 Não iniciado | Slides, roteiro, vídeo |

### Problemas/pontos de atenção encontrados no código

1. **Temperatura 0.2** → a avaliação deve rodar com `temperature=0` (diferença entre versões precisa vir do prompt, não do acaso).
2. **Chunks não guardam o ID do incidente como metadado** (só a página). Sem isso, o guardrail de saída não consegue conferir se o INC citado veio da recuperação, e o hit@k não pode ser medido automaticamente.
3. **`retrieve` quase nunca retorna vazio** (TF-IDF de n-gramas de caractere sempre tem alguma similaridade > 0). O "não sei" depende 100% do LLM → precisa de regra explícita no prompt (v3) e, opcionalmente, um limiar de similaridade.
4. **Histórico de 6 mensagens vai ao modelo sem filtro** → vetor de injection via conversa; também polui a avaliação (avaliar sempre sem histórico).
5. **LGPD:** as conversas **são gravadas** em SQLite sem mascaramento. O guia sugere "conversas não são guardadas" → mascarar PII antes de chamar o modelo **e** antes de gravar; documentar a retenção como risco residual.
6. **Login fixo `admin/admin`** → declarar como limitação (ambiente de estudo).
7. **Chave via `st.secrets`** só funciona dentro do Streamlit → scripts de avaliação precisam ler de variável de ambiente (`GROQ_API_KEY`) também. Adicionar `.env` ao `.gitignore` e criar `.env.example` / `secrets.toml.example`.
8. **Não há documento envenenado nem documento desatualizado contraditório** na base (o guia pede ambos) → criar `docs/extra/*.md` e fazer o `build_index` ler também Markdown (mais simples que regenerar o PDF).
9. **Lógica toda em `app.py`** acoplada ao Streamlit (`st.cache_resource`, `st.secrets`) → extrair RAG/LLM para módulos importáveis pelo `run_eval.py`.
10. `requirements.txt` sem versões fixadas → fixar para a "instalação do zero" funcionar.
11. **Nesta máquina Windows o Python não está instalado** (só o atalho da Microsoft Store). Para rodar o app/avaliação localmente: instalar Python ≥ 3.10, ou usar o Dev Container/Codespaces.

---

## 2. Decisões já tomadas (para o relatório)

| Decisão | Escolha | Justificativa curta |
|---|---|---|
| Tema | Copiloto de plantão de infraestrutura (InfraMind) | Encaixa no caso de RAG do guia; conhecimento em documentos que mudam |
| Provedor LLM | Groq (camada gratuita), `openai/gpt-oss-120b` | Custo zero, baixa latência, modelo open-weights |
| Recuperação | TF-IDF char n-gram (3–5), top-4 | Sem download de modelo, sem GPU, tolera acento/erro de digitação; **a validar** com o experimento hit@k |
| Base | PDF fictício com 27 incidentes | Dados 100% sintéticos (regra do guia) |
| Orquestração | Python puro, sem LangChain | Prompt visível e fácil de explicar |

**A decidir:** modelo de comparação (ex.: outro modelo menor da Groq, como um Llama de ~8B, ou Ollama local) e modelo juiz (diferente do gerador). Conferir no console da Groq quais modelos e limites estão disponíveis hoje.

---

## 3. O que falta fazer (checklist)

### R2 — Prompts versionados
- [ ] Refatorar: `app/rag.py` (chunks com `id`, `titulo`, `categoria`, `severidade`), `app/chain.py` (`responder(pergunta, versao)`), `app/guardrails.py`
- [ ] `prompts/v1.md` — prompt atual (persona + trechos + texto livre) = linha de base
- [ ] `prompts/v2.md` — few-shot (3 exemplos: normal, fora da base, ataque) + JSON Schema + citação obrigatória de INC por passo
- [ ] `prompts/v3.md` — cadeia de 2 chamadas (extrai serviço/sintoma/consulta → responde), delimitadores `<documentos>`/`<pergunta>`, campo `analise`, regra de "não sei", regra de documento mais recente, canário
- [ ] `app/schema.json` (campos: `cobertura`, `severidade`, `analise`, `diagnostico`, `passos[{acao,fonte}]`, `fontes`, `escalar`)
- [ ] Seletor de versão do prompt na barra lateral do Streamlit + renderização do JSON em Markdown
- [ ] Cada ficha com: o que mudou, por quê (erros da versão anterior), texto completo, placar, 2 exemplos antes/depois, o que ainda falha

### R3 — RAG
- [ ] Ler também `docs/extra/*.md` no índice
- [ ] `docs/extra/INC-028-cache-hit-rate.md` — **documento envenenado** (instrução escondida em "Observações")
- [ ] `docs/extra/INC-001-legado.md` — versão antiga (2024) que contradiz a INC-001 atual (teste de "documento mais recente")
- [ ] Adicionar data de atualização como metadado
- [ ] Experimento hit@k: k = 2, 4, 6 × {consulta original, consulta reescrita} → tabela no relatório
- [ ] (Opcional, forte para "Excelente") comparar TF-IDF vs. embeddings multilíngues no mesmo hit@k

### R4 — Avaliação
- [x] `eval/casos_de_teste.jsonl` — 27 casos (ver `eval/PLANO_DE_TESTES.md`)
- [x] `eval/PLANO_DE_TESTES.md` — métricas, metas, resultados esperados por versão, rubrica do juiz
- [ ] `eval/run_eval.py` — roda casos × versão, `temperature=0`, sem histórico, pausa entre chamadas, cache em disco, salva `eval/saidas/vN.jsonl`, calcula métricas automáticas
- [ ] `eval/judge.py` + `prompts/juiz.md` — fidelidade e utilidade 1–5, modelo diferente do gerador
- [ ] Conferir 5 notas do juiz à mão e registrar concordância
- [ ] `eval/placar.md` — tabela métrica × versão + gráfico de barras + análise de erros (recuperação / geração / formato / segurança)
- [ ] Rodar os mesmos casos no modelo alternativo (tabela de comparação de modelos)

### R5 — Segurança
- [ ] Guardrail de entrada: regex para "ignore as instruções", "mostre seu prompt", "você agora é", etc. → `cobertura: recusado`
- [ ] Mascaramento de e-mail, CPF e telefone **antes** do LLM e **antes** do SQLite
- [ ] Canário aleatório no system prompt + busca do canário em toda saída
- [ ] Guardrail de saída: valida JSON Schema; fontes citadas ⊂ IDs recuperados; barra ações perigosas que não estão no INC citado
- [ ] Testes de viés (par estagiária × sênior) comparados lado a lado
- [ ] Registrar riscos residuais (regex contornável, SQLite guarda conversas, login fixo)

### Entregáveis
- [ ] Protótipo executável + README completo (avaliação, decisões, limitações, `.env.example`)
- [ ] Relatório técnico ≤ 8 páginas → template em `relatorio/RELATORIO_TEMPLATE.md` (✅ criado)
- [ ] Biblioteca de prompts `prompts/` (v1, v2, v3, juiz)
- [ ] Slides do pitch (5 blocos: problema 1′, solução 1,5′, demo 2,5′, resultados 1′, riscos 1′)
- [ ] Vídeo curto da demo (plano B)
- [ ] Declaração de uso de IA (inclui o uso do Claude Code neste planejamento, código e textos)
- [ ] Teste de instalação do zero seguindo só o README
- [ ] Conferir que nenhuma chave está no código nem no histórico do git (`git log -p | grep -i gsk_`)

---

## 4. Ordem de ataque (prazo < 1 dia)

Prioridade pela nota (R2 25% + R3 20% + R4 15%) e por dependência:

1. **Refatorar em módulos + metadados de ID nos chunks** (destrava tudo abaixo) — ~1h
2. **Prompts v1/v2/v3 + schema + seletor na UI** — ~2h
3. **Docs extra (envenenado + legado)** — ~20 min
4. **Guardrails (entrada, PII, canário, saída)** — ~1h
5. **`run_eval.py` + rodar v1, v2, v3** — ~1,5h (limite da Groq: usar cache e pausa)
6. **Experimento hit@k** (não usa LLM, é rápido) — ~30 min
7. **`judge.py` + validação manual** — ~1h
8. **Relatório + placar** — ~2h
9. **Slides, vídeo, ensaio** — ~1,5h

Se faltar tempo, cortar nesta ordem: comparação de modelos → TF-IDF vs. embeddings → juiz (manter métricas automáticas).

---

## 5. Registro de progresso

| Data | O que foi feito | Por quem |
|---|---|---|
| ≤ 18/11 | App Streamlit com login, histórico SQLite, RAG TF-IDF sobre PDF fictício (27 INCs) | Grupo |
| 24/11 | Diagnóstico do projeto vs. guia; criados `ANDAMENTO.md`, `relatorio/RELATORIO_TEMPLATE.md`, `eval/PLANO_DE_TESTES.md`, `eval/casos_de_teste.jsonl` | Claude Code (declarar no relatório) |

## 6. Grupo e papéis

| Frente | Responsável |
|---|---|
| Base e RAG | _preencher_ |
| Interface e demo | _preencher_ |
| Prompts | _preencher_ |
| Segurança | _preencher_ |
| Avaliação e relatório | _preencher_ |
