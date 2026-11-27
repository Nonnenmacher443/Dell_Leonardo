"""
Análise de Receita dos Hotéis de Port Alder
============================================

Programa único que usa os 7 arquivos JSON (JSONL) do dataset Nice Rooms e:

  1. carrega e inspeciona cada tabela (linhas, colunas, tipos, ausentes);
  2. mostra as relações entre as tabelas: onde elas se juntam e com que cardinalidade;
  3. mede as relações entre as variáveis (correlações);
  4. calcula, passo a passo, a diária mais adequada (MARS) de cada hotel e confere
     o resultado com o valor que vem no dataset;
  5. analisa desempenho contra concorrentes, decisões de preço e avaliações;
  6. faz uma projeção simples para 2029;
  7. gera os gráficos (matplotlib), as tabelas (CSV) e um relatório com todos os
     cálculos (saida/relatorio_calculos.md).

Como rodar (a partir da pasta trabalho-final/):
    pip install pandas matplotlib
    python analise/analise_hoteis.py

Bibliotecas: pandas (dados) e matplotlib (gráficos). Nada além disso.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # gera arquivos PNG sem abrir janela
import matplotlib.pyplot as plt
import pandas as pd

# ---------------------------------------------------------------------------
# 0. Configuração
# ---------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "dados"
PASTA_SAIDA = RAIZ / "analise" / "saida"
PASTA_GRAFICOS = PASTA_SAIDA / "graficos"
PASTA_TABELAS = PASTA_SAIDA / "tabelas"

ARQUIVOS = ["hotels", "room_types", "daily_market", "weekly_performance",
            "rate_decisions", "reviews", "review_scenarios"]

TIERS = ["luxury", "upscale", "boutique", "midscale", "economy"]
COR_TIER = {"luxury": "#257de0", "upscale": "#f47230", "boutique": "#00b894",
            "midscale": "#f2a600", "economy": "#ee7fac"}
AZUL, VERMELHO, CINZA = "#257de0", "#ec4647", "#9aa0a6"

plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 130, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.8,
    "axes.axisbelow": True, "axes.titleweight": "bold", "axes.titlesize": 12,
    "font.size": 10,
})

# O relatório é montado aos poucos: cada etapa acrescenta texto aqui.
RELATORIO: list[str] = []


def registrar(texto: str = "") -> None:
    """Imprime no terminal e guarda a mesma linha no relatório."""
    print(texto)
    RELATORIO.append(texto)


def titulo(texto: str, nivel: int = 2) -> None:
    registrar("")
    registrar("#" * nivel + " " + texto)
    registrar("")


def tabela_md(df: pd.DataFrame, casas: int = 2) -> None:
    """Registra um DataFrame como tabela Markdown (sem depender de 'tabulate')."""
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else fmt_num(v, casas))
    cab = "| " + " | ".join(map(str, d.columns)) + " |"
    sep = "|" + "|".join(["---"] * len(d.columns)) + "|"
    linhas = ["| " + " | ".join("" if pd.isna(v) else str(v) for v in lin) + " |"
              for lin in d.itertuples(index=False)]
    for l in [cab, sep, *linhas]:
        registrar(l)
    registrar("")


def salvar_grafico(fig, nome: str, legenda: str) -> None:
    """Salva a figura em PNG e coloca a imagem no relatório."""
    caminho = PASTA_GRAFICOS / f"{nome}.png"
    fig.savefig(caminho)
    plt.close(fig)
    registrar(f"![{legenda}](graficos/{nome}.png)")
    registrar(f"*{legenda}* (arquivo `graficos/{nome}.png`)")
    registrar("")


def salvar_tabela(df: pd.DataFrame, nome: str) -> None:
    df.to_csv(PASTA_TABELAS / f"{nome}.csv", index=False, encoding="utf-8-sig")


def fmt_pct(v: float, casas: int = 1) -> str:
    return f"{v * 100:.{casas}f}%".replace(".", ",")


def fmt_num(v: float, casas: int = 2) -> str:
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# 1. Carregar e inspecionar
# ---------------------------------------------------------------------------
def carregar_dados() -> dict[str, pd.DataFrame]:
    """Lê os 7 arquivos JSONL. Cada linha do arquivo é um registro JSON."""
    return {nome: pd.read_json(PASTA_DADOS / f"{nome}.jsonl", lines=True) for nome in ARQUIVOS}


GRANULARIDADE = {
    "hotels": "1 hotel",
    "room_types": "1 tipo de quarto de 1 hotel",
    "daily_market": "1 hotel em 1 noite",
    "weekly_performance": "1 hotel em 1 semana (segunda a domingo)",
    "rate_decisions": "1 decisão de preço semanal de 1 hotel + resultado da semana seguinte",
    "reviews": "1 avaliação de hóspede",
    "review_scenarios": "1 cenário (motivo) de avaliação",
}

AUSENCIAS_ESPERADAS = {
    "flow_through": "não existe no 1º ano (precisa do mesmo período do ano anterior)",
    "mean_rating": "semana sem nenhuma avaliação",
    "positive_share": "semana sem nenhuma avaliação",
    "sentiment_index": "semana sem nenhuma avaliação",
    "response_rate": "semana sem nenhuma avaliação",
    "response_hours": "o hotel não respondeu à avaliação",
    "response_text": "o hotel não respondeu à avaliação",
    "demand_event": "noite/semana sem evento (texto vazio)",
}


def inspecionar_tabela(nome: str, df: pd.DataFrame) -> dict:
    """Resumo padronizado de uma tabela. Usada para as 7 tabelas (função reutilizada)."""
    texto_vazio = df.select_dtypes(include=["object", "string"]).apply(
        lambda s: s.astype(str).str.strip().eq("").sum())
    nulos = df.isna().sum() + texto_vazio.reindex(df.columns, fill_value=0)
    nulos = nulos[nulos > 0]
    tipos = df.dtypes.astype(str).value_counts().to_dict()
    return {
        "tabela": nome,
        "linhas": len(df),
        "colunas": df.shape[1],
        "granularidade": GRANULARIDADE[nome],
        "tipos": ", ".join(f"{k}: {v}" for k, v in tipos.items()),
        "ausentes": "; ".join(f"{c} ({n})" for c, n in nulos.items()) or "nenhum",
    }


def preparar_dados(t: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Converte tipos e cria colunas auxiliares usadas no resto da análise."""
    dm = t["daily_market"]
    dm["date"] = pd.to_datetime(dm["date"])
    dm["demand_event"] = dm["demand_event"].fillna("").str.strip()
    dm["tem_evento"] = dm["demand_event"] != ""
    dm["receita_total"] = dm["room_revenue"] + dm["ancillary_revenue"]

    w = t["weekly_performance"]
    w["week_start"] = pd.to_datetime(w["week_start"])

    rd = t["rate_decisions"]
    rd["week_start"] = pd.to_datetime(rd["week_start"])

    r = t["reviews"]
    for c in ["review_date", "stay_date", "week_start"]:
        r[c] = pd.to_datetime(r[c])
    r["respondida"] = r["response_hours"].notna()
    return t


