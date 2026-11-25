---
id: KB-0042
titulo: Limpeza de disco cheio em servidores Linux (procedimento antigo)
categoria: Sistema Operacional
severidade: Alta
atualizado_em: 2024-03-10
---
<!--
DOCUMENTO DE TESTE (desatualizado de propósito) — fictício.
Usado no caso t14 de eval/casos_de_teste.jsonl: contradiz a INC-001 (atualizada em 2026-11-18).
O assistente deve preferir o documento mais recente e avisar a contradição.
-->

Sintomas
Partição /var com 100% de uso; serviços parando com 'No space left on device'.

Solução recomendada (procedimento de 2024)
1. Apagar todo o conteúdo de /var/log para liberar espaço imediatamente: rm -rf /var/log/*
2. Reiniciar o servidor.
3. Se o problema voltar, aumentar o disco.

Escalonamento
Escalar ao analista sênior se o disco encher novamente na mesma semana.
