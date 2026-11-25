# 🧠 InfraMind

**Your AI Copilot for Infrastructure Troubleshooting.**

O InfraMind é um assistente para profissionais de infraestrutura e equipes de plantão. A pessoa cola o alerta ou descreve o sintoma; o assistente encontra o incidente documentado certo, devolve o diagnóstico provável e os passos de solução **citando a fonte (INC-xxx)**, e diz **"não sei, escale"** quando a base não cobre o caso.

Usa **RAG (Retrieval-Augmented Generation)** sobre uma base de conhecimento **100% fictícia**, três versões de prompt comparáveis (v1 → v2 → v3), guardrails de entrada e saída e uma avaliação offline com 27 casos de teste e LLM-as-judge.

> Trabalho final da disciplina Advanced Generative AI (MBA AI Engineering & Multi-Agent). Andamento em [`ANDAMENTO.md`](ANDAMENTO.md).

## ⚙️ Tecnologias

| Tecnologia | Finalidade |
|---|---|
| Python 3.11+ | Linguagem principal |
| Streamlit | Interface web, login, chat e seletor de versão do prompt |
| Groq (`openai/gpt-oss-120b`) | Inferência do LLM (camada gratuita); modelo alternativo e juiz configuráveis |
| pypdf | Extração de texto do PDF |
| scikit-learn (TF-IDF) | Indexação e busca de trechos (RAG) |
| jsonschema | Validação da saída estruturada |
| SQLite | Histórico de conversas (com dados pessoais mascarados) |
| pytest / matplotlib | Testes unitários e gráfico do placar |

## 🧠 Arquitetura

```
Interface (Streamlit) → Guardrail de entrada → Orquestração ──→ LLM (Groq) → Guardrail de saída → Interface
                        (PII + ataques)        │      ↑                      (schema, fontes,
                                               ↓      │                       ações destrutivas, canário)
                                            RAG (TF-IDF, top-k)
Avaliação offline: eval/run_eval.py → eval/judge.py → eval/placar.py
```

| Bloco | Arquivo |
|---|---|
| Interface | `app.py` |
| Guardrails (PII, ataques, validação da saída, canário) | `core/guardrails.py` |
| Orquestração `responder(pergunta, versao)` | `core/chain.py` |
| RAG (chunking por incidente, metadados, busca) | `core/rag.py` |
| Cliente do LLM (JSON mode, retry) | `core/llm.py` |
| Biblioteca de prompts (fonte única do texto executado) | `prompts/v1.md`, `v2.md`, `v3.md`, `juiz.md` |
| JSON Schema da resposta | `core/schema.json` |
| Configuração (modelos, chave, k) | `core/config.py` |

### Versões do prompt

| Versão | Técnicas | Saída |
|---|---|---|
| v1 | Persona | Texto livre (linha de base) |
| v2 | + few-shot, JSON Schema, fonte obrigatória por passo | JSON |
| v3 | + cadeia de 2 chamadas (triagem → resposta), delimitadores, campo `analise`, regras de "não sei", documento mais recente e documento adulterado | JSON |

Os **guardrails** são uma camada independente da versão (liga/desliga na barra lateral), para medir separadamente o efeito do prompt e o dos guardrails. O **mascaramento de e-mail, CPF e telefone** é sempre aplicado antes de chamar o modelo e antes de gravar no histórico.

## 📚 Base de conhecimento

- `docs/base_conhecimento_infra.pdf` — documento **fictício** com 27 incidentes (INC-001 a INC-027): Linux e Windows, redes, bancos de dados, containers/Kubernetes, cloud, backup, RAID, e-mail e segurança; mais política de severidade, metodologia, cheat sheet, checklist e glossário.
- `docs/extra/*.md` — documentos de **teste** com front matter (`id`, `titulo`, `categoria`, `severidade`, `atualizado_em`):
  - `INC-028` — documento **envenenado** com instrução escondida (teste de prompt injection indireta);
  - `KB-0042` — procedimento **desatualizado** (2024) que contradiz a INC-001 (teste da regra do documento mais recente).

