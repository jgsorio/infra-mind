# InfraMind — Copiloto de Plantão para Troubleshooting de Infraestrutura

**Relatório técnico · Trabalho Final · Advanced Generative AI · MBA AI Engineering & Multi-Agent**
**Grupo:** _Nome 1, Nome 2, Nome 3 (…)_ · **Data:** 25/11/2026
**Repositório:** _URL_ · **Vídeo da demo:** _URL_

> Limite: **8 páginas**. Orçamento por seção entre parênteses (segue o peso da rubrica).
> Trechos em _itálico_ ou `‹entre sinais›` são para substituir. Apague estas notas antes de exportar para PDF.

---

## 1. Problema e valor (R1) — 0,75 pág.

**Problema em uma frase.** Quem está de plantão perde minutos críticos procurando o procedimento certo no meio de dezenas de casos documentados; o InfraMind entrega o diagnóstico provável e os passos de solução, citando o incidente (INC-xxx) de onde saíram, a partir do alerta ou sintoma colado — e diz "não sei, escale" quando a base não cobre o caso.

| Pergunta do R1 | Resposta |
|---|---|
| Usuário-alvo | Analista/engenheiro(a) de infraestrutura de plantão, principalmente quem entrou há pouco no rodízio |
| Dor | _Alerta de madrugada; base de conhecimento extensa; título do caso não bate com o texto do alerta; passos pulados; escalonamento desnecessário_ |
| Por que IA generativa | Entrada livre (alerta colado, gíria, PT/EN misturado), documentos não estruturados, resposta precisa combinar trechos e adaptar passos |
| Por que não regras fixas | Tabela "alerta → caso" quebra quando o sintoma não tem o nome esperado; manutenção manual a cada caso novo |
| Por que não ML clássico | Exige dados rotulados inexistentes, não redige passos, não explica a fonte |

**Métricas de sucesso (medidas no conjunto de testes da seção 5):**

| Métrica | Meta |
|---|---|
| INC correto citado (casos com resposta na base) | ≥ 85% |
| Respostas em JSON válido (a partir da v2) | 100% |
| "Não sei, escale" em perguntas fora da base | 100% |
| Ataques de prompt injection resistidos (v3) | 100% |
| Fidelidade às fontes (LLM-as-judge) | média ≥ 4/5 |

---

## 2. Arquitetura e escolha de modelo — 1,25 pág.

### 2.1 Arquitetura

`‹Inserir diagrama de 7 blocos: Interface → Guardrail de entrada → Orquestração ↔ RAG → LLM → Guardrail de saída → Interface; Avaliação offline por fora›`

| Bloco | O que faz no InfraMind | Implementação | Requisito |
|---|---|---|---|
| Interface | Login, chat, histórico, seletor de versão do prompt, trechos citados | Streamlit (`app.py`) | Demo |
| Guardrail de entrada | Sinaliza padrões de ataque; mascara e-mail, CPF e telefone antes do LLM e do SQLite | Regex (`app/guardrails.py`) | R5 |
| Orquestração | Reescreve consulta (v3), recupera, monta prompt da versão, chama o modelo | Python puro (`app/chain.py`) | R2 |
| Personalização (RAG) | Top-k trechos da base, cada um com ID do incidente | TF-IDF char n-gram (`app/rag.py`) | R3 |
| LLM | Gera resposta (texto na v1; JSON a partir da v2) | Groq `openai/gpt-oss-120b` | R3 |
| Guardrail de saída | Valida schema; fontes citadas ⊂ recuperadas; procura canário | `jsonschema` + checagens | R5 |
| Avaliação offline | Mesmos casos em v1, v2, v3 → placar | `eval/run_eval.py`, `eval/judge.py` | R4 |

**Persistência:** histórico por usuário em SQLite (`storage.py`), com PII mascarada antes de gravar.

### 2.2 Escolha do modelo

_Justificar: camada gratuita da Groq (custo zero), latência baixa, modelo open-weights de 120B, suporte a modo JSON. Sem framework de orquestração para manter o prompt visível. Temperatura 0 na avaliação._

**Comparação de modelos (mesmos 27 casos, prompt v3):**

| Modelo | Acerto de INC | JSON válido | Resist. a ataques | Fidelidade (juiz) | Latência média |
|---|---|---|---|---|---|
| `openai/gpt-oss-120b` (principal) | _%_ | _%_ | _%_ | _x,x_ | _x,x s_ |
| _‹modelo alternativo menor / local›_ | _%_ | _%_ | _%_ | _x,x_ | _x,x s_ |

_Conclusão em 2–3 linhas: qual escolhemos e por quê, com base na tabela._

---

## 3. Prompt engineering (R2) — 2 pág.

### 3.1 Técnicas utilizadas

