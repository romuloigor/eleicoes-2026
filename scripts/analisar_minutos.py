#!/usr/bin/env python3
"""
Análise Minuciosa e Forense dos Minutos dos Votos (Log de Urna - TSE)
Analisa intervalos entre votos, ociosidade, tempo de cabine e dispersão estatística de minutos.
"""

from __future__ import annotations

import os
import sys
import zipfile
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

def carregar_votos(caminho_arquivo: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Lê o arquivo .jez oficial do TSE e extrai as sequências cronológicas de votos.
    """
    if not os.path.exists(caminho_arquivo):
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_arquivo}")

    votos_por_dia: Dict[str, List[Dict[str, Any]]] = {}
    hab_atual = None
    tipo_hab = "N/I"

    try:
        with zipfile.ZipFile(caminho_arquivo, "r") as z:
            nome_interno = "logd.dat"
            if nome_interno not in z.namelist():
                candidatos = [f for f in z.namelist() if f.endswith(".dat") or "log" in f]
                if not candidatos:
                    raise ValueError(f"Arquivo de log não encontrado dentro do ZIP: {caminho_arquivo}")
                nome_interno = candidatos[0]

            with z.open(nome_interno) as f:
                for l in f:
                    linha = l.decode("iso-8859-1").rstrip("\r\n")
                    partes = linha.split("\t")
                    if len(partes) < 5:
                        continue
                    dt_str = partes[0]
                    msg = partes[4]

                    if "Tipo de habilitação do eleitor" in msg:
                        partes_colch = msg.split("[")
                        if len(partes_colch) > 1 and "]" in partes_colch[-1]:
                            tipo_hab = partes_colch[-1].split("]")[0]
                    elif "Eleitor foi habilitado" in msg:
                        hab_atual = dt_str
                    elif "O voto do eleitor foi computado" in msg:
                        try:
                            dt = datetime.strptime(dt_str, "%d/%m/%Y %H:%M:%S")
                        except ValueError:
                            continue

                        dia = dt.strftime("%d/%m/%Y")
                        if dia not in votos_por_dia:
                            votos_por_dia[dia] = []

                        duracao_s = 0
                        if hab_atual:
                            try:
                                t_ini = datetime.strptime(hab_atual, "%d/%m/%Y %H:%M:%S")
                                duracao_s = max(0, int((dt - t_ini).total_seconds()))
                            except Exception:
                                duracao_s = 0

                        votos_por_dia[dia].append({
                            "seq": len(votos_por_dia[dia]) + 1,
                            "datetime": dt,
                            "hora_str": dt.strftime("%H:%M:%S"),
                            "minuto": dt.minute,
                            "segundo": dt.second,
                            "duracao_cabine_s": duracao_s,
                            "tipo_hab": tipo_hab
                        })
                        hab_atual = None
                        tipo_hab = "N/I"
    except zipfile.BadZipFile as e:
        print(f"[ERRO] Arquivo ZIP corrompido: {e}", file=sys.stderr)
        return {}

    return votos_por_dia

def analisar_dia(dia: str, votos: List[Dict[str, Any]]) -> None:
    """
    Executa os cálculos estatísticos e forenses para um dia de votação.
    """
    total_votos = len(votos)
    print("=" * 80)
    print(f"ANÁLISE DE MINUTOS E FLUXO TEMPORAL - {dia} ({total_votos} votos)")
    print("=" * 80)

    if total_votos == 0:
        print("  • Nenhum voto registrado para este dia.")
        return

    # 1. Intervalos entre votos consecutivos (Delta tempo)
    intervalos_min = []
    for i in range(1, total_votos):
        delta_s = (votos[i]["datetime"] - votos[i-1]["datetime"]).total_seconds()
        intervalos_min.append((delta_s / 60.0, votos[i-1]["hora_str"], votos[i]["hora_str"]))

    deltas = [item[0] for item in intervalos_min]
    total_deltas = len(deltas)
    media_delta = (sum(deltas) / total_deltas) if total_deltas > 0 else 0.0
    min_delta = min(deltas) if deltas else 0.0
    max_delta = max(deltas) if deltas else 0.0

    print("1. RITMO E INTERVALOS ENTRE ELEITORES CONSECUTIVOS:")
    print(f"  • Intervalo médio entre votos : {media_delta:.2f} minutos ({media_delta*60:.0f}s)")
    print(f"  • Menor intervalo (fila rápida): {min_delta:.2f} minutos ({min_delta*60:.0f}s)")
    print(f"  • Maior intervalo (ociosidade): {max_delta:.2f} minutos ({max_delta*60:.0f}s)")

    # Maiores pausas
    pausas_ordenadas = sorted(intervalos_min, key=lambda x: x[0], reverse=True)[:5]
    print("\n  Top 5 Maiores Períodos de Ociosidade (Urna sem receber votos):")
    for delta, t1, t2 in pausas_ordenadas:
        print(f"    - {delta:>4.1f} min de pausa (entre {t1} e {t2})")

    # Rajadas rápidas (voto seguinte em menos de 2 minutos)
    rajadas = [d for d in deltas if d <= 2.0]
    pct_rajadas = ((len(rajadas) / total_deltas) * 100.0) if total_deltas > 0 else 0.0
    print(f"\n  • Votos em rajada (intervalo ≤ 2 min): {len(rajadas)} votos ({pct_rajadas:.1f}%)")

    # 2. Duração na Cabine de Votação (em minutos/segundos)
    duracoes = [v["duracao_cabine_s"] for v in votos if v["duracao_cabine_s"] > 0]
    total_duracoes = len(duracoes)
    if total_duracoes > 0:
        media_cabine = (sum(duracoes) / total_duracoes) if total_duracoes > 0 else 0.0
        print("\n2. TEMPO NA CABINE DE VOTAÇÃO (Habilitação -> Voto Computado):")
        print(f"  • Tempo médio na cabine: {media_cabine/60:.2f} min ({media_cabine:.0f}s)")
        print(f"  • Voto mais rápido     : {min(duracoes)}s")
        print(f"  • Voto mais lento      : {max(duracoes)/60:.2f} min ({max(duracoes)}s)")

    # 3. Agrupamento em Janelas de 15 minutos (Picos de votação)
    print("\n3. PICOS DE AFLUÊNCIA EM JANELAS DE 15 MINUTOS (Top 5):")
    blocos15 = Counter()
    for v in votos:
        bloco = f"{v['datetime'].hour:02d}:{(v['minuto'] // 15) * 15:02d}"
        blocos15[bloco] += 1

    for bloco, qtd in blocos15.most_common(5):
        fim_min = int(bloco[3:]) + 14
        print(f"  • {bloco} até {bloco[:2]}:{fim_min:02d} : {qtd:>2} votos {'█' * qtd}")

    # 4. Dispersão dos Minutos ao Longo da Hora (0 a 59)
    print("\n4. DISPERSÃO E UNIFORMIDADE DOS MINUTOS (0 a 59):")
    quadrantes = Counter()
    digitos = Counter()
    for v in votos:
        quadrantes[v["minuto"] // 15] += 1
        digitos[v["minuto"] % 10] += 1

    rotulos = ["00 a 14 min", "15 a 29 min", "30 a 44 min", "45 a 59 min"]
    for q, rot in enumerate(rotulos):
        pct = (quadrantes[q] / total_votos * 100.0) if total_votos > 0 else 0.0
        print(f"  • {rot:<12}: {quadrantes[q]:>2} votos ({pct:>5.1f}%) {'■' * int(pct // 2)}")

    print("\n  Frequência do último dígito dos minutos (0 a 9 - Teste de Uniformidade):")
    linha_digitos = "   ".join([f"[{d}]: {digitos[d]:>2}" for d in range(10)])
    print(f"   {linha_digitos}")
    print()

def main() -> None:
    arquivo = sys.argv[1] if len(sys.argv) > 1 else "o03221mg4100900500224-log.jez"
    if not os.path.exists(arquivo):
        for fallback in [
            os.path.join("data", "raw", arquivo),
            os.path.join("..", "data", "raw", arquivo),
            os.path.join("data", "raw", "o03221mg4100900500224-log.jez"),
            os.path.join("..", "data", "raw", "o03221mg4100900500224-log.jez"),
        ]:
            if os.path.exists(fallback):
                arquivo = fallback
                break

    try:
        votos_por_dia = carregar_votos(arquivo)
        for dia, votos in votos_por_dia.items():
            analisar_dia(dia, votos)
    except Exception as e:
        print(f"[ERRO] Falha ao analisar arquivo: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