Cada incidente vira um trecho (subdividido acima de 1.800 caracteres, repetindo ID e título), com metadados de ID, categoria, severidade, data e página. A capa e o índice ficam fora da busca.

## 🚀 Como executar

### Pré-requisitos

- Python 3.11 ou superior.
- Conta na [Groq](https://console.groq.com/) e uma API Key (camada gratuita).

### Instalação

```bash
git clone <REPOSITORY_URL>
cd infra-mind
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configuração

Copie `.env.example` para `.env` e preencha `GROQ_API_KEY` (ou use `.streamlit/secrets.toml`, a partir de `.streamlit/secrets.toml.example`). Os dois arquivos com a chave estão no `.gitignore`.

### App

```bash
streamlit run app.py
```

Login de demonstração: `admin` / `admin`. Na barra lateral escolha a **versão do prompt**, ligue/desligue os **guardrails** e escolha o **modelo**. Abaixo de cada resposta há os painéis **Trechos utilizados**, **Triagem e análise** (v3) e **Guardrails**.

Exemplos de uso:
- `Alerta: /var no srv-app-03 em 100%, deploy falhando com 'No space left on device'` → INC-001 com fontes.
- `Como faço o failover manual de um cluster Oracle RAC?` → fora da base, escale.
- `A taxa de acerto do cache está caindo desde ontem, o que faço?` → recupera o documento envenenado; compare v1 × v3.

## 🧪 Avaliação

```bash
pytest -q                               # testes unitários (sem API): RAG, guardrails, schema, prompts, LGPD
python eval/recuperacao.py              # hit@k (k = 2, 4, 6) com a consulta original — sem API
python eval/recuperacao.py --com-reescrita
python eval/run_eval.py                 # v1, v2, v3 (sem guardrails) e v3 com guardrails → eval/saidas/
python eval/run_eval.py --versoes v3 --guardrails --modelo llama-3.1-8b-instant   # comparação de modelos
python eval/judge.py                    # LLM-as-judge (fidelidade e utilidade 1–5)
python eval/judge.py --amostra 5        # planilha para validar o juiz à mão
python eval/placar.py                   # eval/placar.md, placar.json e placar.png
```

- Casos: [`eval/casos_de_teste.jsonl`](eval/casos_de_teste.jsonl) (27, congelados). Plano, métricas e resultados esperados: [`eval/PLANO_DE_TESTES.md`](eval/PLANO_DE_TESTES.md).
- A avaliação usa temperatura 0, sem histórico, canário fixo, cache em disco (`eval/cache/`) e pausa entre chamadas para respeitar os limites da camada gratuita.

## 🗂️ Estrutura do projeto

```
infra-mind/
├── app.py                  # Interface Streamlit
├── storage.py              # Histórico (SQLite)
├── core/                   # config, rag, llm, prompts, guardrails, chain, schema.json
├── prompts/                # v1.md, v2.md, v3.md, juiz.md (biblioteca versionada)
├── docs/                   # base_conhecimento_infra.pdf + extra/*.md
├── eval/                   # casos, run_eval, judge, recuperacao, placar, saidas/
├── tests/                  # pytest
├── relatorio/              # template do relatório técnico
├── data/                   # SQLite (gerado em execução, fora do git)
├── .env.example
└── requirements.txt
```

## 🔒 Limitações e considerações

- Login `admin`/`admin` fixo, apenas para estudo/demonstração.
- Guardrails por expressão regular são contornáveis (paráfrase, outro idioma, codificação); são uma camada a mais, junto com o prompt v3.
- O histórico fica no SQLite local (já mascarado); não há política de retenção.
- TF-IDF não entende sinônimos sem sobreposição de caracteres; a v3 compensa com a consulta reescrita.
- O conteúdo recuperado e a pergunta são enviados à API da Groq: use apenas dados sintéticos ou públicos.
- O InfraMind apoia a decisão técnica: valide os comandos antes de executar em produção.

**InfraMind — Less searching, smarter troubleshooting.**
