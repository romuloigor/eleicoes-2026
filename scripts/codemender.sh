#!/usr/bin/env bash
# =============================================================================
# scripts/codemender.sh
# =============================================================================
# Wrapper operacional para Google CodeMender CLI (cm) + Gemini Cyber aplicado
# ao repositório local-eleicoes-2026.
#
# Uso:
#   ./scripts/codemender.sh status
#   ./scripts/codemender.sh baseline
#   ./scripts/codemender.sh strict
#   ./scripts/codemender.sh scan-deep
#   ./scripts/codemender.sh report
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CM_BIN="$(command -v cm 2>/dev/null || echo "${HOME}/bin/cm")"
CONFIG_FILE="${REPO_ROOT}/scripts/codemender-config.yaml"
AUDIT_SCRIPT="${REPO_ROOT}/scripts/codemender_cyber_python_audit.py"
REPORT_DIR="${REPO_ROOT}/tmp/codemender-reports"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${CYAN}ℹ️  $*${NC}"; }
log_ok()    { echo -e "${GREEN}✅ $*${NC}"; }
log_warn()  { echo -e "${YELLOW}⚠️  $*${NC}"; }
log_error() { echo -e "${RED}❌ $*${NC}" >&2; }

cmd_status() {
  log_info "Diagnóstico do Ambiente CodeMender — local-eleicoes-2026"
  echo "------------------------------------------------------------"
  echo "• Raiz do Repositório: ${REPO_ROOT}"
  echo "• Configuração:        ${CONFIG_FILE}"
  echo "• Script Auditor:      ${AUDIT_SCRIPT}"
  
  if [[ -x "${CM_BIN}" ]]; then
    log_ok "Binário oficial 'cm' detectado: ${CM_BIN}"
  else
    log_warn "Binário 'cm' não encontrado. Utilizando auditor nativo Python."
  fi

  # Checagem de token GCP passiva
  if gcloud auth print-access-token >/dev/null 2>&1; then
    log_ok "Sessão GCP / Vertex AI ativa."
  else
    log_warn "Sessão GCP não autenticada no momento (Modo Offline Baseline & Native Ativo)."
  fi

  # Checagem de integridade dos arquivos Python
  echo -n "• Integridade de compilação Python: "
  if python3 -m py_compile "${REPO_ROOT}"/scripts/*.py >/dev/null 2>&1; then
    log_ok "100% dos scripts compilam com sucesso."
  else
    log_error "Erros detectados na compilação dos scripts Python."
  fi
  echo "------------------------------------------------------------"
}

cmd_baseline() {
  log_info "Executando Varredura Baseline Local (Fail-on: NONE)..."
  python3 "${AUDIT_SCRIPT}" --fail-on NONE --format all --output-dir "${REPORT_DIR}"
}

cmd_strict() {
  log_info "Executando Varredura Strict CodeMender (Fail-on: MEDIUM)..."
  python3 "${AUDIT_SCRIPT}" --fail-on MEDIUM --format all --output-dir "${REPORT_DIR}"
}

cmd_scan_deep() {
  log_info "Executando Varredura Profunda (Deep Scan)..."
  mkdir -p "${REPORT_DIR}"
  
  # Se o binário cm estiver disponível e token GCP ativo, tenta cm find --deep
  if [[ -x "${CM_BIN}" ]] && gcloud auth print-access-token >/dev/null 2>&1; then
    log_info "Executando cm find --deep via Vertex AI..."
    "${CM_BIN}" find scripts/ --deep --model gemini-3.8-flash-cyber -y || true
  fi

  # Executa o auditor determinístico estrito profundo
  python3 "${AUDIT_SCRIPT}" --fail-on NONE --format all --output-dir "${REPORT_DIR}"
}

cmd_report() {
  log_info "Exibindo último relatório CodeMender gerado:"
  if [[ -f "${REPORT_DIR}/relatorio_codemender.md" ]]; then
    cat "${REPORT_DIR}/relatorio_codemender.md"
  else
    log_warn "Nenhum relatório encontrado em ${REPORT_DIR}. Execute baseline ou strict primeiro."
  fi
}

# Despacho do comando
ACTION="${1:-status}"
case "${ACTION}" in
  status)    cmd_status ;;
  baseline)  cmd_baseline ;;
  strict)    cmd_strict ;;
  scan-deep) cmd_scan_deep ;;
  report)    cmd_report ;;
  *)
    echo "Uso: $0 {status|baseline|strict|scan-deep|report}"
    exit 1
    ;;
esac
