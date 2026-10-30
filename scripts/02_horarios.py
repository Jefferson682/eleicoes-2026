"""Horário de fechamento das urnas x resultado para Presidente (seções 3 e 4 do relatório).

Uso: python scripts/02_horarios.py
"""
from comum import conectar, mostrar

con = conectar()
con.execute("""
CREATE TEMP TABLE x AS
SELECT s.*, v.lula, v.flavio, v.validos,
       CASE WHEN s.enc_hora IS NULL THEN NULL
            WHEN s.enc_hora <= 17 THEN 0 ELSE ceil((s.enc_hora - 17) * 4)::INT END AS faixa
FROM secoes s JOIN sv v USING (turno, uf, cd_mun, zona, secao)
""")
PCT = "round(100 * sum(lula) / sum(validos), 2) AS lula_pct, round(100 * sum(flavio) / sum(validos), 2) AS flavio_pct"

mostrar(con, "Resultado apurado total (todas as seções)", f"""
SELECT turno, count(*) secoes, {PCT}, sum(lula) lula, sum(flavio) flavio, sum(validos) validos
FROM x GROUP BY 1 ORDER BY 1""", "02_total")

for corte, nome in ((18, "18h00"), (17 + 10 / 60, "17h10"), (17.25, "17h15")):
    mostrar(con, f"Resultado por grupo, corte {nome} (Brasília)", f"""
    SELECT turno, CASE WHEN enc_hora <= {corte} THEN 'até {nome}' ELSE 'após {nome}' END AS grupo,
           count(*) secoes, round(100 * count(*) / sum(count(*)) OVER (PARTITION BY turno), 1) pct_secoes,
           {PCT}, sum(lula) lula, sum(flavio) flavio
    FROM x WHERE enc_hora IS NOT NULL GROUP BY 1, 2 ORDER BY 1, 2 DESC""", f"02_corte_{nome}")

for t in (1, 2):
    mostrar(con, f"{t}º turno: faixas de 15 min (faixa k = (17h + (k-1)*15min, 17h + k*15min])", f"""
    WITH f AS (SELECT faixa, count(*) secoes, sum(lula) lula, sum(flavio) flavio, sum(validos) validos
               FROM x WHERE turno = {t} AND faixa IS NOT NULL GROUP BY 1)
    SELECT faixa,
           strftime(TIMESTAMP '2000-01-01 17:00' + to_minutes(((faixa - 1) * 15)::BIGINT), '%Hh%M') || '-' ||
           strftime(TIMESTAMP '2000-01-01 17:00' + to_minutes((faixa * 15)::BIGINT), '%Hh%M') AS intervalo,
           secoes, round(100 * validos / sum(validos) OVER (), 2) peso_pct,
           round(100 * lula / validos, 2) lula_pct, round(100 * flavio / validos, 2) flavio_pct,
           sum(secoes) OVER w acum_secoes,
           round(100 * sum(lula) OVER w / sum(validos) OVER w, 2) acum_lula_pct,
           round(100 * sum(flavio) OVER w / sum(validos) OVER w, 2) acum_flavio_pct
    FROM f WINDOW w AS (ORDER BY faixa) ORDER BY faixa""", f"02_faixas_15min_{t}t")

mostrar(con, "2º turno: votos válidos por bloco de horário", """
SELECT CASE WHEN enc_hora <= 17.25 THEN '1) fechou até 17h15' WHEN enc_hora <= 18 THEN '2) 17h15-18h'
            WHEN enc_hora <= 19 THEN '3) 18h-19h' ELSE '4) após 19h' END bloco,
       sum(validos) validos, round(100 * sum(validos) / sum(sum(validos)) OVER (), 2) pct
FROM x WHERE turno = 2 AND enc_hora IS NOT NULL GROUP BY 1 ORDER BY 1""", "02_blocos_2t")

mostrar(con, "2º turno: teste de limite (votos após 17h15 todos para um candidato)", """
WITH a AS (SELECT sum(validos) tot, sum(lula) FILTER (WHERE enc_hora <= 17.25) l0,
                  sum(validos) FILTER (WHERE enc_hora > 17.25) resto, sum(lula) lula
           FROM x WHERE turno = 2 AND enc_hora IS NOT NULL)
SELECT round(100 * l0 / tot, 2) todos_para_flavio, round(100 * lula / tot, 2) apurado,
       round(100 * (l0 + resto) / tot, 2) todos_para_lula FROM a""", "02_teste_limite")

# mesmos agrupamentos das tabelas do relatório (3.5 para o 1º turno, 3.6 para o 2º)
GRUPOS = {
    1: "CASE WHEN enc_hora <= 17.25 THEN '1) até 17h15' WHEN enc_hora <= 18 THEN '2) 17h15-18h' "
       "WHEN enc_hora <= 19 THEN '3) 18h-19h' ELSE '4) após 19h' END",
    2: "CASE WHEN enc_hora <= 17.25 THEN '1) até 17h15' WHEN enc_hora <= 17.5 THEN '2) 17h15-17h30' "
       "WHEN enc_hora <= 18 THEN '3) 17h30-18h' ELSE '4) após 18h' END",
}
for t in (1, 2):
    mostrar(con, f"{t}º turno: controle por zona (esperado = seções da mesma zona fechadas até 17h15)", f"""
    WITH z AS (SELECT uf, cd_mun, zona, sum(lula) / sum(validos) ln FROM x
               WHERE turno = {t} AND enc_hora <= 17.25 GROUP BY ALL),
    g AS (SELECT {GRUPOS[t]} g, * FROM x WHERE turno = {t} AND enc_hora IS NOT NULL)
    SELECT g, count(*) secoes, round(100 * sum(lula) / sum(validos), 2) obs,
           round(100 * sum(validos * ln) / sum(validos), 2) esperado_zona,
           round(100 * sum(lula) / sum(validos) - 100 * sum(validos * ln) / sum(validos), 2) dif_pp
    FROM g JOIN z USING (uf, cd_mun, zona) GROUP BY 1 ORDER BY 1""", f"02_controle_zona_{t}t")

