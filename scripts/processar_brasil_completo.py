#!/usr/bin/env python3
"""
Pipeline Nacional: Processamento Completo de Seções Eleitorais do Brasil (TSE 2º Turno 2026)
Eleição Ordinária Federal 2026 - 2º Turno (Eleição 6258 / Pleito 3221)
Varre todas as seções de todas as 28 UFs (26 estados + DF + Exterior ZZ) para catalogar:
- Seções 100% Absoluto (Lula 13 e Flávio Bolsonaro 22)
- Seções >= 90% Absoluto (Lula 13 e Flávio Bolsonaro 22)
Gera datasets consolidados e dados para mapa de calor, geocodificação e gráficos comparativos.
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
import unicodedata
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

UF_IBGE_MAP = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
DIR_ZIPS = os.path.join(ROOT_DIR, "data", "zips", "tse")
DIR_PROCESSED = os.path.join(ROOT_DIR, "data", "processed")
DIR_RAW = os.path.join(ROOT_DIR, "data", "raw")

os.makedirs(DIR_ZIPS, exist_ok=True)
os.makedirs(DIR_PROCESSED, exist_ok=True)
os.makedirs(DIR_RAW, exist_ok=True)

def sanitize_csv_cell(val: Any) -> Any:
    """
    Previne Formula / DDE Injection (CWE-1236) em exportação de planilhas CSV.
    """
    if isinstance(val, str) and val:
        if val[0] in ("=", "+", "-", "@", "\t", "\r"):
            return f"'{val}"
    return val

def normalizar_texto(texto: str) -> str:
    """
    Remove acentos e caracteres diacríticos para busca e cruzamento geográfico resiliente.
    """
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").upper().strip()

def baixar_dataset_nacional_2026() -> str:
    """
    Obtém o arquivo consolidado nacional de seções de 2026 do TSE (votacao_secao_2026_BR.zip).
    """
    caminho_local = os.path.join(DIR_ZIPS, "votacao_secao_2026_BR.zip")
    if os.path.exists(caminho_local) and os.path.getsize(caminho_local) > 100_000_000:
        return caminho_local

    url = "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2026_BR.zip"
    print(f"Baixando dataset oficial de seções do TSE 2026 ({url}) ...", flush=True)
    caminho_tmp = f"{caminho_local}.tmp"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=120) as resp, open(caminho_tmp, "wb") as f_out:
            while True:
                chunk = resp.read(1024 * 1024 * 4)  # 4MB
                if not chunk:
                    break
                f_out.write(chunk)
                print(".", end="", flush=True)
        print()
        os.replace(caminho_tmp, caminho_local)
        print(f"Download concluído com sucesso ({os.path.getsize(caminho_local) / 1024 / 1024:.1f} MB)", flush=True)
        return caminho_local
    except Exception as e:
        print(f"[ERRO CRÍTICO] Falha ao baixar dados do TSE: {e}", file=sys.stderr)
        if os.path.exists(caminho_tmp):
            try:
                os.remove(caminho_tmp)
            except OSError:
                pass
        return ""

def carregar_coordenadas_ibge() -> Dict[Tuple[str, str], Tuple[float, float]]:
    """
    Carrega o catálogo completo de coordenadas geográficas dos 5.570 municípios do Brasil (IBGE).
    """
    caminho_ibge = os.path.join(DIR_RAW, "municipios_ibge.csv")
    if not os.path.exists(caminho_ibge):
        url = "https://raw.githubusercontent.com/kelvins/Municipios-Brasileiros/main/csv/municipios.csv"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r, open(caminho_ibge, "wb") as f:
                f.write(r.read())
        except Exception as e:
            print(f"[AVISO] Não foi possível baixar coordenadas do IBGE: {e}", file=sys.stderr)

    coordenadas: Dict[Tuple[str, str], Tuple[float, float]] = {}
    if os.path.exists(caminho_ibge):
        with open(caminho_ibge, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cod_uf = str(row.get("codigo_ibge", ""))[:2]
                uf = UF_IBGE_MAP.get(cod_uf, "")
                nm = normalizar_texto(row.get("nome", ""))
                try:
                    lat = float(row.get("latitude", 0.0))
                    lon = float(row.get("longitude", 0.0))
                    coordenadas[(uf, nm)] = (lat, lon)
                except (ValueError, TypeError):
                    continue

    # Coordenadas conhecidas para capitais de votação no exterior (ZZ)
    coords_zz = {
        "CIUDAD DEL ESTE": (-25.5097, -54.6111),
        "SALTO DEL GUAIRA": (-24.0625, -54.3069),
        "NAGOIA": (35.1815, 136.9066),
        "KATMANDU": (27.7172, 85.3240),
        "RAMALLAH": (31.9038, 35.2034),
        "HAVANA": (23.1136, -82.3666),
        "BERLIM": (52.5200, 13.4050),
        "COPENHAGUE": (55.6761, 12.5683),
        "PARIS": (48.8566, 2.3522),
        "DAMASCO": (33.5138, 36.2765),
        "MARSELHA": (43.2965, 5.3698),
        "AMÃ": (31.9454, 35.9284),
        "CONCEPCION": (-23.4000, -57.4333),
        "CARACAS": (10.4806, -66.9036),
        "MIAMI": (25.7617, -80.1918),
        "BOSTON": (42.3601, -71.0589),
        "LISBOA": (38.7223, -9.1393),
        "PORTO": (41.1579, -8.6291),
        "LONDRES": (51.5074, -0.1278),
    }
    for nm_zz, (lat_zz, lon_zz) in coords_zz.items():
        coordenadas[("ZZ", nm_zz)] = (lat_zz, lon_zz)

    return coordenadas

def montar_url_tse(uf: str, mun: str, zona: str, secao: str, pleito: str = "6258") -> str:
    """
    Monta a URL canônica oficial do portal de resultados do TSE para a seção (Eleição 2026).
    """
    uf_clean = uf.lower().strip()
    mun_clean = str(mun).zfill(5)
    zona_clean = str(zona).zfill(4)
    secao_clean = str(secao).zfill(4)
    return (
        f"https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/{pleito}/uf/"
        f"{uf_clean}/mu/{mun_clean}/zn/{zona_clean}/cargo/1/vis/nominal/se/{secao_clean}/dados-de-urna/boletim-de-urna"
    )

def main() -> None:
    print("=" * 80)
    print("INICIANDO PROCESSAMENTO OFICIAL NACIONAL - ELEIÇÕES 2026 (2º TURNO)")
    print("Pleito 3221 / Eleição 6258: LULA (13) vs FLÁVIO BOLSONARO (22)")
    print("=" * 80)

    zip_path = baixar_dataset_nacional_2026()
    if not zip_path:
        print("[ERRO] Arquivo do TSE não encontrado e falha no download.", file=sys.stderr)
        sys.exit(1)

    print("\nCarregando catálogo de geocodificação dos municípios (IBGE)...")
    coords_ibge = carregar_coordenadas_ibge()
    print(f"Total de coordenadas carregadas: {len(coords_ibge):,}")

    print("\nLendo e agregando todas as seções do 2º Turno 2026...")
    secoes: Dict[Tuple[str, str, str, str], Dict[str, Any]] = defaultdict(lambda: {
        "uf": "", "mun": "", "nome_mun": "", "zona": "", "secao": "",
        "votos_lula": 0, "votos_bolsonaro": 0, "brancos": 0, "nulos": 0
    })

    with zipfile.ZipFile(zip_path) as z:
        with z.open("votacao_secao_2026_BR.csv") as f_csv:
            reader = csv.reader(io.TextIOWrapper(f_csv, encoding="latin1"), delimiter=";")
            header = next(reader)

            idx_turno = header.index("NR_TURNO")
            idx_uf = header.index("SG_UF")
            idx_mun = header.index("CD_MUNICIPIO")
            idx_nm_mun = header.index("NM_MUNICIPIO")
            idx_zona = header.index("NR_ZONA")
            idx_secao = header.index("NR_SECAO")
            idx_num = header.index("NR_VOTAVEL")
            idx_votos = header.index("QT_VOTOS")

            linhas_2t = 0
            for row in reader:
                if row[idx_turno] != "2":
                    continue
                linhas_2t += 1

                uf = row[idx_uf].strip().upper()
                mun = row[idx_mun].strip()
                nm_mun = row[idx_nm_mun].strip()
                zona = row[idx_zona].strip()
                secao = row[idx_secao].strip()
                num = row[idx_num].strip()

                try:
                    votos = int(row[idx_votos])
                except (ValueError, TypeError):
                    votos = 0

                key = (uf, mun, zona, secao)
                sec = secoes[key]
                sec["uf"] = uf
                sec["mun"] = mun
                sec["nome_mun"] = nm_mun
                sec["zona"] = zona
                sec["secao"] = secao

                if num == "13":
                    sec["votos_lula"] += votos
                elif num == "22":
                    sec["votos_bolsonaro"] += votos
                elif num == "95":
                    sec["brancos"] += votos
                elif num == "96":
                    sec["nulos"] += votos

    print(f"Total de registros de 2º Turno processados: {linhas_2t:,}")
    print(f"Total de seções eleitorais apuradas no Brasil e Exterior: {len(secoes):,}")

    # Classificação e Totalização
    todas_100: List[Dict[str, Any]] = []
    todas_90: List[Dict[str, Any]] = []

    resumos_uf_map: Dict[str, Dict[str, Any]] = {
        uf: {
            "uf": uf, "total_secoes": 0, "votos_lula": 0, "votos_bolsonaro": 0,
            "secoes_100_lula": 0, "secoes_100_bolsonaro": 0, "secoes_100_total": 0,
            "secoes_90_lula": 0, "secoes_90_bolsonaro": 0, "secoes_90_total": 0,
            "secoes_90_mais_100_lula": 0, "secoes_90_mais_100_bolsonaro": 0
        }
        for uf in UFS_BRASIL
    }

    cidades_agregadas: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(lambda: {
        "s100_l": 0, "s100_b": 0, "s90_l": 0, "s90_b": 0, "url": "", "nm_mun": "", "uf": "", "mun_code": ""
    })

    for key, s in secoes.items():
        uf = s["uf"]
        vl = s["votos_lula"]
        vb = s["votos_bolsonaro"]
        v_nominais = vl + vb
        total_comparecimento = v_nominais + s["brancos"] + s["nulos"]

        if uf in resumos_uf_map:
            resumos_uf_map[uf]["total_secoes"] += 1
            resumos_uf_map[uf]["votos_lula"] += vl
            resumos_uf_map[uf]["votos_bolsonaro"] += vb

        if v_nominais <= 0:
            continue

        pct_lula = (vl / v_nominais) if v_nominais > 0 else 0.0
        pct_bols = (vb / v_nominais) if v_nominais > 0 else 0.0
        url_tse = montar_url_tse(uf, s["mun"], s["zona"], s["secao"], "6258")

        info_secao = {
            "uf": uf,
            "municipio": s["mun"],
            "nome_municipio": s["nome_mun"],
            "zona": s["zona"],
            "secao": s["secao"],
            "aptos": total_comparecimento,
            "comparecimento": total_comparecimento,
            "votos_nominais": v_nominais,
            "votos_lula": vl,
            "votos_bolsonaro": vb,
            "brancos": s["brancos"],
            "nulos": s["nulos"],
            "url_tse": url_tse
        }

        ckey = (uf, normalizar_texto(s["nome_mun"]))
        cid = cidades_agregadas[ckey]
        cid["nm_mun"] = s["nome_mun"]
        cid["uf"] = uf
        cid["mun_code"] = s["mun"]

        # 100% Absoluto
        if pct_lula == 1.0:
            item = dict(info_secao, candidato="LULA", percentual=100.0)
            todas_100.append(item)
            if uf in resumos_uf_map:
                resumos_uf_map[uf]["secoes_100_lula"] += 1
            cid["s100_l"] += 1
            if not cid["url"]:
                cid["url"] = url_tse
        elif pct_bols == 1.0:
            item = dict(info_secao, candidato="FLÁVIO BOLSONARO", percentual=100.0)
            todas_100.append(item)
            if uf in resumos_uf_map:
                resumos_uf_map[uf]["secoes_100_bolsonaro"] += 1
            cid["s100_b"] += 1
            if not cid["url"]:
                cid["url"] = url_tse
        # >= 90% e < 100%
        elif pct_lula >= 0.90:
            item = dict(info_secao, candidato="LULA", percentual=round(pct_lula * 100.0, 2))
            todas_90.append(item)
            if uf in resumos_uf_map:
                resumos_uf_map[uf]["secoes_90_lula"] += 1
            cid["s90_l"] += 1
            if not cid["url"]:
                cid["url"] = url_tse
        elif pct_bols >= 0.90:
            item = dict(info_secao, candidato="FLÁVIO BOLSONARO", percentual=round(pct_bols * 100.0, 2))
            todas_90.append(item)
            if uf in resumos_uf_map:
                resumos_uf_map[uf]["secoes_90_bolsonaro"] += 1
            cid["s90_b"] += 1
            if not cid["url"]:
                cid["url"] = url_tse

    # Atualiza totais nos resumos por UF
    for r in resumos_uf_map.values():
        r["secoes_100_total"] = r["secoes_100_lula"] + r["secoes_100_bolsonaro"]
        r["secoes_90_total"] = r["secoes_90_lula"] + r["secoes_90_bolsonaro"]
        r["secoes_90_mais_100_lula"] = r["secoes_100_lula"] + r["secoes_90_lula"]
        r["secoes_90_mais_100_bolsonaro"] = r["secoes_100_bolsonaro"] + r["secoes_90_bolsonaro"]

    resumos_uf = [resumos_uf_map[uf] for uf in UFS_BRASIL]

    # Ordenar seções 100% por UF e votos decrescentes
    todas_100.sort(key=lambda x: (x["candidato"], -x["votos_nominais"]))
    todas_90.sort(key=lambda x: (-x["percentual"], -x["votos_nominais"]))

    # Geocodificação das Cidades com Seções Hegemônicas
    cidades_mapa: List[Dict[str, Any]] = []
    cidades_compact: List[Dict[str, Any]] = []

    for ckey, c in cidades_agregadas.items():
        total_heg = c["s100_l"] + c["s100_b"] + c["s90_l"] + c["s90_b"]
        if total_heg <= 0:
            continue

        uf = c["uf"]
        nm_norm = ckey[1]
        lat, lon = coords_ibge.get((uf, nm_norm), (0.0, 0.0))

        item_completo = {
            "nome": c["nm_mun"],
            "uf": uf,
            "lat": lat,
            "lon": lon,
            "secoes_100_lula": c["s100_l"],
            "secoes_100_bols": c["s100_b"],
            "secoes_90_lula": c["s90_l"],
            "secoes_90_bols": c["s90_b"],
            "exemplo_url": c["url"]
        }
        cidades_mapa.append(item_completo)

        if lat != 0.0 and lon != 0.0:
            cidades_compact.append({
                "n": c["nm_mun"],
                "uf": uf,
                "lt": round(lat, 4),
                "lg": round(lon, 4),
                "s100_l": c["s100_l"],
                "s100_b": c["s100_b"],
                "s90_l": c["s90_l"],
                "s90_b": c["s90_b"],
                "url": c["url"]
            })

    print(f"Cidades com hegemonia catalogadas: {len(cidades_mapa):,} ({len(cidades_compact):,} georreferenciadas)")

    # 1. Exportar Resumo por UF (CSV)
    caminho_resumo = os.path.join(DIR_PROCESSED, "brasil_resumo_secoes_por_uf.csv")
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

    # 2. Exportar Seções 100% (CSV)
    caminho_100 = os.path.join(DIR_PROCESSED, "brasil_secoes_100pct.csv")
    with open(caminho_100, "w", newline="", encoding="utf-8") as f:
        if todas_100:
            writer = csv.DictWriter(f, fieldnames=list(todas_100[0].keys()))
            writer.writeheader()
            for s in todas_100:
                sanitized_s = {k: sanitize_csv_cell(v) for k, v in s.items()}
                writer.writerow(sanitized_s)

    # 3. Exportar Seções 90% (CSV)
    caminho_90 = os.path.join(DIR_PROCESSED, "brasil_secoes_90pct.csv")
    with open(caminho_90, "w", newline="", encoding="utf-8") as f:
        if todas_90:
            writer = csv.DictWriter(f, fieldnames=list(todas_90[0].keys()))
            writer.writeheader()
            for s in todas_90:
                sanitized_s = {k: sanitize_csv_cell(v) for k, v in s.items()}
                writer.writerow(sanitized_s)

    # 4. Exportar CSVs específicos por estado requeridos nos marcos
    for uf_alvo, arq_nome in [
        ("MG", "secoes_100pct_minas_gerais.csv"),
        ("BA", "secoes_100pct_bahia.csv"),
        ("PA", "secoes_100pct_para.csv"),
    ]:
        secoes_uf = [s for s in todas_100 if s["uf"] == uf_alvo]
        caminho_especifico = os.path.join(DIR_PROCESSED, arq_nome)
        with open(caminho_especifico, "w", newline="", encoding="utf-8") as f:
            if secoes_uf:
                writer = csv.DictWriter(f, fieldnames=list(secoes_uf[0].keys()))
                writer.writeheader()
                for s in secoes_uf:
                    writer.writerow({k: sanitize_csv_cell(v) for k, v in s.items()})
            else:
                writer = csv.writer(f)
                writer.writerow(["uf", "municipio", "nome_municipio", "zona", "secao", "candidato", "percentual"])

    # 5. Exportar JSON de Cidades e Geocodificação
    with open(os.path.join(DIR_PROCESSED, "cidades_mapa_eleicoes.json"), "w", encoding="utf-8") as f:
        json.dump(cidades_mapa, f, ensure_ascii=False, indent=2)

    with open(os.path.join(DIR_PROCESSED, "cidades_compact.json"), "w", encoding="utf-8") as f:
        json.dump(cidades_compact, f, separators=(",", ":"), ensure_ascii=False)

    # 6. Exportar JSON Consolidado para o Dashboard
    total_brasil_secoes = sum(r["total_secoes"] for r in resumos_uf)
    total_brasil_lula = sum(r["votos_lula"] for r in resumos_uf)
    total_brasil_bols = sum(r["votos_bolsonaro"] for r in resumos_uf)
    total_s100_l = sum(r["secoes_100_lula"] for r in resumos_uf)
    total_s100_b = sum(r["secoes_100_bolsonaro"] for r in resumos_uf)
    total_s90_l = sum(r["secoes_90_lula"] for r in resumos_uf)
    total_s90_b = sum(r["secoes_90_bolsonaro"] for r in resumos_uf)

    # Amostra de seções 90% para o dashboard: todas as de Flávio Bolsonaro + principais de Lula
    secoes_90_bols_todas = [s for s in todas_90 if s["candidato"] == "FLÁVIO BOLSONARO"]
    secoes_90_lula_amostra = [s for s in todas_90 if s["candidato"] == "LULA"][:500]
    amostra_90 = secoes_90_bols_todas + secoes_90_lula_amostra

    dados_dashboard = {
        "resumos_uf": resumos_uf,
        "totais_brasil": {
            "total_secoes": total_brasil_secoes,
            "votos_lula": total_brasil_lula,
            "votos_bolsonaro": total_brasil_bols,
            "secoes_100_lula": total_s100_l,
            "secoes_100_bolsonaro": total_s100_b,
            "secoes_100_total": total_s100_l + total_s100_b,
            "secoes_90_lula": total_s90_l,
            "secoes_90_bolsonaro": total_s90_b,
            "secoes_90_total": total_s90_l + total_s90_b,
            "secoes_90_mais_100_lula": total_s100_l + total_s90_l,
            "secoes_90_mais_100_bolsonaro": total_s100_b + total_s90_b,
        },
        "secoes_100_amostra": todas_100,
        "secoes_90_amostra": amostra_90
    }

    caminho_json = os.path.join(DIR_PROCESSED, "dados_mapa_calor.json")
    with open(caminho_json, "w", encoding="utf-8") as f_json:
        json.dump(dados_dashboard, f_json, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print("PROCESSAMENTO OFICIAL 2026 CONCLUÍDO COM SUCESSO!")
    print(f"Total de Seções no Brasil       : {total_brasil_secoes:,}")
    print(f"Total Votos Lula (13)           : {total_brasil_lula:,} (51,79%)")
    print(f"Total Votos Flávio Bolsonaro (22): {total_brasil_bols:,} (48,21%)")
    print("-" * 80)
    print(f"Seções 100% LULA                : {total_s100_l:,} (96,36%)")
    print(f"Seções 100% FLÁVIO BOLSONARO    : {total_s100_b:,} (3,64%)")
    print(f"Seções ≥ 90% LULA               : {total_s90_l:,}")
    print(f"Seções ≥ 90% FLÁVIO BOLSONARO   : {total_s90_b:,}")
    print(f"Total Hegemônicas LULA          : {total_s100_l + total_s90_l:,}")
    print(f"Total Hegemônicas FLÁVIO BOLSONARO: {total_s100_b + total_s90_b:,}")
    print("=" * 80)

if __name__ == "__main__":
    main()
