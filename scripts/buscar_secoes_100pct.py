#!/usr/bin/env python3
"""
Buscador de Seções Eleitorais com 100% de Votos para um Único Candidato (TSE 2026)
Suporta 1º Turno (Eleição 6257) e 2º Turno (Eleição 6258).
Permite filtragem ágil por UF e consulta direta dos Boletins de Urna no Portal Oficial do TSE.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import zipfile
from collections import defaultdict
from typing import Any, Dict, List, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
DIR_PROCESSED = os.path.join(ROOT_DIR, "data", "processed")
DIR_ZIPS = os.path.join(ROOT_DIR, "data", "zips", "tse")


def montar_url_portal_tse(uf: str, cod_mun: str, zona: str, secao: str, pleito: str = "6258") -> str:
    """
    Gera a URL oficial interativa do portal Resultados do TSE para o Boletim de Urna da seção.
    """
    uf_clean = uf.lower().strip()
    cod_mun_clean = str(cod_mun).zfill(5)
    zona_clean = str(zona).zfill(4)
    secao_clean = str(secao).zfill(4)
    return (
        f"https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/{pleito}/uf/"
        f"{uf_clean}/mu/{cod_mun_clean}/zn/{zona_clean}/cargo/1/vis/nominal/se/{secao_clean}/dados-de-urna/boletim-de-urna"
    )


def buscar_secoes_processadas(filtro_uf: Optional[str] = None, turno: str = "2") -> List[Dict[str, Any]]:
    """
    Consulta o dataset pré-processado para retorno ultrarrápido das seções 100% do turno selecionado.
    """
    sufixo = "1t" if turno == "1" else "2t"
    caminho_csv = os.path.join(DIR_PROCESSED, f"brasil_secoes_100pct_{sufixo}.csv")
    if not os.path.exists(caminho_csv):
        caminho_csv = os.path.join(DIR_PROCESSED, "brasil_secoes_100pct.csv")

    if not os.path.exists(caminho_csv):
        return []

    resultados: List[Dict[str, Any]] = []
    with open(caminho_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            uf = row.get("uf", "").strip().upper()
            if filtro_uf and uf != filtro_uf.upper():
                continue
            votos_str = row.get("votos_nominais", "0")
            try:
                votos = int(votos_str)
            except ValueError:
                votos = 0
            resultados.append({
                "uf": uf,
                "cod_municipio": row.get("municipio", ""),
                "nome_municipio": row.get("nome_municipio", ""),
                "zona": row.get("zona", ""),
                "secao": row.get("secao", ""),
                "candidato": row.get("candidato", ""),
                "votos": votos,
                "brancos": row.get("brancos", "0"),
                "nulos": row.get("nulos", "0"),
                "url_tse": row.get("url_tse", "")
            })
    return resultados


def analisar_bweb_arquivo(
    caminho_zip_ou_csv: str,
    cargo_filtro: str = "1",
    filtro_uf: Optional[str] = None,
    turno_filtro: str = "2"
) -> List[Dict[str, Any]]:
    """
    Varre o arquivo bruto de seções eleitorais do TSE (1º ou 2º Turno 2026) e encontra seções 100%.
    """
    if not os.path.exists(caminho_zip_ou_csv):
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_zip_ou_csv}")

    secoes = defaultdict(lambda: {
        "uf": "", "municipio": "", "nome_municipio": "", "zona": "", "secao": "",
        "votos_candidatos": defaultdict(int), "brancos": 0, "nulos": 0, "total_nominais": 0
    })

    def processar_leitor(reader: Any, colunas: List[str]) -> None:
        idx_cargo = colunas.index("CD_CARGO_PERGUNTA") if "CD_CARGO_PERGUNTA" in colunas else (colunas.index("CD_CARGO") if "CD_CARGO" in colunas else -1)
        idx_uf = colunas.index("SG_UF") if "SG_UF" in colunas else -1
        idx_mun = colunas.index("CD_MUNICIPIO") if "CD_MUNICIPIO" in colunas else -1
        idx_nom_mun = colunas.index("NM_MUNICIPIO") if "NM_MUNICIPIO" in colunas else None
        idx_zona = colunas.index("NR_ZONA") if "NR_ZONA" in colunas else -1
        idx_secao = colunas.index("NR_SECAO") if "NR_SECAO" in colunas else -1
        idx_cand = colunas.index("NM_VOTAVEL") if "NM_VOTAVEL" in colunas else (colunas.index("NR_VOTAVEL") if "NR_VOTAVEL" in colunas else -1)
        idx_num = colunas.index("NR_VOTAVEL") if "NR_VOTAVEL" in colunas else -1
        idx_votos = colunas.index("QT_VOTOS") if "QT_VOTOS" in colunas else -1
        idx_turno = colunas.index("NR_TURNO") if "NR_TURNO" in colunas else None

        if any(i < 0 for i in (idx_cargo, idx_uf, idx_mun, idx_zona, idx_secao, idx_cand, idx_votos)):
            return

        for linha in reader:
            if not linha or len(linha) <= max(idx_cargo, idx_uf, idx_votos):
                continue
            if linha[idx_cargo] != cargo_filtro:
                continue
            if idx_turno is not None and len(linha) > idx_turno:
                if linha[idx_turno] != turno_filtro:
                    continue

            uf = linha[idx_uf].strip().upper()
            if filtro_uf and uf != filtro_uf.upper():
                continue

            mun = linha[idx_mun].strip()
            nome_mun = linha[idx_nom_mun].strip() if idx_nom_mun is not None and len(linha) > idx_nom_mun else ""
            zona = linha[idx_zona].strip()
            secao = linha[idx_secao].strip()

            nome_cand = linha[idx_cand].strip().upper()
            num_votavel = linha[idx_num].strip() if idx_num >= 0 and len(linha) > idx_num else ""
            try:
                qt_votos = int(linha[idx_votos])
            except (ValueError, TypeError):
                qt_votos = 0

            chave = (uf, mun, zona, secao)
            sec = secoes[chave]
            sec["uf"] = uf
            sec["municipio"] = mun
            sec["nome_municipio"] = nome_mun
            sec["zona"] = zona
            sec["secao"] = secao

            if "BRANCO" in nome_cand or num_votavel == "95":
                sec["brancos"] += qt_votos
            elif "NULO" in nome_cand or num_votavel == "96":
                sec["nulos"] += qt_votos
            else:
                rotulo = "LULA" if num_votavel == "13" else ("FLÁVIO BOLSONARO" if num_votavel == "22" else nome_cand)
                sec["votos_candidatos"][rotulo] += qt_votos
                sec["total_nominais"] += qt_votos

    try:
        if caminho_zip_ou_csv.endswith(".zip"):
            with zipfile.ZipFile(caminho_zip_ou_csv, "r") as z:
                for nome_arq in z.namelist():
                    if nome_arq.endswith(".csv"):
                        with z.open(nome_arq) as f:
                            text_f = io.TextIOWrapper(f, encoding="latin-1")
                            reader = csv.reader(text_f, delimiter=";")
                            header = next(reader)
                            processar_leitor(reader, header)
        else:
            with open(caminho_zip_ou_csv, "r", encoding="latin-1") as f:
                reader = csv.reader(f, delimiter=";")
                header = next(reader)
                processar_leitor(reader, header)
    except (zipfile.BadZipFile, OSError) as e:
        print(f"[ERRO] Falha ao processar arquivo: {e}", file=sys.stderr)
        return []

    pleito_tse = "6257" if turno_filtro == "1" else "6258"
    secoes_100 = []
    for chave, dados in secoes.items():
        if dados["total_nominais"] > 0 and len(dados["votos_candidatos"]) == 1:
            candidato_unico, votos = list(dados["votos_candidatos"].items())[0]
            url = montar_url_portal_tse(dados["uf"], dados["municipio"], dados["zona"], dados["secao"], pleito_tse)
            secoes_100.append({
                "uf": dados["uf"],
                "cod_municipio": dados["municipio"],
                "nome_municipio": dados["nome_municipio"],
                "zona": dados["zona"],
                "secao": dados["secao"],
                "candidato": candidato_unico,
                "votos": votos,
                "brancos": dados["brancos"],
                "nulos": dados["nulos"],
                "url_tse": url
            })

    return sorted(secoes_100, key=lambda x: (x["uf"], x["nome_municipio"], x["secao"]))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Buscador de Seções Eleitorais 100% Absolutas - Eleições 2026 (TSE)"
    )
    parser.add_argument(
        "alvo", nargs="?", default="",
        help="Sigla da UF (ex: PA, RS, MG, BA), ou caminho de arquivo .zip/.csv, ou vazio para ver o Brasil"
    )
    parser.add_argument(
        "--turno", "-t", choices=["1", "2"], default="2",
        help="Turno da eleição (1 = 1º Turno [6257], 2 = 2º Turno [6258], padrão: 2)"
    )
    parser.add_argument(
        "--raw", action="store_true",
        help="Força reprocessamento direto do arquivo zip de seções do TSE em vez do CSV processado"
    )

    args = parser.parse_args()
    turno = args.turno
    alvo = args.alvo.strip()
    pleito = "6257" if turno == "1" else "6258"

    filtro_uf: Optional[str] = None
    arquivo_custom: Optional[str] = None

    if alvo:
        if len(alvo) == 2 and alvo.isalpha():
            filtro_uf = alvo.upper()
        elif os.path.exists(alvo):
            arquivo_custom = alvo
        elif alvo.upper() in ("BR", "BRASIL", "TODOS", "ALL"):
            filtro_uf = None
        else:
            filtro_uf = alvo.upper()

    print("=" * 80)
    print(f"AUDITORIA ELEITORAL TSE 2026 - SEÇÕES 100% ABSOLUTAS ({turno}º TURNO • PLEITO {pleito})")
    if filtro_uf:
        print(f"Filtro aplicado: UF = {filtro_uf}")
    else:
        print("Filtro aplicado: Brasil Completo (Todas as 28 UFs)")
    print("=" * 80)

    # 1. Tentar leitura do CSV processado (ultrarrápido)
    resultados: List[Dict[str, Any]] = []
    if not args.raw and not arquivo_custom:
        resultados = buscar_secoes_processadas(filtro_uf=filtro_uf, turno=turno)

    # 2. Se não encontrou ou flag raw / arquivo customizado especificado, varre o zip
    if not resultados or args.raw or arquivo_custom:
        zip_padrao = os.path.join(DIR_ZIPS, "votacao_secao_2026_BR.zip")
        arq_alvo = arquivo_custom if arquivo_custom else zip_padrao
        if os.path.exists(arq_alvo):
            print(f"Processando arquivo bruto do TSE: {arq_alvo} ...")
            resultados = analisar_bweb_arquivo(arq_alvo, filtro_uf=filtro_uf, turno_filtro=turno)

    print(f"\nTotal de seções encontradas com 100% dos votos nominais no {turno}º Turno: {len(resultados)}")
    for r in resultados:
        print(f"[{r['uf']}] {r['nome_municipio']} (Cód: {r['cod_municipio']}) - Zona {r['zona']}, Seção {r['secao']}")
        print(f"  • Candidato: {r['candidato']} ({r['votos']} votos - 100% nominais | Brancos: {r['brancos']} | Nulos: {r['nulos']})")
        print(f"  • URL Boletim de Urna: {r['url_tse']}\n")


if __name__ == "__main__":
    main()
