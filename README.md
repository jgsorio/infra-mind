# 🧠 InfraMind

**Your AI Copilot for Infrastructure Troubleshooting.**

O InfraMind é um assistente inteligente desenvolvido para apoiar profissionais de infraestrutura e equipes de plantão na investigação e resolução de problemas técnicos relacionados a servidores, sistemas operacionais, serviços e ambientes corporativos.

A aplicação utiliza Inteligência Artificial e a abordagem **RAG (Retrieval-Augmented Generation)** para consultar documentos técnicos em PDF e fornecer respostas contextualizadas com base no conhecimento disponibilizado.

A ideia é centralizar informações técnicas e facilitar o acesso a procedimentos, instruções e soluções, reduzindo o tempo necessário para investigar incidentes e realizar troubleshooting.

## 🎯 Objetivo

Disponibilizar um chat inteligente capaz de interpretar documentações técnicas e auxiliar profissionais durante atendimentos e situações de plantão.

Com o InfraMind, o profissional poderá:

- Consultar procedimentos técnicos documentados.
- Investigar problemas relacionados a sistemas operacionais e infraestrutura.
- Obter orientações para troubleshooting.
- Consultar comandos e instruções presentes na documentação.
- Encontrar soluções para problemas recorrentes.
- Reduzir o tempo de busca por informações técnicas.

## ⚙️ Tecnologias

| Tecnologia                   | Finalidade                                    |
| ---------------------------- | --------------------------------------------- |
| Python                       | Linguagem principal                           |
| Streamlit                    | Interface web, login e chat                   |
| Groq (`openai/gpt-oss-120b`) | Inferência do modelo LLM                      |
| pypdf                        | Extração de texto do PDF                      |
| scikit-learn (TF-IDF)        | Indexação e busca de trechos relevantes (RAG) |
| SQLite                       | Histórico de conversas                        |
| ReportLab                    | Geração do PDF da base de conhecimento        |

## 🧠 Como funciona?

O InfraMind usa **RAG (Retrieval-Augmented Generation)**: o modelo responde com base na documentação, e não apenas no que aprendeu no treinamento.

1. Ao iniciar, a aplicação lê o PDF fixo `docs/base_conhecimento_infra.pdf` e o divide em trechos (_chunks_), um por incidente. Trechos longos são subdivididos, e cada um mantém o ID e o título do caso.
2. Os trechos são indexados com TF-IDF (n-gramas de caracteres), o que tolera variações de escrita e acentuação.
3. A cada pergunta, os 4 trechos mais similares são recuperados e enviados como contexto à Groq, junto com as últimas mensagens da conversa.
4. O modelo responde em português, citando o ID do caso (ex.: `INC-001`), com causa provável, comandos de diagnóstico e solução. A resposta é exibida em streaming, com um expander "Trechos utilizados".
5. Se a documentação não cobrir o problema, o assistente informa isso em vez de inventar uma resposta.

> A base de conhecimento é fixa: **não há upload de documentos** pela interface. Para alterá-la, edite [casos.py](casos.py) e gere o PDF novamente.

## 📚 Base de conhecimento

O arquivo `docs/base_conhecimento_infra.pdf` é um documento **fictício** com 27 incidentes (INC-001 a INC-027) sobre:

- Sistemas operacionais Linux e Windows (disco, CPU, memória, serviços, BSOD, SMB);
- Redes (DNS, DHCP, VPN IPsec, perda de pacotes, NTP);
- Bancos de dados (MySQL, PostgreSQL, Redis);
- Containers e Kubernetes, Cloud, Backup, RAID, e-mail e Segurança (certificado expirado, ransomware).

Cada caso traz: severidade, impacto, sintomas, causa provável, comandos de diagnóstico, solução, validação, prevenção e escalonamento. O documento inclui ainda política de severidade, cheat sheet de comandos, checklist pós-incidente e glossário.

Para regenerar o PDF após editar [casos.py](casos.py):

```bash
python generate_pdf.py
```

## 🚀 Como utilizar

### Pré-requisitos

- Python 3.10 ou superior.
- Conta na [Groq](https://console.groq.com/) e uma API Key.

### Instalação

```bash
git clone <REPOSITORY_URL>
cd InfraMind
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configuração

Crie o arquivo `.streamlit/secrets.toml` (já ignorado pelo Git):

```toml
GROQ_API_KEY = "sua_api_key"
```

### Executando

```bash
streamlit run app.py
```

## 💬 Fluxo de utilização

1. Acesse a aplicação e faça login com usuário `admin` e senha `admin`.
2. Descreva o problema no chat (ex.: _"servidor Linux sem espaço em disco"_).
3. Receba a resposta com base na documentação e consulte os trechos utilizados.
4. Use a barra lateral para:
   - **➕ Nova conversa**: iniciar um novo atendimento;
   - **Conversas recentes**: reabrir e continuar uma conversa anterior;
   - **🗑 / Excluir todas**: apagar uma conversa ou todo o histórico.

O histórico é salvo por usuário em `data/inframind.db` (SQLite, criado automaticamente) e permanece após sair ou reiniciar a aplicação.

## 🗂️ Estrutura do projeto

```
InfraMind/
├── app.py                  # Interface Streamlit: login, chat, histórico e RAG
├── storage.py              # Persistência das conversas (SQLite)
├── casos.py                # Dados dos incidentes (fonte do PDF)
├── generate_pdf.py         # Gerador do PDF da base de conhecimento
├── docs/
│   └── base_conhecimento_infra.pdf
├── data/                   # Banco SQLite (gerado em execução)
├── .streamlit/secrets.toml # Chave da Groq (não versionado)
└── requirements.txt
```

## 🔒 Considerações

O login `admin`/`admin` é fixo e destinado a ambiente de estudo/demonstração;

O InfraMind é uma ferramenta de apoio à tomada de decisão técnica.

As respostas são geradas com base nos documentos disponibilizados e devem ser validadas pelo profissional responsável antes da execução de comandos ou alterações em ambientes corporativos.

Documentos confidenciais devem ser tratados conforme as políticas de segurança da empresa, considerando que o conteúdo recuperado poderá ser enviado à API da Groq para processamento.

**InfraMind — Less searching, smarter troubleshooting.**
