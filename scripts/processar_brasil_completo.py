#!/usr/bin/env python3
"""
Pipeline Nacional: Processamento Completo de Seções Eleitorais do Brasil (TSE 2º Turno)
Varre todas as seções de todos os 27 estados (+ DF e Exterior ZZ) para identificar:
- Seções 100% Absoluto (Lula e Bolsonaro)
- Seções >= 90% Absoluto (Lula e Bolsonaro)
Gera datasets consolidados e dados para mapa de calor e gráficos comparativos.
"""

import os
import sys
import csv
import json
import zipfile
import io
import urllib.request
from collections import defaultdict
from typing import Dict, List, Tuple

UFS_BRASIL = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
    "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
    "RO", "RR", "RS", "SC", "SE", "SP", "TO", "ZZ"
]

def resolver_diretorio_zips():
    for d in ["data/zips/tse", "../data/zips/tse", "zips_tse", "../zips_tse", "data/zips", "."]:
        if os.path.exists(d):
            return d
    return "data/zips/tse"

DIRETORIO_ZIPS = resolver_diretorio_zips()

def baixar_uf(uf: str) -> str:
    os.makedirs(DIRETORIO_ZIPS, exist_ok=True)
    caminho_local = os.path.join(DIRETORIO_ZIPS, f"bweb_2t_{uf}_311020221535.zip")
    
    # Checa possíveis locais existentes
    for candidato in [
        caminho_local,
        os.path.join("data", "zips", "tse", f"bweb_2t_{uf}_311020221535.zip"),
        os.path.join("..", "data", "zips", "tse", f"bweb_2t_{uf}_311020221535.zip"),
        f"bweb_2t_{uf}_311020221535.zip",
        os.path.join("..", f"bweb_2t_{uf}_311020221535.zip")
    ]:
        if os.path.exists(candidato) and os.path.getsize(candidato) > 1000:
            return candidato

    url = f"https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2022/buweb/bweb_2t_{uf}_311020221535.zip"
    print(f"[{uf}] Baixando dados do TSE: {url} ...", flush=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(caminho_local, "wb") as f_out:
            while True:
                chunk = resp.read(1024 * 512)
                if not chunk:
                    break
                f_out.write(chunk)
        print(f"[{uf}] Download concluído ({os.path.getsize(caminho_local) / 1024 / 1024:.1f} MB)", flush=True)
        return caminho_local
    except Exception as e:
        print(f"[{uf}] ERRO ao baixar: {e}", file=sys.stderr)
        if os.path.exists(caminho_local):
            os.remove(caminho_local)
        return ""

def montar_url_tse(uf: str, mun: str, zona: str, secao: str) -> str:
    return f"https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6258/uf/{uf.lower()}/mu/{str(mun).zfill(5)}/zn/{str(zona).zfill(4)}/cargo/1/vis/nominal/se/{str(secao).zfill(4)}/dados-de-urna/boletim-de-urna"

def processar_arquivo_uf(caminho_zip: str, uf: str) -> Tuple[Dict, List[Dict], List[Dict]]:
    """
    Processa uma UF e retorna:
    - Resumo da UF
    - Lista de seções 100%
    - Lista de seções >= 90% (e < 100%)
    """
    if not caminho_zip or not os.path.exists(caminho_zip):
        return {}, [], []

    secoes = defaultdict(lambda: {
        "uf": uf, "mun": "", "nome_mun": "", "zona": "", "secao": "",
        "votos_lula": 0, "votos_bolsonaro": 0, "votos_outros": 0,
        "brancos": 0, "nulos": 0, "aptos": 0, "comparecimento": 0
    })

    with zipfile.ZipFile(caminho_zip, "r") as z:
        csv_nomes = [f for f in z.namelist() if f.endswith(".csv")]
        if not csv_nomes:
            return {}, [], []
        nome_csv = csv_nomes[0]

        with z.open(nome_csv) as f:
            text_io = io.TextIOWrapper(f, encoding="latin-1")
            reader = csv.reader(text_io, delimiter=";")
            header = [h.strip('\"') for h in next(reader)]

            idx_cargo = header.index("CD_CARGO_PERGUNTA")
            idx_mun = header.index("CD_MUNICIPIO")
            idx_nom_mun = header.index("NM_MUNICIPIO")
            idx_zona = header.index("NR_ZONA")
            idx_secao = header.index("NR_SECAO")
            idx_cand = header.index("NM_VOTAVEL")
            idx_num_cand = header.index("NR_VOTAVEL")
            idx_votos = header.index("QT_VOTOS")
            idx_tipo = header.index("DS_TIPO_VOTAVEL")
            idx_aptos = header.index("QT_APTOS")
            idx_comp = header.index("QT_COMPARECIMENTO")

            for row in reader:
                if not row or len(row) <= idx_votos:
                    continue
                if row[idx_cargo] != "1": # 1 = Presidente
                    continue

                chave = (row[idx_mun], row[idx_zona], row[idx_secao])
                s = secoes[chave]
                s["mun"] = row[idx_mun]
                s["nome_mun"] = row[idx_nom_mun]
                s["zona"] = row[idx_zona]
                s["secao"] = row[idx_secao]
                s["aptos"] = int(row[idx_aptos])
                s["comparecimento"] = int(row[idx_comp])

                tipo = row[idx_tipo]
                cand = row[idx_cand].upper()
                num_cand = row[idx_num_cand]
                votos = int(row[idx_votos])

                if tipo == "Branco":
                    s["brancos"] += votos
                elif tipo == "Nulo":
                    s["nulos"] += votos
                elif tipo == "Nominal":
                    if "LULA" in cand or num_cand == "13":
                        s["votos_lula"] += votos
                    elif "BOLSONARO" in cand or num_cand == "22":
                        s["votos_bolsonaro"] += votos
                    else:
                        s["votos_outros"] += votos

    total_secoes = len(secoes)
    secoes_100_lula = []
    secoes_100_bolsonaro = []
    secoes_90_lula = []
    secoes_90_bolsonaro = []

    lista_100 = []
    lista_90 = []

    total_votos_lula = 0
    total_votos_bolsonaro = 0

    for chave, s in secoes.items():
        v_lula = s["votos_lula"]
        v_bols = s["votos_bolsonaro"]
        v_nominais = v_lula + v_bols + s["votos_outros"]
        total_votos_lula += v_lula
        total_votos_bolsonaro += v_bols

        if v_nominais == 0:
            continue

        pct_lula = v_lula / v_nominais
        pct_bols = v_bols / v_nominais
        url = montar_url_tse(uf, s["mun"], s["zona"], s["secao"])

        info_secao = {
            "uf": uf,
            "municipio": s["mun"],
            "nome_municipio": s["nome_mun"],
            "zona": s["zona"],
            "secao": s["secao"],
            "aptos": s["aptos"],
            "comparecimento": s["comparecimento"],
            "votos_nominais": v_nominais,
            "votos_lula": v_lula,
            "votos_bolsonaro": v_bols,
            "brancos": s["brancos"],
            "nulos": s["nulos"],
            "url_tse": url
        }

        # 100% Absoluto
        if pct_lula == 1.0:
            item = dict(info_secao, candidato="LULA", percentual=100.0)
            secoes_100_lula.append(item)
            lista_100.append(item)
        elif pct_bols == 1.0:
            item = dict(info_secao, candidato="JAIR BOLSONARO", percentual=100.0)
            secoes_100_bolsonaro.append(item)
            lista_100.append(item)
        # >= 90% e < 100%
        elif pct_lula >= 0.90:
            item = dict(info_secao, candidato="LULA", percentual=round(pct_lula * 100, 2))
            secoes_90_lula.append(item)
            lista_90.append(item)
        elif pct_bols >= 0.90:
            item = dict(info_secao, candidato="JAIR BOLSONARO", percentual=round(pct_bols * 100, 2))
            secoes_90_bolsonaro.append(item)
            lista_90.append(item)

    resumo = {
        "uf": uf,
        "total_secoes": total_secoes,
        "votos_lula": total_votos_lula,
        "votos_bolsonaro": total_votos_bolsonaro,
        "secoes_100_lula": len(secoes_100_lula),
        "secoes_100_bolsonaro": len(secoes_100_bolsonaro),
        "secoes_100_total": len(secoes_100_lula) + len(secoes_100_bolsonaro),
        "secoes_90_lula": len(secoes_90_lula),
        "secoes_90_bolsonaro": len(secoes_90_bolsonaro),
        "secoes_90_total": len(secoes_90_lula) + len(secoes_90_bolsonaro),
        "secoes_90_mais_100_lula": len(secoes_100_lula) + len(secoes_90_lula),
        "secoes_90_mais_100_bolsonaro": len(secoes_100_bolsonaro) + len(secoes_90_bolsonaro),
    }

    return resumo, lista_100, lista_90

def main():
    print("=" * 80)
    print("INICIANDO PROCESSAMENTO NACIONAL DAS ELEIÇÕES - TODAS AS UFs DO BRASIL")
    print("=" * 80)

    resumos_uf = []
    todas_100 = []
    todas_90 = []

    for idx, uf in enumerate(UFS_BRASIL, 1):
        print(f"\n[{idx:02d}/{len(UFS_BRASIL)}] Processando {uf} ...")
        zip_path = baixar_uf(uf)
        if not zip_path:
            print(f"[{uf}] Falha ao obter dados. Pulando...", file=sys.stderr)
            continue

        resumo, l_100, l_90 = processar_arquivo_uf(zip_path, uf)
        resumos_uf.append(resumo)
        todas_100.extend(l_100)
        todas_90.extend(l_90)

        print(f"  • {uf} Total Seções: {resumo['total_secoes']:,}")
        print(f"  • Seções 100%: Lula = {resumo['secoes_100_lula']} | Bolsonaro = {resumo['secoes_100_bolsonaro']}")
        print(f"  • Seções ≥ 90% (e < 100%): Lula = {resumo['secoes_90_lula']} | Bolsonaro = {resumo['secoes_90_bolsonaro']}")
        print(f"  • Total Hegemônicas (≥ 90%): Lula = {resumo['secoes_90_mais_100_lula']} | Bolsonaro = {resumo['secoes_90_mais_100_bolsonaro']}")

    # Determina diretório de saída dos dados processados
    dir_saida = "."
    for d in ["data/processed", "../data/processed", "."]:
        if os.path.exists(d):
            dir_saida = d
            break

    # Exportar Resumo por UF
    with open(os.path.join(dir_saida, "brasil_resumo_secoes_por_uf.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "uf", "total_secoes", "votos_lula", "votos_bolsonaro",
            "secoes_100_lula", "secoes_100_bolsonaro", "secoes_100_total",
            "secoes_90_lula", "secoes_90_bolsonaro", "secoes_90_total",
            "secoes_90_mais_100_lula", "secoes_90_mais_100_bolsonaro"
        ])
        writer.writeheader()
        for r in resumos_uf:
            writer.writerow(r)

    # Exportar Seções 100%
    with open(os.path.join(dir_saida, "brasil_secoes_100pct.csv"), "w", newline="", encoding="utf-8") as f:
        if todas_100:
            writer = csv.DictWriter(f, fieldnames=list(todas_100[0].keys()))
            writer.writeheader()
            for s in todas_100:
                writer.writerow(s)

    # Exportar Seções 90%
    with open(os.path.join(dir_saida, "brasil_secoes_90pct.csv"), "w", newline="", encoding="utf-8") as f:
        if todas_90:
            writer = csv.DictWriter(f, fieldnames=list(todas_90[0].keys()))
            writer.writeheader()
            for s in todas_90:
                writer.writerow(s)

    # Exportar JSON consolidado para visualização
    dados_dashboard = {
        "resumos_uf": resumos_uf,
        "totais_brasil": {
            "total_secoes": sum(r["total_secoes"] for r in resumos_uf),
            "votos_lula": sum(r["votos_lula"] for r in resumos_uf),
            "votos_bolsonaro": sum(r["votos_bolsonaro"] for r in resumos_uf),
            "secoes_100_lula": sum(r["secoes_100_lula"] for r in resumos_uf),
            "secoes_100_bolsonaro": sum(r["secoes_100_bolsonaro"] for r in resumos_uf),
            "secoes_90_lula": sum(r["secoes_90_lula"] for r in resumos_uf),
            "secoes_90_bolsonaro": sum(r["secoes_90_bolsonaro"] for r in resumos_uf),
            "secoes_90_mais_100_lula": sum(r["secoes_90_mais_100_lula"] for r in resumos_uf),
            "secoes_90_mais_100_bolsonaro": sum(r["secoes_90_mais_100_bolsonaro"] for r in resumos_uf),
        },
        "secoes_100_amostra": todas_100,
        "secoes_90_amostra": todas_90[:500] # primeiras 500 para visualização interativa rápida
    }

    with open(os.path.join(dir_saida, "dados_mapa_calor.json"), "w", encoding="utf-8") as f_json:
        json.dump(dados_dashboard, f_json, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print("PROCESSAMENTO DE TODAS AS UFS CONCLUÍDO COM SUCESSO!")
    print(f"Total de Seções no Brasil: {dados_dashboard['totais_brasil']['total_secoes']:,}")
    print(f"Total Seções 100% LULA     : {dados_dashboard['totais_brasil']['secoes_100_lula']:,}")
    print(f"Total Seções 100% BOLSONARO: {dados_dashboard['totais_brasil']['secoes_100_bolsonaro']:,}")
    print(f"Total Seções ≥ 90% LULA     : {dados_dashboard['totais_brasil']['secoes_90_mais_100_lula']:,}")
    print(f"Total Seções ≥ 90% BOLSONARO: {dados_dashboard['totais_brasil']['secoes_90_mais_100_bolsonaro']:,}")
    print("=" * 80)

if __name__ == "__main__":
    main()