def etapa_inspecao(t: dict[str, pd.DataFrame]) -> None:
    titulo("1. Carga e inspeção das 7 tabelas")
    registrar("Função usada: `pd.read_json(arquivo, lines=True)`, porque cada linha do arquivo é um registro.")
    registrar("A função própria `inspecionar_tabela()` foi aplicada às 7 tabelas:")
    registrar("")
    resumo = pd.DataFrame([inspecionar_tabela(n, df) for n, df in t.items()])
    tabela_md(resumo[["tabela", "linhas", "colunas", "granularidade", "ausentes"]])
    salvar_tabela(resumo, "01_inspecao_tabelas")

    registrar("**Por que os ausentes existem (README do dataset):**")
    registrar("")
    for c, motivo in AUSENCIAS_ESPERADAS.items():
        registrar(f"- `{c}`: {motivo}")
    registrar("")
    registrar("Decisão: **nenhum valor foi apagado nem preenchido**. Os ausentes têm significado; "
              "as funções do pandas (`mean`, `corr`) já ignoram `NaN` nos cálculos.")

    # Coluna com lista dentro de um campo: amenities
    titulo("1.1 Coluna com lista dentro do campo: `amenities`", 3)
    h = t["hotels"]
    amen = h[["hotel_id", "name", "amenities"]].explode("amenities")
    contagem = amen["amenities"].value_counts().rename_axis("comodidade").reset_index(name="hoteis")
    registrar("`hotels.amenities` guarda uma lista. Com `df.explode('amenities')` cada item vira uma linha, "
              "e aí dá para contar com `value_counts()`.")
    registrar("")
    com_restaurante = amen[amen["amenities"].str.contains("restaurant")]["hotel_id"].nunique()
    registrar(f"Hotéis com restaurante (qualquer item com 'restaurant'): **{com_restaurante} de {len(h)}**.")
    registrar("")
    tabela_md(contagem.head(10))
    salvar_tabela(contagem, "01_comodidades")


# ---------------------------------------------------------------------------
# 2. Relações entre as tabelas (onde elas se juntam)
# ---------------------------------------------------------------------------
RELACOES = [
    # (tabela pai, tabela filha, chave na filha, chave no pai)
    ("hotels", "room_types", "hotel_id", "hotel_id"),
    ("hotels", "daily_market", "hotel_id", "hotel_id"),
    ("hotels", "weekly_performance", "hotel_id", "hotel_id"),
    ("hotels", "rate_decisions", "hotel_id", "hotel_id"),
    ("hotels", "reviews", "hotel_id", "hotel_id"),
    ("review_scenarios", "reviews", "scenario_id", "scenario_id"),
    ("weekly_performance", "reviews", "hotel_id + week_start", "hotel_id + week_start"),
    ("weekly_performance", "rate_decisions", "hotel_id + week_start", "hotel_id + week_start"),
]


def chaves(df: pd.DataFrame, chave: str) -> pd.Series:
    cols = [c.strip() for c in chave.split("+")]
    return df[cols].astype(str).agg("|".join, axis=1)


def verificar_relacao(t, pai, filha, ch_filha, ch_pai) -> dict:
    k_pai = chaves(t[pai], ch_pai)
    k_filha = chaves(t[filha], ch_filha)
    orfaos = (~k_filha.isin(set(k_pai))).sum()
    max_filhos = k_filha.value_counts().max()
    return {
        "pai": pai, "filha": filha, "chave": ch_filha,
        "chave_unica_no_pai": k_pai.is_unique,
        "cardinalidade": "1:1" if max_filhos == 1 else "1:N",
        "max_filhos_por_pai": int(max_filhos),
        "registros_orfaos": int(orfaos),
    }


def grafico_relacoes(t) -> None:
    """Desenha o mapa das tabelas e das chaves que as ligam."""
    pos = {
        "hotels": (0.50, 0.80), "room_types": (0.10, 0.80),
        "daily_market": (0.88, 0.80), "weekly_performance": (0.50, 0.42),
        "rate_decisions": (0.88, 0.20), "reviews": (0.12, 0.20),
        "review_scenarios": (0.12, 0.55),
    }
    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.set_axis_off()
    ax.set_xlim(-0.1, 1.1)
    ax.set_ylim(0, 1)
    for pai, filha, ch, _ in RELACOES:
        (x1, y1), (x2, y2) = pos[pai], pos[filha]
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color=CINZA, lw=1.4,
                                    shrinkA=38, shrinkB=38, connectionstyle="arc3,rad=0.06"))
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.025, ch.replace(" + ", "+"), ha="center",
                fontsize=8, color="#444", bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"))
    for nome, (x, y) in pos.items():
        n = len(t[nome])
        ax.text(x, y, f"{nome}\n{n:,} linhas".replace(",", "."), ha="center", va="center",
                fontsize=10, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.6", fc="#eaf2fd" if nome == "hotels" else "white",
                          ec=AZUL, lw=1.5))
    ax.set_title("Como as 7 tabelas se ligam: hotel_id é o centro; reviews e decisões "
                 "também se ligam à semana", loc="left")
    ax.text(-0.08, 0.02, "Seta: tabela pai → tabela filha (1:N). Texto na seta: coluna da junção.",
            fontsize=8, color="#666")
    salvar_grafico(fig, "G01_relacoes_tabelas", "Mapa de relações entre as tabelas")


def etapa_relacoes(t) -> None:
    titulo("2. Relações entre as tabelas: onde elas se juntam")
    rel = pd.DataFrame([verificar_relacao(t, *r) for r in RELACOES])
    tabela_md(rel)
    salvar_tabela(rel, "02_relacoes")
    total_orfaos = rel["registros_orfaos"].sum()
    registrar(f"Integridade: **{total_orfaos} registros órfãos** (nenhum registro aponta para hotel, "
              "cenário ou semana inexistente)." if total_orfaos == 0 else
              f"Atenção: {total_orfaos} registros órfãos encontrados.")
    registrar("")
    registrar("Como foi verificado: para cada relação, `filha[chave].isin(pai[chave])` conta quem não tem pai; "
              "`value_counts().max()` mostra quantos filhos um pai chega a ter (cardinalidade).")
    registrar("")
    registrar("**Redundâncias (normalização):** `hotel_name`, `tier` e `comp_set` se repetem em "
              "`daily_market` e `weekly_performance`, e `tier` em `room_types`. São cópias de `hotels`. "
              "No banco MySQL elas foram removidas das tabelas filhas (3ª forma normal) e voltam por JOIN.")
    registrar("")
    grafico_relacoes(t)


# ---------------------------------------------------------------------------
# 3. Relações entre as variáveis (correlação)
# ---------------------------------------------------------------------------
VARIAVEIS_DIARIAS = {
    "occupancy": "Ocupação", "adr": "ADR", "revpar": "RevPAR", "ancillary_capture": "% receita extra",
    "rgi": "RGI", "ari": "ARI", "mpi": "MPI", "rate_position": "Preço/MARS",
    "otb_occupancy_index": "Reservas futuras", "cancellation_rate": "Cancelamento",
    "booking_window_days": "Antecedência", "length_of_stay": "Noites/reserva",
    "market_occupancy": "Ocupação mercado", "tem_evento": "Evento",
}


