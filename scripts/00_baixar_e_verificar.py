"""Baixa os boletins de urna (bweb_*.zip) e os .sha512 do portal de dados abertos do TSE,
confere o SHA-512 de cada arquivo e extrai os CSVs em extraidos/.

Uso: python scripts/00_baixar_e_verificar.py
"""
import hashlib
import json
import sys
import urllib.request
import zipfile

from comum import API_DATASET, EXTRAIDOS, ZIPS


def sha512(caminho):
    h = hashlib.sha512()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def baixar(url, destino):
    tmp = destino.with_suffix(destino.suffix + ".part")
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        while bloco := r.read(1 << 20):
            f.write(bloco)
    tmp.rename(destino)


def main():
    ZIPS.mkdir(exist_ok=True)
    EXTRAIDOS.mkdir(exist_ok=True)
    with urllib.request.urlopen(API_DATASET) as r:
        pacote = json.load(r)
    urls = sorted({res["url"] for res in pacote["result"]["resources"] if "/bweb_" in res["url"]})
    zips = [u for u in urls if u.endswith(".zip")]
    shas = {u[:-len(".sha512")]: u for u in urls if u.endswith(".zip.sha512")}
    # o catálogo pode listar só o .sha512 de algum arquivo: o .zip fica no mesmo endereço
    zips = sorted(set(zips) | set(shas))

    falhas = []
    for url in zips:
        nome = url.rsplit("/", 1)[1]
        arq, arq_sha = ZIPS / nome, ZIPS / (nome + ".sha512")
        if url in shas and not arq_sha.exists():
            baixar(shas[url], arq_sha)
        esperado = arq_sha.read_text().split()[0] if arq_sha.exists() else None
        if not arq.exists() or (esperado and sha512(arq) != esperado):
            print(f"baixando {nome}")
            baixar(url, arq)
        ok = esperado is not None and sha512(arq) == esperado
        try:
            with zipfile.ZipFile(arq) as z:
                integro = z.testzip() is None
                pendentes = [i for i in z.infolist()
                             if not (EXTRAIDOS / i.filename).exists()
                             or (EXTRAIDOS / i.filename).stat().st_size != i.file_size]
                if ok and integro and pendentes:
                    z.extractall(EXTRAIDOS, members=pendentes)
        except zipfile.BadZipFile:
            integro = False
        print(f"{nome}: SHA-512 {'OK' if ok else 'FALHA'} | zip {'OK' if integro else 'FALHA'}")
        if not (ok and integro):
            falhas.append(nome)

    print(f"\n{len(zips) - len(falhas)}/{len(zips)} arquivos íntegros")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