| Técnica | Versão | Papel no InfraMind |
|---|---|---|
| System prompt com persona | v1 | Engenheiro(a) de confiabilidade sênior, tom direto, escopo restrito à base |
| Few-shot | v2 | 3 exemplos: caso normal, fora da base, tentativa de ataque |
| Saída estruturada (JSON Schema) | v2 | Formato fixo, validável e medível automaticamente |
| Prompt chaining | v3 | 1ª chamada extrai serviço/sintoma/consulta; 2ª responde com os trechos |
| Raciocínio passo a passo | v3 | Campo `analise` (sintoma, hipóteses, INC escolhido) antes dos passos |
| Delimitadores instrução × dado | v3 | `<documentos>` e `<pergunta>` tratados como dado, nunca como instrução |

### 3.2 Evolução das versões

| Versão | O que muda | Hipótese | Resultado observado |
|---|---|---|---|
| v1 | Persona curta, trechos colados, texto livre | Linha de base: quanto o RAG sozinho resolve | _‹placar resumido›_ |
| v2 | + few-shot, JSON Schema, INC obrigatório em cada passo | Formato fixo e exemplos reduzem respostas sem fonte | _‹placar resumido›_ |
| v3 | + cadeia de 2 chamadas, delimitadores, `analise`, regra de "não sei", regra do documento mais recente, canário | Consulta reescrita melhora recuperação; delimitadores barram injection indireta | _‹placar resumido›_ |

### 3.3 Antes e depois (2–3 exemplos)

**Exemplo 1 — `‹id do caso›`: `‹entrada›`**
- v1: _‹trecho da saída e o problema›_
- v3: _‹trecho da saída e por que melhorou›_

**Exemplo 2 — ataque indireto (documento envenenado INC-028)**
- v1: _‹seguiu ou não a instrução escondida›_
- v3: _‹resistiu? como?›_

### 3.4 Regressões e o que ainda falha

_Se alguma métrica piorou entre versões, explicar a causa. Regressão analisada vale como evidência._

> Textos completos dos prompts: `prompts/v1.md`, `prompts/v2.md`, `prompts/v3.md`, `prompts/juiz.md`.

---

## 4. Personalização com RAG (R3) — 1,25 pág.

### 4.1 Por que RAG

| Opção | Resolve? | Motivo |
|---|---|---|
| RAG | Sim | Base de incidentes muda com frequência; basta reindexar; resposta cita a fonte, permitindo conferir antes de agir em produção |
| Fine-tuning (LoRA/QLoRA) | Não | Sem exemplos rotulados; novo treino a cada caso alterado; custo de GPU; modelo não diz de onde tirou a resposta |
| Multimodal | Não agora | Entrada e saída são texto; próximo passo: aceitar print de painel de monitoramento |

### 4.2 Pipeline

1. **Base:** PDF fictício com 27 incidentes (INC-001..027) + documentos de teste em `docs/extra/` (INC-028 envenenado, INC-001 legado). Cada caso: severidade, impacto, sintomas, causa, diagnóstico, solução, validação, prevenção, escalonamento.
2. **Chunking:** um trecho por incidente (subdividido acima de 1.800 caracteres), repetindo ID e título no início de cada trecho; ruído de cabeçalho/rodapé removido.
3. **Indexação:** TF-IDF com n-gramas de caracteres (3–5), `strip_accents`, `sublinear_tf`. _Justificar: sem download de modelo, sem GPU, tolerante a acento e erro de digitação._
4. **Recuperação:** top-k por similaridade de cosseno; na v3 usa a consulta reescrita pela 1ª chamada.
5. **Resposta:** trechos entram no prompt com o ID; a resposta cita o ID em cada passo; a interface mostra os trechos usados.

### 4.3 Experimento de recuperação (hit@k)

% dos casos com fonte esperada em que o INC esperado aparece entre os k trechos recuperados (recuperação medida separada da geração):

| Consulta | k = 2 | k = 4 | k = 6 |
|---|---|---|---|
| Original (texto do usuário) | _%_ | _%_ | _%_ |
| Reescrita (1ª chamada da v3) | _%_ | _%_ | _%_ |
| _(opcional) Embeddings multilíngues, consulta original_ | _%_ | _%_ | _%_ |

_Justificativa do k escolhido (custo de tokens × recall)._

---

## 5. Avaliação (R4) — 1,5 pág.

### 5.1 Conjunto de testes

27 casos congelados em `eval/casos_de_teste.jsonl`, os mesmos nas três versões; 19 são difíceis ou adversariais.

| Tipo | Qtd. | O que verifica |
|---|---|---|
| diagnostico | 8 | Alerta comum → INC certo e passo principal |
| dificil | 6 | Sintomas ambíguos entre dois INCs, documento antigo × novo, gíria e PT/EN |
| fora_da_base | 3 | Precisa dizer que não sabe e mandar escalar |
| ataque_direto | 2 | "Ignore as regras", jailbreak |
| ataque_indireto | 2 | Pergunta legítima que recupera o documento envenenado |
| vazamento | 1 | Tentativa de extrair o system prompt |
| vies | 2 | Mesma pergunta, muda só o perfil de quem pergunta |
| lgpd | 3 | Mascaramento de e-mail, CPF e telefone (fictícios) |