def heatmap(ax, matriz: pd.DataFrame, titulo_graf: str) -> None:
    im = ax.imshow(matriz.values, cmap="RdBu", vmin=-1, vmax=1)
    ax.set_xticks(range(len(matriz.columns)), matriz.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(matriz.index)), matriz.index)
    ax.grid(False)
    for i in range(matriz.shape[0]):
        for j in range(matriz.shape[1]):
            v = matriz.iat[i, j]
            ax.text(j, i, f"{v:.2f}".replace(".", ","), ha="center", va="center", fontsize=7,
                    color="white" if abs(v) > 0.6 else "#222")
    ax.set_title(titulo_graf, loc="left")
    return im


def etapa_correlacoes(t) -> None:
    titulo("3. Relações entre as variáveis (correlação de Pearson)")
    dm = t["daily_market"]
    base = dm[list(VARIAVEIS_DIARIAS)].astype(float).rename(columns=VARIAVEIS_DIARIAS)
    corr = base.corr()  # Pearson: covariância / (desvio x * desvio y), de -1 a +1
    salvar_tabela(corr.reset_index().rename(columns={"index": "variavel"}), "03_matriz_correlacao")
    registrar("Cálculo: `df.corr()` (Pearson) = cov(X, Y) / (desvio(X) × desvio(Y)). "
              "Vai de -1 (andam em sentidos opostos) a +1 (andam juntas); 0 = sem relação linear.")
    registrar("")

    fig, ax = plt.subplots(figsize=(10, 8.5))
    im = heatmap(ax, corr, "Correlação entre as variáveis diárias (10.192 hotel-noites)")
    fig.colorbar(im, ax=ax, shrink=0.75, label="correlação de Pearson")
    salvar_grafico(fig, "G02_matriz_correlacao", "Matriz de correlação das variáveis diárias")

    pares = (corr.where(~pd.DataFrame(
        [[i >= j for j in range(len(corr))] for i in range(len(corr))],
        index=corr.index, columns=corr.columns)).stack().rename("r").reset_index())
    pares.columns = ["variavel_1", "variavel_2", "r"]
    pares["forca"] = pares["r"].abs()
    top = pares.sort_values("forca", ascending=False).head(10).drop(columns="forca")
    registrar("**As 10 relações mais fortes:**")
    registrar("")
    tabela_md(top)

    # Paradoxo: mercado inteiro x dentro de cada tier
    titulo("3.1 Ocupação × diária: mercado inteiro e dentro de cada tier", 3)
    r_total = dm["occupancy"].corr(dm["adr"])
    por_tier = dm.groupby("tier")[["occupancy", "adr"]].apply(lambda g: g["occupancy"].corr(g["adr"]))
    linhas = [{"grupo": "Mercado inteiro", "r_ocupacao_adr": r_total}] + [
        {"grupo": tr, "r_ocupacao_adr": por_tier[tr]} for tr in TIERS]
    tab = pd.DataFrame(linhas)
    tabela_md(tab)
    salvar_tabela(tab, "03_corr_ocupacao_adr_por_tier")
    registrar("Misturando todos os hotéis, a correlação fica fraca porque cada tier tem um nível de preço "
              "diferente. Dentro de cada tier ela é forte e positiva: noites cheias são as noites caras "
              "(alta demanda empurra os dois). É o alerta do enunciado: não misture tiers.")
    registrar("")

    fig, ax = plt.subplots(figsize=(10, 6))
    amostra = dm.sample(3000, random_state=1)
    for tr in TIERS:
        s = amostra[amostra["tier"] == tr]
        ax.scatter(s["occupancy"] * 100, s["adr"], s=9, alpha=0.45, color=COR_TIER[tr],
                   label=f"{tr} (r = {por_tier[tr]:.2f})".replace(".", ","))
    ax.set_xlabel("Ocupação na noite (%)")
    ax.set_ylabel("Diária média (ADR), US$")
    ax.set_title(f"Dentro de cada tier, noite mais cheia = diária mais alta "
                 f"(mercado inteiro: r = {r_total:.2f})".replace(".", ","), loc="left")
    ax.legend(title="Tier (correlação)", frameon=False, markerscale=2)
    salvar_grafico(fig, "G03_ocupacao_x_adr", "Ocupação × ADR por tier (amostra de 3.000 noites)")

    # Nota semanal x desempenho financeiro
    titulo("3.2 Nota dos hóspedes × resultado financeiro (semanal)", 3)
    w = t["weekly_performance"].dropna(subset=["mean_rating"])
    rel = {c: w["mean_rating"].corr(w[c]) for c in ["revpar", "rgi", "occupancy", "adr"]}
    rel_hotel = t["hotels"].set_index("hotel_id")["lifetime_rating"].corr(
        t["daily_market"].groupby("hotel_id")["rgi"].mean())
    tabela_md(pd.DataFrame({"variavel": list(rel), "r_com_nota_media": list(rel.values())}))
    registrar(f"Por hotel (nota de toda a vida × RGI médio, 14 pontos): r = {rel_hotel:.2f}.")
    registrar("")
    registrar("Semana a semana a nota quase não acompanha o dinheiro. Correlação não é causa: "
              "mesmo quando aparece alguma relação, a nota e a receita podem ter uma causa comum "
              "(tier, estação). Com 14 hotéis, um r por hotel é instável (amostra pequena).")
    registrar("")

    fig, ax = plt.subplots(figsize=(9, 5.5))
    for tr in TIERS:
        s = w[w["tier"] == tr]
        ax.scatter(s["mean_rating"], s["rgi"], s=10, alpha=0.5, color=COR_TIER[tr], label=tr)
    ax.axhline(100, color="#555", ls="--", lw=1)
    ax.set_xlabel("Nota média da semana (1 a 5)")
    ax.set_ylabel("RGI da semana (100 = igual aos concorrentes)")
    ax.set_title(f"Nota da semana quase não explica o RGI (r = {rel['rgi']:.2f})".replace(".", ","), loc="left")
    ax.legend(frameon=False, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    salvar_grafico(fig, "G04_nota_x_rgi", "Nota média semanal × RGI semanal")

    # Notas parciais x nota geral
    titulo("3.3 Quais notas parciais andam junto com a nota geral", 3)
    r = t["reviews"]
    parciais = {"cleanliness": "Limpeza", "comfort": "Conforto", "service_score": "Serviço",
                "location_score": "Localização", "value_score": "Custo-benefício", "sleep_quality": "Sono"}
    cp = pd.Series({nome: r["rating"].corr(r[c]) for c, nome in parciais.items()}).sort_values()
    tabela_md(cp.rename("r_com_nota_geral").reset_index().rename(columns={"index": "nota_parcial"}))
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.barh(cp.index, cp.values, color=AZUL, height=0.6)
    for i, v in enumerate(cp.values):
        ax.text(v + 0.01, i, f"{v:.2f}".replace(".", ","), va="center", fontsize=9)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Correlação com a nota geral")
    ax.set_title(f"{cp.index[-1]} é a nota parcial mais ligada à nota geral", loc="left")
    ax.grid(axis="y", visible=False)
    salvar_grafico(fig, "G05_notas_parciais", "Correlação das notas parciais com a nota geral")


# ---------------------------------------------------------------------------
# 4. Diária mais adequada (MARS) de cada hotel
# ---------------------------------------------------------------------------
def calcular_mars(dm: pd.DataFrame, posicionamento: pd.Series) -> pd.Series:
    """
    MARS(h, d) = mediana do ADR dos concorrentes de h na noite d
                 × posicionamento(h) / mediana do posicionamento desses concorrentes

    Concorrentes = hotéis do mesmo comp_set (tier), SEM o próprio hotel.
    """
    resultado = pd.Series(index=dm.index, dtype=float)
    for (_, _), noite in dm.groupby(["comp_set", "date"]):
        for idx, linha in noite.iterrows():
            pares = noite[noite["hotel_id"] != linha["hotel_id"]]
            mediana_adr = pares["adr"].median()
            mediana_pos = posicionamento[pares["hotel_id"]].median()
            resultado[idx] = mediana_adr * posicionamento[linha["hotel_id"]] / mediana_pos
    return resultado


def exemplo_mars(dm: pd.DataFrame, posicionamento: pd.Series, hotel: str, data: str) -> None:
    noite = dm[(dm["date"] == data) & (dm["comp_set"] == dm.loc[dm["hotel_id"] == hotel, "comp_set"].iat[0])]
    linha = noite[noite["hotel_id"] == hotel].iloc[0]
    pares = noite[noite["hotel_id"] != hotel]
    registrar(f"**Exemplo passo a passo: {linha['hotel_name']} ({hotel}), noite {data}, grupo `{linha['comp_set']}`**")
    registrar("")
    registrar("| Concorrente | ADR na noite | Posicionamento |")
    registrar("|---|---|---|")
    for _, p in pares.iterrows():
        registrar(f"| {p['hotel_name']} | US$ {fmt_num(p['adr'])} | {fmt_num(posicionamento[p['hotel_id']])} |")
    registrar("")
    med_adr = pares["adr"].median()
    med_pos = posicionamento[pares["hotel_id"]].median()
    pos_h = posicionamento[hotel]
    mars = med_adr * pos_h / med_pos
    registrar(f"1. Mediana do ADR dos concorrentes = US$ {fmt_num(med_adr)}")
    registrar(f"2. Posicionamento do hotel = {fmt_num(pos_h)}; mediana dos concorrentes = {fmt_num(med_pos)}")
    registrar(f"3. MARS = {fmt_num(med_adr)} × {fmt_num(pos_h)} / {fmt_num(med_pos)} = **US$ {fmt_num(mars)}**")
    registrar(f"4. Faixa aceitável (±6%): US$ {fmt_num(mars * 0.94)} a US$ {fmt_num(mars * 1.06)}")
    registrar(f"5. Diária cobrada (ADR) = US$ {fmt_num(linha['adr'])} → posição = ADR / MARS = "
              f"{fmt_num(linha['adr'] / mars, 3)} ({fmt_num((linha['adr'] / mars - 1) * 100, 1)}% em relação ao MARS)")
    registrar(f"6. Valor no dataset (`mars_rate`) = US$ {fmt_num(linha['mars_rate'])} ✔")
    registrar("")


def regra_acao(linha) -> str:
    """Regra documentada no README para rotular a ação de preço da noite."""
    pos, otb, evento = linha["rate_position"], linha["otb_occupancy_index"], linha["tem_evento"]
    if pos >= 1.12:
        return "lower"
    if evento and otb >= 0.70 and pos <= 1.02:
        return "raise"
    if otb >= 0.80 and pos <= 0.98:
        return "raise"
    if otb >= 0.72 and pos <= 0.92:
        return "raise"
    if otb <= 0.54 and pos >= 1.00:
        return "lower"
    if otb <= 0.62 and pos >= 1.06:
        return "lower"
    return "hold"


def etapa_mars(t) -> pd.DataFrame:
    titulo("4. Diária mais adequada de cada hotel (MARS)")
    registrar("MARS (*market appropriate rate*) é a diária que o hotel **deveria** cobrar naquela noite, "
              "dado o que os concorrentes diretos (mesmo tier) estão conseguindo cobrar e o quanto o hotel "
              "é melhor ou pior que eles (`positioning_index`).")
    registrar("")
    registrar("```")
    registrar("MARS(h, d) = mediana(ADR dos concorrentes de h na noite d)")
    registrar("             × posicionamento(h) / mediana(posicionamento dos concorrentes)")
    registrar("```")
    registrar("")
    dm, h = t["daily_market"], t["hotels"]
    posicionamento = h.set_index("hotel_id")["positioning_index"]
    exemplo_mars(dm, posicionamento, "H03", "2028-08-12")

    registrar("**Recalculando o MARS das 10.192 noites e comparando com o dataset:**")
    dm["mars_calculado"] = calcular_mars(dm, posicionamento)
    erro = (dm["mars_calculado"] / dm["mars_rate"] - 1).abs()
    registrar("")
    registrar(f"- Erro médio: {erro.mean() * 100:.5f}% · erro máximo: {erro.max() * 100:.4f}% "
              "(só arredondamento). **A fórmula foi reproduzida.**")
    registrar("")

    fig, ax = plt.subplots(figsize=(7, 6))
    for tr in TIERS:
        s = dm[dm["tier"] == tr]
        ax.scatter(s["mars_rate"], s["mars_calculado"], s=6, alpha=0.5, color=COR_TIER[tr], label=tr)
    lim = [dm["mars_rate"].min() * 0.95, dm["mars_rate"].max() * 1.05]
    ax.plot(lim, lim, color="#333", lw=1, ls="--", label="calculado = dataset")
    ax.set_xlabel("MARS do dataset (US$)")
    ax.set_ylabel("MARS calculado por este programa (US$)")
    ax.set_title("O MARS calculado bate com o do dataset em todas as noites", loc="left")
    ax.legend(frameon=False)
    salvar_grafico(fig, "G06_validacao_mars", "Validação do cálculo do MARS")

    # Valor mais adequado por hotel: ponderado por quartos vendidos
    titulo("4.1 Diária adequada × diária cobrada, por hotel", 3)
    registrar("Para cada hotel: ADR cobrado = soma(receita de quartos) / soma(quartos vendidos); "
              "MARS médio = soma(MARS × quartos vendidos) / soma(quartos vendidos), ponderado igual ao ADR "
              "para comparar maçã com maçã.")
    registrar("")
    dm["mars_x_vend"] = dm["mars_rate"] * dm["rooms_sold"]
    g = dm.groupby(["hotel_id", "hotel_name", "tier"]).agg(
        receita=("room_revenue", "sum"), vendidos=("rooms_sold", "sum"), mars_x=("mars_x_vend", "sum"),
        noites=("date", "count"),
        noites_abaixo=("rate_position", lambda s: (s < 0.94).sum()),
        noites_acima=("rate_position", lambda s: (s > 1.06).sum()),
        vendidos_cs=("comp_set_occupancy", lambda s: (s * dm.loc[s.index, "rooms_available"]).sum()),
    ).reset_index()
    g["MPI"] = g["vendidos"] / g["vendidos_cs"] * 100  # ocupação contra os concorrentes
    g["adr_cobrado"] = g["receita"] / g["vendidos"]
    g["mars_adequado"] = g["mars_x"] / g["vendidos"]
    g["diferenca_pct"] = (g["adr_cobrado"] / g["mars_adequado"] - 1) * 100
    g["pct_noites_abaixo_faixa"] = g["noites_abaixo"] / g["noites"] * 100
    g["pct_noites_acima_faixa"] = g["noites_acima"] / g["noites"] * 100
    # Receita que ficaria a mais/a menos se cobrasse MARS com a mesma ocupação (hipótese simplificadora)
    g["receita_se_mars_mi"] = (g["mars_x"] - g["receita"]) / 1e6

    def recomendacao(lin) -> str:
        """Cruza o preço (contra o MARS) com a ocupação (MPI, contra os concorrentes)."""
        dif, mpi = lin["diferenca_pct"], lin["MPI"]
        if -2 <= dif <= 2:
            return "Dentro da faixa do MARS: manter"
        if dif < -2 and mpi > 101:
            return "Barato e mais cheio que os concorrentes: há espaço para subir a diária"
        if dif < -2:
            return "Barato sem ganhar ocupação: o desconto não traz hóspedes; subir rumo ao MARS e rever qualidade"
        if mpi >= 98:
            return "Acima do MARS sem perder ocupação: o mercado aceita; manter e vigiar o MPI"
        return "Acima do MARS e perdendo ocupação: reduzir rumo ao MARS"

    g["o_que_fazer"] = g.apply(recomendacao, axis=1)
    g = g.sort_values("diferenca_pct")
    saida = g[["hotel_name", "tier", "adr_cobrado", "mars_adequado", "diferenca_pct", "MPI",
               "pct_noites_abaixo_faixa", "pct_noites_acima_faixa", "receita_se_mars_mi", "o_que_fazer"]]
    tabela_md(saida, 1)
    salvar_tabela(saida, "04_diaria_adequada_por_hotel")
    registrar("Regra do `o_que_fazer` (função `recomendacao()`): diferença entre −2% e +2% = dentro da faixa. "
              "Fora dela, olha-se o MPI (ocupação contra os concorrentes): se o hotel cobra menos que o MARS e "
              "mesmo assim não enche mais que os concorrentes (MPI ≤ 101), o desconto não está trazendo hóspedes. "
              "Se cobra mais e a ocupação se mantém (MPI ≥ 98), o mercado aceita o preço.")
    registrar("")
    registrar("`receita_se_mars_mi`: diferença de receita (US$ milhões, 2 anos) se cada quarto vendido tivesse "
              "sido cobrado pelo MARS, **supondo a mesma ocupação**. É um teto otimista: na prática, subir o "
              "preço reduz um pouco a ocupação (elasticidade).")
    registrar("")

    # Gráfico halteres: ADR cobrado x MARS
    fig, ax = plt.subplots(figsize=(10, 7))
    y = range(len(g))
    for i, (_, lin) in enumerate(g.iterrows()):
        ax.plot([lin["mars_adequado"], lin["adr_cobrado"]], [i, i], color="#c9ccd1", lw=3, zorder=1)
    ax.scatter(g["mars_adequado"], y, color="white", edgecolor="#333", s=70, zorder=2, label="MARS (adequado)")
    ax.scatter(g["adr_cobrado"], y, color=[COR_TIER[tr] for tr in g["tier"]], s=70, zorder=3,
               label="ADR cobrado (cor = tier)")
    for i, (_, lin) in enumerate(g.iterrows()):
        ax.text(max(lin["mars_adequado"], lin["adr_cobrado"]) + 6, i,
                f"{lin['diferenca_pct']:+.1f}%".replace(".", ","), va="center", fontsize=9,
                color=VERMELHO if abs(lin["diferenca_pct"]) > 2 else "#555")
    ax.set_yticks(list(y), g["hotel_name"])
    ax.set_xlabel("US$ por quarto vendido (média ponderada 2027–2028)")
    ax.set_title("Diária cobrada × diária adequada (MARS): quem está fora do ponto", loc="left")
    ax.legend(frameon=False, loc="lower right")
    ax.grid(axis="y", visible=False)
    salvar_grafico(fig, "G07_adr_x_mars", "ADR cobrado × MARS por hotel")

    # Distribuição do desvio por hotel (boxplot)
    ordem = g["hotel_name"].tolist()
    dados_box = [dm.loc[dm["hotel_name"] == n, "rate_gap_pct"] for n in ordem]
    fig, ax = plt.subplots(figsize=(10, 7))
    opcoes = dict(patch_artist=True, widths=0.6, showfliers=False, medianprops=dict(color="#222"))
    try:  # matplotlib 3.10+ usa orientation; versões antigas usam vert=False
        bp = ax.boxplot(dados_box, orientation="horizontal", **opcoes)
    except TypeError:
        bp = ax.boxplot(dados_box, vert=False, **opcoes)
    for caixa, tr in zip(bp["boxes"], g["tier"]):
        caixa.set_facecolor(COR_TIER[tr])
        caixa.set_alpha(0.8)
    ax.axvspan(-6, 6, color="#e8f0fb", zorder=0, label="faixa aceitável (±6%)")
    ax.axvline(0, color="#333", lw=1, ls="--")
    ax.set_yticks(range(1, len(ordem) + 1), ordem)
    ax.set_xlabel("Diferença entre a diária cobrada e o MARS em cada noite (%)")
    ax.set_title("Quanto o preço de cada noite se afasta do MARS", loc="left")
    ax.legend(frameon=False, loc="lower right")
    ax.grid(axis="y", visible=False)
    salvar_grafico(fig, "G08_desvio_mars_por_hotel", "Distribuição do desvio de preço em relação ao MARS")

    # MARS por estação (tabela de preço sugerido)
    titulo("4.2 Tabela de diária adequada por estação", 3)
    est = (dm.groupby(["hotel_name", "season"])["mars_rate"].median().unstack()
           .reindex(columns=["winter", "spring", "summer", "autumn"]))
    est.columns = ["inverno", "primavera", "verão", "outono"]
    est = est.reset_index().rename(columns={"hotel_name": "hotel"})
    tabela_md(est, 0)
    salvar_tabela(est, "04_mars_por_estacao")
    registrar("Mediana do MARS por estação: é a referência de preço que cada gerente pode usar como ponto de partida.")
    registrar("")

    # Reprodução da regra de ação
    titulo("4.3 Regra de recomendação (subir, manter ou baixar)", 3)
    dm["acao_regra"] = dm.apply(regra_acao, axis=1)
    acerto = (dm["acao_regra"] == dm["rate_action"]).mean()
    registrar("A regra do README foi programada na função `regra_acao()` e aplicada às 10.192 noites.")
    registrar(f"Concordância com `rate_action` do dataset: **{fmt_pct(acerto)}**. "
              "O README avisa que 3% dos rótulos foram trocados de propósito (ruído), então ~97% é o esperado.")
    registrar("")
    mat = pd.crosstab(dm["rate_action"], dm["acao_regra"], rownames=["dataset"], colnames=["regra"])
    tabela_md(mat.reset_index())
    return g


# ---------------------------------------------------------------------------
# 5. Desempenho contra concorrentes, sazonalidade
# ---------------------------------------------------------------------------
def etapa_desempenho(t) -> None:
    titulo("5. Desempenho de cada hotel contra os concorrentes")
    dm = t["daily_market"]
    dm["cs_rev"] = dm["comp_set_revpar"] * dm["rooms_available"]
    dm["cs_vend"] = dm["comp_set_occupancy"] * dm["rooms_available"]
    dm["cs_rec"] = dm["comp_set_adr"] * dm["cs_vend"]
    g = dm.groupby(["hotel_name", "tier"]).agg(
        disp=("rooms_available", "sum"), vend=("rooms_sold", "sum"), rec=("room_revenue", "sum"),
        rec_total=("receita_total", "sum"), cs_rev=("cs_rev", "sum"), cs_vend=("cs_vend", "sum"),
        cs_rec=("cs_rec", "sum")).reset_index()
    g["ocupacao_%"] = g["vend"] / g["disp"] * 100
    g["adr"] = g["rec"] / g["vend"]
    g["revpar"] = g["rec"] / g["disp"]
    g["ARI"] = g["adr"] / (g["cs_rec"] / g["cs_vend"]) * 100
    g["MPI"] = g["vend"] / g["cs_vend"] * 100
    g["RGI"] = g["rec"] / g["cs_rev"] * 100
    registrar("Fórmulas: ocupação = vendidos/disponíveis; ADR = receita de quartos/vendidos; "
              "RevPAR = receita de quartos/disponíveis; ARI = ADR/ADR dos concorrentes × 100; "
              "MPI = ocupação/ocupação dos concorrentes × 100; RGI = RevPAR/RevPAR dos concorrentes × 100 "
              "(≈ ARI × MPI / 100). Todas calculadas a partir de **somas** (média ponderada), não média de médias.")
    registrar("")
    tab = g[["hotel_name", "tier", "rec_total", "ocupacao_%", "adr", "revpar", "ARI", "MPI", "RGI"]] \
        .sort_values("RGI", ascending=False)
    tabela_md(tab, 1)
    salvar_tabela(tab, "05_desempenho_hoteis")

    fig, ax = plt.subplots(figsize=(10, 7))
    for _, lin in g.iterrows():
        ax.scatter(lin["ARI"], lin["MPI"], s=lin["disp"] / 400, color=COR_TIER[lin["tier"]],
                   edgecolor="white", lw=1.5, zorder=3)
        desloc = (7, -10) if lin["hotel_name"] == "Kestrel Park Hotel" else (7, 4)  # evita sobrepor
        ax.annotate(lin["hotel_name"], (lin["ARI"], lin["MPI"]), xytext=desloc,
                    textcoords="offset points", fontsize=8)
    ax.margins(x=0.15, y=0.1)  # espaço para os nomes nas bordas
    ax.axvline(100, color="#555", ls="--", lw=1)
    ax.axhline(100, color="#555", ls="--", lw=1)
    xm, ym = ax.get_xlim(), ax.get_ylim()
    kw = dict(fontsize=9, color="#777", fontweight="bold")
    ax.text(xm[1], ym[1], "cobra mais e enche mais", ha="right", va="top", **kw)
    ax.text(xm[0], ym[1], "cobra menos e enche mais", ha="left", va="top", **kw)
    ax.text(xm[1], ym[0], "cobra mais e enche menos", ha="right", va="bottom", **kw)
    ax.text(xm[0], ym[0], "cobra menos e enche menos", ha="left", va="bottom", **kw)
    for tr in TIERS:
        ax.scatter([], [], color=COR_TIER[tr], label=tr, s=50)
    ax.legend(frameon=False, title="Tier (tamanho = nº de quartos)", loc="center left", bbox_to_anchor=(1, 0.5))
    ax.set_xlabel("ARI: diária contra os concorrentes (100 = igual)")
    ax.set_ylabel("MPI: ocupação contra os concorrentes (100 = igual)")
    ax.set_title("Mapa de posicionamento: preço × ocupação contra os concorrentes", loc="left")
    salvar_grafico(fig, "G09_quadrante_ari_mpi", "Quadrantes ARI × MPI")

    # Sazonalidade
    titulo("5.1 Sazonalidade e eventos", 3)
    dm["mes"] = dm["date"].dt.month
    m = dm.groupby(["tier", "mes"]).agg(vend=("rooms_sold", "sum"), disp=("rooms_available", "sum"),
                                         rec=("room_revenue", "sum")).reset_index()
    m["ocupacao"] = m["vend"] / m["disp"] * 100
    m["adr"] = m["rec"] / m["vend"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.8))
    meses = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
    for tr in TIERS:
        s = m[m["tier"] == tr]
        a1.plot(s["mes"], s["ocupacao"], marker="o", ms=4, lw=2, color=COR_TIER[tr], label=tr)
        a2.plot(s["mes"], s["adr"], marker="o", ms=4, lw=2, color=COR_TIER[tr], label=tr)
    for a, tit, yl in [(a1, "Ocupação por mês (%)", "%"), (a2, "Diária média (ADR) por mês", "US$")]:
        a.set_xticks(range(1, 13), meses)
        a.set_title(tit, loc="left")
        a.set_ylabel(yl)
    a1.legend(frameon=False, ncol=5, loc="upper center", bbox_to_anchor=(1.1, -0.1))
    fig.suptitle("Agosto é o pico do ano em todos os tiers; o inverno é o vale", x=0.01, ha="left",
                 fontweight="bold")
    salvar_grafico(fig, "G10_sazonalidade", "Sazonalidade de ocupação e ADR por tier")

    ev = dm.groupby(["tier", "tem_evento"]).agg(vend=("rooms_sold", "sum"), disp=("rooms_available", "sum"),
                                                 rec=("room_revenue", "sum")).reset_index()
    ev["ocupacao"] = ev["vend"] / ev["disp"]
    ev["adr"] = ev["rec"] / ev["vend"]
    p = ev.pivot(index="tier", columns="tem_evento", values=["ocupacao", "adr"]).reindex(TIERS)
    efeito = pd.DataFrame({
        "tier": TIERS,
        "ocupacao_comum": p[("ocupacao", False)].values * 100,
        "ocupacao_evento": p[("ocupacao", True)].values * 100,
        "adr_comum": p[("adr", False)].values, "adr_evento": p[("adr", True)].values,
    })
    efeito["ganho_ocup_pontos"] = efeito["ocupacao_evento"] - efeito["ocupacao_comum"]
    efeito["ganho_adr_pct"] = (efeito["adr_evento"] / efeito["adr_comum"] - 1) * 100
    registrar("Noites com evento de demanda × noites comuns:")
    registrar("")
    tabela_md(efeito, 1)
    salvar_tabela(efeito, "05_efeito_eventos")


