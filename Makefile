.PHONY: help status codemender-status codemender-baseline codemender-strict codemender-scan compile test

SHELL := /bin/bash

help:
	@echo "============================================================================="
	@echo "Comandos Disponíveis — Auditoria & CodeMender (local-eleicoes-2026)"
	@echo "============================================================================="
	@echo "  make codemender-status    - Diagnóstico do ambiente e integridade dos códigos"
	@echo "  make codemender-baseline  - Varredura estática baseline (offline, sem fail-on)"
	@echo "  make codemender-strict    - Varredura de segurança estrita (bloqueia em MEDIUM)"
	@echo "  make codemender-scan      - Varredura profunda com geração de relatórios completos"
	@echo "  make compile              - Verifica compilação sintática de todos os scripts Python"
	@echo "  make test                 - Executa suíte de validação e testes dos scripts"
	@echo "============================================================================="

status: codemender-status

codemender-status:
	@./scripts/codemender.sh status

codemender-baseline:
	@./scripts/codemender.sh baseline

codemender-strict:
	@./scripts/codemender.sh strict

codemender-scan:
	@./scripts/codemender.sh scan-deep

compile:
	@python3 -m py_compile scripts/*.py && echo "✅ Todos os scripts Python compilaram com sucesso!"

test: compile
	@echo "Rodando testes de sanidade nos módulos..."
	@python3 -c "import scripts.ler_log_urna; import scripts.analisar_minutos; import scripts.buscar_secoes_100pct; print('✅ Módulos importados com sucesso!')"