mostrar(con, "2º turno: controle por zona, seções após 18h, por UF (>= 50 seções)", """
WITH z AS (SELECT uf, cd_mun, zona, sum(lula) / sum(validos) ln FROM x
           WHERE turno = 2 AND enc_hora <= 18 GROUP BY ALL)
SELECT uf, count(*) secoes, round(100 * sum(lula) / sum(validos), 2) obs,
       round(100 * sum(validos * ln) / sum(validos), 2) esperado_zona,
       round(100 * sum(lula) / sum(validos) - 100 * sum(validos * ln) / sum(validos), 2) dif_pp
FROM x JOIN z USING (uf, cd_mun, zona) WHERE turno = 2 AND enc_hora > 18
GROUP BY 1 HAVING count(*) >= 50 ORDER BY 2 DESC""", "02_controle_zona_uf")

mostrar(con, "Mesmas seções nos dois turnos (Lula entre os dois), pelo fechamento no 2º turno", """
WITH a AS (SELECT uf, cd_mun, zona, secao, lula l1, flavio f1 FROM x WHERE turno = 1),
     b AS (SELECT uf, cd_mun, zona, secao, lula l2, flavio f2,
                  CASE WHEN enc_hora > 18 THEN 'após 18h' ELSE 'até 18h' END grupo FROM x WHERE turno = 2)
SELECT grupo, count(*) secoes, round(100 * sum(l1) / sum(l1 + f1), 2) lula_1t,
       round(100 * sum(l2) / sum(l2 + f2), 2) lula_2t
FROM a JOIN b USING (uf, cd_mun, zona, secao) GROUP BY 1 ORDER BY 1""", "02_mesmas_secoes")

for t in (1, 2):
    mostrar(con, f"{t}º turno: por região", f"""
    SELECT regiao, count(*) secoes,
           count(*) FILTER (WHERE enc_hora > 17.25) apos_1715, round(100 * count(*) FILTER (WHERE enc_hora > 17.25) / count(*), 1) pct_1715,
           count(*) FILTER (WHERE enc_hora > 18) apos_18, round(100 * count(*) FILTER (WHERE enc_hora > 18) / count(*), 1) pct_18
    FROM x WHERE turno = {t} GROUP BY 1 ORDER BY apos_18 DESC""", f"02_regioes_{t}t")
    mostrar(con, f"{t}º turno: por UF", f"""
    SELECT uf, count(*) secoes,
           strftime(TIMESTAMP '2000-01-01' + to_seconds((avg(enc_hora) * 3600)::BIGINT), '%H:%M') media,
           strftime(TIMESTAMP '2000-01-01' + to_seconds((max(enc_hora) * 3600)::BIGINT), '%H:%M') ultima,
           round(100 * count(*) FILTER (WHERE enc_hora > 17.25) / count(*), 1) pct_1715,
           count(*) FILTER (WHERE enc_hora > 18) apos_18, round(100 * count(*) FILTER (WHERE enc_hora > 18) / count(*), 1) pct_18
    FROM x WHERE turno = {t} AND enc_hora IS NOT NULL GROUP BY 1 ORDER BY pct_1715 DESC""", f"02_ufs_{t}t")
    mostrar(con, f"{t}º turno: municípios com mais seções após 18h", f"""
    SELECT uf, nm_mun, count(*) secoes, count(*) FILTER (WHERE enc_hora > 18) apos_18,
           round(100 * count(*) FILTER (WHERE enc_hora > 18) / count(*), 1) pct
    FROM x WHERE turno = {t} GROUP BY ALL ORDER BY apos_18 DESC LIMIT 12""", f"02_municipios_{t}t")

mostrar(con, "2º turno: encerramentos por minuto entre 18h50 e 19h20", """
SELECT strftime(encerramento + to_hours(ajuste_h), '%H:%M') hora, count(*) secoes
FROM x WHERE turno = 2 AND enc_hora BETWEEN 18 + 50 / 60 AND 19 + 20 / 60 GROUP BY 1 ORDER BY 1""", "02_pico_19h")

mostrar(con, "Seções que passaram das 18h no 2º turno e também no 1º", """
WITH a AS (SELECT uf, cd_mun, zona, secao, max(enc_hora) FILTER (WHERE turno = 1) h1,
                  max(enc_hora) FILTER (WHERE turno = 2) h2 FROM x GROUP BY ALL)
SELECT count(*) FILTER (WHERE h2 > 18) tardias_2t, count(*) FILTER (WHERE h2 > 18 AND h1 > 18) tardias_ambos FROM a""",
       "02_tardias_ambos")