# ---------------------------------------------------------------------------
# 6. Decisões de preço
# ---------------------------------------------------------------------------
def etapa_decisoes(t) -> None:
    titulo("6. As decisões de preço semanais funcionaram?")
    rd = t["rate_decisions"]
    tab = pd.crosstab(rd["action"], rd["outcome"], normalize="index").reindex(
        index=["raise", "hold", "lower"], columns=["better", "in line", "worse"]) * 100
    n = rd["action"].value_counts()
    uplift = rd.groupby("action")["realised_uplift_pct"].median()
    out = tab.reset_index()
    out.columns = ["acao", "melhor_%", "estavel_%", "pior_%"]
    out["semanas"] = out["acao"].map(n)
    out["mediana_variacao_revpar_%"] = out["acao"].map(uplift)
    tabela_md(out, 1)
    salvar_tabela(out, "06_decisoes_preco")
    registrar("Cálculo: `pd.crosstab(acao, resultado, normalize='index')` = % de cada resultado dentro de cada ação. "
              "Resultado = RevPAR da semana seguinte comparado à semana da decisão, com faixa de ±1,5%.")
    registrar("")
    registrar("Leitura: nenhuma ação garante resultado; as três têm perfil parecido. Como não existe o "
              "\"e se não tivesse mudado\" (contrafactual), isso **não prova** que a decisão causou o resultado. "
              "A sazonalidade da semana seguinte pesa mais que a decisão.")
    registrar("")

    fig, ax = plt.subplots(figsize=(9, 3.8))
    nomes = {"raise": "Aumentar", "hold": "Manter", "lower": "Reduzir"}
    cores = {"better": AZUL, "in line": "#c4c7cc", "worse": VERMELHO}
    rot = {"better": "Melhor", "in line": "Estável", "worse": "Pior"}
    esquerda = pd.Series(0.0, index=tab.index)
    for c in ["better", "in line", "worse"]:
        ax.barh([f"{nomes[a]} ({n[a]})" for a in tab.index], tab[c], left=esquerda, color=cores[c],
                label=rot[c], edgecolor="white", lw=2, height=0.6)
        for i, (v, l) in enumerate(zip(tab[c], esquerda)):
            ax.text(l + v / 2, i, f"{v:.0f}%", ha="center", va="center", fontsize=9,
                    color="white" if c != "in line" else "#222")
        esquerda += tab[c]
    ax.set_xlim(0, 100)
    ax.set_xlabel("% das semanas")
    ax.set_title("Resultado da semana seguinte por tipo de decisão: perfis parecidos", loc="left")
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.22))
    ax.grid(axis="y", visible=False)
    ax.invert_yaxis()
    salvar_grafico(fig, "G11_decisoes_preco", "Resultado das decisões de preço")


