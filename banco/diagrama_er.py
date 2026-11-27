"""Desenha o diagrama Entidade-Relacionamento do banco MySQL (banco/diagrama_er.png).

Como rodar (a partir da pasta trabalho-final/):
    python banco/diagrama_er.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SAIDA = Path(__file__).resolve().parent / "diagrama_er.png"

# Cada tabela: posição (x, y) do canto superior esquerdo e colunas principais.
# PK = chave primária, FK = chave estrangeira. "..." = demais colunas de métricas.
TABELAS = {
    "hoteis": ((0.36, 0.97), ["PK hotel_id", "name, brand, tier", "rooms, comp_set",
                              "positioning_index", "base_rate, neighbourhood"]),
    "hotel_comodidades": ((0.02, 0.97), ["PK,FK hotel_id", "PK comodidade"]),
    "tipos_quarto": ((0.02, 0.66), ["PK room_type_id", "FK hotel_id", "room_type, rooms", "bar_rate, view_type"]),
    "mercado_diario": ((0.70, 0.97), ["PK,FK hotel_id", "PK date", "rooms_sold, adr, revpar",
                                      "rgi, ari, mpi", "mars_rate, rate_action", "... (50 colunas)"]),
    "desempenho_semanal": ((0.36, 0.62), ["PK,FK hotel_id", "PK week_start", "occupancy, adr, revpar",
                                          "rgi, mean_rating", "... (38 colunas)"]),
    "decisoes_preco": ((0.70, 0.52), ["PK decision_id", "FK hotel_id", "FK (hotel_id, week_start)",
                                      "action, outcome", "realised_uplift_pct"]),
    "avaliacoes": ((0.36, 0.32), ["PK review_id", "FK hotel_id", "FK scenario_id",
                                  "FK (hotel_id, week_start)", "rating, notas parciais", "response_hours"]),
    "cenarios_avaliacao": ((0.02, 0.30), ["PK scenario_id", "label, rating_band", "recovery_action"]),
}
LARGURA, ALTURA_LINHA = 0.27, 0.035

# (pai, filho, cardinalidade)
RELACOES = [
    ("hoteis", "hotel_comodidades", "1 : N"),
    ("hoteis", "tipos_quarto", "1 : N"),
    ("hoteis", "mercado_diario", "1 : N"),
    ("hoteis", "desempenho_semanal", "1 : N"),
    ("desempenho_semanal", "decisoes_preco", "1 : 0..1"),
    ("desempenho_semanal", "avaliacoes", "1 : N"),
    ("cenarios_avaliacao", "avaliacoes", "1 : N"),
]


def caixa(nome):
    (x, y), cols = TABELAS[nome]
    h = ALTURA_LINHA * (len(cols) + 1.2)
    return x, y - h, LARGURA, h


def centro(nome):
    x, y, w, h = caixa(nome)
    return x + w / 2, y + h / 2


def main():
    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    for pai, filho, card in RELACOES:
        (x1, y1), (x2, y2) = centro(pai), centro(filho)
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), zorder=1,
                    arrowprops=dict(arrowstyle="-|>", color="#9aa0a6", lw=1.5, shrinkA=60, shrinkB=60))
        ax.text((x1 + x2) / 2, (y1 + y2) / 2, card, fontsize=9, ha="center", zorder=4,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#9aa0a6"))

    for nome, ((x, y), cols) in TABELAS.items():
        bx, by, bw, bh = caixa(nome)
        ax.add_patch(plt.Rectangle((bx, by), bw, bh, fc="white", ec="#257de0", lw=1.5, zorder=2))
        ax.add_patch(plt.Rectangle((bx, y - ALTURA_LINHA * 1.1), bw, ALTURA_LINHA * 1.1,
                                   fc="#257de0", ec="#257de0", zorder=3))
        ax.text(bx + 0.01, y - ALTURA_LINHA * 0.55, nome, color="white", fontweight="bold",
                va="center", fontsize=10, zorder=4)
        for i, c in enumerate(cols):
            chave = c.startswith(("PK", "FK"))
            ax.text(bx + 0.01, y - ALTURA_LINHA * (1.7 + i), c, fontsize=8.5, va="center", zorder=4,
                    fontweight="bold" if chave else "normal", color="#191919" if chave else "#555")

    ax.set_title("Diagrama ER: banco nice_rooms (MySQL)", loc="left", fontweight="bold", fontsize=14)
    ax.text(0, 0.0, "PK = chave primária · FK = chave estrangeira · seta: tabela pai → tabela filha. "
            "hoteis também é pai de decisoes_preco e avaliacoes (FK hotel_id).", fontsize=8.5, color="#555")
    fig.savefig(SAIDA, dpi=130, bbox_inches="tight")
    print(f"Diagrama salvo em {SAIDA}")


if __name__ == "__main__":
    main()
