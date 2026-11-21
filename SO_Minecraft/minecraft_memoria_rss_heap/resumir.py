#!/usr/bin/env python3
"""Consolida RSS e heap usado: primeiro medias por repeticao, depois por condicao."""
import csv
from pathlib import Path
import re
from statistics import mean, stdev

BASE = Path(__file__).resolve().parent
DATA = BASE / "dados"
METRICS = ("rss_mib", "heap_used_mib", "heap_committed_mib")


def summarize(data_dir=DATA):
    results = {}
    runs = []
    for path in sorted(data_dir.glob("VD*_run*.csv")):
        m = re.fullmatch(r"VD(4|8|12)_run(10|[1-9])\.csv", path.name)
        if not m:
            continue
        vd, rep = map(int, m.groups())
        with path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            print(f"Ignorado: {path.name} esta vazio")
            continue
        try:
            values = {metric: [float(row[metric]) for row in rows] for metric in METRICS}
        except (KeyError, ValueError) as exc:
            raise ValueError(f"CSV invalido {path}: {exc}") from exc
        summary = {"view_distance": vd, "repeticao": rep, "amostras": len(rows)}
        for metric in METRICS:
            summary[f"{metric}_media"] = round(mean(values[metric]), 3)
            summary[f"{metric}_pico_amostrado"] = round(max(values[metric]), 3)
            summary[f"{metric}_min"] = round(min(values[metric]), 3)
        runs.append(summary)
        results.setdefault(vd, []).append(summary)
        print(f"VD={vd:>2} run={rep} N={len(rows)} | RSS medio={summary['rss_mib_media']:.1f} MiB | Heap medio={summary['heap_used_mib_media']:.1f} MiB")
        if len(rows) != 25:
            print(f"AVISO: {path.name} tem {len(rows)} amostras (padrao: 25).")
    if not runs:
        print("Nao existem dados reais. Execute coletar_memoria.py primeiro.")
        return None

    with (data_dir / "resumo_por_repeticao.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(runs[0]))
        writer.writeheader()
        writer.writerows(runs)

    conds = []
    for vd in sorted(results):
        group = results[vd]
        record = {"view_distance": vd, "n_repeticoes": len(group)}
        for metric in METRICS:
            run_means = [r[f"{metric}_media"] for r in group]
            record[f"{metric}_media_das_medias"] = round(mean(run_means), 3)
            record[f"{metric}_maior_pico_amostrado"] = max(r[f"{metric}_pico_amostrado"] for r in group)
            record[f"{metric}_desvio_padrao_entre_repeticoes"] = round(stdev(run_means), 3) if len(run_means) > 1 else ""
        conds.append(record)
        if len(group) != 10:
            print(f"AVISO: VD={vd} tem {len(group)} repeticoes (meta: 10)")
    with (data_dir / "resumo_por_condicao.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(conds[0]))
        writer.writeheader()
        writer.writerows(conds)
    print("\nResultados salvos em dados/resumo_por_repeticao.csv e dados/resumo_por_condicao.csv")
    return conds

if __name__ == "__main__":
    summarize()
