"""Caminhos, conexão DuckDB e visões compartilhadas pelos scripts de análise."""
import os
from pathlib import Path

import duckdb

# pasta onde ficam zips/, extraidos/, dados/ e resultados/ (padrão: a raiz do repositório)
RAIZ = Path(os.environ.get("ELEICOES_RAIZ", Path(__file__).resolve().parent.parent))
ZIPS = RAIZ / "zips"
EXTRAIDOS = RAIZ / "extraidos"
DADOS = RAIZ / "dados"
RESULTADOS = RAIZ / "resultados"

URL_DATASET = "https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna"
API_DATASET = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-2026-boletim-de-urna"

# códigos de votável usados na análise de Presidente
LULA, FLAVIO = 13, 22
BRANCO_NULO = (95, 96, 97)

REGIAO_SQL = """
CASE WHEN uf IN ('AC','AM','AP','PA','RO','RR','TO') THEN 'Norte'
     WHEN uf IN ('AL','BA','CE','MA','PB','PE','PI','RN','SE') THEN 'Nordeste'
     WHEN uf IN ('DF','GO','MS','MT') THEN 'Centro-Oeste'
     WHEN uf IN ('ES','MG','RJ','SP') THEN 'Sudeste'
     WHEN uf IN ('PR','RS','SC') THEN 'Sul'
     ELSE 'Exterior' END
"""


def conectar():
    """Abre o DuckDB com as visões:
    - secoes: uma linha por seção/turno, com horário de encerramento em Brasília (enc_hora, hora decimal)
    - votos:  votos por seção/turno/votável (cargo Presidente)
    - sv:     uma linha por seção/turno com Lula, Flávio, válidos, brancos/nulos e total
    """
    con = duckdb.connect()
    con.execute("SET enable_progress_bar=false")
    con.execute(f"CREATE VIEW votos AS SELECT * FROM read_parquet('{DADOS}/votos.parquet')")
    # Fuso: o BU registra hora local. A abertura oficial é 8h de Brasília, então o ajuste de cada
    # município é 8 - (hora de abertura mais comum no município).
    con.execute(f"""
    CREATE VIEW secoes AS
    WITH sec AS (SELECT * FROM read_parquet('{DADOS}/secoes.parquet')),
    moda AS (SELECT uf, cd_mun, mode(hour(abertura)) AS h_abre
             FROM sec WHERE abertura IS NOT NULL GROUP BY ALL)
    SELECT sec.*, 8 - moda.h_abre AS ajuste_h,
           hour(encerramento) + minute(encerramento) / 60 + second(encerramento) / 3600
             + (8 - moda.h_abre) AS enc_hora,
           {REGIAO_SQL} AS regiao
    FROM sec LEFT JOIN moda USING (uf, cd_mun)
    """)
    con.execute(f"""
    CREATE VIEW sv AS
    SELECT turno, uf, cd_mun, zona, secao,
           coalesce(sum(votos) FILTER (WHERE nr_votavel = {LULA}), 0)::BIGINT AS lula,
           coalesce(sum(votos) FILTER (WHERE nr_votavel = {FLAVIO}), 0)::BIGINT AS flavio,
           coalesce(sum(votos) FILTER (WHERE nr_votavel NOT IN {BRANCO_NULO}), 0)::BIGINT AS validos,
           coalesce(sum(votos) FILTER (WHERE nr_votavel IN {BRANCO_NULO}), 0)::BIGINT AS bn,
           sum(votos)::BIGINT AS total
    FROM votos GROUP BY ALL
    """)
    return con


def mostrar(con, titulo, sql, arquivo=None):
    """Imprime uma consulta e, opcionalmente, salva em resultados/<arquivo>.csv."""
    df = con.sql(sql).df()
    print(f"\n=== {titulo} ===")
    print(df.to_string(index=False))
    if arquivo:
        RESULTADOS.mkdir(exist_ok=True)
        df.to_csv(RESULTADOS / f"{arquivo}.csv", index=False)
    return df
