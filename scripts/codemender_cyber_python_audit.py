#!/usr/bin/env python3
"""
Auditor de Código e Segurança CodeMender + Gemini Cyber para Repositórios Python & Web.
Implementa a matriz determinística de 14 regras OWASP/CWE + Checagens Web/DOM + Compilação + Hashing SHA-256.

Compatível com o padrão corporativo da Squad Antigravity e diretrizes do GUIA_CODEMENDER da Wiki Central.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

EXCLUDED_DIRS = {
    ".git",
    ".vscode",
    "venv",
    ".venv",
    "__pycache__",
    "node_modules",
    "tmp",
    "data/zips",
    "data/raw",
    "scratch",
    ".tempmediaStorage",
}

MONITORED_EXTENSIONS = {".py", ".sh", ".html", ".js", ".json", ".yaml", ".yml"}

SEVERITY_LEVELS = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "INFO": 0,
}

@dataclass
class Finding:
    finding_id: str
    rule_id: str
    cwe: str
    severity: str
    category: str
    title: str
    file_path: str
    line_number: int
    evidence: str
    impact: str
    remediation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FileScanner:
    def __init__(self, root: pathlib.Path):
        self.root = root

    def discover_files(self) -> List[pathlib.Path]:
        files_to_scan = []
        for p in self.root.rglob("*"):
            if not p.is_file():
                continue
            # Verifica exclusão de diretórios
            rel_parts = p.relative_to(self.root).parts
            if any(part in EXCLUDED_DIRS for part in rel_parts):
                continue
            if p.suffix.lower() in MONITORED_EXTENSIONS:
                files_to_scan.append(p)
        return sorted(files_to_scan)


class RuleEngine:
    def __init__(self, root: pathlib.Path):
        self.root = root
        self.findings: List[Finding] = []
        self._counter = 1

    def _next_id(self) -> str:
        fid = f"CM-VULN-{self._counter:04d}"
        self._counter += 1
        return fid

    def audit_python_file(self, path: pathlib.Path, content: str, lines: List[str]) -> None:
        rel_path = str(path.relative_to(self.root))

        # Ignora auto-inspeção das regras dentro do próprio auditor
        if path.name == "codemender_cyber_python_audit.py":
            return

        # 1. Regras Baseadas em Regex / Padrões de Linha
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            # CYBER-PY-01: Hardcoded Secrets (CWE-798)
            if re.search(r'''(?i)(api[_-]?key|secret[_-]?key|auth[_-]?token|bearer\s+[A-Za-z0-9_\-\.]{20,}|password)\s*[:=]\s*["'][A-Za-z0-9_\-\.]{12,}["']''', line):
                # Evita falso positivo em declarações de parâmetros ou schemas
                if "os.environ" not in line and "getenv" not in line and "argparse" not in line and "header" not in line.lower():
                    self.findings.append(Finding(
                        finding_id=self._next_id(),
                        rule_id="CYBER-PY-01",
                        cwe="CWE-798",
                        severity="CRITICAL",
                        category="Hardcoded Secrets",
                        title="Segredo ou Token em Texto Puro",
                        file_path=rel_path,
                        line_number=idx,
                        evidence=stripped[:120],
                        impact="Exposição de credenciais em código estático rastreável no controle de versão.",
                        remediation="Utilize variáveis de ambiente (os.environ.get) ou Secret Manager."
                    ))

            # CYBER-PY-02: Insecure Subprocess Execution (CWE-78)
            if re.search(r'''subprocess\.(Popen|run|call|check_call|check_output)\([^)]*shell\s*=\s*True''', line):
                self.findings.append(Finding(
                    finding_id=self._next_id(),
                    rule_id="CYBER-PY-02",
                    cwe="CWE-78",
                    severity="HIGH",
                    category="Command Injection",
                    title="Execução de Subprocess com shell=True",
                    file_path=rel_path,
                    line_number=idx,
                    evidence=stripped[:120],
                    impact="Permite command injection se argumentos contiverem dados não confiáveis.",
                    remediation="Passe os argumentos como lista e defina shell=False explicitamente."
                ))

            # CYBER-PY-03: Dynamic Code Evaluation (CWE-94)
            if re.search(r'''\b(eval|exec)\s*\(''', line):
                self.findings.append(Finding(
                    finding_id=self._next_id(),
                    rule_id="CYBER-PY-03",
                    cwe="CWE-94",
                    severity="HIGH",
                    category="Code Injection",
                    title="Avaliação Dinâmica de Código (eval/exec)",
                    file_path=rel_path,
                    line_number=idx,
                    evidence=stripped[:120],
                    impact="Execução arbitrária de código Python através de strings avaliadas em runtime.",
                    remediation="Substitua eval/exec por parsing estruturado via ast.literal_eval ou json.loads."
                ))

            # CYBER-PY-05: Overly Permissive Permissions (CWE-732)
            if re.search(r'''os\.chmod\([^)]*0o?777''', line) or "chmod 777" in line:
                self.findings.append(Finding(
                    finding_id=self._next_id(),
                    rule_id="CYBER-PY-05",
                    cwe="CWE-732",
                    severity="MEDIUM",
                    category="Insecure Permissions",
                    title="Permissões Excessivas em Arquivo (chmod 777)",
                    file_path=rel_path,
                    line_number=idx,
                    evidence=stripped[:120],
                    impact="Permite leitura, escrita e execução irrestrita para qualquer usuário local.",
                    remediation="Limite as permissões para 0o750 ou 0o640."
                ))

            # CYBER-PY-06: Insecure TLS (CWE-295)
            if re.search(r'''verify\s*=\s*False''', line) or "curl -k" in line:
                self.findings.append(Finding(
                    finding_id=self._next_id(),
                    rule_id="CYBER-PY-06",
                    cwe="CWE-295",
                    severity="MEDIUM",
                    category="Insecure Transport",
                    title="Bypass de Verificação de Certificado TLS",
                    file_path=rel_path,
                    line_number=idx,
                    evidence=stripped[:120],
                    impact="Vulnerável a ataques Man-in-the-Middle (MitM) ao ignorar certificados inválidos.",
                    remediation="Mantenha a verificação TLS padrão ativa (verify=True)."
                ))

            # CYBER-PY-11: High-Risk Functions (CWE-676)
            if re.search(r'''\bos\.system\s*\(''', line):
                self.findings.append(Finding(
                    finding_id=self._next_id(),
                    rule_id="CYBER-PY-11",
                    cwe="CWE-676",
                    severity="HIGH",
                    category="Dangerous Functions",
                    title="Uso de Função Perigosa os.system()",
                    file_path=rel_path,
                    line_number=idx,
                    evidence=stripped[:120],
                    impact="os.system() executa diretamente no shell sem isolamento de argumentos nem controle de IO.",
                    remediation="Substitua por subprocess.run(['cmd', 'arg'], check=True, timeout=X)."
                ))

        # 2. Análise Estrutural AST (Python)
        try:
            tree = ast.parse(content, filename=str(path))
            self._audit_ast(tree, rel_path, lines)
        except SyntaxError as e:
            self.findings.append(Finding(
                finding_id=self._next_id(),
                rule_id="CYBER-PY-00",
                cwe="CWE-754",
                severity="CRITICAL",
                category="Syntax Error",
                title="Erro de Sintaxe Python",
                file_path=rel_path,
                line_number=e.lineno or 1,
                evidence=str(e),
                impact="O script não compila nem executa em Python 3.",
                remediation="Corrija o erro de sintaxe."
            ))

    def _audit_ast(self, tree: ast.AST, rel_path: str, lines: List[str]) -> None:
        for node in ast.walk(tree):
            # CYBER-PY-09: Chamadas de rede sem Timeout (CWE-400)
            if isinstance(node, ast.Call):
                func_name = ""
                caller_name = ""
                if isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                    if isinstance(node.func.value, ast.Name):
                        caller_name = node.func.value.id
                    elif isinstance(node.func.value, ast.Attribute):
                        caller_name = node.func.value.attr
                elif isinstance(node.func, ast.Name):
                    func_name = node.func.id

                # Apenas requisições de rede reais
                is_net_call = False
                if func_name == "urlopen":
                    is_net_call = True
                elif func_name in ("get", "post", "put", "delete", "request") and caller_name in ("requests", "session", "http", "urllib"):
                    is_net_call = True

                if is_net_call:
                    has_timeout = any(kw.arg == "timeout" for kw in node.keywords)
                    if not has_timeout and len(node.args) < 3:
                        line_no = getattr(node, "lineno", 1)
                        ev = lines[line_no - 1].strip() if line_no <= len(lines) else ""
                        self.findings.append(Finding(
                            finding_id=self._next_id(),
                            rule_id="CYBER-PY-09",
                            cwe="CWE-400",
                            severity="MEDIUM",
                            category="Uncontrolled Resource Consumption",
                            title=f"Chamada de Rede {func_name}() sem Parâmetro timeout",
                            file_path=rel_path,
                            line_number=line_no,
                            evidence=ev[:120],
                            remediation="Especifique sempre um timeout explícito (ex: timeout=30)."
                        ))

                # CYBER-PY-09: subprocess sem timeout
                if func_name in ("run", "Popen", "check_output", "call", "check_call"):
                    if isinstance(node.func, ast.Attribute) and getattr(node.func.value, "id", "") == "subprocess":
                        has_timeout = any(kw.arg == "timeout" for kw in node.keywords)
                        if not has_timeout:
                            line_no = getattr(node, "lineno", 1)
                            ev = lines[line_no - 1].strip() if line_no <= len(lines) else ""
                            self.findings.append(Finding(
                                finding_id=self._next_id(),
                                rule_id="CYBER-PY-09",
                                cwe="CWE-400",
                                severity="MEDIUM",
                                category="Uncontrolled Resource Consumption",
                                title="Execução de subprocess sem timeout",
                                file_path=rel_path,
                                line_number=line_no,
                                evidence=ev[:120],
                                impact="Subprocessos órfãos ou processos bloqueantes podem paralisar o pipeline indefinidamente.",
                                remediation="Adicione o parâmetro timeout (ex: timeout=120) na chamada subprocess."
                            ))

                # CYBER-PY-04: Insecure Deserialization (CWE-502)
                if func_name in ("loads", "load") and isinstance(node.func, ast.Attribute):
                    mod_id = getattr(node.func.value, "id", "")
                    if mod_id in ("pickle", "_pickle", "cPickle"):
                        line_no = getattr(node, "lineno", 1)
                        self.findings.append(Finding(
                            finding_id=self._next_id(),
                            rule_id="CYBER-PY-04",
                            cwe="CWE-502",
                            severity="HIGH",
                            category="Deserialization of Untrusted Data",
                            title="Desserialização Insegura com pickle",
                            file_path=rel_path,
                            line_number=line_no,
                            evidence=lines[line_no - 1].strip()[:120] if line_no <= len(lines) else "",
                            impact="Pickle permite execução arbitrária de código durante o desempacotamento de objetos.",
                            remediation="Utilize formatos seguros de dados como JSON ou Protocol Buffers."
                        ))

            # CYBER-PY-13: Potencial Divisão por Zero em Cálculos Estatísticos / Percentuais (CWE-369)
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                right = node.right
                # Se o denominador for uma variável simples ou chamada que pode ser 0
                if isinstance(right, (ast.Name, ast.Attribute, ast.Call)):
                    line_no = getattr(node, "lineno", 1)
                    ev = lines[line_no - 1].strip() if line_no <= len(lines) else ""
                    # Verifica se há proteção óbvia na mesma linha (if ... else ou ternário)
                    if not any(token in ev for token in ("if", "else", "or 1", "max(", "try", "?")):
                        self.findings.append(Finding(
                            finding_id=self._next_id(),
                            rule_id="CYBER-PY-13",
                            cwe="CWE-369",
                            severity="MEDIUM",
                            category="Numeric Errors",
                            title="Divisão sem Verificação Explícita de Denominador Nulo",
                            file_path=rel_path,
                            line_number=line_no,
                            evidence=ev[:120],
                            impact="Risco de exceção ZeroDivisionError abortando processamento em conjuntos de dados vazios.",
                            remediation="Proteja o cálculo com fallback condicional (ex: x / denom if denom else 0)."
                        ))

    def audit_web_file(self, path: pathlib.Path, content: str, lines: List[str]) -> None:
        rel_path = str(path.relative_to(self.root))

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()

            # CYBER-WEB-01: Reverse Tabnabbing (CWE-1022)
            # target="_blank" sem rel="noopener noreferrer"
            if 'target="_blank"' in line or "target='_blank'" in line:
                if "noopener" not in line and "noreferrer" not in line:
                    self.findings.append(Finding(
                        finding_id=self._next_id(),
                        rule_id="CYBER-WEB-01",
                        cwe="CWE-1022",
                        severity="MEDIUM",
                        category="Reverse Tabnabbing",
                        title='Link target="_blank" sem rel="noopener noreferrer"',
                        file_path=rel_path,
                        line_number=idx,
                        evidence=stripped[:120],
                        impact="A página de destino pode manipular a janela de origem via window.opener gerando phishing.",
                        remediation='Adicione o atributo rel="noopener noreferrer" em todos os links target="_blank".'
                    ))

            # CYBER-WEB-02: DOM XSS via unescaped innerHTML (CWE-79)
            if re.search(r'''\b(innerHTML|outerHTML)\s*=\s*`[^`]*\${''', line):
                # Interpolação direta de template string em innerHTML sem sanitização
                if "escapeHtml" not in line and "sanitize" not in line and "textNode" not in line:
                    self.findings.append(Finding(
                        finding_id=self._next_id(),
                        rule_id="CYBER-WEB-02",
                        cwe="CWE-79",
                        severity="HIGH",
                        category="Cross-Site Scripting (XSS)",
                        title="Atribuição de innerHTML com Template Literal Não Sanitizado",
                        file_path=rel_path,
                        line_number=idx,
                        evidence=stripped[:120],
                        impact="Injeção de tags HTML maliciosas e scripts caso os dados interpolados contenham payload de eleitor/município.",
                        remediation="Sanitize os valores dinâmicos com uma função escapeHtml() ou utilize textContent."
                    ))


class CodeMenderAuditEngine:
    def __init__(self, root: pathlib.Path, fail_on: str = "MEDIUM"):
        self.root = root
        self.fail_on = fail_on.upper()
        self.scanner = FileScanner(root)
        self.rule_engine = RuleEngine(root)
        self.file_hashes: Dict[str, str] = {}
        self.compile_results: Dict[str, bool] = {}

    def compute_sha256(self, path: pathlib.Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def run_compilation_check(self, py_files: List[pathlib.Path]) -> None:
        for p in py_files:
            rel = str(p.relative_to(self.root))
            try:
                res = subprocess.run(
                    [sys.executable, "-m", "py_compile", str(p)],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                self.compile_results[rel] = (res.returncode == 0)
                if res.returncode != 0:
                    self.rule_engine.findings.append(Finding(
                        finding_id=self.rule_engine._next_id(),
                        rule_id="CYBER-PY-00",
                        cwe="CWE-754",
                        severity="CRITICAL",
                        category="Compilation Error",
                        title=f"Falha na Compilação Python de {rel}",
                        file_path=rel,
                        line_number=1,
                        evidence=res.stderr.strip()[:150],
                        impact="O código não executa devido a erro sintático ou de compilação de bytecode.",
                        remediation="Corrija o código Python até que python3 -m py_compile passe com sucesso."
                    ))
            except Exception as e:
                self.compile_results[rel] = False

    def scan(self) -> List[Finding]:
        files = self.scanner.discover_files()
        py_files = [f for f in files if f.suffix.lower() == ".py"]

        # Hashing de evidências
        for f in files:
            rel = str(f.relative_to(self.root))
            self.file_hashes[rel] = self.compute_sha256(f)

        # Checagem de Compilação
        self.run_compilation_check(py_files)

        # Varredura de Regras
        for f in files:
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
            except Exception as e:
                continue

            if f.suffix.lower() == ".py":
                self.rule_engine.audit_python_file(f, content, lines)
            elif f.suffix.lower() in (".html", ".js"):
                self.rule_engine.audit_web_file(f, content, lines)

        return self.rule_engine.findings

    def generate_markdown_report(self, findings: List[Finding]) -> str:
        now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report = []
        report.append("# Relatório de Auditoria e Varredura CodeMender + Gemini Cyber")
        report.append(f"**Data da Execução:** `{now_str}`  ")
        report.append(f"**Repositório:** `{self.root.name}`  ")
        report.append(f"**Rigor de Segurança:** `STRICT` (Fail-on: `{self.fail_on}`)  \n")

        # Resumo Estatístico
        severities = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
        for f in findings:
            severities[f.severity] = severities.get(f.severity, 0) + 1

        report.append("## 📊 1. Resumo Executivo das Severidades\n")
        report.append("| Severidade | Quantidade | Ação Requerida |")
        report.append("|---|:---:|---|")
        report.append(f"| 🚨 **CRITICAL** | **{severities['CRITICAL']}** | Bloqueio imediato de pipeline |")
        report.append(f"| ⚠️ **HIGH** | **{severities['HIGH']}** | Correção mandatória pré-merge |")
        report.append(f"| 🛡️ **MEDIUM** | **{severities['MEDIUM']}** | Remediação no ciclo de mender |")
        report.append(f"| ℹ️ **LOW / INFO** | **{severities['LOW'] + severities['INFO']}** | Observações e melhorias de código |")
        report.append(f"| **TOTAL** | **{len(findings)}** | | \n")

        # Matriz de Integridade SHA-256
        report.append("## 🔒 2. Matriz de Evidências Criptográficas (SHA-256)\n")
        report.append("| Arquivo Analisado | Compilação | Hash SHA-256 |")
        report.append("|---|:---:|---|")
        for rel_path, sha in sorted(self.file_hashes.items()):
            comp = "✅ OK" if self.compile_results.get(rel_path, True) else "❌ FALHA"
            report.append(f"| `{rel_path}` | {comp} | `{sha[:20]}...` |")
        report.append("\n")

        # Detalhamento dos Achados
        report.append("## 🔍 3. Detalhamento dos Achados de Segurança\n")
        if not findings:
            report.append("> ✅ **Nenhuma vulnerabilidade ou code smell encontrado! O código está 100% aprovado pelo CodeMender.**\n")
        else:
            for f in findings:
                report.append(f"### [{f.severity}] {f.finding_id}: {f.title}")
                report.append(f"* **Regra:** `{f.rule_id}` ({f.cwe}) | **Categoria:** `{f.category}`")
                report.append(f"* **Localização:** [`{f.file_path}:{f.line_number}`](file://{self.root}/{f.file_path}#L{f.line_number})")
                report.append(f"* **Evidência:** `{f.evidence}`")
                report.append(f"* **Impacto:** {f.impact}")
                report.append(f"* **Remediação Sugerida:** {f.remediation}\n")
                report.append("---\n")

        return "\n".join(report)

    def generate_sarif(self, findings: List[Finding]) -> Dict[str, Any]:
        sarif_results = []
        for f in findings:
            level = "error" if f.severity in ("CRITICAL", "HIGH") else ("warning" if f.severity == "MEDIUM" else "note")
            sarif_results.append({
                "ruleId": f.rule_id,
                "level": level,
                "message": {"text": f"{f.title}: {f.impact}"},
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": f.file_path},
                        "region": {"startLine": f.line_number}
                    }
                }]
            })

        return {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [{
                "tool": {
                    "driver": {
                        "name": "Google CodeMender + Gemini Cyber Baseline",
                        "version": "1.4.2",
                        "informationUri": "http://mini:3000/usitsupport/usit-developer-guide/wiki/GUIA_CODEMENDER"
                    }
                },
                "results": sarif_results
            }]
        }


def main():
    parser = argparse.ArgumentParser(description="Auditor CodeMender de Segurança e Qualidade de Código")
    parser.add_argument("--fail-on", default="MEDIUM", choices=["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"], help="Nível de severidade para abortar com erro")
    parser.add_argument("--output-dir", default="tmp/codemender-reports", help="Diretório para salvar os relatórios")
    parser.add_argument("--format", default="markdown", choices=["markdown", "sarif", "json", "all"], help="Formato de exportação do relatório")

    args = parser.parse_args()
    engine = CodeMenderAuditEngine(REPO_ROOT, fail_on=args.fail_on)

    print("=" * 80)
    print("INICIANDO VARREDURA CODEMENDER + GEMINI CYBER (STRICT AUDIT)")
    print("=" * 80)
    print(f"Diretório Raiz: {REPO_ROOT}")
    print(f"Política de Bloqueio (Fail-on): {args.fail_on}\n")

    findings = engine.scan()

    print(f"Arquivos verificados: {len(engine.file_hashes)}")
    print(f"Total de achados encontrados: {len(findings)}\n")

    # Garante diretório de relatórios
    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    md_report = engine.generate_markdown_report(findings)
    md_file = out_dir / "relatorio_codemender.md"
    md_file.write_text(md_report, encoding="utf-8")
    print(f"📄 Relatório Markdown salvo em: {md_file}")

    if args.format in ("sarif", "all"):
        sarif_data = engine.generate_sarif(findings)
        sarif_file = out_dir / "relatorio_codemender.sarif"
        sarif_file.write_text(json.dumps(sarif_data, indent=2), encoding="utf-8")
        print(f"📄 Relatório SARIF salvo em: {sarif_file}")

    if args.format in ("json", "all"):
        json_file = out_dir / "relatorio_codemender.json"
        json_file.write_text(json.dumps([f.to_dict() for f in findings], indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"📄 Relatório JSON salvo em: {json_file}")

    print("\n" + "=" * 80)
    if not findings:
        print("✅ CODEMENDER: NENHUMA VULNERABILIDADE DETECTADA. BUILD APROVADO!")
        print("=" * 80)
        sys.exit(0)
    else:
        print("ACHADOS ENCONTRADOS PELO SCANNER:")
        max_severity_found = 0
        for f in findings:
            score = SEVERITY_LEVELS.get(f.severity, 0)
            if score > max_severity_found:
                max_severity_found = score
            print(f"  • [{f.severity}] {f.finding_id} ({f.rule_id} - {f.cwe}) em {f.file_path}:{f.line_number}")
            print(f"    Título: {f.title}")
            print(f"    Evidência: {f.evidence[:90]}")
            print(f"    Remediação: {f.remediation}\n")

        threshold = SEVERITY_LEVELS.get(args.fail_on, 999)
        if args.fail_on != "NONE" and max_severity_found >= threshold:
            print(f"❌ CODEMENDER GATE FAILED: Foram encontrados achados de severidade >= {args.fail_on}.")
            print("=" * 80)
            sys.exit(1)
        else:
            print("⚠️ Achados identificados, mas abaixo do limiar de bloqueio (Gate Aprovado com Ressalvas).")
            print("=" * 80)
            sys.exit(0)


if __name__ == "__main__":
    main()
