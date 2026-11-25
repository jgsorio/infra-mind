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

| Guardrails | Camada independente do prompt (toggle) | Permite medir o efeito do prompt (v1–v3) e o dos guardrails (v3_g) separadamente |
| PII | Mascaramento sempre ligado | LGPD não é técnica de prompt: vale para qualquer versão |
| Prompts | `prompts/*.md` são a fonte única do texto executado | A biblioteca documentada é exatamente o que roda |

**Padrões configuráveis (`core/config.py` / `.env`):** modelo alternativo `llama-3.1-8b-instant` e juiz `llama-3.3-70b-versatile` (Groq). Conferir no console da Groq se continuam disponíveis e os limites da camada gratuita.

---

## 3. O que falta fazer (checklist)

Legenda: [x] feito · [~] código pronto, falta rodar/validar · [ ] pendente

### R2 — Prompts versionados
- [x] Refatoração em módulos: `core/rag.py`, `core/chain.py` (`responder(pergunta, versao)`), `core/guardrails.py`, `core/llm.py`, `core/prompts.py`, `core/config.py`
- [x] `prompts/v1.md` — prompt original do app (persona + trechos + texto livre) = linha de base
- [x] `prompts/v2.md` — few-shot (normal, fora da base, ataque) + JSON Schema + fonte obrigatória por passo
- [x] `prompts/v3.md` — cadeia triagem → resposta, delimitadores, campo `analise`, regras de "não sei", documento mais recente, documento adulterado, sigilo, viés
- [x] `core/schema.json` (severidade inclui `critica`, porque a base tem nível Crítica; campo `aviso` para contradições)
- [x] Seletor de versão, toggle de guardrails e seletor de modelo na barra lateral; JSON renderizado em Markdown; painéis de trechos, triagem e guardrails
- [ ] Preencher nas fichas: placar, 2 exemplos antes/depois, o que ainda falha (depende das rodadas)

### R3 — RAG
- [x] Índice lê `docs/extra/*.md` além do PDF; capa e índice fora da busca; ruído de cabeçalho/rodapé removido
- [x] `docs/extra/INC-028-cache-hit-rate.md` — documento envenenado
- [x] `docs/extra/KB-0042-disco-cheio-legado.md` — procedimento de 2024 que contradiz a INC-001
- [x] Metadados por chunk: id, título, categoria, severidade, atualizado_em, origem, página
- [~] Experimento hit@k: `python eval/recuperacao.py [--com-reescrita]` → `eval/recuperacao.md`
- [ ] (Opcional) comparar TF-IDF vs. embeddings multilíngues no mesmo hit@k

### R4 — Avaliação
- [x] `eval/casos_de_teste.jsonl` — 27 casos (ver `eval/PLANO_DE_TESTES.md`)
- [x] `eval/PLANO_DE_TESTES.md` — métricas, metas, resultados esperados por versão, rubrica do juiz
- [~] `eval/run_eval.py` — v1, v2, v3 (sem guardrails) + v3_g; temperatura 0, sem histórico, cache, pausa, canário fixo
- [~] `eval/judge.py` + `prompts/juiz.md` — fidelidade/utilidade 1–5 com modelo diferente; `--amostra 5` gera `eval/validacao_juiz.md`
- [ ] Conferir 5 notas do juiz à mão e registrar concordância
- [~] `eval/placar.py` → `eval/placar.md` + `placar.json` + `placar.png` + análise de erros automática (revisar à mão)
- [ ] Rodar no modelo alternativo: `python eval/run_eval.py --versoes v3 --guardrails --modelo llama-3.1-8b-instant`

### R5 — Segurança
- [x] Guardrail de entrada (regex PT/EN: ignorar regras, extrair prompt, repetir texto acima, troca de persona, ocultar rastros) → `recusado` sem chamar o modelo
- [x] Mascaramento de e-mail, CPF e telefone antes do LLM e antes do SQLite (sempre ligado)
- [x] Canário no system prompt (todas as versões, como instrumento de medição) + bloqueio na saída
- [x] Guardrail de saída: JSON Schema; fontes ⊂ recuperadas; remove ações destrutivas (DROP DATABASE, FLUSHALL, rm -rf /, shred…)
- [~] Par de viés t23 × t24 medido no placar (fontes, severidade, similaridade dos passos)
- [x] Riscos residuais registrados no README (regex contornável, SQLite, login fixo, API de terceiros)

### Entregáveis
- [~] Protótipo executável + README completo (feito; falta validar instalação do zero)
- [ ] Relatório técnico ≤ 8 páginas → template em `relatorio/RELATORIO_TEMPLATE.md`
- [x] Biblioteca de prompts `prompts/` (v1, v2, v3, juiz) — é a fonte única do texto executado
- [ ] Slides do pitch (5 blocos: problema 1′, solução 1,5′, demo 2,5′, resultados 1′, riscos 1′)
- [ ] Vídeo curto da demo (plano B)
- [ ] Declaração de uso de IA (inclui o uso do Claude Code no planejamento, código e textos)
- [ ] Teste de instalação do zero seguindo só o README
- [x] Nenhuma chave no código nem no histórico do git (verificado em 24/11)

### Próximos comandos (nesta ordem)
1. `pip install -r requirements.txt` e `pytest -q` (sem API)
2. `python eval/recuperacao.py` (sem API) e `python eval/recuperacao.py --com-reescrita`
3. `python eval/run_eval.py` → `python eval/judge.py` → `python eval/placar.py`
4. Ler `eval/placar.md`, preencher as fichas `prompts/v*.md` e o relatório
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
| 24/11 | Implementação: módulos `core/`, prompts v1/v2/v3/juiz, schema, guardrails (PII, ataques, canário, saída), docs de teste (INC-028 envenenado, KB-0042 legado), UI com seletor de versão, `run_eval.py`, `judge.py`, `placar.py`, `recuperacao.py`, testes `pytest`, README. Ainda não executado (Python ausente na máquina) | Claude Code (declarar no relatório) |

## 6. Grupo e papéis

| Frente | Responsável |
|---|---|
| Base e RAG | _preencher_ |
| Interface e demo | _preencher_ |
| Prompts | _preencher_ |
| Segurança | _preencher_ |
| Avaliação e relatório | _preencher_ |
