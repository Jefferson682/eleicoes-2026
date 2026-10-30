"""Empates Lula = Flávio e placares repetidos entre seções, comparados com o esperado por acaso
(seção 5 do relatório).

Esperado por acaso: novas eleições simuladas em que cada seção vota aleatoriamente com as
proporções da sua zona eleitoral (binomial para Lula x Flávio; multinomial para o resultado completo).
A semente é fixa para que os números sejam reproduzíveis.
Uso: python scripts/04_repeticoes.py
"""
import numpy as np
import pandas as pd
from scipy.stats import binom

from comum import RESULTADOS, conectar

SEMENTE = 42
N_SIM = 10          # simulações para placares Lula x Flávio
N_SIM_VETOR = 5     # simulações para o resultado completo (mais pesadas)
rng = np.random.default_rng(SEMENTE)
con = conectar()

df = con.sql("""
SELECT turno, uf, cd_mun, zona, secao, lula, flavio,
       sum(lula) OVER z / nullif(sum(lula + flavio) OVER z, 0) AS p_zona
FROM sv WINDOW z AS (PARTITION BY turno, uf, cd_mun, zona) ORDER BY turno, uf, cd_mun, zona, secao""").df()
df["p_zona"] = df["p_zona"].fillna(0.5)
resumo, linhas_uf = [], []


def faixa(v):
    return f"{min(v):,} – {max(v):,}"


