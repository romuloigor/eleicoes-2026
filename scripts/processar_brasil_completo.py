#!/usr/bin/env python3
"""
Pipeline Nacional: Processamento Completo de Seções Eleitorais do Brasil (TSE 2º Turno)
Varre todas as seções de todos os 27 estados (+ DF e Exterior ZZ) para identificar:
- Seções 100% Absoluto (Lula e Bolsonaro)
- Seções >= 90% Absoluto (Lula e Bolsonaro)
Gera datasets consolidados e dados para mapa de calor e gráficos comparativos.
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

UFS_BRASIL = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
    "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
    "RO", "RR", "RS", "SC", "SE", "SP", "TO", "ZZ"
]

def resolver_diretorio_zips() -> str:
    for d in ["data/zips/tse", "../data/zips/tse", "zips_tse", "../zips_tse", "data/zips", "."]:
        if os.path.exists(d):
            return d
    return "data/zips/tse"

DIRETORIO_ZIPS = resolver_diretorio_zips()

def sanitize_csv_cell(val: Any) -> Any:
    """
    Previne Formula / DDE Injection (CWE-1236) em exportação de planilhas CSV.
    """
    if isinstance(val, str) and val:
        if val[0] in ("=", "+", "-", "@", "\t", "\r"):
            return f"'{val}"
    return val

def baixar_uf(uf: str) -> str:
    """
    Realiza o download atômico e resiliente do arquivo de Boletim de Urna (BWEB) do TSE.
    """
    os.makedirs(DIRETORIO_ZIPS, exist_ok=True)
    caminho_local = os.path.join(DIRETORIO_ZIPS, f"bweb_2t_{uf}_311020221535.zip")

    # Checa possíveis locais existentes com arquivo válido
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
    caminho_tmp = f"{caminho_local}.tmp"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(caminho_tmp, "wb") as f_out:
            while True:
                chunk = resp.read(1024 * 512)
                if not chunk:
                    break
                f_out.write(chunk)

        # Download completado com sucesso: renomeia atomicamente
        os.replace(caminho_tmp, caminho_local)
        print(f"[{uf}] Download concluído ({os.path.getsize(caminho_local) / 1024 / 1024:.1f} MB)", flush=True)
        return caminho_local
    except Exception as e:
        print(f"[{uf}] ERRO ao baixar dados oficiais do TSE: {e}", file=sys.stderr)
        if os.path.exists(caminho_tmp):
            try:
                os.remove(caminho_tmp)
            except OSError:
                pass
        return ""

def montar_url_tse(uf: str, mun: str, zona: str, secao: str) -> str:
    """
    Monta o link canônico do portal de resultados oficiais do TSE para a seção.
    """
    uf_clean = uf.lower().strip()
    mun_clean = str(mun).zfill(5)
    zona_clean = str(zona).zfill(4)
    secao_clean = str(secao).zfill(4)
    return f"https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6258/uf/{uf_clean}/mu/{mun_clean}/zn/{zona_clean}/cargo/1/vis/nominal/se/{secao_clean}/dados-de-urna/boletim-de-urna"

def processar_arquivo_uf(caminho_zip: str, uf: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Processa uma UF e retorna:
    - Resumo consolidado da UF
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

    try:
        with zipfile.ZipFile(caminho_zip, "r") as z:
            csv_nomes = [f for f in z.namelist() if f.endswith(".csv")]
            if not csv_nomes:
                return {}, [], []
            nome_csv = csv_nomes[0]

            with z.open(nome_csv) as f:
                text_io = io.TextIOWrapper(f, encoding="latin-1")
                reader = csv.reader(text_io, delimiter=";")
                header = [h.strip('\"') for h in next(reader)]

                def achar_idx(coluna_cand: List[str]) -> int:
                    for col in coluna_cand:
                        if col in header:
                            return header.index(col)
                    return -1

                idx_cargo = achar_idx(["CD_CARGO_PERGUNTA", "CD_CARGO"])
                idx_mun = achar_idx(["CD_MUNICIPIO"])
                idx_nom_mun = achar_idx(["NM_MUNICIPIO"])
                idx_zona = achar_idx(["NR_ZONA"])
                idx_secao = achar_idx(["NR_SECAO"])
                idx_cand = achar_idx(["NM_VOTAVEL"])
                idx_num_cand = achar_idx(["NR_VOTAVEL"])
                idx_votos = achar_idx(["QT_VOTOS"])
                idx_tipo = achar_idx(["DS_TIPO_VOTAVEL"])
                idx_aptos = achar_idx(["QT_APTOS"])
                idx_comp = achar_idx(["QT_COMPARECIMENTO"])

                indices_obrigatorios = [idx_cargo, idx_mun, idx_zona, idx_secao, idx_votos]
                if any(idx < 0 for idx in indices_obrigatorios):
                    print(f"[{uf}] Header com colunas ausentes no CSV do TSE.", file=sys.stderr)
                    return {}, [], []

                for row in reader:
                    if not row or len(row) <= idx_votos:
                        continue
                    if row[idx_cargo] != "1":  # 1 = Presidente
                        continue

                    chave = (row[idx_mun], row[idx_zona], row[idx_secao])
                    s = secoes[chave]
                    s["mun"] = row[idx_mun]
                    s["nome_mun"] = row[idx_nom_mun] if idx_nom_mun >= 0 and len(row) > idx_nom_mun else ""
                    s["zona"] = row[idx_zona]
                    s["secao"] = row[idx_secao]

                    if idx_aptos >= 0 and len(row) > idx_aptos:
                        try:
                            s["aptos"] = int(row[idx_aptos])
                        except (ValueError, TypeError):
                            s["aptos"] = 0

                    if idx_comp >= 0 and len(row) > idx_comp:
                        try:
                            s["comparecimento"] = int(row[idx_comp])
                        except (ValueError, TypeError):
                            s["comparecimento"] = 0

                    tipo = row[idx_tipo] if idx_tipo >= 0 and len(row) > idx_tipo else ""
                    cand = row[idx_cand].upper() if idx_cand >= 0 and len(row) > idx_cand else ""
                    num_cand = row[idx_num_cand] if idx_num_cand >= 0 and len(row) > idx_num_cand else ""

                    try:
                        votos = int(row[idx_votos])
                    except (ValueError, TypeError):
                        votos = 0

                    if tipo == "Branco" or cand == "BRANCO":
                        s["brancos"] += votos
                    elif tipo == "Nulo" or cand == "NULO":
                        s["nulos"] += votos
                    else:
                        if "LULA" in cand or num_cand == "13":
                            s["votos_lula"] += votos
                        elif "BOLSONARO" in cand or num_cand == "22":
                            s["votos_bolsonaro"] += votos
                        else:
                            s["votos_outros"] += votos
    except (zipfile.BadZipFile, OSError) as e:
        print(f"[{uf}] Erro ao ler arquivo compactado: {e}", file=sys.stderr)
        return {}, [], []

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

        if v_nominais <= 0:
            continue

        pct_lula = (v_lula / v_nominais) if v_nominais > 0 else 0.0
        pct_bols = (v_bols / v_nominais) if v_nominais > 0 else 0.0
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
            item = dict(info_secao, candidato="LULA", percentual=round(pct_lula * 100.0, 2))
            secoes_90_lula.append(item)
            lista_90.append(item)
        elif pct_bols >= 0.90:
            item = dict(info_secao, candidato="JAIR BOLSONARO", percentual=round(pct_bols * 100.0, 2))
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

def main() -> None:
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
        if not resumo:
            print(f"[{uf}] Resumo vazio ou falha na leitura.", file=sys.stderr)
            continue

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

    # Exportar Resumo por UF com sanitização de fórmula
    caminho_resumo = os.path.join(dir_saida, "brasil_resumo_secoes_por_uf.csv")
    with open(caminho_resumo, "w", newline="", encoding="utf-8") as f:
        colunas = [
            "uf", "total_secoes", "votos_lula", "votos_bolsonaro",
            "secoes_100_lula", "secoes_100_bolsonaro", "secoes_100_total",
            "secoes_90_lula", "secoes_90_bolsonaro", "secoes_90_total",
            "secoes_90_mais_100_lula", "secoes_90_mais_100_bolsonaro"
        ]
        writer = csv.DictWriter(f, fieldnames=colunas)
        writer.writeheader()
        for r in resumos_uf:
            sanitized = {k: sanitize_csv_cell(v) for k, v in r.items()}
            writer.writerow(sanitized)

    # Exportar Seções 100%
    caminho_100 = os.path.join(dir_saida, "brasil_secoes_100pct.csv")
    with open(caminho_100, "w", newline="", encoding="utf-8") as f:
        if todas_100:
            writer = csv.DictWriter(f, fieldnames=list(todas_100[0].keys()))
            writer.writeheader()
            for s in todas_100:
                sanitized_s = {k: sanitize_csv_cell(v) for k, v in s.items()}
                writer.writerow(sanitized_s)

    # Exportar Seções 90%
    caminho_90 = os.path.join(dir_saida, "brasil_secoes_90pct.csv")
    with open(caminho_90, "w", newline="", encoding="utf-8") as f:
        if todas_90:
            writer = csv.DictWriter(f, fieldnames=list(todas_90[0].keys()))
            writer.writeheader()
            for s in todas_90:
                sanitized_s = {k: sanitize_csv_cell(v) for k, v in s.items()}
                writer.writerow(sanitized_s)

    # Exportar JSON consolidado para visualização
    dados_dashboard = {
        "resumos_uf": resumos_uf,
        "totais_brasil": {
            "total_secoes": sum(r["total_secoes"] for r in resumos_uf) if resumos_uf else 0,
            "votos_lula": sum(r["votos_lula"] for r in resumos_uf) if resumos_uf else 0,
            "votos_bolsonaro": sum(r["votos_bolsonaro"] for r in resumos_uf) if resumos_uf else 0,
            "secoes_100_lula": sum(r["secoes_100_lula"] for r in resumos_uf) if resumos_uf else 0,
            "secoes_100_bolsonaro": sum(r["secoes_100_bolsonaro"] for r in resumos_uf) if resumos_uf else 0,
            "secoes_90_lula": sum(r["secoes_90_lula"] for r in resumos_uf) if resumos_uf else 0,
            "secoes_90_bolsonaro": sum(r["secoes_90_bolsonaro"] for r in resumos_uf) if resumos_uf else 0,
            "secoes_90_mais_100_lula": sum(r["secoes_90_mais_100_lula"] for r in resumos_uf) if resumos_uf else 0,
            "secoes_90_mais_100_bolsonaro": sum(r["secoes_90_mais_100_bolsonaro"] for r in resumos_uf) if resumos_uf else 0,
        },
        "secoes_100_amostra": todas_100,
        "secoes_90_amostra": todas_90[:500]
    }

    caminho_json = os.path.join(dir_saida, "dados_mapa_calor.json")
    with open(caminho_json, "w", encoding="utf-8") as f_json:
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
