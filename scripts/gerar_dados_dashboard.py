"""Gera o arquivo de dados resumido que o painel web consome.

Uso (a partir da raiz do projeto):
    python scripts/gerar_dados_dashboard.py

Lê os arquivos JSONL de dados/ e grava dashboard/dados.js.

Por que um arquivo .js e não .json?
    Quando a página é aberta com duplo clique (file://), o navegador bloqueia
    fetch() de arquivos locais. Um .js carregado por <script> funciona sem
    servidor e sem instalação, que é o que o enunciado exige.

Nível de agregação: hotel x mês (14 hotéis x 24 meses = 336 linhas).
    - Mês é fino o bastante para mostrar sazonalidade e eventos.
    - Guardamos SOMAS (quartos vendidos, receita, etc.) e não médias, para que
      o JavaScript recalcule ocupação, ADR e RevPAR corretamente (ponderados)
      para qualquer combinação de filtros. Média de médias daria errado.
"""
from pathlib import Path
import json
import shutil

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
SAIDA = RAIZ / "dashboard" / "dados.js"
PASTA_IMG = RAIZ / "dashboard" / "img"
# Gráficos gerados por analise/analise_hoteis.py e banco/diagrama_er.py
ORIGENS_IMG = [RAIZ / "analise" / "saida" / "graficos", RAIZ / "banco"]


def ler(nome: str) -> pd.DataFrame:
    """Lê um arquivo JSONL (um registro por linha)."""
    return pd.read_json(DADOS / f"{nome}.jsonl", lines=True)


def mensal(daily: pd.DataFrame) -> list[dict]:
    d = daily.copy()
    d["mes"] = d["date"].dt.month
    d["evento"] = (d["demand_event"].fillna("").str.strip() != "").astype(int)
    # Componentes "comp set" multiplicados pelos quartos disponíveis do hotel,
    # para chegar a índices ponderados (aproximação do RGI/ARI/MPI mensal).
    d["cs_rev"] = d["comp_set_revpar"] * d["rooms_available"]
    d["cs_vend"] = d["comp_set_occupancy"] * d["rooms_available"]
    d["cs_rec"] = d["comp_set_adr"] * d["cs_vend"]
    d["mars_x_vend"] = d["mars_rate"] * d["rooms_sold"]
    d["receita_total"] = d["room_revenue"] + d["ancillary_revenue"]
    d["abaixo"] = (d["rate_position"] < 0.94).astype(int)   # noite abaixo da faixa do MARS (-6%)
    d["acima"] = (d["rate_position"] > 1.06).astype(int)    # noite acima da faixa do MARS (+6%)

    g = d.groupby(["hotel_id", "year", "mes"]).agg(
        disp=("rooms_available", "sum"),
        vend=("rooms_sold", "sum"),
        rec_q=("room_revenue", "sum"),
        rec_t=("receita_total", "sum"),
        gop=("gross_operating_profit", "sum"),
        cs_rev=("cs_rev", "sum"),
        cs_vend=("cs_vend", "sum"),
        cs_rec=("cs_rec", "sum"),
        mars=("mars_x_vend", "sum"),
        noites_evento=("evento", "sum"),
        noites=("date", "count"),
        abaixo=("abaixo", "sum"),
        acima=("acima", "sum"),
        mars_soma=("mars_rate", "sum"),
    ).reset_index()
    g = g.rename(columns={"hotel_id": "h", "year": "a", "mes": "m"})
    return g.round(2).to_dict(orient="records")


def avaliacoes(reviews: pd.DataFrame) -> list[dict]:
    r = reviews.copy()
    r["a"] = pd.to_datetime(r["stay_date"]).dt.year
    r["resp"] = r["response_hours"].notna().astype(int)
    g = r.groupby(["hotel_id", "a", "rating"]).agg(
        n=("review_id", "count"), resp=("resp", "sum")
    ).reset_index()
    g = g.rename(columns={"hotel_id": "h", "rating": "nota"})
    return g.to_dict(orient="records")


def cenarios(reviews: pd.DataFrame) -> list[dict]:
    r = reviews.copy()
    r["a"] = pd.to_datetime(r["stay_date"]).dt.year
    g = r.groupby(["hotel_id", "a", "scenario_id"]).agg(
        n=("review_id", "count"), soma=("rating", "sum")
    ).reset_index()
    g = g.rename(columns={"hotel_id": "h", "scenario_id": "c"})
    return g.to_dict(orient="records")