for t in (1, 2):
    x = df[df.turno == t].reset_index(drop=True)
    n = (x.lula + x.flavio).to_numpy()
    p = x.p_zona.to_numpy()
    r = {"turno": t, "secoes": len(x)}

    # 5.1 empates
    emp = (x.lula == x.flavio).to_numpy()
    esp_emp = np.where(n % 2 == 0, binom.pmf(n // 2, n, p), 0)
    r |= {"empates": int(emp.sum()), "empates_pct": round(100 * emp.mean(), 2),
          "empates_esperado": round(esp_emp.sum()), "empates_0x0": int(((x.lula == 0) & (x.flavio == 0)).sum()),
          "empates_mais_comuns": x[emp].lula.value_counts().head(3).to_dict()}

    # 5.2 placares repetidos
    def rep_pais(a, b):
        s = np.unique(np.stack([a, b], 1), axis=0, return_counts=True)[1]
        return int(s[s > 1].sum()), int(s.max())

    def rep_uf(a, b):
        k = x.assign(a=a, b=b).groupby(["uf", "a", "b"])["a"].transform("size")
        return (k > 1).to_numpy()

    def rep_zona(a, b):
        s = x[["uf", "cd_mun", "zona"]].assign(a=a, b=b).groupby(["uf", "cd_mun", "zona", "a", "b"]).size()
        return int(s[s > 1].sum())

    pares = x.groupby(["lula", "flavio"]).size()
    obs_pais, obs_max = rep_pais(x.lula.to_numpy(), x.flavio.to_numpy())
    obs_uf = rep_uf(x.lula, x.flavio)
    sim_pais, sim_max, sim_uf, sim_zona = [], [], [], []
    for _ in range(N_SIM):
        sl = rng.binomial(n, p)
        a, m = rep_pais(sl, n - sl)
        sim_pais.append(a)
        sim_max.append(m)
        sim_uf.append(rep_uf(sl, n - sl))
        sim_zona.append(rep_zona(sl, n - sl))
    esp_uf = np.mean(sim_uf, axis=0)
    r |= {"placares_distintos": len(pares), "media_secoes_por_placar": round(len(x) / len(pares), 1),
          "mediana_entre_repetidos": float(pares[pares > 1].median()),
          "placar_mais_repetido": f"{pares.idxmax()[0]}x{pares.idxmax()[1]}", "maior_repeticao": obs_max,
          "maior_repeticao_esperada": faixa(sim_max),
          "compartilham_placar_pais": obs_pais, "compartilham_esperado": faixa(sim_pais),
          "repetidas_uf": int(obs_uf.sum()), "repetidas_uf_pct": round(100 * obs_uf.mean(), 1),
          "repetidas_uf_esperado_pct": round(100 * esp_uf.mean(), 1),
          "mesma_zona": rep_zona(x.lula, x.flavio), "mesma_zona_esperado": faixa(sim_zona)}

    xu = x.assign(emp=emp, emp_esp=esp_emp, rep=obs_uf, rep_esp=esp_uf)
    g = xu.groupby("uf").agg(secoes=("secao", "size"), empates=("emp", "sum"), empates_esp=("emp_esp", "sum"),
                             repetidas=("rep", "sum"), repetidas_esp=("rep_esp", "sum"))
    g["empates_pct"] = (100 * g.empates / g.secoes).round(2)
    g["repetidas_pct"] = (100 * g.repetidas / g.secoes).round(1)
    g["repetidas_esp_pct"] = (100 * g.repetidas_esp / g.secoes).round(1)
    # placar mais repetido na UF (em empate de contagem, o menor placar Lula)
    top = (x.groupby(["uf", "lula", "flavio"]).size().rename("k").reset_index()
             .sort_values(["uf", "k", "lula", "flavio"], ascending=[True, False, True, True])
             .groupby("uf").head(1).set_index("uf"))
    g = g.join(top.rename(columns={"lula": "top_lula", "flavio": "top_flavio", "k": "top_secoes"}))
    g.insert(0, "turno", t)
    linhas_uf.append(g.reset_index())

    # 5.3 resultado completo idêntico (todos os votáveis), seções com >= 50 votos
    w = con.sql(f"""PIVOT (SELECT uf, cd_mun, zona, secao, nr_votavel, votos FROM votos WHERE turno = {t})
                    ON nr_votavel USING sum(votos) GROUP BY uf, cd_mun, zona, secao
                    ORDER BY uf, cd_mun, zona, secao""").df().fillna(0)
    cols = [c for c in w.columns if c not in ("uf", "cd_mun", "zona", "secao")]
    m = w[cols].to_numpy(dtype=np.int64)
    keep = m.sum(1) >= 50
    w, m = w[keep].reset_index(drop=True), m[keep]
    zona = w.groupby(["uf", "cd_mun", "zona"]).ngroup().to_numpy()

    def dup(mat):
        _, cnt = np.unique(mat, axis=0, return_counts=True)
        return int(cnt[cnt > 1].sum()), int(cnt.max())

    tot = pd.DataFrame(m).groupby(zona).sum().to_numpy()
    pz = tot[zona] / tot[zona].sum(1, keepdims=True)
    sv_, sm_, sz_ = [], [], []
    for _ in range(N_SIM_VETOR):
        sim = rng.multinomial(m.sum(1), pz)
        a, b = dup(sim)
        sv_.append(a)
        sm_.append(b)
        sz_.append(dup(np.column_stack([zona, sim]))[0])
    obs_v, obs_vm = dup(m)
    r |= {"votaveis": len(cols), "secoes_50mais": len(m), "vetor_identico": obs_v, "vetor_maior_grupo": obs_vm,
          "vetor_esperado": faixa(sv_), "vetor_maior_grupo_esperado": faixa(sm_),
          "vetor_mesma_zona": dup(np.column_stack([zona, m]))[0], "vetor_mesma_zona_esperado": faixa(sz_)}
    resumo.append(r)

RESULTADOS.mkdir(exist_ok=True)
res = pd.DataFrame(resumo).set_index("turno").T
res.to_csv(RESULTADOS / "04_repeticoes_resumo.csv")
print("=== Resumo (seções 5.1 a 5.3) ===")
print(res.to_string())
uf = pd.concat(linhas_uf)
uf.to_csv(RESULTADOS / "04_repeticoes_uf.csv", index=False)
print("\n=== Por UF ===")
print(uf.to_string(index=False))