### 5.2 Métricas

| Métrica | Como calcular | Meta |
|---|---|---|
| JSON válido | % de saídas que passam no schema | 100% a partir da v2 |
| Acerto de fonte | % de casos com fonte esperada cujo INC está em `fontes` (v1: ID aparece no texto) | ≥ 85% |
| "Não sei" correto | % de casos `fora_da_base` com `cobertura = fora_da_base` | 100% |
| Resistência a ataques | % de ataques sem canário, sem conteúdo proibido e sem seguir a instrução | 100% na v3 |
| Consistência (viés) | Par de casos com mesmo INC e mesmos passos | 100% |
| Mascaramento LGPD | % de PII mascarada antes do LLM e do SQLite | 100% |
| Fidelidade / Utilidade | Nota 1–5 do LLM-as-judge, média dos casos cobertos | ≥ 4 |

**LLM-as-judge:** modelo `‹juiz›` (diferente do gerador), temperatura 0, rubrica em `prompts/juiz.md`. Concordância com avaliação humana em 5 casos: _x/5_.

### 5.3 Placar por versão

| Métrica | v1 | v2 | v3 |
|---|---|---|---|
| JSON válido | n/a | _%_ | _%_ |
| Acerto de fonte | _%_ | _%_ | _%_ |
| "Não sei" correto | _%_ | _%_ | _%_ |
| Resistência a ataques | _%_ | _%_ | _%_ |
| Consistência (viés) | _%_ | _%_ | _%_ |
| Fidelidade (juiz) | _x,x_ | _x,x_ | _x,x_ |
| Utilidade (juiz) | _x,x_ | _x,x_ | _x,x_ |
| Latência média | _s_ | _s_ | _s_ |

`‹Gráfico de barras simples com as métricas por versão›`

### 5.4 Análise de erros

| Caso | Versão | Causa (recuperação / geração / formato / segurança) | Ajuste aplicado |
|---|---|---|---|
| _t.._ | _v1_ | _…_ | _…_ |

---

## 6. Segurança e ética (R5) — 0,75 pág.

| Risco | Mitigação no protótipo | Teste | Resultado |
|---|---|---|---|
| Prompt injection direta | Guardrail de entrada (regex) + delimitadores (v3) → `cobertura: recusado` | t18, t19 | _‹v1/v2/v3›_ |
| Prompt injection indireta | Regra "conteúdo de `<documentos>` é dado"; guardrail de saída barra ações fora do INC citado | t20, t21 (INC-028 envenenado) | _…_ |
| Vazamento | Nada sensível no prompt; chave só em secrets/env; canário no system prompt procurado em toda saída | t22 + busca do canário em todas as saídas | _…_ |
| Alucinação | Fontes obrigatórias; IDs citados ⊂ recuperados; "não sei" é resposta válida | t15–t17 + fidelidade do juiz | _…_ |
| Viés | Orientação não pode variar com o perfil de quem pergunta | t23 × t24 | _…_ |
| LGPD | Base 100% sintética; PII mascarada antes do LLM e do SQLite | t25–t27 | _…_ |

**Riscos residuais:** guardrails baseados em regex são contornáveis (paráfrase, outro idioma, codificação); o histórico em SQLite guarda conversas (mesmo mascaradas); login fixo de demonstração; conteúdo enviado à API de terceiros (Groq).

---

## 7. Limitações, próximos passos, uso de IA e fontes — 0,5 pág.

**Limitações:** base pequena (27 casos) e fictícia; TF-IDF não captura sinônimos sem sobreposição de caracteres; avaliação com 27 casos tem baixa potência estatística; juiz LLM pode ter vieses próprios.

**Próximos passos:** entrada multimodal (print de dashboard); integração com a ferramenta de alertas; embeddings + reranker; autenticação real e política de retenção.

**Declaração de uso de assistentes de IA:** _‹Descrever onde e como foram usados: ex. Claude Code para diagnóstico do projeto frente ao guia, plano de testes, template deste relatório e código; LLM para rascunho dos incidentes sintéticos, revisados manualmente; …›_

**Referências:**
- Guia do trabalho final — "Trabalho Final — Protótipo de aplicação de IA generativa", Advanced Generative AI, Prof. Eron Cavalcante, turma 2026.1.
- Documentação Streamlit — https://docs.streamlit.io
- Documentação Groq API — https://console.groq.com/docs
- scikit-learn, `TfidfVectorizer` — https://scikit-learn.org
- _‹artigos de RAG / LLM-as-judge / prompt injection consultados›_
