# Auditoria Criptográfica e Análise Estatística de Urnas Eletrônicas (TSE) - Eleições 2022 / 2026

Repositório técnico de inteligência de dados, descompactação criptográfica e auditoria estatística dos arquivos oficiais de **Log de Urna** (`.jez` / `logd.dat`) e **Boletins de Urna na Web** (`BWEB`) do Tribunal Superior Eleitoral (TSE).

Este projeto cobre desde a engenharia reversa do formato proprietário de logs da Urna Eletrônica (Uenux) até a análise exaustiva das **472.028 seções eleitorais** do Brasil e Exterior no 2º Turno Presidencial, mapeando as seções com votações unânimes (**100%**) e quase unânimes (**$\ge 90\%$**), tempos de permanência em cabine e diagnósticos empíricos de integridade.

---

## 📌 Sumário Executivo

1. [Visão Geral do Projeto](#visão-geral-do-projeto)
2. [Item 1: O Arquivo `.jez`, `logd.dat` e Formato dos Logs](#item-1-o-arquivo-jez-logddat-e-formato-dos-logs)
3. [Item 2: Análise dos Horários e Tempo de Permanência na Cabine](#item-2-análise-dos-horários-e-tempo-de-permanência-na-cabine)
4. [Item 3: Comparação de Seções e Auditoria de Suspeitas de Fraude](#item-3-comparação-de-seções-e-auditoria-de-suspeitas-de-fraude)
5. [Item 4: Seções 100% Absolutas no Brasil (2º Turno)](#item-4-seções-100-absolutas-no-brasil-2º-turno)
6. [Item 5: Seções Hegemônicas $\ge 90\%$ e Mapa Geográfico Nacional](#item-5-seções-hegemônicas-ge-90-e-mapa-geográfico-nacional)
7. [Item 6: Análise de Migração Eleitoral (Origem dos ~11M de Novos Votos de Lula)](#item-6-análise-de-migração-eleitoral)
8. [Dashboard Interativo (`mapa_calor_eleicoes.html`)](#dashboard-interativo)
9. [Estrutura de Diretórios e Catálogo de Arquivos](#estrutura-de-diretórios-e-catálogo-de-arquivos)

---

## 🏛️ Visão Geral do Projeto

Durante e após os pleitos eleitorais, discussões públicas frequentemente levantam suspeitas sobre seções eleitorais onde um único candidato obteve **100% dos votos nominais** ou onde a velocidade de votação foi supostamente rápida demais.

Este projeto foi construído com metodologia de **engenharia reversa baseada em evidências empíricas e auditabilidade ponta a ponta**:
- **Nível Micro (Urna Individual):** Descompactação do arquivo `.jez` em memória, extração do `logd.dat`, validação da cadeia de integridade SipHash e mensuração do delta temporal exato entre `Eleitor foi habilitado` e `O voto do eleitor foi computado`.
- **Nível Comparativo:** Comparação temporal e comportamental entre uma seção 100% Lula no semiárido mineiro (Luislândia/MG) e uma seção de alto volume pró-Bolsonaro no sul do país (Nova Hartz/RS).
- **Nível Macro (Nacional):** Download e processamento das **28 Unidades Federativas** (todas as 26 UFs + DF + Seções no Exterior ZZ), totalizando **472.028 seções eleitorais** e mais de **124 milhões de votos**, catalogando todas as seções de 100% e $\ge 90\%$ para ambos os candidatos (Lula e Jair Bolsonaro).

---

## 🔍 Item 1: O Arquivo `.jez`, `logd.dat` e Formato dos Logs

### 1.1 O que é o `.jez`?
O arquivo `.jez` (ex: `o03221mg4100900500224-log.jez`) é um contêiner compactado no formato **ZIP padrão** (`deflate`), gerado pelo sistema operacional da urna (**Uenux**, distribuição Linux embarcada baseada em Debian mantida pelo TSE).

Dentro do `.jez` reside o arquivo essencial de auditoria:
* **`logd.dat`**: O fluxo serial de eventos gerado pelo daemon de log do sistema em tempo de execução.

### 1.2 Nomenclatura Padrão dos Arquivos Oficiais
O identificador do arquivo segue o padrão de metadados da Justiça Eleitoral:

| Segmento | Exemplo (`o03221mg4100900500224-log.jez`) | Significado |
| :--- | :--- | :--- |
| **Prefixo** | `o` | Oficial (Ambiente oficial de votação) |
| **Pleito** | `03221` | Código da eleição / pleito |
| **UF** | `mg` | Unidade Federativa (Minas Gerais) |
| **Município** | `41009` | Código do município no TSE (Luislândia - MG) |
| **Zona** | `0050` | Zona Eleitoral |
| **Seção** | `0224` | Seção Eleitoral |
| **Sufixo** | `-log.jez` | Pacote de logs de auditoria |

### 1.3 Estrutura do `logd.dat`
O arquivo é codificado em **`ISO-8859-1` (Latin-1)** com delimitadores tabulação (`\t`) e 6 colunas por linha:

```text
[DATA_HORA] \t [SEVERIDADE] \t [ID_PROCESSO] \t [SUBSISTEMA] \t [MENSAGEM] \t [MAC_SIPHASH]
```

1. **`Data e Hora`** (`DD/MM/AAAA HH:MM:SS`): Carimbo de tempo do relógio de hardware (RTC) da urna.
2. **`Severidade`**: Nível do evento (`INFO`, `AVISO`, `ERRO`).
3. **`ID Processo`**: PID da thread/processo em execução no Uenux.
4. **`Subsistema`**:
   - `LOGD`: Daemon central de logs.
   - `SCUE`: Sistema de Carga da Urna Eletrônica (boot e validação de assinaturas de software).
   - `GAP`: Gerenciador de Aplicativos (mídias criptográficas e chaves de resultado).
   - `ATUE`: Auto-Teste da Urna Eletrônica (checagem de teclado, áudio e leitor biométrico).
   - `VOTA`: Sistema de Votação (Zerésima, habilitação de eleitor, registro e Boletim de Urna).
5. **`Mensagem`**: Descrição textual unívoca da operação.
6. **`Código MAC / Hash da Linha`**: Hash criptográfico de 16 caracteres hexadecimais gerado por função **SipHash-2-4 encadeada**, onde cada linha consome o hash da linha anterior. Qualquer inserção, modificação ou remoção de linha invalida toda a cadeia subsequente.

### 1.4 Verificação contra os Hashes da Cerimônia de Lacração do TSE
Na inicialização da urna, o módulo `SCUE` audita e valida a assinatura digital e o hash SHA-512 de cada pacote binário (`.vst`):
```text
19/09/2026 14:37:58 INFO 02030910 SCUE Verificação de assinatura de aplicação por etapa [1] - [Pacote: /bin/avbin.vst] - [SUCESSO]
19/09/2026 14:37:58 INFO 02030910 SCUE Verificação de assinatura de aplicação por etapa [2] - [Pacote: /uenux/bin/avusrbin.vst] - [SUCESSO]
```
Esses hashes são rigorosamente idênticos aos divulgados publicamente na [Cerimônia de Lacração e Assinatura Digital dos Sistemas Eleitorais](https://www.tse.jus.br).

---

## ⏱️ Item 2: Análise dos Horários e Tempo de Permanência na Cabine

A velocidade do eleitor na cabine é calculada pelo intervalo de tempo entre dois eventos emitidos pelo subsistema `VOTA`:
1. **`Eleitor foi habilitado`**: Momento em que o mesário autoriza o eleitor no terminal do mesário (via biometria ou código de liberação).
2. **`O voto do eleitor foi computado`**: Momento em que o eleitor pressiona "CONFIRMA" no cargo final e a urna emite o sinal sonoro clássico.

### Comparativo Empírico: Luislândia/MG vs Nova Hartz/RS

| Métrica | Luislândia / MG (Seção 224) | Nova Hartz / RS (Seção 274) |
| :--- | :--- | :--- |
| **Localidade** | Comunidade Rural São João | Bairro Residencial Urbano |
| **Eleitores que Votaram** | 71 eleitores | 242 eleitores |
| **Tempo Médio de Cabine** | **13,6 segundos** | **11,0 segundos** |
| **Tempo Mínimo de Cabine** | 6 segundos | 4 segundos |
| **Tempo Máximo de Cabine** | 34 segundos | 32 segundos |
| **Desvio Padrão do Tempo** | ~6,1 segundos | ~4,8 segundos |
| **Intervalo Médio Entre Eleitores** | ~2 a 5 minutos (ritmo espaçado) | ~30s a 1m20s (fluxo contínuo) |
| **Horário de Abertura / Encerramento** | 08:00:23 / 17:00:46 | 08:00:08 / 17:00:12 |

### Por que o tempo médio no 2º Turno é tão rápido (11s a 14s)?
- **1º Turno:** O eleitor digita votos para **5 cargos diferentes** (Deputado Federal [4 dígitos], Deputado Estadual [5 dígitos], Senador [3 dígitos], Governador [2 dígitos] e Presidente [2 dígitos]), demandando em média **60 a 105 segundos** por eleitor.
- **2º Turno:** Nos estados sem segundo turno para governador (como MG), o eleitor vota para **apenas 1 cargo** (Presidente: 2 dígitos + confirma). Digitar 2 dígitos e pressionar "CONFIRMA" consome naturalmente entre **8 e 15 segundos**, mesmo para eleitores idosos ou com pouca familiaridade com tecnologia.

---

## 🛡️ Item 3: Comparação de Seções e Auditoria de Suspeitas de Fraude

### Pergunta Central da Auditoria:
> *"É possível que seções com 100% de votos para um candidato tenham sido fruto de fraude na urna eletrônica?"*

### Evidências Técnicas Coletadas nos Logs (`logd.dat`):

1. **Integridade da Assinatura e Criptografia do Kernel:**
   - Todos os binários em Luislândia/MG e Nova Hartz/RS foram verificados pelo `SCUE` com `[SUCESSO]`.
   - A sequência de hashes SipHash de todas as linhas de log manteve-se matematicamente íntegra do boot (`07:00`) até a emissão do Boletim de Urna (`17:00`).

2. **Ausência de Comportamento Robótico em Bloco:**
   - Em caso de invasão ou script malicioso injetando votos falsos em lote, observar-se-ia uma rajada de votos em milissegundos idênticos ou intervalos fixos (ex: exatamente 3 segundos a cada voto).
   - O log de Luislândia/MG demonstra uma **distribuição Gaussiana natural**: eleitores votando em horários espaçados ao longo do dia, com tempos individuais de 6s, 8s, 14s, 22s e até 34s, além de intervalos de até 15 minutos de cabine ociosa entre um eleitor e outro.

3. **Dupla Habilitação (Terminal do Mesário):**
   - Antes de cada voto, o terminal do mesário registra o evento formal de liberação individual com conferência do título de eleitor e biometria/assinatura física no caderno de votação.

4. **Explicação Sociodemográfica das Seções 100%:**
   - A Seção 224 de Luislândia/MG está instalada na **Escola Municipal de São João**, uma comunidade rural tradicionalmente quilombola do Norte de Minas Gerais, onde residem poucas famílias com forte identidade comunitária e histórico de votação hegemônica.
   - Do total de 71 votantes, 69 votaram no candidato Lula, 1 votou em branco e 1 anulou (totalizando 100% dos votos válidos nominais).
   - O mesmo fenômeno ocorre em sentido inverso em seções rurais de imigrantes europeus no Sul ou em reservas indígenas com lideranças específicas alinhadas a Bolsonaro.

---

## 🇧🇷 Item 4: Seções 100% Absolutas no Brasil (2º Turno)

Ao processar todas as **472.028 seções eleitorais** do 2º turno da eleição presidencial, identificamos um total de **147 seções eleitorais** com 100% dos votos nominais destinados a um único candidato.

```
Total de Seções Auditadas no Brasil: 472.028
Seções com 100% de Votos Nominais:   147 (0,031% do total nacional)
├── Lula (PT):                       143 seções (97,28%)
└── Jair Bolsonaro (PL):               4 seções (2,72%)
```

### Distribuição Estadual das 147 Seções 100%:

| Unidade Federativa | Seções 100% Lula | Seções 100% Bolsonaro | Total 100% na UF |
| :--- | :---: | :---: | :---: |
| **Maranhão (MA)** | **47** | 0 | 47 |
| **Amazonas (AM)** | **23** | 0 | 23 |
| **Bahia (BA)** | **19** | 0 | 19 |
| **Minas Gerais (MG)** | **9** | 0 | 9 |
| **Ceará (CE)** | **8** | 0 | 8 |
| **Pará (PA)** | **8** | **1** | 9 |
| **Piauí (PI)** | **7** | 0 | 7 |
| **Paraíba (PB)** | **5** | 0 | 5 |
| **Pernambuco (PE)** | **5** | 0 | 5 |
| **Sergipe (SE)** | **3** | 0 | 3 |
| **Alagoas (AL)** | **3** | 0 | 3 |
| **Rio Grande do Norte (RN)** | **2** | 0 | 2 |
| **Mato Grosso (MT)** | **2** | 0 | 2 |
| **Mato Grosso do Sul (MS)** | **1** | 0 | 1 |
| **Acre (AC)** | **1** | 0 | 1 |
| **Rio Grande do Sul (RS)** | 0 | **1** | 1 |
| **Exterior (ZZ)** | 0 | **2** | 2 |
| **Demais 11 UFs** | 0 | 0 | 0 |
| **TOTAL BRASIL** | **143** | **4** | **147** |

### Onde estão as 4 Seções 100% de Jair Bolsonaro?
1. **Pará (PA) - Município de Chaves (Ilha do Marajó):**
   - Zona 16, Seção 144: **25 votos (100% Bolsonaro)**. Comunidade ribeirinha isolada.
2. **Rio Grande do Sul (RS) - Município de Charrua:**
   - Zona 88, Seção 79: **51 votos (100% Bolsonaro)**. Localizada na Reserva Indígena do Ligeiro.
3. **Exterior (ZZ) - Caracas / Venezuela:**
   - Zona 1, Seção 78: **12 votos (100% Bolsonaro)**. Seção consular de brasileiros no exterior.
4. **Exterior (ZZ) - Caracas / Venezuela:**
   - Zona 1, Seção 79: **12 votos (100% Bolsonaro)**. Seção consular de brasileiros no exterior.

---

## 🗺️ Item 5: Seções Hegemônicas $\ge 90\%$ e Mapa Geográfico Nacional

Para além do 100% absoluto, foi auditado o segundo critério solicitado: **seções com dominância hegemônica igual ou superior a 90% dos votos nominais** ($\ge 90\%$).

```
Total de Seções Hegemônicas (≥ 90%): 9.758 seções (2,07% das seções do país)
├── Lula (PT):                       9.538 seções (97,75%)
└── Jair Bolsonaro (PL):               220 seções (2,25%)
```

### Principais Concentrações Regionais:
- **Lula ($\ge 90\%$):** 
  - Predomínio quase total em municípios do interior do Nordeste:
    - **Bahia:** 3.048 seções
    - **Piauí:** 2.072 seções
    - **Maranhão:** 1.527 seções
    - **Ceará:** 1.109 seções
    - **Paraíba:** 523 seções
    - **Pernambuco:** 507 seções
    - **Minas Gerais:** 374 seções (especialmente Vale do Jequitinhonha e Norte de MG)
    - **Pará:** 187 seções
    - **Amazonas:** 114 seções
- **Bolsonaro ($\ge 90\%$):**
  - Concentração em municípios agrícolas do Sul, Centro-Oeste e polos de colonização:
    - **Rio Grande do Sul:** 58 seções (Serra Gaúcha, Vale do Taquari, Noroeste)
    - **Santa Catarina:** 31 seções (Vale do Itajaí, Oeste Catarinense)
    - **Mato Grosso:** 28 seções (Polos do Agronegócio e BR-163)
    - **Paraná:** 24 seções
    - **Pará:** 17 seções (Região de Novo Progresso / Castelo dos Sonhos)
    - **Goiás:** 14 seções
    - **Rondônia:** 10 seções
    - **São Paulo:** 8 seções

---

## 🔄 Item 6: Análise de Migração Eleitoral (Origem dos ~11M de Novos Votos de Lula)

Entre o 1º Turno (Eleição Ordinária 6257) e o 2º Turno (Eleição Ordinária 6258), o candidato Lula obteve um salto de **+10.376.694 votos nominais adicionais** (+19,26%), indo de **53.879.538** para **64.256.232 votos**, consolidando a vitória no 2º turno.

* [Link Oficial do TSE - Painel Totalização 1º Turno (BR)](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6257/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/br)
* [Link Oficial do TSE - Painel Totalização 2º Turno (BR)](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6258/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/br)

### 6.1 De Onde Veio o Reservatório de Votos Disputados no 2º Turno?

Matematicamente, todo novo voto obtido no 2º turno provém de quatro fontes oficiais apuradas pela Justiça Eleitoral:

| Fonte Oficial do Eleitorado | Votos Disponíveis no 1ºT / Variação | Comportamento no 2º Turno |
| :--- | :---: | :--- |
| **Votos em Terceiros Candidatos** | **9.316.747** votos | Augusto Cury (3,45M), Renan Santos (2,68M), Ronaldo Caiado (2,61M), Romeu Zema (326k), Samara (123k) e outros saíram do páreo. |
| **Mobilização de Novos Eleitores (Queda Abstenção)** | **+2.960.239** eleitores | O comparecimento subiu de 78,92% (125,27M) para 80,78% (128,23M). Quase 3 milhões de eleitores que faltaram no 1ºT votaram no 2ºT. |
| **Redução de Votos em Branco** | **+870.302** votos nominais | O total de brancos caiu de 2.300.798 para 1.430.496, convertendo-se em votos nominais válidos. |
| **Redução de Votos Nulos** | **+945.698** votos nominais | O total de nulos caiu de 3.669.003 para 2.723.305, convertendo-se em votos nominais válidos. |
| **TOTAL DO RESERVATÓRIO DISPUTADO** | **~14.092.986 votos** | **Lula absorveu 73,6% (+10,38M) e Bolsonaro 26,4% (+3,72M).** |

### 6.2 Decomposição Regional dos Novos Votos de Lula

O crescimento de Lula foi puxado de maneira decisiva pela virada nos colégios eleitorais do Sudeste e pela consolidação no Nordeste:

* **Região Sudeste (+4.648.396 votos - 44,8% do ganho nacional):** O grande motor eleitoral da repactuação, destacando-se São Paulo (+2.613.861 votos), Minas Gerais (+1.162.163 votos com virada pró-Lula) e Rio de Janeiro (+872.372 votos).
* **Região Nordeste (+2.756.887 votos - 26,6% do ganho nacional):** Ampliação da margem absoluta em redutos históricos, liderada pela Bahia (+820.487 votos), Pernambuco (+563.542 votos) e Ceará (+480.861 votos).
* **Região Sul (+1.332.846 votos - 12,8% do ganho nacional):** Avanço em capitais e cidades médias do Rio Grande do Sul (+529.793 votos), Paraná (+511.907 votos) e Santa Catarina (+291.146 votos).
* **Região Norte (+937.440 votos - 9,0% do ganho nacional):** Liderada pelo Pará (+263.212 votos) e Amazonas (+98.787 votos).
* **Região Centro-Oeste (+658.358 votos - 6,3% do ganho nacional):** Liderada por Goiás (+396.675 votos) e Distrito Federal (+149.597 votos).
* **Exterior / ZZ (+42.767 votos - 0,4% do ganho nacional):** Comunidades brasileiras nas seções consulares.

### 6.3 Top 10 Estados com Maior Ganho de Votos para Lula (com Links TSE)

| UF | Região | Lula 1ºT | Lula 2ºT | Ganho Líquido (Delta) | % Cresc. | Part. Nacional | Link Oficial TSE |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **SP** | Sudeste | 9.505.413 | 12.119.274 | **+2.613.861** | +27,5% | **25,2%** | [TSE 1ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6257/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/sp) / [TSE 2ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6258/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/sp) |
| **MG** | Sudeste | 5.188.936 | 6.351.099 | **+1.162.163** | +22,4% | **11,2%** | [TSE 1ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6257/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/mg) / [TSE 2ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6258/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/mg) |
| **RJ** | Sudeste | 3.693.021 | 4.565.393 | **+872.372** | +23,6% | **8,4%** | [TSE 1ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6257/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/rj) / [TSE 2ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6258/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/rj) |
| **BA** | Nordeste | 5.664.771 | 6.485.258 | **+820.487** | +14,5% | **7,9%** | [TSE 1ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6257/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/ba) / [TSE 2ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6258/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/ba) |
| **PE** | Nordeste | 3.553.971 | 4.117.513 | **+563.542** | +15,9% | **5,4%** | [TSE 1ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6257/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/pe) / [TSE 2ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6258/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/pe) |
| **RS** | Sul | 2.294.759 | 2.824.552 | **+529.793** | +23,1% | **5,1%** | [TSE 1ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6257/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/rs) / [TSE 2ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6258/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/rs) |
| **PR** | Sul | 2.054.597 | 2.566.504 | **+511.907** | +24,9% | **4,9%** | [TSE 1ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6257/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/pr) / [TSE 2ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6258/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/pr) |
| **CE** | Nordeste | 3.555.263 | 4.036.124 | **+480.861** | +13,5% | **4,6%** | [TSE 1ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6257/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/ce) / [TSE 2ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6258/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/ce) |
| **GO** | Centro-Oeste | 1.188.880 | 1.585.555 | **+396.675** | +33,4% | **3,8%** | [TSE 1ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6257/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/go) / [TSE 2ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6258/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/go) |
| **SC** | Sul | 1.127.168 | 1.418.314 | **+291.146** | +25,8% | **2,8%** | [TSE 1ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6257/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/sc) / [TSE 2ºT](https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6258/escrutinio/totalizacao/cargo/1/vis/nominal/ordem/v/consolidado/sc) |

---

## 💻 Dashboard Interativo (`mapa_calor_eleicoes.html`)

O repositório disponibiliza uma aplicação web rica e autocontida para visualização analítica:

### Características da Aplicação:
1. **Fundo Claro Moderno (*Light Mode* Padrão):**
   - Paleta equilibrada em tons neutros claros (`#f8fafc` / `#ffffff`), tipografia moderna (Inter/Segoe UI) e alto contraste para relatórios executivos.
   - Botão para alternar dinamicamente entre tema claro e escuro (*Dark/Light Mode*).
2. **Cards com KPIs Nacionais:**
   - Total de seções do país, total de seções 100% e $\ge 90\%$ para Lula e Bolsonaro.
   - Alternância em tempo real entre a métrica **"100% Absoluto"** e **"$\ge 90\%$ Hegemônico"**.
3. **Grid do Mapa de Calor por UF:**
   - 28 cards (todas as UFs) colorizados de acordo com a intensidade das seções hegemônicas.
4. **Mapa Geográfico do Brasil com Cidades (Leaflet + OpenStreetMap):**
   - Posicionado imediatamente abaixo do Mapa de Calor por UF.
   - Renderização fluida de **1.466 cidades georreferenciadas** com marcadores circulares dimensionados proporcionalmente ao número de seções.
   - Marcadores com destaque pulsante para cidades com seções 100%.
   - **Popups Interativos:** Ao clicar em qualquer cidade, exibe o nome, UF, votação total, detalhamento de zonas e seções, e **link direto para o Boletim de Urna (BU) oficial no site do TSE**.
5. **Painel de Migração Eleitoral (1ºT vs 2ºT):**
   - Cards com a decomposição matemática das 4 fontes dos novos ~11M de votos.
   - Distribuição regional do ganho eleitoral.
   - Tabela com todas as 28 UFs e **botões oficiais para acessar a apuração no TSE (1ºT e 2ºT)**.
6. **Ranking e Tabela Dinâmica de Auditoria:**
   - Campo de busca instantânea por município, zona eleitoral ou seção.
   - Links diretos clicáveis para abrir o Boletim de Urna oficial no portal `resultados.tse.jus.br`.

### Como abrir o dashboard:
No macOS:
```bash
open mapa_calor_eleicoes.html
```
Ou abra o arquivo [mapa_calor_eleicoes.html](file:///Users/romuloigor/Local/local-eleicoes-2026/mapa_calor_eleicoes.html) diretamente em qualquer navegador web.

---

## 📂 Estrutura de Diretórios e Catálogo de Arquivos

O repositório foi organizado com uma arquitetura modular, limpa e padronizada:

```text
local-eleicoes-2026/
├── README.md                      # Documentação técnica e relatório de auditoria
├── mapa_calor_eleicoes.html       # Dashboard Interativo Nacional (Leaflet + OpenStreetMap)
├── data/
│   ├── zips/
│   │   ├── tse/                   # 28 arquivos bweb_2t_[UF].zip baixados do TSE
│   │   └── urnas/                 # Pacotes de amostras de urnas (DadosDeUrna / LogDeUrna)
│   ├── raw/                       # Artefatos extraídos da urna (.jez, .dat, .vsc)
│   └── processed/                 # Datasets consolidados em CSV e JSON
└── scripts/                       # Pipelines e ferramentas em Python
```

### 🛠️ Scripts Python (`scripts/`)

| Script | Finalidade | Como Executar |
| :--- | :--- | :--- |
| [`scripts/analisar_migracao_votos.py`](file:///Users/romuloigor/Local/local-eleicoes-2026/scripts/analisar_migracao_votos.py) | Compara 1º e 2º turnos oficiais do TSE e calcula a migração e de onde vieram os ~11M de novos votos. | `python3 scripts/analisar_migracao_votos.py` |
| [`scripts/ler_log_urna.py`](file:///Users/romuloigor/Local/local-eleicoes-2026/scripts/ler_log_urna.py) | Descompacta arquivos `.jez` em memória, extrai eventos, valida estrutura e gera CSV de horários de votação. | `python3 scripts/ler_log_urna.py --votos --csv` |
| [`scripts/analisar_minutos.py`](file:///Users/romuloigor/Local/local-eleicoes-2026/scripts/analisar_minutos.py) | Calcula tempo exato de cabine por voto (habilitação $\to$ confirmação), ociosidade e distribuição por minuto. | `python3 scripts/analisar_minutos.py` |
| [`scripts/buscar_secoes_100pct.py`](file:///Users/romuloigor/Local/local-eleicoes-2026/scripts/buscar_secoes_100pct.py) | Processador de arquivos BWEB estaduais via streaming (busca por UF ou arquivo). | `python3 scripts/buscar_secoes_100pct.py BA` |
| [`scripts/processar_brasil_completo.py`](file:///Users/romuloigor/Local/local-eleicoes-2026/scripts/processar_brasil_completo.py) | Pipeline nacional que processa as 472.028 seções das 28 UFs e salva em `data/processed/`. | `python3 scripts/processar_brasil_completo.py` |
| [`scripts/gerar_html_mapa.py`](file:///Users/romuloigor/Local/local-eleicoes-2026/scripts/gerar_html_mapa.py) | Compila os dados consolidados, geocodifica os 1.466 municípios e gera o `mapa_calor_eleicoes.html`. | `python3 scripts/gerar_html_mapa.py` |

### 📊 Datasets e Arquivos Consolidados (`data/processed/`)

| Arquivo | Descrição |
| :--- | :--- |
| [`data/processed/analise_migracao_lula_1t_2t.csv`](file:///Users/romuloigor/Local/local-eleicoes-2026/data/processed/analise_migracao_lula_1t_2t.csv) | Tabela auditada das 28 UFs comparando votos nominais de Lula no 1ºT e 2ºT, ganhos, % de crescimento, participação nacional e links oficiais do TSE. |
| [`data/processed/decomposicao_votos_brasil.json`](file:///Users/romuloigor/Local/local-eleicoes-2026/data/processed/decomposicao_votos_brasil.json) | Decomposição estruturada completa das 4 fontes de votos e do crescimento regional de Lula consumida pelo dashboard. |
| [`data/processed/brasil_resumo_secoes_por_uf.csv`](file:///Users/romuloigor/Local/local-eleicoes-2026/data/processed/brasil_resumo_secoes_por_uf.csv) | Tabela resumo com total de seções, votos nominais e contagem de seções 100% e $\ge 90\%$ para Lula e Bolsonaro em cada uma das 28 UFs. |
| [`data/processed/brasil_secoes_100pct.csv`](file:///Users/romuloigor/Local/local-eleicoes-2026/data/processed/brasil_secoes_100pct.csv) | Relação detalhada de todas as **147 seções eleitorais** com 100% de votos no país (candidato, UF, município, zona, seção, votos e link oficial do BU). |
| [`data/processed/brasil_secoes_90pct.csv`](file:///Users/romuloigor/Local/local-eleicoes-2026/data/processed/brasil_secoes_90pct.csv) | Relação detalhada das **9.758 seções** com votação igual ou superior a 90% dos votos nominais. |
| [`data/processed/cidades_mapa_eleicoes.json`](file:///Users/romuloigor/Local/local-eleicoes-2026/data/processed/cidades_mapa_eleicoes.json) | Base georreferenciada de 1.466 municípios brasileiros com coordenadas de latitude/longitude e agregação de seções. |
| [`data/processed/dados_mapa_calor.json`](file:///Users/romuloigor/Local/local-eleicoes-2026/data/processed/dados_mapa_calor.json) | Estrutura compilada de estatísticas e rankings estaduais consumida pelo dashboard. |
| [`data/processed/horarios_votos.csv`](file:///Users/romuloigor/Local/local-eleicoes-2026/data/processed/horarios_votos.csv) | Registro auditado individual de cada voto de Luislândia/MG com milissegundos e tempo de cabine. |
| [`data/processed/secoes_100pct_bahia.csv`](file:///Users/romuloigor/Local/local-eleicoes-2026/data/processed/secoes_100pct_bahia.csv) | Extrato específico com as 19 seções 100% da Bahia. |
| [`data/processed/secoes_100pct_minas_gerais.csv`](file:///Users/romuloigor/Local/local-eleicoes-2026/data/processed/secoes_100pct_minas_gerais.csv) | Extrato específico com as 9 seções 100% de Minas Gerais. |
| [`data/processed/secoes_100pct_para.csv`](file:///Users/romuloigor/Local/local-eleicoes-2026/data/processed/secoes_100pct_para.csv) | Extrato específico com as 9 seções 100% do Pará (8 Lula e 1 Bolsonaro). |

---

## 🔒 Conclusão da Auditoria

1. **Cadeia Criptográfica Inviolada:** A análise dos arquivos `.jez` comprovou a integridade dos módulos de software assinados no Uenux e a continuidade encadeada dos hashes SipHash das linhas de log.
2. **Dinâmica Humana Comprovada:** O tempo médio de cabine no 2º turno oscila entre 11 e 14 segundos devido ao fato de haver apenas o voto presidencial (2 dígitos + confirma). A distribuição Gaussiana dos horários descarta votações artificiais em lote.
3. **Padrão Sociodemográfico dos Extremos Eleitorais:** As seções 100% ou $\ge 90\%$ ocorrem predominantemente em comunidades pequenas, rurais, quilombolas, ribeirinhas ou indígenas com homogeneidade cultural e política, refletindo padrões regionais consolidados do eleitorado brasileiro.
