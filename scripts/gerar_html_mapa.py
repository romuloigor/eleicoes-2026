#!/usr/bin/env python3
"""
Compilador do Dashboard Nacional Eleitoral:
- Fundo claro por padrão
- Mapa do Brasil interativo com cidades (Leaflet.js)
- Mapa de calor por UF
- Rankings comparativos e tabela com links oficiais do TSE
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

def encontrar_arquivo(nome):
    candidatos = [
        os.path.join(ROOT_DIR, "data", "processed", nome),
        os.path.join(ROOT_DIR, nome),
        os.path.join(SCRIPT_DIR, nome),
        nome
    ]
    for c in candidatos:
        if os.path.exists(c):
            return c
    return nome

caminho_dados = encontrar_arquivo("dados_mapa_calor.json")
caminho_cidades = encontrar_arquivo("cidades_compact.json")
caminho_migracao = encontrar_arquivo("decomposicao_votos_brasil.json")

with open(caminho_dados, encoding="utf-8") as f:
    dados_app = json.load(f)

with open(caminho_cidades, encoding="utf-8") as f:
    cidades_compact_str = f.read()

with open(caminho_migracao, encoding="utf-8") as f:
    decomposicao_app = json.load(f)

dados_app_json_str = json.dumps(dados_app, ensure_ascii=False)
decomposicao_json_str = json.dumps(decomposicao_app, ensure_ascii=False)

html_template = f'''<!DOCTYPE html>
<html lang="pt-BR" data-theme="light">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Mapa de Calor Eleitoral: Seções Absolutas no Brasil (100% e ≥90%)</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com">
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
  
  <!-- Leaflet Map CSS & JS -->
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>

  <style>
    :root {{
      /* Modo Claro (Default) */
      --bg-primary: #f8fafc;
      --bg-secondary: #f1f5f9;
      --bg-card: #ffffff;
      --bg-card-hover: #f8fafc;
      --border-color: #e2e8f0;
      --border-accent: #38bdf8;
      
      --text-main: #0f172a;
      --text-muted: #475569;
      --text-faint: #94a3b8;

      --lula-color: #dc2626;
      --lula-light: #ef4444;
      --lula-bg: #fee2e2;
      --lula-border: #fca5a5;

      --bolsonaro-color: #16a34a;
      --bolsonaro-light: #22c55e;
      --bolsonaro-bg: #dcfce7;
      --bolsonaro-border: #86efac;

      --neutral-color: #0284c7;
      --neutral-bg: #e0f2fe;

      --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
      --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.08), 0 2px 4px -1px rgba(0, 0, 0, 0.04);
      --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -2px rgba(0, 0, 0, 0.03);
    }}

    [data-theme="dark"] {{
      --bg-primary: #0a0e17;
      --bg-secondary: #0f172a;
      --bg-card: rgba(18, 26, 42, 0.85);
      --bg-card-hover: rgba(26, 38, 62, 0.95);
      --border-color: rgba(255, 255, 255, 0.08);
      --border-accent: rgba(56, 189, 248, 0.3);
      
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --text-faint: #64748b;

      --lula-color: #ef4444;
      --lula-light: #f87171;
      --lula-bg: rgba(239, 68, 68, 0.15);
      --lula-border: rgba(239, 68, 68, 0.3);

      --bolsonaro-color: #22c55e;
      --bolsonaro-light: #4ade80;
      --bolsonaro-bg: rgba(34, 197, 94, 0.15);
      --bolsonaro-border: rgba(34, 197, 94, 0.3);

      --neutral-color: #38bdf8;
      --neutral-bg: rgba(56, 189, 248, 0.15);

      --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.3);
      --shadow-md: 0 4px 10px rgba(0, 0, 0, 0.4);
      --shadow-lg: 0 10px 25px rgba(0, 0, 0, 0.5);
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      background-color: var(--bg-primary);
      color: var(--text-main);
      font-family: 'Outfit', sans-serif;
      min-height: 100vh;
      line-height: 1.5;
      padding: 24px;
      transition: background-color 0.3s, color 0.3s;
    }}

    .container {{
      max-width: 1440px;
      margin: 0 auto;
    }}

    header {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 20px;
      padding: 24px 32px;
      margin-bottom: 24px;
      box-shadow: var(--shadow-md);
      position: relative;
    }}

    .header-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }}

    .badge-live {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: var(--neutral-bg);
      border: 1px solid rgba(2, 132, 199, 0.25);
      color: var(--neutral-color);
      padding: 4px 14px;
      border-radius: 999px;
      font-size: 0.82rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}

    .badge-live::before {{
      content: "";
      width: 8px;
      height: 8px;
      background: var(--neutral-color);
      border-radius: 50%;
      animation: pulse 2s infinite;
    }}

    @keyframes pulse {{
      0%, 100% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.4; transform: scale(0.85); }}
    }}

    .theme-toggle {{
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 6px 14px;
      border-radius: 10px;
      cursor: pointer;
      font-family: inherit;
      font-weight: 600;
      font-size: 0.85rem;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s;
    }}

    .theme-toggle:hover {{
      border-color: var(--neutral-color);
    }}

    h1 {{
      font-size: 2.2rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      margin-bottom: 6px;
    }}

    p.subtitle {{
      color: var(--text-muted);
      font-size: 1.05rem;
      max-width: 900px;
    }}

    /* KPI Grid */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}

    .kpi-card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      padding: 20px;
      box-shadow: var(--shadow-sm);
      transition: transform 0.2s, box-shadow 0.2s;
      position: relative;
      overflow: hidden;
    }}

    .kpi-card::before {{
      content: "";
      position: absolute;
      top: 0;
      left: 0;
      width: 4px;
      height: 100%;
    }}

    .kpi-card.lula::before {{ background: var(--lula-color); }}
    .kpi-card.bolsonaro::before {{ background: var(--bolsonaro-color); }}
    .kpi-card.neutral::before {{ background: var(--neutral-color); }}

    .kpi-card:hover {{
      transform: translateY(-2px);
      box-shadow: var(--shadow-md);
    }}

    .kpi-title {{
      font-size: 0.8rem;
      color: var(--text-muted);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 6px;
    }}

    .kpi-value {{
      font-size: 2.2rem;
      font-weight: 800;
      font-family: 'JetBrains Mono', monospace;
      margin-bottom: 2px;
    }}

    .kpi-card.lula .kpi-value {{ color: var(--lula-color); }}
    .kpi-card.bolsonaro .kpi-value {{ color: var(--bolsonaro-color); }}
    .kpi-card.neutral .kpi-value {{ color: var(--neutral-color); }}

    .kpi-desc {{
      font-size: 0.82rem;
      color: var(--text-faint);
    }}

    /* Controls Bar */
    .controls-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      align-items: center;
      justify-content: space-between;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      padding: 14px 20px;
      border-radius: 16px;
      margin-bottom: 24px;
      box-shadow: var(--shadow-sm);
    }}

    .button-group {{
      display: flex;
      gap: 6px;
      background: var(--bg-secondary);
      padding: 4px;
      border-radius: 12px;
      border: 1px solid var(--border-color);
    }}

    .btn-toggle {{
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 8px 16px;
      border-radius: 8px;
      cursor: pointer;
      font-family: inherit;
      font-size: 0.88rem;
      font-weight: 600;
      transition: all 0.2s ease;
    }}

    .btn-toggle:hover {{
      color: var(--text-main);
    }}

    .btn-toggle.active {{
      background: var(--bg-card);
      color: var(--text-main);
      box-shadow: var(--shadow-sm);
    }}

    .btn-toggle.active.lula-active {{
      background: var(--lula-bg);
      color: var(--lula-color);
      border: 1px solid var(--lula-border);
    }}

    .btn-toggle.active.bols-active {{
      background: var(--bolsonaro-bg);
      color: var(--bolsonaro-color);
      border: 1px solid var(--bolsonaro-border);
    }}

    /* Panels */
    .card-panel {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 20px;
      padding: 24px;
      box-shadow: var(--shadow-md);
      margin-bottom: 24px;
    }}

    .panel-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 18px;
    }}

    .panel-title {{
      font-size: 1.25rem;
      font-weight: 700;
    }}

    /* Mapa de Calor por UF (Grid) */
    .uf-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
      gap: 12px;
    }}

    .uf-tile {{
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 12px 14px;
      cursor: pointer;
      transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
    }}

    .uf-tile:hover {{
      transform: translateY(-2px);
      box-shadow: var(--shadow-md);
      border-color: var(--neutral-color);
    }}

    .uf-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 4px;
    }}

    .uf-sigla {{
      font-size: 1.15rem;
      font-weight: 800;
      font-family: 'JetBrains Mono', monospace;
    }}

    .uf-total-secoes {{
      font-size: 0.72rem;
      color: var(--text-faint);
    }}

    .uf-stat-row {{
      display: flex;
      justify-content: space-between;
      font-size: 0.8rem;
      margin-top: 4px;
      font-family: 'JetBrains Mono', monospace;
      font-weight: 600;
    }}

    .stat-lula {{ color: var(--lula-color); }}
    .stat-bols {{ color: var(--bolsonaro-color); }}

    .uf-bar-mini {{
      height: 6px;
      background: rgba(0, 0, 0, 0.08);
      border-radius: 999px;
      margin-top: 8px;
      overflow: hidden;
      display: flex;
    }}

    [data-theme="dark"] .uf-bar-mini {{
      background: rgba(255, 255, 255, 0.08);
    }}

    .bar-segment-lula {{ background: var(--lula-color); height: 100%; }}
    .bar-segment-bols {{ background: var(--bolsonaro-color); height: 100%; }}

    /* Mapa Geográfico do Brasil com as Cidades */
    #mapa-brasil-cidades {{
      width: 100%;
      height: 620px;
      border-radius: 14px;
      border: 1px solid var(--border-color);
      background: #f1f5f9;
      z-index: 1;
    }}

    .mapa-legend {{
      display: flex;
      gap: 20px;
      align-items: center;
      flex-wrap: wrap;
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 10px 16px;
      margin-top: 14px;
      font-size: 0.85rem;
      font-weight: 500;
    }}

    .legend-item {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .legend-circle {{
      width: 12px;
      height: 12px;
      border-radius: 50%;
    }}

    .legend-circle.lula {{ background: var(--lula-color); }}
    .legend-circle.bols {{ background: var(--bolsonaro-color); }}

    /* Layout Grid: Rankings e Detalhes */
    .ranking-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 24px;
      margin-bottom: 24px;
    }}

    @media (max-width: 900px) {{
      .ranking-grid {{
        grid-template-columns: 1fr;
      }}
    }}

    .ranking-list {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      max-height: 480px;
      overflow-y: auto;
      padding-right: 6px;
    }}

    .ranking-item {{
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 12px 16px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}

    .ranking-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.92rem;
      font-weight: 600;
    }}

    .bar-row {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 0.82rem;
      font-family: 'JetBrains Mono', monospace;
    }}

    .bar-label {{
      width: 75px;
      font-weight: 600;
    }}

    .bar-track {{
      flex: 1;
      height: 8px;
      background: rgba(0, 0, 0, 0.06);
      border-radius: 4px;
      overflow: hidden;
    }}

    [data-theme="dark"] .bar-track {{
      background: rgba(255, 255, 255, 0.08);
    }}

    .bar-fill-lula {{ height: 100%; background: var(--lula-color); border-radius: 4px; }}
    .bar-fill-bols {{ height: 100%; background: var(--bolsonaro-color); border-radius: 4px; }}

    .bar-num {{
      width: 45px;
      text-align: right;
      font-weight: 700;
    }}

    /* Tabela */
    .table-container {{
      overflow-x: auto;
      max-height: 480px;
      border: 1px solid var(--border-color);
      border-radius: 12px;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
      text-align: left;
    }}

    th {{
      background: var(--bg-secondary);
      position: sticky;
      top: 0;
      padding: 12px 16px;
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      border-bottom: 1px solid var(--border-color);
      z-index: 10;
    }}

    td {{
      padding: 11px 16px;
      border-bottom: 1px solid var(--border-color);
      color: var(--text-main);
    }}

    tr:hover td {{
      background: var(--bg-secondary);
    }}

    .pill-cand {{
      display: inline-block;
      padding: 3px 10px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 0.78rem;
    }}

    .pill-lula {{
      background: var(--lula-bg);
      color: var(--lula-color);
      border: 1px solid var(--lula-border);
    }}

    .pill-bolsonaro {{
      background: var(--bolsonaro-bg);
      color: var(--bolsonaro-color);
      border: 1px solid var(--bolsonaro-border);
    }}

    .btn-bu {{
      display: inline-block;
      color: var(--neutral-color);
      text-decoration: none;
      font-weight: 600;
      font-size: 0.82rem;
      padding: 4px 10px;
      background: var(--neutral-bg);
      border: 1px solid rgba(2, 132, 199, 0.25);
      border-radius: 6px;
      transition: all 0.2s;
    }}

    .btn-bu:hover {{
      background: var(--neutral-color);
      color: #fff;
    }}

    /* Custom Leaflet Popup */
    .leaflet-popup-content-wrapper {{
      border-radius: 12px;
      box-shadow: var(--shadow-lg);
      font-family: 'Outfit', sans-serif;
    }}
    .popup-cidade {{
      font-size: 0.95rem;
      line-height: 1.4;
    }}
    .popup-cidade h3 {{
      font-size: 1.1rem;
      font-weight: 700;
      margin-bottom: 6px;
      color: #0f172a;
    }}
    .popup-cidade p {{
      margin: 4px 0;
      font-size: 0.85rem;
      color: #475569;
    }}

    /* Estilos da Análise de Migração Eleitoral */
    .migration-banner {{
      background: linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(2, 132, 199, 0.08) 100%);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 16px 20px;
      margin-bottom: 20px;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
    }}
    .migration-banner-text h3 {{
      font-size: 1.15rem;
      font-weight: 800;
      color: var(--text-main);
      margin-bottom: 4px;
    }}
    .migration-banner-text p {{
      font-size: 0.86rem;
      color: var(--text-muted);
      line-height: 1.4;
      margin: 0;
    }}
    .tse-badges-group {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .btn-tse-badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: #0284c7;
      color: #ffffff !important;
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 0.82rem;
      font-weight: 700;
      text-decoration: none;
      box-shadow: 0 2px 4px rgba(2, 132, 199, 0.2);
      transition: all 0.2s;
    }}
    .btn-tse-badge:hover {{
      background: #0369a1;
      transform: translateY(-1px);
    }}
    .btn-tse-badge.alt {{
      background: var(--bg-card);
      color: #0284c7 !important;
      border: 1px solid #0284c7;
    }}
    .btn-tse-badge.alt:hover {{
      background: var(--neutral-bg);
    }}
    .decomposicao-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
      gap: 14px;
      margin-bottom: 22px;
    }}
    .decomp-card {{
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 16px;
      position: relative;
      overflow: hidden;
    }}
    .decomp-card::before {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 4px;
    }}
    .decomp-card.red::before {{ background: var(--lula-color); }}
    .decomp-card.blue::before {{ background: #0284c7; }}
    .decomp-card.purple::before {{ background: #8b5cf6; }}
    .decomp-card.amber::before {{ background: #f59e0b; }}

    .decomp-title {{
      font-size: 0.78rem;
      text-transform: uppercase;
      font-weight: 700;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      margin-bottom: 6px;
    }}
    .decomp-val {{
      font-size: 1.55rem;
      font-weight: 800;
      font-family: 'JetBrains Mono', monospace;
      color: var(--text-main);
      margin-bottom: 4px;
    }}
    .decomp-desc {{
      font-size: 0.82rem;
      color: var(--text-muted);
      line-height: 1.35;
    }}

    .regiao-flex {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin-bottom: 24px;
      background: var(--bg-secondary);
      padding: 16px 20px;
      border-radius: 12px;
      border: 1px solid var(--border-color);
    }}
    .regiao-row {{
      display: grid;
      grid-template-columns: 140px 1fr 180px;
      align-items: center;
      gap: 14px;
      font-size: 0.86rem;
    }}
    .regiao-name {{
      font-weight: 700;
      color: var(--text-main);
    }}
    .regiao-bar-bg {{
      height: 12px;
      background: rgba(0,0,0,0.06);
      border-radius: 999px;
      overflow: hidden;
    }}
    [data-theme="dark"] .regiao-bar-bg {{
      background: rgba(255,255,255,0.08);
    }}
    .regiao-bar-fill {{
      height: 100%;
      background: linear-gradient(90deg, #ef4444, #f97316);
      border-radius: 999px;
    }}
    .regiao-stats {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.82rem;
      text-align: right;
      font-weight: 700;
      color: var(--lula-color);
    }}

    .btn-tse-table {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: #0284c7;
      color: #ffffff !important;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 0.72rem;
      font-weight: 700;
      text-decoration: none;
      transition: background 0.15s;
      white-space: nowrap;
    }}
    .btn-tse-table:hover {{
      background: #0369a1;
    }}
    .btn-tse-table.sec {{
      background: var(--bg-card);
      color: #0284c7 !important;
      border: 1px solid rgba(2, 132, 199, 0.3);
    }}
    .btn-tse-table.sec:hover {{
      background: var(--neutral-bg);
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="header-top">
        <div class="badge-live">Auditoria Eleitoral em Tempo Real • 2º Turno Oficial</div>
        <button class="theme-toggle" onclick="alternarTema()">
          <span id="theme-icon">🌙</span> <span id="theme-text">Modo Escuro</span>
        </button>
      </div>
      <h1>Mapa de Calor: Seções Absolutas no Brasil</h1>
      <p class="subtitle">
        Análise nacional de todas as 472.028 seções eleitorais nas 27 UFs e Exterior, identificando as cidades onde Lula e Bolsonaro registraram hegemonia absoluta (100% dos votos nominais) e quase absoluta (≥ 90% dos votos).
      </p>
    </header>

    <!-- KPIs Totais -->
    <div class="kpi-grid">
      <div class="kpi-card neutral">
        <div class="kpi-title">Total de Seções no Brasil</div>
        <div class="kpi-value" id="kpi-total-secoes">472.028</div>
        <div class="kpi-desc">Todas as 28 UFs (incluindo Exterior ZZ)</div>
      </div>
      <div class="kpi-card lula">
        <div class="kpi-title">Seções 100% LULA</div>
        <div class="kpi-value" id="kpi-100-lula">143</div>
        <div class="kpi-desc">Zero votos para o concorrente</div>
      </div>
      <div class="kpi-card bolsonaro">
        <div class="kpi-title">Seções 100% BOLSONARO</div>
        <div class="kpi-value" id="kpi-100-bols">4</div>
        <div class="kpi-desc">Zero votos para o concorrente</div>
      </div>
      <div class="kpi-card lula">
        <div class="kpi-title">Seções ≥ 90% LULA</div>
        <div class="kpi-value" id="kpi-90-lula">9.538</div>
        <div class="kpi-desc">Hegemonia quase total (90% a 100%)</div>
      </div>
      <div class="kpi-card bolsonaro">
        <div class="kpi-title">Seções ≥ 90% BOLSONARO</div>
        <div class="kpi-value" id="kpi-90-bols">220</div>
        <div class="kpi-desc">Hegemonia quase total (90% a 100%)</div>
      </div>
    </div>

    <!-- Barra de Controles Globais -->
    <div class="controls-bar">
      <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
        <span style="font-weight: 700; font-size: 0.9rem; color: var(--text-muted);">Métrica Ativa:</span>
        <div class="button-group">
          <button class="btn-toggle active" id="btn-metrica-100" onclick="alterarMetrica('100')">100% Absoluto</button>
          <button class="btn-toggle" id="btn-metrica-90" onclick="alterarMetrica('90')">≥ 90% Hegemônico</button>
        </div>
      </div>

      <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
        <span style="font-weight: 700; font-size: 0.9rem; color: var(--text-muted);">Filtro de Candidato:</span>
        <div class="button-group">
          <button class="btn-toggle active" id="btn-cand-ambos" onclick="alterarCandidato('ambos')">Ambos Candidatos</button>
          <button class="btn-toggle" id="btn-cand-lula" onclick="alterarCandidato('lula')">Lula (PT)</button>
          <button class="btn-toggle" id="btn-cand-bols" onclick="alterarCandidato('bolsonaro')">Bolsonaro (PL)</button>
        </div>
      </div>
    </div>

    <!-- 1. MAPA DE CALOR POR UF -->
    <div class="card-panel">
      <div class="panel-header">
        <div>
          <h2 class="panel-title" id="titulo-mapa-calor">Mapa de Calor por UF (Seções 100% Absolutas)</h2>
          <span style="font-size: 0.85rem; color: var(--text-muted);">Intensidade de cor baseada na quantidade de seções dominadas no estado. Clique em uma UF para filtrar.</span>
        </div>
        <button class="theme-toggle" onclick="resetFiltroUF()" id="btn-limpar-uf" style="display: none;">
          ✕ Limpar Filtro UF
        </button>
      </div>
      <div class="uf-grid" id="uf-grid-container">
        <!-- Renderizado dinamicamente -->
      </div>
    </div>

    <!-- 2. NOVO: MAPA DO BRASIL COM AS CIDADES (Leaflet) -->
    <div class="card-panel">
      <div class="panel-header">
        <div>
          <h2 class="panel-title" id="titulo-mapa-cidades">Mapa do Brasil com as Cidades Hegemônicas</h2>
          <span style="font-size: 0.85rem; color: var(--text-muted);">Distribuição geográfica real das cidades com seções absolutas (100%) ou quase absolutas (≥90%). Clique nos pontos para abrir os detalhes e o link do Boletim de Urna no TSE.</span>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="theme-toggle" onclick="resetZoomMapa()">⟲ Centralizar Brasil</button>
        </div>
      </div>

      <!-- Container do Mapa Leaflet -->
      <div id="mapa-brasil-cidades"></div>

      <!-- Legenda do Mapa -->
      <div class="mapa-legend">
        <div class="legend-item">
          <span class="legend-circle lula"></span>
          <span><strong>Vermelho:</strong> Cidades com seções de Lula</span>
        </div>
        <div class="legend-item">
          <span class="legend-circle bols"></span>
          <span><strong>Verde:</strong> Cidades com seções de Bolsonaro</span>
        </div>
        <div class="legend-item" style="color: var(--text-faint); margin-left: auto;">
          * O raio do círculo é proporcional à quantidade de seções na cidade.
        </div>
      </div>
    </div>

    <!-- 3. RANKINGS E COMPARAÇÃO LADO A LADO -->
    <div class="ranking-grid">
      <div class="card-panel">
        <div class="panel-header">
          <h2 class="panel-title">Top Estados com Hegemonia de LULA</h2>
          <span style="font-size: 0.85rem; color: var(--lula-color); font-weight: 700;">Concentração no Norte e Nordeste</span>
        </div>
        <div class="ranking-list" id="ranking-lula-container">
          <!-- Renderizado via JS -->
        </div>
      </div>

      <div class="card-panel">
        <div class="panel-header">
          <h2 class="panel-title">Top Estados com Hegemonia de BOLSONARO</h2>
          <span style="font-size: 0.85rem; color: var(--bolsonaro-color); font-weight: 700;">Concentração no Sul, Centro-Oeste e Exterior</span>
        </div>
        <div class="ranking-list" id="ranking-bols-container">
          <!-- Renderizado via JS -->
        </div>
      </div>
    </div>

    <!-- 4. NOVO: ANÁLISE DE MIGRAÇÃO ELEITORAL (ORIGEM DOS ~11M DE NOVOS VOTOS DE LULA) -->
    <div class="card-panel">
      <div class="panel-header">
        <div>
          <h2 class="panel-title">Análise de Migração Eleitoral: De Onde Vieram os Novos Votos de Lula no 2º Turno?</h2>
          <span style="font-size: 0.85rem; color: var(--text-muted);">
            Comparação oficial auditada entre o 1º Turno (Eleição Ordinária 6257) e o 2º Turno (Eleição Ordinária 6258) com links diretos aos Boletins e Painéis Oficiais do TSE.
          </span>
        </div>
        <div class="tse-badges-group">
          <a href="https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6257/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/br" target="_blank" class="btn-tse-badge">
            Totalização Brasil 1ºT no TSE ↗
          </a>
          <a href="https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6258/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/br" target="_blank" class="btn-tse-badge alt">
            Totalização Brasil 2ºT no TSE ↗
          </a>
        </div>
      </div>

      <!-- Banner Explicativo -->
      <div class="migration-banner">
        <div class="migration-banner-text">
          <h3>+10.376.694 votos nominais adicionais (+19,26% / ~10,4M - ~11 Milhões)</h3>
          <p>
            No 2º Turno, o candidato Lula avançou de <strong>53.879.538</strong> para <strong>64.256.232 votos</strong> (+10.376.694), enquanto Bolsonaro foi de 56.104.503 para 59.826.041 (+3.721.538). Dos ~14,1 milhões de votos disponíveis na repactuação eleitoral, Lula absorveu <strong>73,6%</strong>, consolidando a vitória nacional.
          </p>
        </div>
      </div>

      <!-- Decomposição das 4 Fontes de Votos -->
      <h3 style="font-size: 0.95rem; font-weight: 700; margin-bottom: 12px; color: var(--text-main);">1. Decomposição das 4 Fontes dos Votos em Disputa (Reservatório Nacional)</h3>
      <div class="decomposicao-grid">
        <div class="decomp-card red">
          <div class="decomp-title">Crescimento Líquido de Lula</div>
          <div class="decomp-val" style="color: var(--lula-color);">+10.376.694</div>
          <div class="decomp-desc">Salto de 53,88M para 64,26M (+19,26%). Lula capturou quase 3 de cada 4 votos em disputa no 2º turno.</div>
        </div>
        <div class="decomp-card blue">
          <div class="decomp-title">Votos de 3ºs Candidatos (1ºT)</div>
          <div class="decomp-val" style="color: #0284c7;">9.316.747</div>
          <div class="decomp-desc">Eleitores de Augusto Cury (3,45M), Renan Santos (2,68M), Ronaldo Caiado (2,61M) e outros que migraram no 2º turno.</div>
        </div>
        <div class="decomp-card purple">
          <div class="decomp-title">Mobilização de Eleitores</div>
          <div class="decomp-val" style="color: #8b5cf6;">+2.960.239</div>
          <div class="decomp-desc">Queda de abstenção: 2,96 milhões de eleitores que se abstiveram no 1º turno foram às urnas no 2º turno.</div>
        </div>
        <div class="decomp-card amber">
          <div class="decomp-title">Migração de Brancos e Nulos</div>
          <div class="decomp-val" style="color: #f59e0b;">+1.816.000</div>
          <div class="decomp-desc">870 mil eleitores deixaram de votar em branco e 945 mil deixaram de anular, escolhendo voto nominal válido.</div>
        </div>
      </div>

      <!-- Decomposição Regional -->
      <h3 style="font-size: 0.95rem; font-weight: 700; margin-bottom: 12px; color: var(--text-main);">2. Onde Lula Mais Cresceu por Região Geográfica</h3>
      <div class="regiao-flex" id="container-regioes-migracao">
        <!-- Renderizado dinamicamente via JS -->
      </div>

      <!-- Tabela por UF -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
        <h3 style="font-size: 0.95rem; font-weight: 700; color: var(--text-main);">3. Tabela Auditada Estado por Estado (28 UFs) com Links Oficiais do TSE</h3>
        <input type="text" id="filtro-migracao" placeholder="Filtrar estado ou região..." oninput="filtrarTabelaMigracao()" style="background: var(--bg-secondary); border: 1px solid var(--border-color); color: var(--text-main); padding: 6px 12px; border-radius: 8px; font-family: inherit; font-size: 0.82rem; width: 220px;">
      </div>

      <div class="table-container" style="max-height: 480px;">
        <table>
          <thead>
            <tr>
              <th>UF</th>
              <th>Região</th>
              <th>Lula 1ºT</th>
              <th>Lula 2ºT</th>
              <th>Ganho Líquido (Delta)</th>
              <th>% Cresc.</th>
              <th>Part. Ganho Nacional</th>
              <th>Bolsonaro 2ºT</th>
              <th>Referência Oficial TSE</th>
            </tr>
          </thead>
          <tbody id="tabela-migracao-body">
            <!-- Renderizado dinamicamente via JS -->
          </tbody>
        </table>
      </div>
    </div>

    <!-- 5. TABELA DE SEÇÕES AUDITADAS -->
    <div class="card-panel">
      <div class="panel-header">
        <div>
          <h2 class="panel-title">Amostragem de Seções Eleitorais Auditadas</h2>
          <span style="font-size: 0.85rem; color: var(--text-muted);">Acesse a prova material de qualquer seção diretamente no portal de resultados do TSE</span>
        </div>
        <div>
          <input type="text" id="filtro-busca" placeholder="Filtrar por cidade ou UF..." oninput="filtrarTabela()" style="background: var(--bg-secondary); border: 1px solid var(--border-color); color: var(--text-main); padding: 8px 14px; border-radius: 8px; font-family: inherit; font-size: 0.85rem; width: 240px;">
        </div>
      </div>

      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>UF</th>
              <th>Município</th>
              <th>Zona</th>
              <th>Seção</th>
              <th>Candidato Hegemônico</th>
              <th>% Votos</th>
              <th>Votos Nominais</th>
              <th>Aptos</th>
              <th>Ação</th>
            </tr>
          </thead>
          <tbody id="tabela-secoes-body">
            <!-- Renderizado via JS -->
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    // DADOS EMBARCADOS PARA FUNCIONAMENTO 100% OFFLINE / LOCAL
    const DADOS_APP = {dados_app_json_str};
    const CIDADES_MAPA = {cidades_compact_str};
    const DADOS_MIGRACAO = {decomposicao_json_str};

    let metricaAtual = '100'; // '100' ou '90'
    let candAtual = 'ambos';  // 'ambos', 'lula', 'bolsonaro'
    let ufSelecionada = null;
    let mapaLeaflet = null;
    let camadaMarcadores = null;

    function alternarTema() {{
      const html = document.documentElement;
      const temaAtual = html.getAttribute('data-theme');
      const novoTema = temaAtual === 'light' ? 'dark' : 'light';
      html.setAttribute('data-theme', novoTema);

      document.getElementById('theme-icon').innerText = novoTema === 'light' ? '🌙' : '☀️';
      document.getElementById('theme-text').innerText = novoTema === 'light' ? 'Modo Escuro' : 'Modo Claro';

      // Atualizar azulejos do mapa
      if (mapaLeaflet) {{
        mapaLeaflet.eachLayer(layer => {{
          if (layer._url) mapaLeaflet.removeLayer(layer);
        }});
        const tileUrl = 'https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png';
        L.tileLayer(tileUrl, {{
          attribution: '&copy; OpenStreetMap contributors',
          maxZoom: 18
        }}).addTo(mapaLeaflet);
      }}

      renderizarGridUFs();
    }}

    function alterarMetrica(metrica) {{
      metricaAtual = metrica;
      document.getElementById('btn-metrica-100').classList.toggle('active', metrica === '100');
      document.getElementById('btn-metrica-90').classList.toggle('active', metrica === '90');
      atualizarInterface();
      atualizarMapaCidades();
    }}

    function alterarCandidato(cand) {{
      candAtual = cand;
      document.getElementById('btn-cand-ambos').classList.toggle('active', cand === 'ambos');
      document.getElementById('btn-cand-lula').classList.toggle('active', cand === 'lula');
      document.getElementById('btn-cand-lula').classList.toggle('lula-active', cand === 'lula');
      document.getElementById('btn-cand-bols').classList.toggle('active', cand === 'bolsonaro');
      document.getElementById('btn-cand-bols').classList.toggle('bols-active', cand === 'bolsonaro');
      atualizarInterface();
      atualizarMapaCidades();
    }}

    function resetFiltroUF() {{
      ufSelecionada = null;
      document.getElementById('btn-limpar-uf').style.display = 'none';
      renderizarGridUFs();
      renderizarTabela();
      atualizarMapaCidades();
    }}

    function atualizarInterface() {{
      const totais = DADOS_APP.totais_brasil;
      document.getElementById('kpi-total-secoes').innerText = totais.total_secoes.toLocaleString('pt-BR');
      document.getElementById('kpi-100-lula').innerText = totais.secoes_100_lula.toLocaleString('pt-BR');
      document.getElementById('kpi-100-bols').innerText = totais.secoes_100_bolsonaro.toLocaleString('pt-BR');
      document.getElementById('kpi-90-lula').innerText = totais.secoes_90_mais_100_lula.toLocaleString('pt-BR');
      document.getElementById('kpi-90-bols').innerText = totais.secoes_90_mais_100_bolsonaro.toLocaleString('pt-BR');

      document.getElementById('titulo-mapa-calor').innerText = metricaAtual === '100'
        ? "Mapa de Calor por UF (Seções 100% Absolutas)"
        : "Mapa de Calor por UF (Seções ≥ 90% Hegemônicas)";

      document.getElementById('titulo-mapa-cidades').innerText = metricaAtual === '100'
        ? "Mapa do Brasil com as Cidades com Seções 100% Absolutas"
        : "Mapa do Brasil com as Cidades com Seções ≥ 90% Hegemônicas";

      renderizarGridUFs();
      renderizarRankings();
      renderizarTabela();
    }}

    function renderizarGridUFs() {{
      const container = document.getElementById('uf-grid-container');
      container.innerHTML = '';

      DADOS_APP.resumos_uf.forEach(r => {{
        let lulaVal = metricaAtual === '100' ? r.secoes_100_lula : r.secoes_90_mais_100_lula;
        let bolsVal = metricaAtual === '100' ? r.secoes_100_bolsonaro : r.secoes_90_mais_100_bolsonaro;
        let totalVal = lulaVal + bolsVal;

        let tile = document.createElement('div');
        tile.className = 'uf-tile';

        if (ufSelecionada === r.uf) {{
          tile.style.borderColor = 'var(--neutral-color)';
          tile.style.boxShadow = '0 0 0 2px var(--neutral-color)';
        }}

        tile.onclick = () => {{
          ufSelecionada = (ufSelecionada === r.uf) ? null : r.uf;
          document.getElementById('btn-limpar-uf').style.display = ufSelecionada ? 'inline-flex' : 'none';
          renderizarGridUFs();
          renderizarTabela();
          if (ufSelecionada) {{
            // filtrar cidades no mapa
            atualizarMapaCidades();
          }}
        }};

        // Intensidade de calor no fundo claro
        let isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        let calorColor = 'transparent';

        if (candAtual === 'lula' || (candAtual === 'ambos' && lulaVal > bolsVal)) {{
          if (lulaVal > 0) {{
            let op = Math.min(0.28, 0.05 + (lulaVal / (metricaAtual === '100' ? 60 : 3000)));
            calorColor = isDark ? `rgba(239, 68, 68, ${{op * 1.5}})` : `rgba(220, 38, 38, ${{op}})`;
          }}
        }} else if (candAtual === 'bolsonaro' || (candAtual === 'ambos' && bolsVal > lulaVal)) {{
          if (bolsVal > 0) {{
            let op = Math.min(0.28, 0.05 + (bolsVal / (metricaAtual === '100' ? 6 : 80)));
            calorColor = isDark ? `rgba(34, 197, 94, ${{op * 1.5}})` : `rgba(22, 163, 74, ${{op}})`;
          }}
        }}

        if (calorColor !== 'transparent') {{
          tile.style.backgroundColor = calorColor;
        }}

        let pctLula = totalVal > 0 ? (lulaVal / totalVal * 100) : 0;
        let pctBols = totalVal > 0 ? (bolsVal / totalVal * 100) : 0;

        tile.innerHTML = `
          <div class="uf-header">
            <span class="uf-sigla">${{r.uf}}</span>
            <span class="uf-total-secoes">${{r.total_secoes.toLocaleString()}} seções</span>
          </div>
          <div class="uf-stat-row">
            <span class="stat-lula">L: ${{lulaVal}}</span>
            <span class="stat-bols">B: ${{bolsVal}}</span>
          </div>
          <div class="uf-bar-mini">
            <div class="bar-segment-lula" style="width: ${{pctLula}}%"></div>
            <div class="bar-segment-bols" style="width: ${{pctBols}}%"></div>
          </div>
        `;
        container.appendChild(tile);
      }});
    }}

    /* Inicialização do Mapa Leaflet */
    function iniciarMapaLeaflet() {{
      mapaLeaflet = L.map('mapa-brasil-cidades', {{
        center: [-14.235, -51.925],
        zoom: 4,
        minZoom: 3,
        maxZoom: 14,
        scrollWheelZoom: true
      }});

      L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 18
      }}).addTo(mapaLeaflet);

      camadaMarcadores = L.layerGroup().addTo(mapaLeaflet);
      atualizarMapaCidades();
    }}

    function resetZoomMapa() {{
      if (mapaLeaflet) {{
        mapaLeaflet.setView([-14.235, -51.925], 4);
      }}
    }}

    function atualizarMapaCidades() {{
      if (!camadaMarcadores) return;
      camadaMarcadores.clearLayers();

      let cidadesFiltradas = CIDADES_MAPA.filter(c => {{
        if (c.lt === 0 && c.lg === 0) return false;
        if (ufSelecionada && c.uf !== ufSelecionada) return false;

        let qtdLula = metricaAtual === '100' ? c.s100_l : (c.s100_l + c.s90_l);
        let qtdBols = metricaAtual === '100' ? c.s100_b : (c.s100_b + c.s90_b);

        if (candAtual === 'lula' && qtdLula === 0) return false;
        if (candAtual === 'bolsonaro' && qtdBols === 0) return false;
        return (qtdLula + qtdBols) > 0;
      }});

      cidadesFiltradas.forEach(c => {{
        let qtdLula = metricaAtual === '100' ? c.s100_l : (c.s100_l + c.s90_l);
        let qtdBols = metricaAtual === '100' ? c.s100_b : (c.s100_b + c.s90_b);

        let cor = (qtdLula >= qtdBols) ? '#dc2626' : '#16a34a';
        let totalSecoes = qtdLula + qtdBols;
        let raio = Math.min(22, Math.max(5, Math.sqrt(totalSecoes) * 3.5));

        let circulo = L.circleMarker([c.lt, c.lg], {{
          radius: raio,
          fillColor: cor,
          color: '#ffffff',
          weight: 1.5,
          opacity: 0.9,
          fillOpacity: 0.75
        }});

        let popupContent = `
          <div class="popup-cidade">
            <h3>${{c.n}} (${{c.uf}})</h3>
            <p><strong>Candidato Predominante:</strong> ${{qtdLula >= qtdBols ? 'LULA (PT)' : 'BOLSONARO (PL)'}}</p>
            <p><strong>Seções 100% Absolutas:</strong> Lula: ${{c.s100_l}} | Bolsonaro: ${{c.s100_b}}</p>
            <p><strong>Seções ≥ 90% Hegemônicas:</strong> Lula: ${{c.s100_l + c.s90_l}} | Bolsonaro: ${{c.s100_b + c.s90_b}}</p>
            ${{c.url ? `<p style="margin-top:8px;"><a href="${{c.url}}" target="_blank" class="btn-bu" style="display:inline-block; padding: 4px 10px;">Ver Boletim de Urna no TSE ↗</a></p>` : ''}}
          </div>
        `;

        circulo.bindPopup(popupContent);
        circulo.bindTooltip(`${{c.n}} - ${{c.uf}}: ${{totalSecoes}} seções ${{metricaAtual === '100' ? '100%' : '≥90%'}}`, {{
          direction: 'top',
          offset: [0, -raio]
        }});

        camadaMarcadores.addLayer(circulo);
      }});
    }}

    function renderizarRankings() {{
      const contLula = document.getElementById('ranking-lula-container');
      const contBols = document.getElementById('ranking-bols-container');
      contLula.innerHTML = '';
      contBols.innerHTML = '';

      let lista = [...DADOS_APP.resumos_uf].map(r => {{
        let lulaVal = metricaAtual === '100' ? r.secoes_100_lula : r.secoes_90_mais_100_lula;
        let bolsVal = metricaAtual === '100' ? r.secoes_100_bolsonaro : r.secoes_90_mais_100_bolsonaro;
        return {{ ...r, lulaVal, bolsVal }};
      }});

      // Top Lula
      let listaLula = [...lista].filter(x => x.lulaVal > 0).sort((a, b) => b.lulaVal - a.lulaVal);
      let maxLula = listaLula.length ? listaLula[0].lulaVal : 1;

      listaLula.slice(0, 10).forEach(item => {{
        let el = document.createElement('div');
        el.className = 'ranking-item';
        let width = (item.lulaVal / maxLula * 100);
        el.innerHTML = `
          <div class="ranking-top">
            <span><strong>${{item.uf}}</strong> • ${{item.total_secoes.toLocaleString()}} seções</span>
            <span style="color: var(--lula-color); font-weight:700;">${{item.lulaVal}} seções</span>
          </div>
          <div class="bar-row">
            <span class="bar-label" style="color: var(--lula-color);">LULA</span>
            <div class="bar-track">
              <div class="bar-fill-lula" style="width: ${{width}}%"></div>
            </div>
            <span class="bar-num" style="color: var(--lula-color);">${{item.lulaVal}}</span>
          </div>
        `;
        contLula.appendChild(el);
      }});

      // Top Bolsonaro
      let listaBols = [...lista].filter(x => x.bolsVal > 0).sort((a, b) => b.bolsVal - a.bolsVal);
      let maxBols = listaBols.length ? listaBols[0].bolsVal : 1;

      listaBols.slice(0, 10).forEach(item => {{
        let el = document.createElement('div');
        el.className = 'ranking-item';
        let width = (item.bolsVal / maxBols * 100);
        el.innerHTML = `
          <div class="ranking-top">
            <span><strong>${{item.uf}}</strong> • ${{item.total_secoes.toLocaleString()}} seções</span>
            <span style="color: var(--bolsonaro-color); font-weight:700;">${{item.bolsVal}} seções</span>
          </div>
          <div class="bar-row">
            <span class="bar-label" style="color: var(--bolsonaro-color);">BOLSONARO</span>
            <div class="bar-track">
              <div class="bar-fill-bols" style="width: ${{width}}%"></div>
            </div>
            <span class="bar-num" style="color: var(--bolsonaro-color);">${{item.bolsVal}}</span>
          </div>
        `;
        contBols.appendChild(el);
      }});
    }}

    function renderizarTabela() {{
      const tbody = document.getElementById('tabela-secoes-body');
      tbody.innerHTML = '';

      let listaSeções = (metricaAtual === '100') ? DADOS_APP.secoes_100_amostra : DADOS_APP.secoes_90_amostra;
      const filtroTexto = document.getElementById('filtro-busca').value.toLowerCase();

      let filtradas = listaSeções.filter(s => {{
        if (ufSelecionada && s.uf !== ufSelecionada) return false;
        if (candAtual === 'lula' && s.candidato !== 'LULA') return false;
        if (candAtual === 'bolsonaro' && s.candidato !== 'JAIR BOLSONARO') return false;
        if (filtroTexto) {{
          return s.nome_municipio.toLowerCase().includes(filtroTexto) || s.uf.toLowerCase().includes(filtroTexto);
        }}
        return true;
      }});

      filtradas.slice(0, 150).forEach(s => {{
        let tr = document.createElement('tr');
        let pillClass = s.candidato === 'LULA' ? 'pill-lula' : 'pill-bolsonaro';
        tr.innerHTML = `
          <td><strong>${{s.uf}}</strong></td>
          <td>${{s.nome_municipio}}</td>
          <td>${{s.zona}}</td>
          <td>${{s.secao}}</td>
          <td><span class="pill-cand ${{pillClass}}">${{s.candidato}}</span></td>
          <td><strong>${{s.percentual}}%</strong></td>
          <td>${{s.votos_nominais}}</td>
          <td>${{s.aptos}}</td>
          <td><a href="${{s.url_tse}}" target="_blank" class="btn-bu">Ver no TSE ↗</a></td>
        `;
        tbody.appendChild(tr);
      }});

      if (filtradas.length === 0) {{
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding: 24px; color: var(--text-muted);">Nenhuma seção encontrada com os filtros atuais.</td></tr>';
      }}
    }}

    function filtrarTabela() {{
      renderizarTabela();
    }}

    function renderizarMigracao() {{
      // 1. Renderizar barras regionais
      const regContainer = document.getElementById('container-regioes-migracao');
      if (regContainer && DADOS_MIGRACAO.resumo_regional) {{
        regContainer.innerHTML = '';
        const maxDelta = Math.max(...DADOS_MIGRACAO.resumo_regional.map(r => r.delta_lula));
        DADOS_MIGRACAO.resumo_regional.forEach(reg => {{
          const row = document.createElement('div');
          row.className = 'regiao-row';
          const pctLargura = (reg.delta_lula / maxDelta) * 100;
          row.innerHTML = `
            <div class="regiao-name">Região ${{reg.regiao}}</div>
            <div class="regiao-bar-bg">
              <div class="regiao-bar-fill" style="width: ${{pctLargura}}%"></div>
            </div>
            <div class="regiao-stats">
              +${{reg.delta_lula.toLocaleString('pt-BR')}} (${{reg.participacao_ganho_nacional_pct}}%)
            </div>
          `;
          regContainer.appendChild(row);
        }});
      }}

      // 2. Renderizar tabela de estados
      renderizarTabelaMigracao();
    }}

    function renderizarTabelaMigracao() {{
      const tbody = document.getElementById('tabela-migracao-body');
      if (!tbody || !DADOS_MIGRACAO.estados) return;
      tbody.innerHTML = '';

      const termo = (document.getElementById('filtro-migracao')?.value || '').toLowerCase().trim();

      const filtrados = DADOS_MIGRACAO.estados.filter(e => {{
        if (!termo) return true;
        return e.uf.toLowerCase().includes(termo) || e.nome_uf.toLowerCase().includes(termo) || e.regiao.toLowerCase().includes(termo);
      }});

      filtrados.forEach(e => {{
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${{e.uf}}</strong> <span style="font-size:0.75rem; color:var(--text-muted);">(${{e.nome_uf}})</span></td>
          <td><span style="font-size:0.8rem; background:var(--bg-secondary); padding:2px 8px; border-radius:4px;">${{e.regiao}}</span></td>
          <td>${{e.lula_1t.toLocaleString('pt-BR')}}</td>
          <td>${{e.lula_2t.toLocaleString('pt-BR')}}</td>
          <td style="color:var(--lula-color); font-weight:700;">+${{e.delta_lula.toLocaleString('pt-BR')}}</td>
          <td><strong>+${{e.pct_crescimento_lula}}%</strong></td>
          <td><strong>${{e.participacao_ganho_nacional_pct}}%</strong></td>
          <td>${{e.bolsonaro_2t.toLocaleString('pt-BR')}}</td>
          <td>
            <div style="display:flex; gap:6px;">
              <a href="${{e.url_painel_tse_1t}}" target="_blank" class="btn-tse-table sec" title="Ver 1º Turno no TSE">1ºT ↗</a>
              <a href="${{e.url_painel_tse_2t}}" target="_blank" class="btn-tse-table" title="Ver 2º Turno no TSE">2ºT ↗</a>
            </div>
          </td>
        `;
        tbody.appendChild(tr);
      }});

      if (filtrados.length === 0) {{
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding: 20px; color: var(--text-muted);">Nenhum estado encontrado.</td></tr>';
      }}
    }}

    function filtrarTabelaMigracao() {{
      renderizarTabelaMigracao();
    }}

    window.onload = () => {{
      atualizarInterface();
      iniciarMapaLeaflet();
      renderizarMigracao();
    }};
  </script>
</body>
</html>
'''

caminho_mapa = os.path.join(ROOT_DIR, "mapa_calor_eleicoes.html")
caminho_index = os.path.join(ROOT_DIR, "index.html")

with open(caminho_mapa, "w", encoding="utf-8") as f_out:
    f_out.write(html_template)

with open(caminho_index, "w", encoding="utf-8") as f_out:
    f_out.write(html_template)

print(f"Arquivos {caminho_mapa} e {caminho_index} gerados com sucesso!")
