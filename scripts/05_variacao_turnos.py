"""Variação de votos do 1º para o 2º turno (seção 6 do relatório).

Parte 1 (fatos): ganho de cada candidato e as três fontes líquidas de votos novos.
Parte 2 (estimativa): de onde provavelmente veio o ganho de cada um. O voto é secreto; é uma
regressão ecológica seção a seção, feita estado por estado, com frações entre 0 e 1.
Uso: python scripts/05_variacao_turnos.py
"""
import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear

from comum import BRANCO_NULO, FLAVIO, LULA, RESULTADOS, conectar, mostrar

# CONTEXTO EXTERNO (não vem dos dados do TSE): candidatos do 1º turno que declararam apoio a
# Flávio Bolsonaro no 2º turno, segundo a imprensa (ver relatório): Augusto Cury (70),
# Ronaldo Caiado (55) e Romeu Zema (30). Renan Santos (14) liberou os eleitores.
APOIO_FLAVIO = (70, 55, 30)
LIBEROU = (14,)

con = conectar()
# só seções presentes nos dois turnos (uma seção do exterior existe apenas no 1º turno)
mostrar(con, "Ganho por região (seções presentes nos dois turnos)", """
WITH par AS (SELECT uf, cd_mun, zona, secao FROM sv GROUP BY ALL HAVING count(DISTINCT turno) = 2),
r AS (SELECT s.regiao, v.turno, sum(v.lula) l, sum(v.flavio) f
      FROM sv v JOIN par USING (uf, cd_mun, zona, secao)
      JOIN secoes s USING (turno, uf, cd_mun, zona, secao) GROUP BY ALL)
SELECT a.regiao, a.l lula_1t, b.l lula_2t, b.l - a.l ganho_lula, round(100 * (b.l / a.l - 1), 1) pct_lula,
       a.f flavio_1t, b.f flavio_2t, b.f - a.f ganho_flavio, round(100 * (b.f / a.f - 1), 1) pct_flavio
FROM r a JOIN r b ON a.regiao = b.regiao AND a.turno = 1 AND b.turno = 2
UNION ALL
SELECT 'Brasil', sum(a.l), sum(b.l), sum(b.l - a.l), round(100 * (sum(b.l) / sum(a.l) - 1), 1),
       sum(a.f), sum(b.f), sum(b.f - a.f), round(100 * (sum(b.f) / sum(a.f) - 1), 1)
FROM r a JOIN r b ON a.regiao = b.regiao AND a.turno = 1 AND b.turno = 2
ORDER BY ganho_lula DESC""", "05_ganho_regiao")

df = con.sql(f"""
WITH v AS (
  SELECT turno, uf, cd_mun, zona, secao,
         coalesce(sum(votos) FILTER (WHERE nr_votavel = {LULA}), 0)::DOUBLE l,
         coalesce(sum(votos) FILTER (WHERE nr_votavel = {FLAVIO}), 0)::DOUBLE f,
         coalesce(sum(votos) FILTER (WHERE nr_votavel IN {BRANCO_NULO}), 0)::DOUBLE bn,
         coalesce(sum(votos) FILTER (WHERE nr_votavel IN {APOIO_FLAVIO}), 0)::DOUBLE apoio,
         coalesce(sum(votos) FILTER (WHERE nr_votavel IN {LIBEROU + (0,)}), 0)::DOUBLE liberou,
         sum(votos)::DOUBLE comp
  FROM votos GROUP BY ALL)
SELECT a.uf, a.l l1, a.f f1, a.bn bn1, a.apoio, a.liberou,
       a.comp - a.l - a.f - a.bn - a.apoio - a.liberou AS demais,
       a.comp - a.l - a.f - a.bn AS outros,
       b.comp - a.comp dc, b.l - a.l dl, b.f - a.f dff, b.bn - a.bn dbn
FROM v a JOIN v b USING (uf, cd_mun, zona, secao) WHERE a.turno = 1 AND b.turno = 2""").df()

mi = lambda v: f"{v / 1e6:,.2f} mi"
G = df.dl.sum() + df.dff.sum()
print("\n=== Fatos ===")
print(f"Ganho Lula {mi(df.dl.sum())} ({100 * df.dl.sum() / G:.1f}% do ganho somado) | "
      f"Flávio {mi(df.dff.sum())} ({100 * df.dff.sum() / G:.1f}%) | total {mi(G)}")
