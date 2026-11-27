# Trabalho Final: Inteligência de Receita para os Hotéis de Port Alder

Trabalho final do curso de Ciência de Dados ([enunciado](https://github.com/labeduc/trabalho-final/blob/main/docs/enunciado-trabalho-final.md)).
Dataset: *Nice Rooms: Hotel Revenue, MARS and Reviews* (dados **sintéticos**, licença CC BY 4.0).

**Autores:** _preencher_

---

## 1. O que tem aqui

O trabalho responde às três perguntas da diretoria da associação de hotéis:

1. Quais hotéis estão cobrando abaixo (ou acima) do que o mercado aceita, e qual é a **diária mais adequada (MARS)** de cada um?
2. As decisões semanais de preço estão dando resultado?
3. Quais problemas das avaliações dos hóspedes atacar primeiro?

| Parte | Onde está | O que entrega |
|---|---|---|
| Análise em Python (pandas + matplotlib) | `analise/` | usa os 7 arquivos JSON, mostra relações entre variáveis, junções, cálculo do MARS, 14 gráficos, 13 tabelas e o relatório com todos os cálculos e funções usadas |
| Banco MySQL | `banco/` | modelo das tabelas (PK, FK, CHECK), carga dos dados, consultas de negócio e diagrama ER |
| Documento escrito | `documentos/` | análise escrita de cada gráfico (Word e PDF) |
| Painel HTML | `dashboard/` | painel interativo com filtros, pesquisa e gráficos com zoom, funciona offline |

---

## 2. Estrutura das pastas

```
DELL _Léo/
├── README.md                     ← este arquivo
├── dados/                        ← 7 arquivos .jsonl originais + README do dataset
├── analise/
│   ├── analise_hoteis.py         ← PROGRAMA PRINCIPAL
│   └── saida/                    ← tudo que o programa gera
│       ├── relatorio_calculos.md ← todos os cálculos, passo a passo
│       ├── graficos/             ← 14 gráficos PNG (G01 a G14)
│       └── tabelas/              ← 13 tabelas CSV
├── banco/
│   ├── modelo_mysql.sql          ← CREATE TABLE (banco nice_rooms)
│   ├── carregar_mysql.py         ← carrega os JSONL no MySQL e confere as contagens
│   ├── consultas_mysql.sql       ← integridade + 9 consultas de negócio
│   ├── diagrama_er.py            ← gera o diagrama Entidade-Relacionamento
│   └── diagrama_er.png
├── documentos/
│   ├── analise_dos_graficos.docx
│   └── analise_dos_graficos.pdf
├── scripts/
│   └── gerar_dados_dashboard.py  ← gera dashboard/dados.js e copia as imagens
├── dashboard/
│   ├── index.html                ← ABRA ESTE para ver o painel
│   ├── style.css  script.js  analises.js  dados.js
│   ├── img/                      ← gráficos PNG usados no painel
│   └── lib/                      ← Chart.js, plugin de zoom e Hammer.js (cópias locais)
├── dashboard-preview.png         ← print do painel (visão geral)
└── dashboard-preview-mars.png    ← print do painel (aba diária adequada)
```

---

## 3. Passo a passo

### Passo 0: instalar o necessário (uma vez só)

1. Instale o **Python 3** (python.org). Na instalação, marque **"Add Python to PATH"**.
2. Abra o Prompt de Comando e rode:
   ```
   pip install pandas matplotlib mysql-connector-python
   ```
3. Para a parte do banco: instale o **MySQL Server 8** e o **MySQL Workbench** (pelo MySQL Installer). Anote a senha do usuário `root`.

> Só quer ver os resultados? Tudo já está gerado. Pule direto para o **Passo 5** (painel) ou o **Passo 6** (documento).

### Passo 1: abrir o terminal na pasta do trabalho

Abra a pasta `C:\Users\nonne\Documents\DELL _Léo` no Explorador de Arquivos, clique na barra de endereço, apague o que estiver lá, digite `cmd` e aperte Enter. O Prompt de Comando abre já dentro da pasta.

### Passo 2: rodar a análise em Python

```
python analise/analise_hoteis.py
```

Leva uns 20 segundos. O programa:

1. **Carrega** os 7 arquivos JSON (`hotels`, `room_types`, `daily_market`, `weekly_performance`, `rate_decisions`, `reviews`, `review_scenarios`) e inspeciona linhas, colunas, tipos e valores faltantes.
2. **Mostra as relações**: onde as tabelas se juntam (`hotel_id`, `scenario_id`, `hotel_id + week_start`) e confere que não há registro órfão (0 em todas).
3. **Correlações** entre as variáveis (mapa de calor).
4. **Calcula o MARS** (diária mais adequada) de cada hotel, noite a noite, com um exemplo passo a passo, e diz **o que fazer** com cada hotel (subir, manter ou reduzir).
5. **Desempenho**: ocupação, ADR, RevPAR, RGI, ARI e MPI por hotel, efeito dos eventos.
6. **Decisões de preço** e **avaliações** (notas, cenários, taxa de resposta).
7. **Projeção** de receita e a **lista das funções** usadas.

Tudo sai no terminal e é gravado em `analise/saida/` (gráficos, tabelas e `relatorio_calculos.md`).

### Passo 3: montar o banco MySQL

1. Abra `banco/carregar_mysql.py` num editor e troque `sua_senha_aqui` pela sua senha do MySQL (ou defina a variável de ambiente `MYSQL_PASSWORD`).
2. Rode:
   ```
   python banco/carregar_mysql.py
   ```
   Ele cria o banco `nice_rooms` a partir de `modelo_mysql.sql`, insere todos os dados e mostra a contagem de cada tabela.
3. Abra `banco/consultas_mysql.sql` no **MySQL Workbench** e execute (raio ⚡).

| Consulta | O que responde |
|---|---|
| A | Integridade: registros órfãos (deve dar 0) |
| 0 | Recalcula os totais de cada hotel (confere com o Python) |
| 1 | Ranking de hotéis por RevPAR (`RANK()`) |
| 2 | Desempenho por tier × estação |
| 3 | Hotéis com mais de 30% de avaliações 1–2★ (`HAVING`) |
| 4 | Avaliações por cenário (`JOIN`) |
| 5 | Resultado das decisões de preço |
| 6 | Taxa de resposta às avaliações |
| 7 | Pergunta própria: distância entre ADR e MARS por hotel |
| 8 | MARS por estação |
| 9 | Hotéis com restaurante × desempenho |

4. (Opcional) Gerar de novo o diagrama ER: `python banco/diagrama_er.py`.

**Decisões da modelagem:** as comodidades viraram a tabela `hotel_comodidades` (1ª forma normal); colunas repetidas (nome, tier, comp_set) saíram das tabelas filhas (3ª forma normal); `view` virou `view_type` e `trigger` virou `trigger_desc` por serem palavras reservadas do MySQL.

### Passo 4: atualizar os dados do painel (só se mudar algo)

```
python scripts/gerar_dados_dashboard.py
```

Gera `dashboard/dados.js` e copia os gráficos para `dashboard/img/`.
Ordem para atualizar tudo: `analise/analise_hoteis.py` → `banco/diagrama_er.py` → `scripts/gerar_dados_dashboard.py`.

### Passo 5: abrir o painel

Dê dois cliques em `dashboard/index.html`. Não precisa de internet nem de servidor.

No topo ficam os **filtros de ano, tier e hotel** e a **caixa de pesquisa** (acha hotel, gráfico ou texto, sem diferenciar acento). Tudo atualiza junto.

| Aba | O que mostra |
|---|---|
| Visão geral | KPIs, evolução mensal, RGI, quadrante preço × ocupação, decisões, notas, cenários e tabela por hotel |
| Diária adequada | MARS × ADR de cada hotel, recomendação, % de noites fora da faixa ±6%, tabela por estação e o cálculo passo a passo |
| Dados e relações | as 7 tabelas, as chaves de junção, o mapa de relações e o diagrama ER |
| Gráficos e análises | os gráficos do Python refeitos como interativos, com a análise escrita de cada um |
| Cálculos | fórmulas usadas e lista de funções |

**Como interagir com os gráficos:** passe o mouse para ver os valores; clique na legenda para ligar/desligar séries; **arraste** para dar zoom; **duplo clique** volta ao normal; **Shift + arrastar** move o gráfico; **clique num hotel** para filtrar o painel por ele; o botão de tema troca entre claro e escuro.

### Passo 6: ler a análise escrita

Abra `documentos/analise_dos_graficos.docx` (Word) ou `.pdf`. Cada gráfico tem: o que mostra, o que se conclui e o que fazer.

---

## 4. Principais resultados

**Fórmula do MARS (diária mais adequada):** mediana do ADR dos concorrentes do mesmo grupo (sem o próprio hotel) × posicionamento do hotel ÷ mediana do posicionamento dos concorrentes. Reproduz o MARS do dataset com erro máximo de 0,0075%. Faixa aceitável: ±6%.

| Hotel | Tier | ADR cobrado | MARS | Diferença | O que fazer |
|---|---|---|---|---|---|
| The Foxglove | boutique | 183,86 | 225,94 | −18,6% | Barato sem ganhar ocupação: subir rumo ao MARS |
| Willowmere Lodge | upscale | 210,96 | 231,28 | −8,8% | Barato sem ganhar ocupação: subir |
| Ridgeline Motor Inn | economy | 88,32 | 94,01 | −6,1% | Barato sem ganhar ocupação: subir |
| Cedar & Salt Hotel | midscale | 147,97 | 154,44 | −4,2% | Barato sem ganhar ocupação: subir |
| The Copper Meridian | luxury | 357,21 | 372,44 | −4,1% | Barato sem ganhar ocupação: subir |
| The Wren Rooms | boutique | 199,78 | 206,25 | −3,1% | Barato e mais cheio que os concorrentes: subir |
| Seabright Grand | upscale | 220,04 | 224,57 | −2,0% | Levemente abaixo: subir aos poucos |
| Paloma Court Hotel | midscale | 154,75 | 155,78 | −0,7% | Dentro da faixa: manter |
| Alder & Quay Hotel | upscale | 233,43 | 230,55 | +1,2% | Dentro da faixa: manter |
| Marisol Bay Resort | luxury | 395,10 | 378,82 | +4,3% | Acima, mas o mercado aceita: manter e vigiar o MPI |
| Kestrel Park Hotel | midscale | 163,71 | 155,98 | +5,0% | Acima, mas o mercado aceita: manter |
| Northgate Inn | economy | 98,51 | 92,51 | +6,5% | Acima, mas o mercado aceita: manter |
| Harborlight Suites | upscale | 251,58 | 222,08 | +13,3% | Acima, mas o mercado aceita: manter |
| The Lantern House | boutique | 264,58 | 213,48 | +23,9% | Acima, mas o mercado aceita: manter e vigiar |

**Regra de recomendação:** diferença dentro de ±2% = manter; abaixo de −2% = subir (com MPI acima de 101 o hotel já está mais cheio que os concorrentes, então há espaço; senão o desconto não está trazendo hóspedes e é preciso rever qualidade); acima de +2% com MPI ≥ 98 = o mercado aceita, manter; acima com MPI baixo = reduzir.

**Decisões de preço:** a regra de ação deduzida reproduz 97,0% dos rótulos do dataset (os 3% restantes são ruído proposital).

**Projeção:** feita com receita **por dia**, porque 2027 tem 362 dias nos dados e 2028 tem 366. Por dia, o crescimento é −0,09% (somar o ano daria um falso +1,01%).

---

## 5. Conferência dos números

| KPI (sem filtro) | Painel | Python | MySQL |
|---|---|---|---|
| Receita total | US$ 236,0 mi | 236.002.362 | igual |
| Ocupação | 70,7% | 70,7% | igual |
| ADR | US$ 224 | 223,79 | igual |
| RevPAR | US$ 158 | 158,25 | igual |
| Nota média | 3,31 | 3,31 | igual |

O ADR é **ponderado** (receita ÷ quartos vendidos = 223,79). O README do dataset cita 207, que é a média simples das linhas diárias e dá peso igual a um hotel pequeno e um grande. RGI, ARI e MPI também são calculados a partir das somas.

---

## 6. Cuidados com os dados

- Os dados são **sintéticos**: servem para treinar o método, não descrevem hotéis reais.
- Não misturar tiers ao comparar preço: um hotel luxury e um economy não competem entre si. Por isso o MARS usa só os concorrentes do mesmo grupo.
- Valores faltantes existem onde é esperado (por exemplo, respostas a avaliações que nunca foram respondidas) e foram tratados, não apagados.
- Correlação não é causa: preço e ocupação sobem juntos na alta temporada porque a demanda sobe, não porque o preço alto atrai hóspedes.
- Os anos não têm o mesmo número de dias nos dados; compare por dia, não por soma anual.

---

## 7. Ferramentas usadas

- **Python 3**: pandas (dados), matplotlib (gráficos).
- **MySQL 8** + Workbench, mysql-connector-python (testado também em MariaDB 10.11).
- **HTML, CSS e JavaScript** com Chart.js 4.4.6, chartjs-plugin-zoom 2.2.0 e Hammer.js 2.0.8 (cópias locais em `dashboard/lib/`).
- **Claude (IA)** como parceiro no desenvolvimento. Registrar os prompts usados no Diário de Campo, como pede o enunciado.
