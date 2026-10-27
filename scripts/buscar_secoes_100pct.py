#!/usr/bin/env python3
"""
Buscador de Seções Eleitorais com 100% de Votos para um Único Candidato (TSE 2026)
Processa arquivos consolidados de Boletim de Urna (BWEB) e Votação por Seção do TSE.
"""

from __future__ import annotations

import csv
import io
import os
import sys
import zipfile
from collections import defaultdict
from typing import Any, Dict, List, Optional

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

def analisar_bweb_arquivo(
    caminho_zip_ou_csv: str,
    cargo_filtro: str = "1",
    filtro_uf: Optional[str] = None,
    turno_filtro: str = "2"
) -> List[Dict[str, Any]]:
    """
    Lê o arquivo de seções eleitorais do TSE (2º Turno 2026) e encontra seções 100%.
    Cargo '1' = Presidente.
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
        idx_tipo = colunas.index("DS_TIPO_VOTAVEL") if "DS_TIPO_VOTAVEL" in colunas else None
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
            cand = linha[idx_cand].strip()
            num = linha[idx_num].strip() if idx_num >= 0 and len(linha) > idx_num else ""

            # Padroniza nomes para 2026
            if num == "13" or "LULA" in cand.upper():
                cand_nome = "LULA"
            elif num == "22" or "BOLSONARO" in cand.upper():
                cand_nome = "FLÁVIO BOLSONARO"
            else:
                cand_nome = cand

            try:
                qtd = int(linha[idx_votos])
            except (ValueError, TypeError):
                qtd = 0

            tipo = linha[idx_tipo].lower() if idx_tipo is not None and len(linha) > idx_tipo else ""

            chave = (uf, mun, zona, secao)
            sec = secoes[chave]
            sec["uf"] = uf
            sec["municipio"] = mun
            sec["nome_municipio"] = nome_mun
            sec["zona"] = zona
            sec["secao"] = secao

            if "branco" in tipo or cand.lower() == "branco" or num == "95":
                sec["brancos"] += qtd
            elif "nulo" in tipo or cand.lower() == "nulo" or num == "96":
                sec["nulos"] += qtd
            else:
                sec["votos_candidatos"][cand_nome] += qtd
                sec["total_nominais"] += qtd

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

    # Filtrar seções 100%
    secoes_100 = []
    for chave, dados in secoes.items():
        if dados["total_nominais"] > 0 and len(dados["votos_candidatos"]) == 1:
            candidato_unico, votos = list(dados["votos_candidatos"].items())[0]
            url = montar_url_portal_tse(dados["uf"], dados["municipio"], dados["zona"], dados["secao"], "6258")
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

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 buscar_secoes_100pct.py <UF (ex: PA, RS, BA) ou caminho_do_arquivo.zip>")
        print("\nExemplos:")
        print("  python3 scripts/buscar_secoes_100pct.py PA")
        print("  python3 scripts/buscar_secoes_100pct.py data/zips/tse/votacao_secao_2026_BR.zip")
        sys.exit(0)

    arg = sys.argv[1]
    filtro_uf: Optional[str] = None
    arquivo = arg

    if not os.path.exists(arquivo):
        # Se for sigla de UF (2 letras)
        if len(arg) == 2 and arg.isalpha():
            filtro_uf = arg.upper()
            candidatos = [
                os.path.join("data", "zips", "tse", "votacao_secao_2026_BR.zip"),
                os.path.join("..", "data", "zips", "tse", "votacao_secao_2026_BR.zip"),
            ]
            for c in candidatos:
                if os.path.exists(c):
                    arquivo = c
                    break
        else:
            for c in [
                os.path.join("data", "zips", "tse", arg),
                os.path.join("..", "data", "zips", "tse", arg),
            ]:
                if os.path.exists(c):
                    arquivo = c
                    break

    if not os.path.exists(arquivo):
        print(f"[ERRO] Arquivo de dados não encontrado: {arg}")
        sys.exit(1)

    print(f"Analisando arquivo: {arquivo}" + (f" (Filtro UF: {filtro_uf})" if filtro_uf else "") + " ...")
    resultados = analisar_bweb_arquivo(arquivo, filtro_uf=filtro_uf)
    print(f"\nTotal de seções encontradas com 100% dos votos nominais: {len(resultados)}")
    for r in resultados:
        print(f"[{r['uf']}] {r['nome_municipio']} (Cód: {r['cod_municipio']}) - Zona {r['zona']}, Seção {r['secao']}")
        print(f"  • Candidato: {r['candidato']} ({r['votos']} votos - 100% nominais | Brancos: {r['brancos']} | Nulos: {r['nulos']})")
        print(f"  • URL Boletim de Urna: {r['url_tse']}\n")