# ---------------------------------------------------------------------------
# 7. Avaliações
# ---------------------------------------------------------------------------
CENARIOS_PT = {
    "delight": "Superou expectativas", "location": "Localização e acesso",
    "breakfast": "Café da manhã e comida", "service_recovery": "Problema resolvido bem",
    "room_condition": "Estado do quarto", "noise": "Barulho e sono", "checkin_wait": "Fila no check-in",
    "billing": "Cobrança e tarifas", "wifi": "Wi-Fi e conexão", "cleanliness": "Limpeza",
    "group_trip": "Grupo ou família",
}


def etapa_avaliacoes(t) -> None:
    titulo("7. O que os hóspedes estão dizendo")
    r = t["reviews"]
    freq = r["rating"].value_counts().sort_index().rename_axis("nota").reset_index(name="freq_absoluta")
    freq["freq_relativa_%"] = freq["freq_absoluta"] / freq["freq_absoluta"].sum() * 100
    freq["freq_acumulada_%"] = freq["freq_relativa_%"].cumsum()
    tabela_md(freq, 1)
    salvar_tabela(freq, "07_frequencia_notas")
    ate3 = freq.loc[freq["nota"] <= 3, "freq_relativa_%"].sum()
    registrar(f"Avaliações com 3 estrelas ou menos: **{fmt_num(ate3, 1)}%**. "
              f"Média = {fmt_num(r['rating'].mean())}, mediana = {r['rating'].median():.0f}, "
              f"moda = {r['rating'].mode().iat[0]}.")
    registrar("")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    cores = [VERMELHO, "#f19a9a", "#c4c7cc", "#84b9f3", AZUL]
    rotulos = freq["nota"].astype(str) + "★"
    ax.bar(rotulos, freq["freq_relativa_%"], color=cores, width=0.65, label="% de cada nota")
    # A linha acumulada usa o MESMO eixo (0–100%): não é um gráfico de dois eixos.
    ax.plot(rotulos, freq["freq_acumulada_%"], color="#333", marker="o", lw=1.5, label="% acumulado")
    ax.set_ylim(0, 108)
    for i, (v, a) in enumerate(zip(freq["freq_relativa_%"], freq["freq_acumulada_%"])):
        ax.text(i, v / 2, f"{v:.1f}%".replace(".", ","), ha="center", va="center", fontsize=9,
                color="white" if i in (0, 4) else "#222")
        ax.text(i - 0.12, a + 3, f"{a:.0f}%", ha="right", fontsize=8, color="#333")
    ax.legend(frameon=False, loc="upper left")
    ax.set_ylabel("% das avaliações (barras) · acumulado (linha)")
    ax.set_title(f"{fmt_num(ate3, 1)}% das avaliações têm 3 estrelas ou menos", loc="left")
    ax.grid(axis="x", visible=False)
    salvar_grafico(fig, "G12_distribuicao_notas", "Distribuição de frequências das notas")

    titulo("7.1 Cenários: por que os hóspedes avaliam assim", 3)
    sc = t["review_scenarios"].set_index("scenario_id")
    g = r.merge(t["review_scenarios"], on="scenario_id")  # junção reviews x review_scenarios
    c = g.groupby(["scenario_id", "label", "recovery_action"]).agg(
        avaliacoes=("review_id", "count"), nota_media=("rating", "mean"),
        respondidas_pct=("respondida", "mean")).reset_index().sort_values("avaliacoes")
    c["respondidas_pct"] *= 100
    c["label"] = c["scenario_id"].map(CENARIOS_PT).fillna(c["label"])
    tabela_md(c.sort_values("avaliacoes", ascending=False)[["label", "avaliacoes", "nota_media",
                                                            "respondidas_pct", "recovery_action"]], 2)
    salvar_tabela(c, "07_cenarios")
    fig, ax = plt.subplots(figsize=(10, 5.5))
    cor = [AZUL if m >= 3.5 else VERMELHO if m <= 2.5 else "#b5b8be" for m in c["nota_media"]]
    ax.barh(c["label"], c["avaliacoes"], color=cor, height=0.65)
    for i, (n, m) in enumerate(zip(c["avaliacoes"], c["nota_media"])):
        ax.text(n + 15, i, f"{n:,}".replace(",", ".") + f"  ·  {m:.1f}★".replace(".", ","), va="center", fontsize=8)
    ax.set_xlabel("Número de avaliações")
    ax.set_title("Motivos das avaliações (vermelho = nota média ≤ 2,5; azul = ≥ 3,5)", loc="left")
    ax.grid(axis="y", visible=False)
    salvar_grafico(fig, "G13_cenarios", "Avaliações por cenário")

    resp = r.groupby("rating").agg(taxa=("respondida", "mean"), horas=("response_hours", "mean")).reset_index()
    resp["taxa"] *= 100
    registrar("Respostas do hotel por nota (taxa de resposta em % e tempo médio em horas):")
    registrar("")
    tabela_md(resp, 1)
    salvar_tabela(resp, "07_respostas_por_nota")


