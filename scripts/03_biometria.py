"""Eleitores com biometria cadastrada não habilitados por ela (seção 2 do relatório).

Campo oficial: QT_ELEI_BIOM_SEM_HABILITACAO. Não inclui quem não tem biometria cadastrada.
Uso: python scripts/03_biometria.py
"""
from comum import conectar, mostrar

con = conectar()
PCT = "round(100 * sum(biom_sem_hab) / sum(comparecimento), 2)"

mostrar(con, "Brasil por turno", f"""
SELECT turno, sum(comparecimento)::BIGINT comparecimento, sum(biom_sem_hab)::BIGINT biom_sem_hab, {PCT} pct
FROM secoes GROUP BY 1 ORDER BY 1""", "03_biometria_brasil")

mostrar(con, "Por região e turno", f"""
SELECT regiao, turno, sum(comparecimento)::BIGINT comparecimento, sum(biom_sem_hab)::BIGINT biom_sem_hab, {PCT} pct
FROM secoes GROUP BY ALL ORDER BY 1, 2""", "03_biometria_regiao")

mostrar(con, "Por UF (1º x 2º turno)", """
WITH t AS (SELECT uf, turno, 100 * sum(biom_sem_hab) / sum(comparecimento) p FROM secoes GROUP BY ALL)
SELECT a.uf, round(a.p, 2) pct_1t, round(b.p, 2) pct_2t, round(b.p - a.p, 2) dif
FROM t a JOIN t b ON a.uf = b.uf AND a.turno = 1 AND b.turno = 2 ORDER BY pct_2t DESC""", "03_biometria_uf")

mostrar(con, "Por grupo de horário de fechamento (corte 18h)", f"""
SELECT turno, CASE WHEN enc_hora IS NULL THEN 'sem horário' WHEN enc_hora <= 18 THEN 'até 18h' ELSE 'após 18h' END grupo,
       sum(comparecimento)::BIGINT comparecimento, sum(biom_sem_hab)::BIGINT biom_sem_hab, {PCT} pct
FROM secoes GROUP BY ALL ORDER BY 1, 2""", "03_biometria_horario")
