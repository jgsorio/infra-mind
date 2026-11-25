"""Roda os casos de teste em uma ou mais versões do prompt e salva as saídas em eval/saidas/.

Exemplos (na raiz do projeto):
    python eval/run_eval.py                          # v1, v2, v3 sem guardrails + v3 com guardrails
    python eval/run_eval.py --versoes v1 --ids t01 t15
    python eval/run_eval.py --versoes v3 --guardrails --modelo llama-3.1-8b-instant

Regras: temperatura 0, sem histórico, cache em disco (não repete chamada já feita) e pausa entre chamadas.
Depois rode `python eval/placar.py` para gerar eval/placar.md.
"""
import argparse
import hashlib
import time

import comum  # noqa: F401  (ajusta sys.path e o canário antes de importar core)
from comum import SAIDAS, cache_get, cache_put, carregar_casos, chave_cache, escrever_jsonl, ler_jsonl, nome_rodada
from core import config, rag
from core.chain import responder


def _hash_prompt(versao: str) -> str:
    return hashlib.sha256((config.PROMPTS_DIR / f"{versao}.md").read_bytes()).hexdigest()[:12]


def rodar(versao: str, guardrails: bool, modelo: str, casos: list[dict], kb, k: int, pausa: float) -> str:
    nome = nome_rodada(versao, guardrails, modelo, config.MODELO_PRINCIPAL)
    registros = []
    print(f"\n== {nome} ({len(casos)} casos) ==")
    for caso in casos:
        chave = chave_cache("gen", versao, guardrails, modelo, k, caso["entrada"], config.CANARIO,
                            _hash_prompt(versao), sorted(kb.ids))
        reg = cache_get(chave)
        origem = "cache"
        if reg is None:
            origem = "api"
            try:
                r = responder(caso["entrada"], versao, kb, modelo=modelo, k=k, guardrails_on=guardrails,
                              historico=None, temperatura=config.TEMPERATURA_EVAL)
                reg = {**r.to_dict(), "erro": None}
            except Exception as e:  # registra a falha e segue (ex.: limite da API)
                reg = {"versao": versao, "modelo": modelo, "guardrails": guardrails, "erro": f"{type(e).__name__}: {e}"}
            if not reg.get("erro"):
                cache_put(chave, reg)
            time.sleep(pausa)
        reg = {"id": caso["id"], "tipo": caso["tipo"], "par": caso.get("par"), "entrada": caso["entrada"],
               "esperado": caso["esperado"], **reg}
        registros.append(reg)
        status = reg.get("erro") or (reg.get("dados") or {}).get("cobertura") or "texto"
        print(f"  {caso['id']:4} [{origem:5}] {status} · recuperados={reg.get('ids_recuperados')}")
    # Mescla com a rodada anterior (rodar só alguns --ids não apaga os demais casos).
    path = SAIDAS / f"{nome}.jsonl"
    todos = {r["id"]: r for r in ler_jsonl(path)}
    todos.update({r["id"]: r for r in registros})
    ordem = [c["id"] for c in carregar_casos()]
    escrever_jsonl(path, [todos[i] for i in ordem if i in todos])
    return nome


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--versoes", nargs="+", default=None, help="v1 v2 v3 (padrão: v1 v2 v3 + v3 com guardrails)")
    ap.add_argument("--guardrails", action="store_true", help="liga os guardrails nas versões escolhidas")
    ap.add_argument("--modelo", default=config.MODELO_PRINCIPAL)
    ap.add_argument("--k", type=int, default=config.TOP_K)
    ap.add_argument("--ids", nargs="+", help="roda só estes casos (ex.: t01 t20)")
    ap.add_argument("--pausa", type=float, default=2.0, help="segundos entre chamadas novas à API")
    args = ap.parse_args()

    casos = carregar_casos(ids=args.ids)
    kb = rag.BaseConhecimento.carregar(incluir_extra=True)
    if args.versoes:
        plano = [(v, args.guardrails) for v in args.versoes]
    else:
        plano = [("v1", False), ("v2", False), ("v3", False), ("v3", True)]
    for versao, g in plano:
        rodar(versao, g, args.modelo, casos, kb, args.k, args.pausa)
    print("\nPronto. Gere o placar com: python eval/placar.py")


if __name__ == "__main__":
    main()
