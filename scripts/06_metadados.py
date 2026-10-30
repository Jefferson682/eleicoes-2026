"""Volume de dados, integridade e metadados dos arquivos (seção "Volume" e seção 7 do relatório).

- confere o SHA-512 de cada zip com o .sha512 local e com o .sha512 publicado hoje pelo TSE
- lê o Last-Modified de cada arquivo no servidor do TSE
- lê as datas internas dos CSVs dentro dos zips
- verifica as datas registradas dentro dos CSVs (geração, emissão e recebimento dos BUs)

Uso: python scripts/06_metadados.py [--sem-rede]
"""
import hashlib
import sys
import urllib.request
import zipfile

import duckdb

from comum import EXTRAIDOS, ZIPS, mostrar

SEM_REDE = "--sem-rede" in sys.argv
CDN = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb/"


def sha512(caminho):
    h = hashlib.sha512()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


zips = sorted(ZIPS.glob("bweb_*.zip"))
print(f"=== Volume ===\nzips: {len(zips)} arquivos, {sum(z.stat().st_size for z in zips) / 1e9:.2f} GB")
csvs = sorted(EXTRAIDOS.glob("bweb_*.csv"))
for t in ("1t", "2t"):
    tam = sum(c.stat().st_size for c in csvs if f"_{t}_" in c.name)
    print(f"CSVs {t}: {tam / 1e9:.2f} GB")
print(f"CSVs total: {sum(c.stat().st_size for c in csvs) / 1e9:.2f} GB")

print("\n=== Integridade e datas por arquivo ===")
falhas = 0
for z in zips:
    esperado = (z.parent / (z.name + ".sha512")).read_text().split()[0]
    ok_local = sha512(z) == esperado
    with zipfile.ZipFile(z) as zf:
        integro = zf.testzip() is None
        csv = next(i for i in zf.infolist() if i.filename.endswith(".csv"))
        data_zip = "%04d-%02d-%02d %02d:%02d" % csv.date_time[:5]
    linha = f"{z.name}: SHA local {'OK' if ok_local else 'FALHA'} | zip {'OK' if integro else 'FALHA'} | CSV interno {data_zip}"
    if not SEM_REDE:
        with urllib.request.urlopen(CDN + z.name + ".sha512") as r:
            ok_tse = r.read().decode().split()[0] == esperado
        req = urllib.request.Request(CDN + z.name, method="HEAD")
        with urllib.request.urlopen(req) as r:
            lm = r.headers.get("Last-Modified")
        linha += f" | .sha512 = TSE hoje: {'SIM' if ok_tse else 'NÃO'} | Last-Modified {lm}"
        ok_local = ok_local and ok_tse
    falhas += not (ok_local and integro)
    print(linha)
print(f"\n{len(zips) - falhas}/{len(zips)} arquivos íntegros")

con = duckdb.connect()
con.execute("SET enable_progress_bar=false")
con.execute(f"""
CREATE TABLE t AS
SELECT regexp_extract(filename, 'bweb_(\\d)t_', 1)::INT turno, SG_UF uf, CD_CARGO_PERGUNTA cargo,
       NR_ZONA zona, NR_SECAO secao, DT_GERACAO || ' ' || HH_GERACAO geracao,
       TRY_CAST(DT_BU_RECEBIDO AS TIMESTAMP) recebido, TRY_CAST(DT_EMISSAO_BU AS TIMESTAMP) emissao,
       TRY_CAST(DT_ENCERRAMENTO AS TIMESTAMP) encerramento, TRY_CAST(DT_CARGA_URNA_EFETIVADA AS TIMESTAMP) carga
FROM read_csv('{EXTRAIDOS}/bweb_*.csv', delim=';', header=true, encoding='latin-1', all_varchar=true, filename=true)
""")
mostrar(con, "Linhas de dados", """
SELECT turno, count(*) linhas, count(*) FILTER (WHERE cargo = '1') linhas_presidente FROM t GROUP BY 1 ORDER BY 1""",
        "06_linhas")
mostrar(con, "Extrações (DT_GERACAO) por turno", """
SELECT turno, geracao, count(DISTINCT uf) ufs FROM t GROUP BY ALL ORDER BY 1, 2""", "06_geracao")
mostrar(con, "Datas dos BUs", """
SELECT turno, max(carga) carga_max, min(emissao) emissao_min, max(emissao) emissao_max,
       min(recebido) recebido_min, max(recebido) recebido_max,
       count(*) FILTER (WHERE emissao < encerramento) emissao_antes_encerramento,
       count(*) FILTER (WHERE recebido::DATE > (SELECT min(encerramento)::DATE FROM t t2 WHERE t2.turno = t.turno) + 1)
         recebido_apos_d1
FROM t GROUP BY 1 ORDER BY 1""", "06_datas_bu")
mostrar(con, "BUs recebidos no dia seguinte à eleição", """
SELECT turno, uf, recebido::DATE dia, count(*) linhas, max(recebido) ultimo FROM t
WHERE recebido::DATE > (SELECT min(encerramento)::DATE FROM t t2 WHERE t2.turno = t.turno)
GROUP BY ALL ORDER BY 1, 2""", "06_recebidos_d1")
mostrar(con, "Seções com BU 'recebido antes de emitido' (cargo Presidente)", """
SELECT turno, uf, count(DISTINCT zona || '-' || secao) secoes FROM t
WHERE cargo = '1' AND recebido < emissao GROUP BY ALL ORDER BY 1, 3 DESC""", "06_recebido_antes_emitido")
