#!/usr/bin/env python3
"""
Leitor e Analisador de Log de Urna Eletrônica (.jez / logd.dat) - TSE
Compatível com logs oficiais do Tribunal Superior Eleitoral.
"""

from __future__ import annotations

import csv
import os
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

def sanitize_csv_cell(val: Any) -> Any:
    """
    Previne Formula / DDE Injection (CWE-1236) em células exportadas para CSV.
    """
    if isinstance(val, str) and val:
        if val[0] in ("=", "+", "-", "@", "\t", "\r"):
            return f"'{val}"
    return val

class LogUrnaParser:
    """
    Parser para arquivos de Log de Urna do TSE (.jez contendo logd.dat).
    """

    COLUNAS = ["data_hora", "nivel", "id_processo", "modulo", "mensagem", "hash_linha"]

    def __init__(self, caminho_arquivo: str):
        self.caminho_arquivo = os.path.abspath(caminho_arquivo)
        if not os.path.exists(self.caminho_arquivo):
            raise FileNotFoundError(f"Arquivo não encontrado: {self.caminho_arquivo}")
        self.metadados = self._extrair_metadados_nome()

    def _extrair_metadados_nome(self) -> Dict[str, str]:
        """
        Interpreta o padrão de nomenclatura oficial do TSE:
        Exemplo: o03221mg4100900500224-log.jez
        - 'o': Tipo de arquivo / oficial
        - '03221': Código do pleito / eleição
        - 'mg': UF (Estado)
        - '41009': Código do município no TSE
        - '0050': Zona Eleitoral
        - '0224': Seção Eleitoral
        """
        nome = os.path.basename(self.caminho_arquivo)
        padrao = r"^(?P<tipo>[a-zA-Z])(?P<pleito>\d{5})(?P<uf>[a-zA-Z]{2})(?P<municipio>\d{5})(?P<zona>\d{4})(?P<secao>\d{4})-log\.jez$"
        match = re.match(padrao, nome)
        if match:
            return match.groupdict()
        return {}

    def iterar_linhas(self) -> Generator[Dict[str, Any], None, None]:
        """
        Gera as linhas do arquivo logd.dat decodificadas como ISO-8859-1.
        Não requer extração prévia para o disco.
        """
        try:
            with zipfile.ZipFile(self.caminho_arquivo, "r") as z:
                nome_interno = "logd.dat"
                if nome_interno not in z.namelist():
                    candidatos = [f for f in z.namelist() if f.endswith(".dat") or "log" in f]
                    if not candidatos:
                        raise ValueError(f"Arquivo {nome_interno} não encontrado dentro de {self.caminho_arquivo}")
                    nome_interno = candidatos[0]

                with z.open(nome_interno) as f:
                    for num_linha, linha in enumerate(f, start=1):
                        texto = linha.decode("iso-8859-1").rstrip("\r\n")
                        partes = texto.split("\t")
                        if len(partes) >= 6:
                            yield {
                                "linha": num_linha,
                                "data_hora": partes[0],
                                "nivel": partes[1],
                                "id_processo": partes[2],
                                "modulo": partes[3],
                                "mensagem": partes[4],
                                "hash_linha": partes[5],
                            }
                        elif len(partes) == 5:
                            yield {
                                "linha": num_linha,
                                "data_hora": partes[0],
                                "nivel": partes[1],
                                "id_processo": partes[2],
                                "modulo": partes[3],
                                "mensagem": partes[4],
                                "hash_linha": "",
                            }
        except zipfile.BadZipFile as e:
            raise ValueError(f"Arquivo de log corrompido ou formato inválido: {e}") from e

    def gerar_resumo(self) -> Dict[str, Any]:
        """
        Processa os eventos e gera métricas consolidadas da seção eleitoral.
        """
        total_linhas = 0
        modulos = Counter()
        niveis = Counter()
        votos_por_data = Counter()
        modelo_urna = None
        serie_mr = None
        municipio = self.metadados.get("municipio")
        zona = self.metadados.get("zona")
        secao = self.metadados.get("secao")
        marcos_importantes = []

        for reg in self.iterar_linhas():
            total_linhas += 1
            modulos[reg["modulo"]] += 1
            niveis[reg["nivel"]] += 1
            msg = reg["mensagem"]
            dt = reg["data_hora"]

            # Identificação do hardware e local
            if "Identificação do Modelo de Urna:" in msg and not modelo_urna:
                modelo_urna = msg.split(":")[-1].strip()
            if "Número de série da MR:" in msg and not serie_mr:
                serie_mr = msg.split(":")[-1].strip()
            if "Município:" in msg and not municipio:
                municipio = msg.split(":")[-1].strip()
            if "Zona Eleitoral:" in msg and not zona:
                zona = msg.split(":")[-1].strip()
            if "Seção Eleitoral:" in msg and not secao:
                secao = msg.split(":")[-1].strip()

            # Votos computados
            if "voto do eleitor foi computado" in msg.lower():
                partes_dt = dt.split()
                data_dia = partes_dt[0] if partes_dt else "N/D"
                votos_por_data[data_dia] += 1

            # Eventos críticos
            if any(chave in msg.lower() for chave in [
                "zerésima", 
                "emissão do boletim de urna", 
                "encerramento da votação", 
                "início da votação", 
                "urna ligada em",
                "gerando arquivo de resultado [bu.jez]"
            ]):
                marcos_importantes.append((dt, reg["modulo"], msg))

        return {
            "arquivo": os.path.basename(self.caminho_arquivo),
            "metadados": self.metadados,
            "total_linhas": total_linhas,
            "municipio": municipio,
            "zona": zona,
            "secao": secao,
            "modelo_urna": modelo_urna,
            "serie_mr": serie_mr,
            "distribuicao_niveis": dict(niveis),
            "distribuicao_modulos": dict(modulos.most_common(10)),
            "votos_computados": dict(votos_por_data),
            "marcos_importantes": marcos_importantes,
        }

    def extrair_horarios_votos(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extrai o histórico detalhado de cada voto computado com segurança de parsing.
        """
        votos_por_dia: Dict[str, List[Dict[str, Any]]] = {}
        hab_atual = None
        tipo_hab = "N/I"

        for reg in self.iterar_linhas():
            msg = reg["mensagem"]
            dt_str = reg["data_hora"]

            if "Tipo de habilitação do eleitor" in msg:
                match = re.search(r"\[(.*?)\]", msg)
                if match:
                    tipo_hab = match.group(1)
            elif "Eleitor foi habilitado" in msg:
                hab_atual = dt_str
            elif "O voto do eleitor foi computado" in msg:
                partes_dt = dt_str.split()
                dia = partes_dt[0] if len(partes_dt) > 0 else "N/D"
                hora = partes_dt[1] if len(partes_dt) > 1 else "N/D"

                if dia not in votos_por_dia:
                    votos_por_dia[dia] = []

                duracao = 0
                hora_hab = "N/D"
                if hab_atual:
                    partes_hab = hab_atual.split()
                    hora_hab = partes_hab[1] if len(partes_hab) > 1 else "N/D"
                    try:
                        t_ini = datetime.strptime(hab_atual, "%d/%m/%Y %H:%M:%S")
                        t_fim = datetime.strptime(dt_str, "%d/%m/%Y %H:%M:%S")
                        duracao = max(0, int((t_fim - t_ini).total_seconds()))
                    except Exception:
                        duracao = 0

                votos_por_dia[dia].append({
                    "sequencial": len(votos_por_dia[dia]) + 1,
                    "data": dia,
                    "hora_computado": hora,
                    "hora_habilitado": hora_hab,
                    "duracao_segundos": duracao,
                    "tipo_habilitacao": tipo_hab
                })
                hab_atual = None
                tipo_hab = "N/I"

        return votos_por_dia

def imprimir_relatorio(resumo: Dict[str, Any], detalhar_votos: bool = True) -> None:
    print("=" * 80)
    print(f"RELATÓRIO DE AUDITORIA DO LOG DE URNA - TSE")
    print("=" * 80)
    print(f"Arquivo analisado: {resumo['arquivo']}")
    print(f"Total de registros de log: {resumo['total_linhas']:,}")
    print(f"Estado (UF): {resumo['metadados'].get('uf', 'N/D').upper()}")
    print(f"Município (Código TSE): {resumo['municipio']}")
    print(f"Zona Eleitoral: {resumo['zona']}")
    print(f"Seção Eleitoral: {resumo['secao']}")
    print(f"Modelo da Urna: {resumo['modelo_urna']}")
    print(f"Série da Mídia de Resultado (MR): {resumo['serie_mr']}")
    print("-" * 80)
    print("VOTOS COMPUTADOS POR DIA DE VOTAÇÃO:")
    for data, qtd in resumo["votos_computados"].items():
        print(f"  • {data}: {qtd} eleitores votaram")
    print("-" * 80)
    print("DISTRIBUIÇÃO POR SUBSISTEMA (MÓDULOS):")
    for mod, qtd in resumo["distribuicao_modulos"].items():
        print(f"  • {mod:<8}: {qtd:>5} eventos")
    print("-" * 80)
    print("MARCOS DO CICLO ELEITORAL DETECTADOS:")
    for dt, mod, msg in resumo["marcos_importantes"][:10]:
        print(f"  [{dt}] [{mod}] {msg}")
    if len(resumo["marcos_importantes"]) > 10:
        print(f"  ... e mais {len(resumo['marcos_importantes']) - 10} eventos chave.")
    print("=" * 80)

if __name__ == "__main__":
    import argparse
    parser_args = argparse.ArgumentParser(description="Auditor de Log de Urna Eletrônica (TSE)")
    parser_args.add_argument("arquivo", nargs="?", default="o03221mg4100900500224-log.jez", help="Caminho do arquivo .jez")
    parser_args.add_argument("--votos", action="store_true", help="Listar todos os horários individuais de votos")
    parser_args.add_argument("--csv", action="store_true", help="Exportar votos para CSV")

    args = parser_args.parse_args()
    caminho_arq = args.arquivo
    if not os.path.exists(caminho_arq):
        for fallback in [
            os.path.join("data", "raw", caminho_arq),
            os.path.join("..", "data", "raw", caminho_arq),
            os.path.join("data", "raw", "o03221mg4100900500224-log.jez"),
            os.path.join("..", "data", "raw", "o03221mg4100900500224-log.jez"),
        ]:
            if os.path.exists(fallback):
                caminho_arq = fallback
                break

    try:
        parser = LogUrnaParser(caminho_arq)
        resumo = parser.gerar_resumo()
        imprimir_relatorio(resumo)

        if args.votos or args.csv:
            historico_votos = parser.extrair_horarios_votos()
            for dia, lista_votos in historico_votos.items():
                print(f"\nCRONOLOGIA DE VOTOS - DIA {dia} ({len(lista_votos)} votos computados):")
                print(f"{'Seq':<5} | {'Habilitado':<10} | {'Computado':<10} | {'Duração':<9} | {'Tipo Habilitação':<18}")
                print("-" * 65)
                for v in lista_votos:
                    print(f"{v['sequencial']:<5} | {v['hora_habilitado']:<10} | {v['hora_computado']:<10} | {v['duracao_segundos']:>4}s    | {v['tipo_habilitacao']}")

            if args.csv:
                nome_csv = "horarios_votos.csv"
                if os.path.exists(os.path.join("data", "processed")):
                    nome_csv = os.path.join("data", "processed", "horarios_votos.csv")
                elif os.path.exists(os.path.join("..", "data", "processed")):
                    nome_csv = os.path.join("..", "data", "processed", "horarios_votos.csv")

                with open(nome_csv, "w", newline="", encoding="utf-8") as f_csv:
                    writer = csv.writer(f_csv)
                    writer.writerow(["Data", "Sequencial", "Hora_Habilitacao", "Hora_Voto_Computado", "Duracao_Segundos", "Tipo_Habilitacao"])
                    for dia, lista_votos in historico_votos.items():
                        for v in lista_votos:
                            writer.writerow([
                                sanitize_csv_cell(v["data"]),
                                v["sequencial"],
                                sanitize_csv_cell(v["hora_habilitado"]),
                                sanitize_csv_cell(v["hora_computado"]),
                                v["duracao_segundos"],
                                sanitize_csv_cell(v["tipo_habilitacao"])
                            ])
                print(f"\n[SUCESSO] Horários exportados para {nome_csv}")
    except Exception as e:
        print(f"[ERRO] {e}", file=sys.stderr)
        sys.exit(1)