def exemplo_mars(daily: pd.DataFrame, hotels: pd.DataFrame, hotel="H14", data="2028-08-12") -> dict:
    """Um cálculo do MARS passo a passo, para mostrar na página."""
    pos = hotels.set_index("hotel_id")["positioning_index"]
    grupo = hotels.set_index("hotel_id").loc[hotel, "comp_set"]
    noite = daily[(daily["date"] == data) & (daily["comp_set"] == grupo)]
    lin = noite[noite["hotel_id"] == hotel].iloc[0]
    pares = noite[noite["hotel_id"] != hotel]
    med_adr = float(pares["adr"].median())
    med_pos = float(pos[pares["hotel_id"]].median())
    return {
        "hotel": lin["hotel_name"], "data": data, "grupo": grupo,
        "concorrentes": [{"nome": r["hotel_name"], "adr": float(r["adr"]), "pos": float(pos[r["hotel_id"]])}
                         for _, r in pares.iterrows()],
        "med_adr": med_adr, "pos_hotel": float(pos[hotel]), "med_pos": med_pos,
        "mars": med_adr * float(pos[hotel]) / med_pos, "mars_dataset": float(lin["mars_rate"]),
        "adr": float(lin["adr"]),
    }


def relacoes(t: dict[str, pd.DataFrame]) -> list[dict]:
    """Chaves que ligam as tabelas, cardinalidade e registros órfãos."""
    lig = [("hotels", "room_types", ["hotel_id"]), ("hotels", "daily_market", ["hotel_id"]),
           ("hotels", "weekly_performance", ["hotel_id"]), ("hotels", "rate_decisions", ["hotel_id"]),
           ("hotels", "reviews", ["hotel_id"]), ("review_scenarios", "reviews", ["scenario_id"]),
           ("weekly_performance", "reviews", ["hotel_id", "week_start"]),
           ("weekly_performance", "rate_decisions", ["hotel_id", "week_start"])]
    saida = []
    for pai, filha, ch in lig:
        kp = t[pai][ch].astype(str).agg("|".join, axis=1)
        kf = t[filha][ch].astype(str).agg("|".join, axis=1)
        maxf = int(kf.value_counts().max())
        saida.append({"pai": pai, "filha": filha, "chave": " + ".join(ch),
                      "card": "1:1" if maxf == 1 else "1:N", "max": maxf,
                      "orfaos": int((~kf.isin(set(kp))).sum())})
    return saida


def tabelas_info(t: dict[str, pd.DataFrame]) -> list[dict]:
    grao = {"hotels": "1 hotel", "room_types": "1 tipo de quarto de 1 hotel",
            "daily_market": "1 hotel em 1 noite", "weekly_performance": "1 hotel em 1 semana",
            "rate_decisions": "1 decisão semanal de preço + semana seguinte",
            "reviews": "1 avaliação de hóspede", "review_scenarios": "1 motivo de avaliação"}
    saida = []
    for n, df in t.items():
        txt = df.select_dtypes(include=["object", "string"]).apply(lambda s: s.astype(str).str.strip().eq("").sum())
        aus = df.isna().sum() + txt.reindex(df.columns, fill_value=0)
        aus = aus[aus > 0]
        saida.append({"nome": n, "linhas": len(df), "colunas": df.shape[1], "grao": grao[n],
                      "ausentes": ", ".join(f"{c} ({v})" for c, v in aus.items()) or "nenhum"})
    return saida


VARS_CORR = {
    "occupancy": "Ocupação", "adr": "ADR", "revpar": "RevPAR", "ancillary_capture": "% receita extra",
    "rgi": "RGI", "ari": "ARI", "mpi": "MPI", "rate_position": "Preço/MARS",
    "otb_occupancy_index": "Reservas futuras", "cancellation_rate": "Cancelamento",
    "booking_window_days": "Antecedência", "length_of_stay": "Noites/reserva",
    "market_occupancy": "Ocupação mercado", "evento": "Evento",
}


