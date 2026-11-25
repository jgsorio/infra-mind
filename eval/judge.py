"""LLM-as-judge: dá notas de fidelidade e utilidade (1–5) às saídas dos casos cobertos.

    python eval/judge.py                 # julga todas as rodadas em eval/saidas/
    python eval/judge.py --rodadas v1 v3_g
    python eval/judge.py --amostra 5     # sorteia 5 casos para validação humana (eval/validacao_juiz.md)

Usa um modelo diferente do gerador (INFRAMIND_MODELO_JUIZ), temperatura 0 e cache em disco.
"""
import argparse
import random
import time

import comum  # noqa: F401
from comum import SAIDAS, cache_get, cache_put, chave_cache, escrever_jsonl, ler_jsonl, rodadas_disponiveis
from core import config, llm, prompts

JUIZ_DIR = SAIDAS / "juiz"


def deve_julgar(reg: dict) -> bool:
    return reg.get("esperado", {}).get("cobertura") == "coberto" and not reg.get("erro")


def julgar(reg: dict, modelo: str) -> dict:
    p = prompts.carregar("juiz")
    user = prompts.preencher(p["user"], pergunta=reg.get("pergunta_mascarada", reg["entrada"]),
                             documentos=reg.get("documentos", ""), resposta=reg.get("texto", ""))
    texto, lat = llm.chat([{"role": "system", "content": p["system"]}, {"role": "user", "content": user}],
                          modelo, config.TEMPERATURA_EVAL, json_mode=True)
    nota = llm.extrair_json(texto) or {}
    return {"id": reg["id"], "fidelidade": nota.get("fidelidade"), "utilidade": nota.get("utilidade"),
            "justificativa": nota.get("justificativa", texto[:300]), "modelo_juiz": modelo, "latencia_s": lat}


def amostra(n: int, rodadas: list[str]) -> None:
    pool = []
    for nome in rodadas:
        notas = {j["id"]: j for j in ler_jsonl(JUIZ_DIR / f"{nome}.jsonl")}
        pool += [(nome, r, notas.get(r["id"])) for r in ler_jsonl(SAIDAS / f"{nome}.jsonl") if deve_julgar(r)]
    random.seed(42)
    linhas = ["# Validação humana do juiz", "",
              "Duas pessoas dão nota (1–5) sem olhar a nota do juiz; depois comparem. Concordância = diferença ≤ 1.", "",
              "| Rodada | Caso | Pergunta | Fid. juiz | Útil. juiz | Fid. humano | Útil. humano | Concorda? |",
              "|---|---|---|---|---|---|---|---|"]
    for nome, r, j in random.sample(pool, min(n, len(pool))):
        j = j or {}
        linhas.append(f"| {nome} | {r['id']} | {r['entrada'][:60]} | {j.get('fidelidade', '')} | {j.get('utilidade', '')} |  |  |  |")
    linhas += ["", "Respostas completas: ver `eval/saidas/<rodada>.jsonl` (campo `texto`) e os trechos (campo `documentos`)."]
    destino = SAIDAS.parent / "validacao_juiz.md"
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"Amostra salva em {destino}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rodadas", nargs="+", default=None)
    ap.add_argument("--modelo", default=config.MODELO_JUIZ)
    ap.add_argument("--pausa", type=float, default=2.0)
    ap.add_argument("--amostra", type=int, default=0)
    args = ap.parse_args()
    rodadas = args.rodadas or [n for n in rodadas_disponiveis()]
    if args.amostra:
        return amostra(args.amostra, rodadas)

    for nome in rodadas:
        regs = [r for r in ler_jsonl(SAIDAS / f"{nome}.jsonl") if deve_julgar(r)]
        print(f"\n== juiz: {nome} ({len(regs)} casos) ==")
        notas = []
        for reg in regs:
            chave = chave_cache("juiz", args.modelo, reg["id"], reg.get("texto", ""), reg.get("documentos", ""))
            nota = cache_get(chave)
            if nota is None:
                try:
                    nota = julgar(reg, args.modelo)
                    cache_put(chave, nota)
                except Exception as e:
                    nota = {"id": reg["id"], "erro": f"{type(e).__name__}: {e}"}
                time.sleep(args.pausa)
            notas.append(nota)
            print(f"  {reg['id']:4} fid={nota.get('fidelidade')} util={nota.get('utilidade')} {nota.get('erro', '')}")
        escrever_jsonl(JUIZ_DIR / f"{nome}.jsonl", notas)
    print("\nPronto. Atualize o placar com: python eval/placar.py")


if __name__ == "__main__":
    main()
