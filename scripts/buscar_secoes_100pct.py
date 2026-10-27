#!/usr/bin/env python3
"""
Buscador de Seções Eleitorais com 100% de Votos para um Único Candidato (TSE)
Processa arquivos consolidados de Boletim de Urna (BWEB) dos Dados Abertos do TSE.
"""

import os
import sys
import csv
import zipfile
import urllib.request
from collections import defaultdict

URL_BASE_DADOS_ABERTOS = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2022/buweb/bweb_2t_{uf}_311020221535.zip"

def montar_url_portal_tse(uf: str, cod_mun: str, zona: str, secao: str, pleito: str = "6258") -> str:
    """
    Gera a URL oficial interativa do portal Resultados do TSE para o Boletim de Urna da seção.
    """
    uf = uf.lower()
    cod_mun = str(cod_mun).zfill(5)
    zona = str(zona).zfill(4)
    secao = str(secao).zfill(4)
    return f"https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/{pleito}/uf/{uf}/mu/{cod_mun}/zn/{zona}/cargo/1/vis/nominal/se/{secao}/dados-de-urna/boletim-de-urna"

def analisar_bweb_arquivo(caminho_zip_ou_csv: str, cargo_filtro: str = "1"):
    """
    Lê o arquivo BWEB (Boletim de Urna na Web) do 2º turno do TSE e encontra seções 100%.
    Cargo '1' = Presidente.
    """
    secoes = defaultdict(lambda: {
        "uf": "", "municipio": "", "nome_municipio": "", "zona": "", "secao": "",
        "votos_candidatos": defaultdict(int), "brancos": 0, "nulos": 0, "total_nominais": 0
    })

    def processar_leitor(reader, colunas):
        idx_cargo = colunas.index("CD_CARGO_PERGUNTA") if "CD_CARGO_PERGUNTA" in colunas else colunas.index("CD_CARGO")
        idx_uf = colunas.index("SG_UF")
        idx_mun = colunas.index("CD_MUNICIPIO")
        idx_nom_mun = colunas.index("NM_MUNICIPIO") if "NM_MUNICIPIO" in colunas else None
        idx_zona = colunas.index("NR_ZONA")
        idx_secao = colunas.index("NR_SECAO")
        idx_cand = colunas.index("NM_VOTAVEL") if "NM_VOTAVEL" in colunas else colunas.index("NR_VOTAVEL")
        idx_votos = colunas.index("QT_VOTOS")
        idx_tipo = colunas.index("DS_TIPO_VOTAVEL") if "DS_TIPO_VOTAVEL" in colunas else None

        for linha in reader:
            if not linha or len(linha) <= max(idx_cargo, idx_uf, idx_votos):
                continue
            cargo = linha[idx_cargo]
            if cargo != cargo_filtro:
                continue

            uf = linha[idx_uf]
            mun = linha[idx_mun]
            nome_mun = linha[idx_nom_mun] if idx_nom_mun else ""
            zona = linha[idx_zona]
            secao = linha[idx_secao]
            cand = linha[idx_cand]
            qtd = int(linha[idx_votos])
            tipo = linha[idx_tipo].lower() if idx_tipo else ""

            chave = (uf, mun, zona, secao)
            sec = secoes[chave]
            sec["uf"] = uf
            sec["municipio"] = mun
            sec["nome_municipio"] = nome_mun
            sec["zona"] = zona
            sec["secao"] = secao

            if "branco" in tipo or cand.lower() == "branco":
                sec["brancos"] += qtd
            elif "nulo" in tipo or cand.lower() == "nulo":
                sec["nulos"] += qtd
            else:
                sec["votos_candidatos"][cand] += qtd
                sec["total_nominais"] += qtd

    if caminho_zip_ou_csv.endswith(".zip"):
        with zipfile.ZipFile(caminho_zip_ou_csv, "r") as z:
            for nome_arq in z.namelist():
                if nome_arq.endswith(".csv"):
                    with z.open(nome_arq) as f:
                        import io
                        text_f = io.TextIOWrapper(f, encoding="latin-1")
                        reader = csv.reader(text_f, delimiter=";")
                        header = next(reader)
                        processar_leitor(reader, header)
    else:
        with open(caminho_zip_ou_csv, "r", encoding="latin-1") as f:
            reader = csv.reader(f, delimiter=";")
            header = next(reader)
            processar_leitor(reader, header)

    # Filtrar seções 100%
    secoes_100 = []
    for chave, dados in secoes.items():
        if dados["total_nominais"] > 0 and len(dados["votos_candidatos"]) == 1:
            candidato_unico, votos = list(dados["votos_candidatos"].items())[0]
            url = montar_url_portal_tse(dados["uf"], dados["municipio"], dados["zona"], dados["secao"])
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
        print("Uso: python3 buscar_secoes_100pct.py <arquivo_bweb.zip ou UF (ex: BA, MG, PA)>")
        print("\nPara analisar dados do TSE de um estado já baixado:")
        print("  python3 scripts/buscar_secoes_100pct.py BA")
        print("  python3 scripts/buscar_secoes_100pct.py data/zips/tse/bweb_2t_BA_311020221535.zip")
        sys.exit(0)

    arg = sys.argv[1]
    arquivo = arg
    if not os.path.exists(arquivo):
        uf_upper = arg.upper()
        candidatos = [
            os.path.join("data", "zips", "tse", f"bweb_2t_{uf_upper}_311020221535.zip"),
            os.path.join("..", "data", "zips", "tse", f"bweb_2t_{uf_upper}_311020221535.zip"),
            os.path.join("data", "zips", "tse", arg),
            os.path.join("..", "data", "zips", "tse", arg),
        ]
        for c in candidatos:
            if os.path.exists(c):
                arquivo = c
                break

    if not os.path.exists(arquivo):
        print(f"[ERRO] Arquivo não encontrado: {arg}")
        sys.exit(1)

    print(f"Analisando arquivo: {arquivo} ...")
    resultados = analisar_bweb_arquivo(arquivo)
    print(f"\nTotal de seções encontradas com 100% dos votos nominais: {len(resultados)}")
    for r in resultados:
        print(f"[{r['uf']}] {r['nome_municipio']} (Cód: {r['cod_municipio']}) - Zona {r['zona']}, Seção {r['secao']}")
        print(f"  • Candidato: {r['candidato']} ({r['votos']} votos - 100% nominais | Brancos: {r['brancos']} | Nulos: {r['nulos']})")
        print(f"  • URL Boletim de Urna: {r['url_tse']}\n")
