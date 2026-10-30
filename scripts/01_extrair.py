"""Lê todos os CSVs de BU (cargo Presidente) e gera:
- dados/secoes.parquet: uma linha por seção/turno (horários, comparecimento, biometria)
- dados/votos.parquet:  votos por seção/turno/votável

Uso: python scripts/01_extrair.py
"""
import duckdb

from comum import DADOS, EXTRAIDOS

DADOS.mkdir(exist_ok=True)
con = duckdb.connect()
con.execute("SET threads TO 6; SET memory_limit='10GB'; SET preserve_insertion_order=false; SET enable_progress_bar=false;")

con.execute(f"""
CREATE TABLE pres AS
SELECT CAST(NR_TURNO AS INT) AS turno, SG_UF AS uf, CAST(CD_MUNICIPIO AS INT) AS cd_mun, NM_MUNICIPIO AS nm_mun,
       CAST(NR_ZONA AS INT) AS zona, CAST(NR_SECAO AS INT) AS secao,
       CAST(QT_APTOS AS INT) AS aptos, CAST(QT_COMPARECIMENTO AS INT) AS comparecimento,
       TRY_CAST(DT_ABERTURA AS TIMESTAMP) AS abertura, TRY_CAST(DT_ENCERRAMENTO AS TIMESTAMP) AS encerramento,
       CAST(QT_ELEI_BIOM_SEM_HABILITACAO AS INT) AS biom_sem_hab,
       CAST(NR_VOTAVEL AS INT) AS nr_votavel, NM_VOTAVEL AS nm_votavel, CAST(QT_VOTOS AS INT) AS votos
FROM read_csv('{EXTRAIDOS}/bweb_*.csv', delim=';', quote='"', header=true, encoding='latin-1', all_varchar=true)
WHERE CD_CARGO_PERGUNTA = '1'
""")
chave = "turno, uf, cd_mun, nm_mun, zona, secao"
con.execute(f"""
COPY (SELECT {chave}, max(aptos) aptos, max(comparecimento) comparecimento,
             min(abertura) abertura, max(encerramento) encerramento, max(biom_sem_hab) biom_sem_hab
      FROM pres GROUP BY {chave})
TO '{DADOS}/secoes.parquet' (FORMAT parquet)""")
con.execute(f"""
COPY (SELECT turno, uf, cd_mun, zona, secao, nr_votavel, any_value(nm_votavel) nm_votavel, sum(votos) votos
      FROM pres GROUP BY ALL)
TO '{DADOS}/votos.parquet' (FORMAT parquet)""")
print(con.execute(f"""SELECT turno, count(*) secoes, sum(comparecimento) comparecimento
                      FROM read_parquet('{DADOS}/secoes.parquet') GROUP BY 1 ORDER BY 1""").df().to_string(index=False))