def extras_interativos(daily, weekly, reviews) -> dict:
    """Dados para os gráficos interativos da aba 'Gráficos e análises'."""
    d = daily.copy()
    d["evento"] = (d["demand_event"].fillna("").str.strip() != "").astype(float)
    corr = d[list(VARS_CORR)].astype(float).corr().round(3)
    amostra = d.sample(2000, random_state=1)
    w = weekly.dropna(subset=["mean_rating"])
    parciais = {"Limpeza": "cleanliness", "Conforto": "comfort", "Serviço": "service_score",
                "Localização": "location_score", "Custo-benefício": "value_score", "Sono": "sleep_quality"}
    quartis = []
    for (h, a), g in d.groupby(["hotel_id", "year"]):
        q = g["rate_gap_pct"].quantile([0.05, 0.25, 0.5, 0.75, 0.95]).round(2).tolist()
        quartis.append({"h": h, "a": int(a), "q": q})
    for h, g in d.groupby("hotel_id"):
        q = g["rate_gap_pct"].quantile([0.05, 0.25, 0.5, 0.75, 0.95]).round(2).tolist()
        quartis.append({"h": h, "a": 0, "q": q})
    return {
        "corr": {"vars": list(VARS_CORR.values()), "m": corr.values.tolist()},
        "amostra": [{"h": r.hotel_id, "a": int(r.year), "o": round(r.occupancy, 4), "p": round(r.adr, 2)}
                    for r in amostra.itertuples()],
        "semanal": [{"h": r.hotel_id, "a": r.week_start.year if hasattr(r.week_start, "year") else int(str(r.week_start)[:4]),
                     "n": round(r.mean_rating, 2), "g": round(r.rgi, 1)} for r in w.itertuples()],
        "parciais": [{"nome": k, "r": round(reviews["rating"].corr(reviews[v]), 3)} for k, v in parciais.items()],
        "desvio": quartis,
    }


def copiar_imagens() -> int:
    PASTA_IMG.mkdir(exist_ok=True)
    n = 0
    for pasta in ORIGENS_IMG:
        for png in sorted(pasta.glob("*.png")):
            shutil.copy2(png, PASTA_IMG / png.name)
            n += 1
    return n


def decisoes(rd: pd.DataFrame) -> list[dict]:
    r = rd.copy()
    r["a"] = pd.to_datetime(r["week_start"]).dt.year
    g = r.groupby(["hotel_id", "a", "action", "outcome"]).size().reset_index(name="n")
    g = g.rename(columns={"hotel_id": "h", "action": "acao", "outcome": "res"})
    return g.to_dict(orient="records")


def main() -> None:
    hotels = ler("hotels")
    daily = ler("daily_market")
    reviews = ler("reviews")
    rd = ler("rate_decisions")
    sc = ler("review_scenarios")

    pacote = {
        "gerado_em": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
        "hoteis": hotels[["hotel_id", "name", "tier", "rooms", "neighbourhood"]]
        .join(hotels[["positioning_index", "comp_set"]])
        .rename(columns={"hotel_id": "id", "name": "nome", "rooms": "quartos",
                         "neighbourhood": "bairro", "positioning_index": "pos"})
        .to_dict(orient="records"),
        "cenarios_info": sc[["scenario_id", "label", "recovery_action"]]
        .rename(columns={"scenario_id": "id", "label": "nome", "recovery_action": "acao"})
        .to_dict(orient="records"),
        "mensal": mensal(daily),
        "avaliacoes": avaliacoes(reviews),
        "cenarios": cenarios(reviews),
        "decisoes": decisoes(rd),
        "exemplo_mars": exemplo_mars(daily, hotels),
        "relacoes": relacoes({"hotels": hotels, "room_types": ler("room_types"), "daily_market": daily,
                              "weekly_performance": ler("weekly_performance"), "rate_decisions": rd,
                              "reviews": reviews, "review_scenarios": sc}),
        "interativo": extras_interativos(daily, ler("weekly_performance"), reviews),
        "tabelas": tabelas_info({"hotels": hotels, "room_types": ler("room_types"), "daily_market": daily,
                                 "weekly_performance": ler("weekly_performance"), "rate_decisions": rd,
                                 "reviews": reviews, "review_scenarios": sc}),
    }
    texto = json.dumps(pacote, ensure_ascii=False, separators=(",", ":"))
    SAIDA.write_text(
        "// Gerado por scripts/gerar_dados_dashboard.py. Não edite à mão.\n"
        f"window.DADOS = {texto};\n",
        encoding="utf-8",
    )
    print(f"OK: {SAIDA} ({SAIDA.stat().st_size / 1024:.0f} KB)")
    print(f"Imagens copiadas para dashboard/img: {copiar_imagens()} "
          "(rode antes analise/analise_hoteis.py e banco/diagrama_er.py)")

    # Valores de conferência (o painel deve mostrar os mesmos, sem filtro)
    disp, vend, rec = daily["rooms_available"].sum(), daily["rooms_sold"].sum(), daily["room_revenue"].sum()
    print(f"Receita total: {(daily['room_revenue'] + daily['ancillary_revenue']).sum():,.0f}")
    print(f"Ocupação: {vend / disp:.1%} | ADR: {rec / vend:,.2f} | RevPAR: {rec / disp:,.2f}")
    print(f"Nota média: {reviews['rating'].mean():.2f}")


if __name__ == "__main__":
    main()
