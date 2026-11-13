"""Avalia a triagem com os casos de teste e gera um relatório com as métricas.

Uso (na raiz do projeto):
    python -m avaliacao.avaliar --modo ia             # Gemini + RAG (precisa da GEMINI_API_KEY no .env)
    python -m avaliacao.avaliar --modo ia --sem-rag   # Gemini sem a base de conhecimento (experimento)
    python -m avaliacao.avaliar --modo regras         # modo reserva, sem IA

Métricas:
- Acerto da busca (RAG): % de casos em que o trecho da categoria correta veio entre os 2 primeiros.
- Acurácia de categoria, de urgência e combinada (as duas certas ao mesmo tempo).
- Acerto nos casos de falha (fora do escopo, texto sem sentido, tentativa de manipular a IA, dados pessoais).
- Tempo médio de resposta.
"""
import argparse
import csv
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

PASTA = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modo", choices=["ia", "regras"], default="ia")
    parser.add_argument("--sem-rag", action="store_true", help="desliga a base de conhecimento (só no modo ia)")
    parser.add_argument("--intervalo", type=float, default=4.0,
                        help="segundos entre chamadas à IA, para não estourar o limite do plano gratuito")
    parser.add_argument("--tentativas", type=int, default=3,
                        help="quantas vezes repetir um caso quando a IA não responde (ex.: limite por minuto)")
    parser.add_argument("--espera-erro", type=float, default=30.0,
                        help="segundos de espera antes de repetir um caso que falhou")
    args = parser.parse_args()

    if args.modo == "regras":
        os.environ["USAR_IA"] = "false"

    from app import config  # importado depois de ajustar o ambiente
    from app.schemas import TriagemRequest
    from app.triagem import recuperador, triar

    if args.modo == "ia" and not config.ia_habilitada():
        sys.exit("Modo 'ia' precisa da GEMINI_API_KEY no arquivo .env")

    usar_rag = not (args.modo == "ia" and args.sem_rag)
    nome = "ia_sem_rag" if not usar_rag else args.modo

    casos = list(csv.DictReader(open(PASTA / "casos_teste.csv", encoding="utf-8")))
    linhas, tempos = [], []
    acertos = defaultdict(int)
    por_tipo = defaultdict(lambda: [0, 0])
    por_categoria = defaultdict(lambda: [0, 0])
    busca = [0, 0]
    caiu_no_reserva = 0
    motivos = defaultdict(int)
    so_ia = [0, 0]  # acertos combinados considerando só as respostas que vieram da IA

    for caso in casos:
        esperada = caso["categoria_esperada"]

        # Avaliação da busca do RAG (não depende da IA)
        if esperada != "fora_do_escopo":
            top2 = [t.fonte for t, _ in recuperador().buscar(caso["descricao"], k=2, arquivo="01_")]
            busca[0] += any(f"Categoria {esperada} " in f for f in top2)
            busca[1] += 1

        for tentativa in range(1, args.tentativas + 1):
            inicio = time.perf_counter()
            r = triar(TriagemRequest(descricao=caso["descricao"]), usar_rag=usar_rag)
            duracao = time.perf_counter() - inicio
            if args.modo != "ia" or r.modo == "ia" or tentativa == args.tentativas:
                break
            print(f"#{caso['id']:>2} {r.aviso} Nova tentativa em {args.espera_erro:.0f} s...")
            time.sleep(args.espera_erro)
        tempos.append(duracao)
        if args.modo == "ia" and r.modo != "ia":
            caiu_no_reserva += 1
            motivos[r.aviso or "sem detalhe"] += 1

        ok_cat = r.categoria == esperada
        ok_urg = r.urgencia == caso["urgencia_esperada"]
        acertos["categoria"] += ok_cat
        acertos["urgencia"] += ok_urg
        acertos["ambos"] += ok_cat and ok_urg
        por_tipo[caso["tipo"]][0] += ok_cat and ok_urg
        por_tipo[caso["tipo"]][1] += 1
        por_categoria[esperada][0] += ok_cat
        por_categoria[esperada][1] += 1
        if r.modo == "ia":
            so_ia[0] += ok_cat and ok_urg
            so_ia[1] += 1
        linhas.append((caso, r, ok_cat, ok_urg))
        print(f"#{caso['id']:>2} {'OK ' if ok_cat and ok_urg else 'ERRO'} {r.categoria}/{r.urgencia} ({r.modo})")
        if args.modo == "ia":
            time.sleep(args.intervalo)

    n = len(casos)
    pct = lambda a, b: f"{100 * a / b:.1f}%"  # noqa: E731

    if args.modo == "regras":
        descricao_modo = "Modo reserva por palavras-chave (sem IA)."
    else:
        descricao_modo = f"Modelo: `{config.GEMINI_MODEL}` · RAG: {'ligado' if usar_rag else 'DESLIGADO'}"

    relatorio = [
        f"# Resultados da avaliação: `{nome}`",
        "",
        descricao_modo,
        "",
        f"Data: {time.strftime('%d/%m/%Y %H:%M')} · Casos: {n}",
        "",
        "## Métricas gerais",
        "",
        "| Métrica | Resultado |",
        "|---|---|",
        f"| Acerto da busca do RAG (categoria certa entre os 2 trechos recuperados) | {pct(*busca)} ({busca[0]}/{busca[1]}) |",
        f"| Acurácia de categoria | {pct(acertos['categoria'], n)} ({acertos['categoria']}/{n}) |",
        f"| Acurácia de urgência | {pct(acertos['urgencia'], n)} ({acertos['urgencia']}/{n}) |",
        f"| Acurácia combinada (categoria + urgência) | {pct(acertos['ambos'], n)} ({acertos['ambos']}/{n}) |",
        f"| Casos normais corretos | {pct(*por_tipo['normal'])} ({por_tipo['normal'][0]}/{por_tipo['normal'][1]}) |",
        f"| Casos de falha tratados corretamente | {pct(*por_tipo['falha'])} ({por_tipo['falha'][0]}/{por_tipo['falha'][1]}) |",
        f"| Tempo médio por triagem | {sum(tempos) / n:.2f} s |",
    ]
    if args.modo == "ia":
        relatorio.append(f"| Respostas que caíram no modo reserva (erro ou limite da API) | {caiu_no_reserva}/{n} |")
        if so_ia[1]:
            relatorio.append(f"| Acurácia combinada só nas respostas da IA | {pct(*so_ia)} ({so_ia[0]}/{so_ia[1]}) |")
        if motivos:
            relatorio += ["", "## Motivos das falhas da IA", "", "| Motivo | Casos |", "|---|---|"]
            relatorio += [f"| {m.replace('|', '/')} | {q} |" for m, q in motivos.items()]

    relatorio += ["", "## Acurácia de categoria por tipo de problema", "",
                  "| Categoria | Acertos |", "|---|---|"]
    relatorio += [f"| {c} | {a}/{t} |" for c, (a, t) in sorted(por_categoria.items())]

    relatorio += ["", "## Resultado por caso", "",
                  "| # | Tipo | Relato | Esperado | Obtido | Respondido por | Certo? |", "|---|---|---|---|---|---|---|"]
    for caso, r, ok_cat, ok_urg in linhas:
        relato = caso["descricao"].replace("|", "/")
        relato = relato if len(relato) <= 70 else relato[:67] + "..."
        certo = "sim" if ok_cat and ok_urg else ("errou urgência" if ok_cat else "não")
        relatorio.append(
            f"| {caso['id']} | {caso['tipo']} | {relato} | {caso['categoria_esperada']} / {caso['urgencia_esperada']} "
            f"| {r.categoria} / {r.urgencia} | {r.modo} | {certo} |"
        )

    destino = PASTA / f"resultados_{nome}.md"
    destino.write_text("\n".join(relatorio) + "\n", encoding="utf-8")
    print(f"\nBusca RAG {pct(*busca)} | Categoria {pct(acertos['categoria'], n)} | "
          f"Urgência {pct(acertos['urgencia'], n)} | Combinada {pct(acertos['ambos'], n)}")
    if args.modo == "ia" and caiu_no_reserva:
        print(f"ATENÇÃO: {caiu_no_reserva} respostas caíram no modo reserva. Aumente --intervalo e rode de novo.")
    print(f"Relatório salvo em {destino}")


if __name__ == "__main__":
    main()
