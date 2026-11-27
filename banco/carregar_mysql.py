"""
Carrega os 7 arquivos JSONL no MySQL, seguindo o modelo de banco/modelo_mysql.sql.

Pré-requisitos:
    pip install pandas mysql-connector-python
    MySQL 8 rodando (por exemplo, o MySQL Installer + Workbench no Windows).

Como rodar (a partir da pasta trabalho-final/):
    python banco/carregar_mysql.py

Usuário e senha: edite CONFIG abaixo ou use as variáveis de ambiente
MYSQL_HOST, MYSQL_PORT, MYSQL_USER e MYSQL_PASSWORD.

O script:
  1. executa modelo_mysql.sql (apaga e recria o banco nice_rooms);
  2. prepara cada DataFrame (tira colunas redundantes, separa amenities,
     troca texto vazio por NULL, converte datas);
  3. insere tudo com executemany (em lotes);
  4. confere se o número de linhas no banco bate com o dos arquivos.
"""
import os
from pathlib import Path

import mysql.connector
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
MODELO = Path(__file__).resolve().parent / "modelo_mysql.sql"

CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "sua_senha_aqui"),
}


def ler(nome: str) -> pd.DataFrame:
    return pd.read_json(DADOS / f"{nome}.jsonl", lines=True)


def vazio_para_nulo(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Texto vazio vira NULL: no banco, 'sem evento' e 'sem resposta' ficam explícitos."""
    for c in colunas:
        df[c] = df[c].where(df[c].astype(str).str.strip() != "", None)
    return df


def preparar() -> dict[str, pd.DataFrame]:
    h = ler("hotels")
    comodidades = h[["hotel_id", "amenities"]].explode("amenities").rename(columns={"amenities": "comodidade"})
    hoteis = h.drop(columns=["amenities", "review_count", "lifetime_rating", "share_rating_5", "share_rating_1_2"])

    tipos = ler("room_types").drop(columns=["tier"]).rename(columns={"view": "view_type"})
    tipos = tipos[["room_type_id", "hotel_id", "room_type", "rooms", "max_occupancy", "size_sqm",
                   "rate_premium_pct", "bar_rate", "view_type"]]

    diario = ler("daily_market").drop(columns=["hotel_name", "tier", "comp_set", "available_rooms"])
    diario = vazio_para_nulo(diario, ["demand_event"])

    semanal = ler("weekly_performance").drop(columns=["hotel_name", "tier", "comp_set"])
    semanal = vazio_para_nulo(semanal, ["demand_event"])

    decisoes = vazio_para_nulo(ler("rate_decisions"), ["demand_event"])

    cenarios = ler("review_scenarios").rename(columns={"trigger": "trigger_desc"})

    aval = vazio_para_nulo(ler("reviews"), ["response_text"])

    # Ordem importa: tabelas "pai" antes das "filhas" (chaves estrangeiras)
    return {
        "hoteis": hoteis, "hotel_comodidades": comodidades, "tipos_quarto": tipos,
        "mercado_diario": diario, "desempenho_semanal": semanal, "decisoes_preco": decisoes,
        "cenarios_avaliacao": cenarios, "avaliacoes": aval,
    }


def para_python(v):
    """Converte valores do pandas/numpy para tipos que o conector aceita."""
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NaT:
        return None
    if isinstance(v, pd.Timestamp):
        return v.date()
    if hasattr(v, "item"):  # numpy int64, float64, bool_
        return v.item()
    return v


def inserir(cursor, tabela: str, df: pd.DataFrame, lote: int = 1000) -> None:
    for c in df.columns:
        if "date" in c or c == "week_start":
            df[c] = pd.to_datetime(df[c])
    colunas = ", ".join(f"`{c}`" for c in df.columns)
    marcadores = ", ".join(["%s"] * len(df.columns))
    sql = f"INSERT INTO {tabela} ({colunas}) VALUES ({marcadores})"
    linhas = [tuple(para_python(v) for v in lin) for lin in df.itertuples(index=False, name=None)]
    for i in range(0, len(linhas), lote):
        cursor.executemany(sql, linhas[i:i + lote])


def main() -> None:
    conexao = mysql.connector.connect(**CONFIG)
    cursor = conexao.cursor()

    print("1. Criando o banco nice_rooms a partir de modelo_mysql.sql ...")
    script = MODELO.read_text(encoding="utf-8")
    comandos = [c.strip() for c in "\n".join(
        l for l in script.splitlines() if not l.strip().startswith("--")).split(";") if c.strip()]
    for comando in comandos:
        cursor.execute(comando)

    print("2. Preparando os dados ...")
    tabelas = preparar()

    print("3. Inserindo ...")
    for nome, df in tabelas.items():
        inserir(cursor, nome, df)
        conexao.commit()
        print(f"   {nome:<20} {len(df):>6} linhas")

    print("4. Conferindo contagens no banco ...")
    tudo_ok = True
    for nome, df in tabelas.items():
        cursor.execute(f"SELECT COUNT(*) FROM {nome}")
        n = cursor.fetchone()[0]
        ok = n == len(df)
        tudo_ok &= ok
        print(f"   {nome:<20} arquivo={len(df):>6}  banco={n:>6}  {'OK' if ok else 'DIFERENTE!'}")

    cursor.close()
    conexao.close()
    print("\nCarga concluída com sucesso." if tudo_ok else "\nAtenção: alguma contagem não bateu.")


if __name__ == "__main__":
    main()
