"""Experimento de recuperação (R3): hit@k separado da geração.

% dos casos com fonte esperada em que algum documento aceito aparece entre os k trechos recuperados,
para k = 2, 4 e 6, com a consulta original e (opcional) com a consulta reescrita pela triagem da v3.

    python eval/recuperacao.py                 # só consulta original (não usa a API)
    python eval/recuperacao.py --com-reescrita  # + consulta reescrita (1 chamada de triagem por caso, com cache)
"""
import argparse
import time

import comum  # noqa: F401
from comum import EVAL_DIR, cache_get, cache_put, carregar_casos, chave_cache
from core import config, rag
from core.chain import consulta_expandida, triagem
from core.guardrails import mascarar_pii

KS = [2, 4, 6]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--com-reescrita", action="store_true")
    ap.add_argument("--modelo", default=config.MODELO_PRINCIPAL)
    ap.add_argument("--pausa", type=float, default=2.0)
    args = ap.parse_args()

    kb = rag.BaseConhecimento.carregar(incluir_extra=True)
    casos = [c for c in carregar_casos() if c["esperado"].get("fontes_aceitas")]
    consultas = {"original": {c["id"]: mascarar_pii(c["entrada"])[0] for c in casos}}
    if args.com_reescrita:
        consultas["reescrita"] = {}
        for c in casos:
            q = consultas["original"][c["id"]]
            chave = chave_cache("triagem", args.modelo, q)
            tri = cache_get(chave)
            if tri is None:
                tri, _ = triagem(q, args.modelo, config.TEMPERATURA_EVAL)
                cache_put(chave, tri)
                time.sleep(args.pausa)
            consultas["reescrita"][c["id"]] = consulta_expandida(q, tri)

    tabela, erros = {}, []
    for nome, qs in consultas.items():
        tabela[nome] = {}
        for k in KS:
            acertos = 0
            for c in casos:
                ids = [h["id"] for h in kb.buscar(qs[c["id"]], k=k)]
                if set(ids) & set(c["esperado"]["fontes_aceitas"]):
                    acertos += 1
                elif k == config.TOP_K:
                    erros.append(f"- `{c['id']}` ({nome}, k={k}): esperado {c['esperado']['fontes_aceitas']}, recuperados {ids}")
            tabela[nome][k] = round(100 * acertos / len(casos), 1)

    md = ["# Experimento de recuperação (hit@k)", "",
          f"{len(casos)} casos com fonte esperada · índice TF-IDF (char 3–5) com {len(kb.chunks)} trechos de {len(kb.ids)} documentos.", "",
          "| Consulta | " + " | ".join(f"k = {k}" for k in KS) + " |", "|---|" + "---|" * len(KS)]
    for nome, linha in tabela.items():
        md.append(f"| {nome} | " + " | ".join(f"{linha[k]}%" for k in KS) + " |")
    md += ["", f"## Falhas em k = {config.TOP_K}", ""] + (erros or ["- nenhuma"])
    (EVAL_DIR / "recuperacao.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
