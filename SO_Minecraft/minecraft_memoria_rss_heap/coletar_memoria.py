#!/usr/bin/env python3
"""Coletor macOS: RSS do processo Java + Java heap usado/comprometido via jstat.

Uso: python3 coletar_memoria.py <view-distance: 4|8|12> <repeticao: 1..10> [--amostras 25 --intervalo 5] <PID>
"""
import argparse
import csv
from datetime import datetime
import platform
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "dados"
FIELDS = [
    "timestamp", "segundo_planejado", "segundo_real", "rss_kib", "rss_mib",
    "heap_used_kib", "heap_used_mib", "heap_committed_kib",
    "heap_committed_mib", "gc_young_count", "gc_full_count",
]

def execute(*cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"Comando falhou ({' '.join(cmd)}): "
            + (result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}")
        )
    return result.stdout


def parse_jstat(output):
    """jstat -gc emits a header line and a values line, columns may change order."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("jstat -gc sem cabecalho e valores")
    headers = lines[0].split()
    values = lines[-1].split()
    if len(headers) != len(values):
        raise ValueError(f"Colunas inesperadas no jstat: {len(headers)} cabecalhos / {len(values)} valores")
    numbers = {}
    for k, v in zip(headers, values):
        try:
            numbers[k] = float(v)
        except ValueError:
            numbers[k] = None
    used_cols = ("S0U", "S1U", "EU", "OU")
    committed_cols = ("S0C", "S1C", "EC", "OC")
    for col in used_cols + committed_cols:
        if col not in numbers or numbers[col] is None:
            raise ValueError(f"Coluna {col} indisponivel no jstat. Verifique JVM e GC usados.")
    # S0/S1 survivor, Eden e Old. Metaspace NAO faz parte do Java heap.
    used = sum(numbers[c] for c in used_cols)
    committed = sum(numbers[c] for c in committed_cols)
    if used < 0 or committed < 0:
        raise ValueError("Valores negativos de heap no jstat")
    return used, committed, numbers.get("YGC"), numbers.get("FGC")


def collect_once(pid):
    raw_ps = execute("ps", "-o", "rss=", "-p", str(pid))
    rss = raw_ps.strip().split()
    if not rss or not rss[0].isdigit():
        raise ValueError(f"ps nao retornou RSS numerico para PID {pid}: {raw_ps!r}")
    rss_kib = int(rss[0])
    raw_jstat = execute("jstat", "-gc", str(pid))
    used_kib, committed_kib, ygc, fgc = parse_jstat(raw_jstat)
    return rss_kib, used_kib, committed_kib, ygc, fgc, raw_ps, raw_jstat


def fmt_optional(value):
    return "" if value is None else (str(int(value)) if value.is_integer() else str(value))


def main():
    parser = argparse.ArgumentParser(description="Coleta RSS e heap usado da JVM de Minecraft no macOS")
    parser.add_argument("view_distance", type=int, choices=[4, 8, 12])
    parser.add_argument("repeticao", type=int, choices=range(1, 11))
    parser.add_argument("pid", type=int)
    parser.add_argument("--amostras", type=int, default=25, help="Padrao: 25 (t=0 a 120 segundos)")
    parser.add_argument("--intervalo", type=float, default=5.0, help="Padrao: 5 segundos")
    args = parser.parse_args()
    if args.pid <= 0 or args.amostras <= 0 or args.intervalo <= 0:
        parser.error("PID, --amostras e --intervalo devem ser positivos")
    if platform.system() != "Darwin":
        parser.error("Este script foi preparado para macOS. 'ps rss' pode ter outra unidade em outros sistemas.")
    if not shutil.which("jstat"):
        parser.error("jstat nao encontrado no PATH: instale/use um JDK, nao apenas um JRE.")
    if not shutil.which("ps"):
        parser.error("ps nao encontrado")
    if not subprocess.run(["ps", "-p", str(args.pid)], capture_output=True).returncode == 0:
        parser.error(f"PID {args.pid} nao encontrado")
    DATA_DIR.mkdir(exist_ok=True)
    prefix = DATA_DIR / f"VD{args.view_distance}_run{args.repeticao}"
    csv_file = Path(str(prefix) + ".csv")
    raw_file = Path(str(prefix) + "_raw.txt")
    meta_file = Path(str(prefix) + "_meta.txt")
    if any(p.exists() for p in (csv_file, raw_file, meta_file)):
        parser.error(f"Ja existem dados para este teste: {prefix.name}. Nao sobrescrever dados brutos.")

    # Testar se o processo esta sendo monitorado pelo jstat ANTES de criar arquivos.
    try:
        first = collect_once(args.pid)
    except (RuntimeError, ValueError) as exc:
        parser.error(f"Falha no teste de coleta: {exc}")
    command = execute("ps", "-p", str(args.pid), "-o", "command=").strip()
    if "java" not in command.lower():
        print("AVISO: comando do processo nao parece Java. Confira o PID do servidor.", file=sys.stderr)
    java_version = subprocess.run(["java", "-version"], capture_output=True, text=True).stderr.strip()
    now = datetime.now().astimezone()
    meta_file.write_text(
        "projeto=Minecraft server memory vs view-distance\n"
        f"view_distance={args.view_distance}\nrepeticao={args.repeticao}\n"
        f"pid={args.pid}\ninicio={now.isoformat()}\n"
        f"amostras={args.amostras}\nintervalo_segundos={args.intervalo}\n"
        f"sistema={platform.platform()}\ncomando_java={command}\n"
        f"java_version={java_version}\n"
        "unidades=KiB de 1024 bytes; MiB = KiB / 1024\n"
        "heap_used=jstat -gc (S0U + S1U + EU + OU), sem Metaspace\n"
        "heap_committed=jstat -gc (S0C + S1C + EC + OC)\n"
        "NOTA: registrar versao do servidor, mundo, coordenadas, jogadores, simulation-distance\n",
        encoding="utf-8"
    )
    start = time.monotonic()
    try:
        with csv_file.open("w", newline="", encoding="utf-8") as fcsv, raw_file.open("w", encoding="utf-8") as fraw:
            writer = csv.DictWriter(fcsv, fieldnames=FIELDS)
            writer.writeheader()
            for i in range(args.amostras):
                target = start + i * args.intervalo
                if i:
                    time.sleep(max(0, target - time.monotonic()))
                sampled = time.monotonic()
                try:
                    data = first if i == 0 else collect_once(args.pid)
                except (RuntimeError, ValueError) as exc:
                    raise RuntimeError(f"Falha na amostra {i+1}: {exc}") from exc
                rss, used, committed, ygc, fgc, raw_ps, raw_jstat = data
                row = {
                    "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "segundo_planejado": round(i * args.intervalo, 3),
                    "segundo_real": round(sampled - start, 3),
                    "rss_kib": rss,
                    "rss_mib": round(rss / 1024, 3),
                    "heap_used_kib": round(used, 3),
                    "heap_used_mib": round(used / 1024, 3),
                    "heap_committed_kib": round(committed, 3),
                    "heap_committed_mib": round(committed / 1024, 3),
                    "gc_young_count": fmt_optional(ygc),
                    "gc_full_count": fmt_optional(fgc),
                }
                writer.writerow(row)
                fcsv.flush()
                fraw.write(f"=== AMOSTRA {i+1}, t_plan={i*args.intervalo:.2f}s ===\n")
                fraw.write(f"$ ps -o rss= -p {args.pid}\n{raw_ps}\n")
                fraw.write(f"$ jstat -gc {args.pid}\n{raw_jstat}\n")
                fraw.flush()
                print(f"VD={args.view_distance:>2} run={args.repeticao} t={row['segundo_planejado']:>5}s | RSS={row['rss_mib']:>8.1f} MiB | heap usado={row['heap_used_mib']:>8.1f} MiB")
    except (KeyboardInterrupt, RuntimeError) as exc:
        print(f"Coleta interrompida: {exc}. Os arquivos parciais foram preservados.", file=sys.stderr)
        return 1
    finally:
        with meta_file.open("a", encoding="utf-8") as f:
            f.write(f"fim={datetime.now().astimezone().isoformat()}\n")
    print(f"Salvos: {csv_file.name}, {raw_file.name}, {meta_file.name}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