print(f"Fontes líquidas: outros candidatos do 1º turno {mi(df.outros.sum())} | aumento do comparecimento "
      f"{mi(df.dc.sum())} | redução de brancos/nulos {mi(-df.dbn.sum())}")
print(f"Conta fecha em todas as seções: {bool(((df.dl + df.dff) == (df.dc + df.outros - df.dbn)).all())}")
print(f"Outros candidatos: apoio declarado a Flávio {mi(df.apoio.sum())} ({100 * df.apoio.sum() / df.outros.sum():.1f}%) | "
      f"liberou {mi(df.liberou.sum())} | demais {mi(df.demais.sum())}")

print("\n=== Seção a seção ===")
exc_l = df.dl - (df.outros + df.bn1 + df.dc.clip(lower=0))
exc_f = df.dff - (df.outros + df.bn1 + df.dc.clip(lower=0))
print(f"Lula perdeu votos em {(df.dl < 0).sum():,} seções; Flávio em {(df.dff < 0).sum():,}")
print(f"Ganho de Lula maior que todos os votos disponíveis: {(exc_l > 0).sum():,} seções, excedente {exc_l[exc_l > 0].sum():,.0f} votos")
print(f"Ganho de Flávio maior que todos os votos disponíveis: {(exc_f > 0).sum():,} seções, excedente {exc_f[exc_f > 0].sum():,.0f} votos")


def estimar(fontes, restrito=True):
    """Regressão por UF (sem intercepto), agregada pelo peso de cada fonte. Devolve a fração de cada
    fonte que foi para Lula, Flávio e branco/nulo."""
    acc = {(alvo, k): 0.0 for alvo in ("Lula", "Flávio", "Branco/nulo") for k in fontes}
    for _, x in df.groupby("uf"):
        X = x[fontes].to_numpy()
        for alvo, y in (("Lula", x.dl), ("Flávio", x.dff), ("Branco/nulo", x.dbn)):
            if restrito:
                lo = [-1 if (alvo == "Branco/nulo" and k == "bn1") else 0 for k in fontes]
                b = lsq_linear(X, y.to_numpy(), bounds=(lo, [1] * len(fontes))).x
            else:
                b = np.linalg.lstsq(X, y.to_numpy(), rcond=None)[0]
            for k, coef in zip(fontes, b):
                acc[(alvo, k)] += coef * x[k].sum()
    linhas = []
    for k in fontes:
        tot = df[k].sum()
        linhas.append({"fonte": k, "votos_1t_mi": round(tot / 1e6, 2),
                       **{f"{a}_pct": round(100 * acc[(a, k)] / tot) for a in ("Lula", "Flávio")},
                       **{f"{a}_mi": round(acc[(a, k)] / 1e6, 2) for a in ("Lula", "Flávio")}})
    return pd.DataFrame(linhas)


RESULTADOS.mkdir(exist_ok=True)
print("\n=== Estimativa principal: por UF, frações entre 0 e 1 ===")
e = estimar(["outros", "bn1", "dc"])
print(e.to_string(index=False))
print(f"Total estimado: Lula {e.Lula_mi.sum():.2f} mi (real {df.dl.sum() / 1e6:.2f}) | "
      f"Flávio {e.Flávio_mi.sum():.2f} mi (real {df.dff.sum() / 1e6:.2f})")
e.to_csv(RESULTADOS / "05_estimativa_fontes.csv", index=False)

print("\n=== Mesma estimativa separando os candidatos que apoiaram Flávio (contexto externo) ===")
e2 = estimar(["apoio", "liberou", "demais", "bn1", "dc"])
print(e2.to_string(index=False))
e2.to_csv(RESULTADOS / "05_estimativa_apoios.csv", index=False)

print("\n=== Robustez: mesma estimativa sem restrição (permite frações negativas) ===")
print(estimar(["outros", "bn1", "dc"], restrito=False).to_string(index=False))
print(estimar(["apoio", "liberou", "demais", "bn1", "dc"], restrito=False).to_string(index=False))
X = df[["outros", "bn1", "dc"]].to_numpy()
bl = np.linalg.lstsq(X, df.dl.to_numpy(), rcond=None)[0]
bf = np.linalg.lstsq(X, df.dff.to_numpy(), rcond=None)[0]
print("Modelo nacional único, sem restrição (versão anterior do relatório, descartada): "
      f"outros -> Lula {bl[0]:.2f} / Flávio {bf[0]:.2f}; brancos/nulos 1T -> Lula {bl[1]:.2f} / Flávio {bf[1]:.2f}")