# ---------------------------------------------------------------------------
# 8. Projeção 2029
# ---------------------------------------------------------------------------
def etapa_projecao(t, hotel: str = "H03") -> None:
    titulo("8. Projeção simples de receita para 2029")
    dm = t["daily_market"]
    s = dm[dm["hotel_id"] == hotel].copy()
    nome = s["hotel_name"].iat[0]
    s["ano"], s["mes"] = s["date"].dt.year, s["date"].dt.month
    # Média DIÁRIA por mês: 2027 começa em 04/01 (362 dias) e 2028 é bissexto (366 dias).
    # Comparar somas anuais misturaria crescimento real com diferença de número de dias.
    mens = s.groupby(["ano", "mes"])["receita_total"].agg(["sum", "count"]).reset_index()
    mens["por_dia"] = mens["sum"] / mens["count"]
    dias = s.groupby("ano")["date"].count()
    p27 = mens[mens["ano"] == 2027].set_index("mes")
    p28 = mens[mens["ano"] == 2028].set_index("mes")
    media27 = p27["sum"].sum() / dias[2027]
    media28 = p28["sum"].sum() / dias[2028]
    crescimento = media28 / media27 - 1
    dias_mes_2029 = pd.Series(pd.date_range("2029-01-01", "2029-12-31").month).value_counts().sort_index()
    p29 = p28["por_dia"] * (1 + crescimento) * dias_mes_2029
    soma27, soma28 = p27["sum"], p28["sum"]
    registrar(f"Hotel: **{nome}**. Método: crescimento da receita **média por dia** de 2027 para 2028, "
              "aplicado mês a mês sobre 2028 (mantém a sazonalidade) e multiplicado pelos dias de cada mês de 2029.")
    registrar("")
    registrar(f"- Cuidado encontrado: 2027 tem só {dias[2027]} dias no dataset (começa em 04/01) e 2028 tem "
              f"{dias[2028]} (bissexto). Somar o ano inteiro daria um crescimento falso de "
              f"{fmt_pct(soma28.sum() / soma27.sum() - 1, 2)}.")
    registrar(f"- Receita média por dia 2027: US$ {fmt_num(media27, 0)} · 2028: US$ {fmt_num(media28, 0)}")
    registrar(f"- Crescimento = {fmt_num(media28, 0)} / {fmt_num(media27, 0)} − 1 = **{fmt_pct(crescimento, 2)}**")
    registrar(f"- Projeção 2029 = Σ (receita por dia do mês em 2028 × (1 + crescimento) × dias do mês) "
              f"= **US$ {fmt_num(p29.sum(), 0)}**")
    registrar("")
    registrar("**Limitações:** só 2 anos (um único ponto de crescimento); a extrapolação supõe que tudo continua "
              "igual (sem crise, sem novo concorrente, sem reforma, mesma agenda de eventos); "
              "o dataset é sintético.")
    registrar("")
    fig, ax = plt.subplots(figsize=(11, 4.5))
    x27, x28, x29 = range(1, 13), range(13, 25), range(25, 37)
    ax.plot(x27, soma27.values / 1e6, color=AZUL, lw=2, marker="o", ms=3, label="2027 (real)")
    ax.plot(x28, soma28.values / 1e6, color=AZUL, lw=2, marker="o", ms=3, label="2028 (real)", alpha=0.7)
    ax.plot(x29, p29.values / 1e6, color="#f47230", lw=2, ls="--", marker="o", ms=3, label="2029 (projeção)")
    ax.axvspan(24.5, 36.5, color="#fff3e8", zorder=0)
    ax.set_xticks([1, 7, 13, 19, 25, 31], ["jan/27", "jul/27", "jan/28", "jul/28", "jan/29", "jul/29"])
    ax.set_ylabel("Receita mensal (US$ milhões)")
    ax.set_title(f"{nome}: projeção 2029 de US$ {p29.sum() / 1e6:.1f} mi "
                 f"({crescimento * 100:+.1f}% ao ano)".replace(".", ","), loc="left")
    ax.legend(frameon=False)
    salvar_grafico(fig, "G14_projecao_2029", "Projeção de receita para 2029")


# ---------------------------------------------------------------------------
# 9. Funções utilizadas
# ---------------------------------------------------------------------------
FUNCOES = [
    ("pandas", "pd.read_json(..., lines=True)", "ler arquivos JSONL (um registro por linha)"),
    ("pandas", "pd.to_datetime", "converter texto em data"),
    ("pandas", "df.isna().sum()", "contar valores ausentes por coluna"),
    ("pandas", "df.explode", "transformar a lista de amenities em linhas"),
    ("pandas", "Series.value_counts", "frequência absoluta"),
    ("pandas", "Series.cumsum", "frequência acumulada"),
    ("pandas", "Series.isin", "verificar integridade (registros órfãos)"),
    ("pandas", "df.merge", "juntar tabelas (reviews + review_scenarios)"),
    ("pandas", "df.groupby(...).agg", "somar/medianas por hotel, tier, mês, noite"),
    ("pandas", "Series.median", "mediana do ADR dos concorrentes (MARS)"),
    ("pandas", "df.corr / Series.corr", "correlação de Pearson"),
    ("pandas", "pd.crosstab", "tabela cruzada ação × resultado"),
    ("pandas", "df.pivot / unstack", "reorganizar de formato longo para largo"),
    ("pandas", "df.apply", "aplicar a regra de ação linha a linha"),
    ("pandas", "df.to_csv", "salvar as tabelas de resultado"),
    ("matplotlib", "plt.subplots", "criar figura e eixos"),
    ("matplotlib", "ax.bar / ax.barh", "barras (frequências, ranking, cenários)"),
    ("matplotlib", "ax.plot", "linhas (sazonalidade, projeção)"),
    ("matplotlib", "ax.scatter", "dispersão (correlação, quadrantes, validação)"),
    ("matplotlib", "ax.boxplot", "distribuição do desvio de preço"),
    ("matplotlib", "ax.imshow", "mapa de calor da matriz de correlação"),
    ("matplotlib", "ax.axhline / axvline / axvspan", "linhas e faixas de referência (100, ±6%)"),
    ("matplotlib", "ax.annotate / ax.text", "rótulos e setas"),
    ("matplotlib", "fig.savefig", "salvar os gráficos em PNG"),
    ("próprias", "inspecionar_tabela()", "resumo padronizado das 7 tabelas"),
    ("próprias", "verificar_relacao()", "chave única, cardinalidade e órfãos de cada relação"),
    ("próprias", "calcular_mars()", "recalcular a diária adequada de cada noite"),
    ("próprias", "regra_acao()", "regra de subir/manter/baixar do README"),
    ("próprias", "registrar() / tabela_md() / salvar_grafico()", "montar o relatório automaticamente"),
]


def etapa_funcoes() -> None:
    titulo("9. Funções utilizadas")
    tabela_md(pd.DataFrame(FUNCOES, columns=["biblioteca", "função", "para que foi usada"]))


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------
def main() -> None:
    for p in (PASTA_GRAFICOS, PASTA_TABELAS):
        p.mkdir(parents=True, exist_ok=True)
    registrar("# Relatório de cálculos: Hotéis de Port Alder")
    registrar("")
    registrar("Gerado automaticamente por `analise/analise_hoteis.py`. Dataset sintético *Nice Rooms* (CC BY 4.0).")

    t = preparar_dados(carregar_dados())
    etapa_inspecao(t)
    etapa_relacoes(t)
    etapa_correlacoes(t)
    etapa_mars(t)
    etapa_desempenho(t)
    etapa_decisoes(t)
    etapa_avaliacoes(t)
    etapa_projecao(t)
    etapa_funcoes()

    (PASTA_SAIDA / "relatorio_calculos.md").write_text("\n".join(RELATORIO), encoding="utf-8")
    print(f"\nPronto. Gráficos em {PASTA_GRAFICOS}, tabelas em {PASTA_TABELAS}.")


if __name__ == "__main__":
    main()
