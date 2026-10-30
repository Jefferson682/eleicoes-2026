# Brazil 2026 elections – analysis of the TSE ballot box reports

[🇧🇷 Português](README.md) | 🇺🇸 English

An **independent and impartial** analysis of the ballot box reports (*boletins de urna*, BU) from Brazil's 2026 presidential election (1st and 2nd round). It uses **only the raw data published by the TSE** (Brazil's Superior Electoral Court) on its [open data portal](https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna).

- 📄 **Full report (PDF, Portuguese):** [Google Drive](https://drive.google.com/file/d/1lvo6YSrL5hZp1svr5e6W5HquW7BvZeIv/view?usp=sharing)
- 🧮 **This repository:** only the analysis code. The data is downloaded straight from the TSE by the first script.

> **Statement of independence.** This work was done on the author's own initiative, **with no compensation of any kind** and **with no intention of validating or invalidating the electoral process**. No external data, news or opinion is used in any calculation. The only external information, cited as context (endorsements declared before the 2nd round), is flagged in section 6.3 of the report and in `05_variacao_turnos.py`.

The goal of this repository is to let **anyone redo the analysis from scratch, check every number, adjust the methodology and test other hypotheses**.

## Requirements

- Python 3.10 or newer
- ~45 GB of free disk space: 5.2 GB of zips + 32.4 GB of CSVs + intermediate data
- 8 GB of RAM or more (DuckDB processes the CSVs without loading everything into memory)
- Internet access for the download and the metadata checks

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## How to run

Run the scripts in order, from the repository root:

```bash
python scripts/00_baixar_e_verificar.py   # downloads and verifies the 56 TSE files (~5 GB)
python scripts/01_extrair.py              # builds the section and vote tables (President)
python scripts/02_horarios.py             # closing time x result
python scripts/03_biometria.py            # voters not authenticated by biometrics
python scripts/04_repeticoes.py           # ties and repeated counts x chance
python scripts/05_variacao_turnos.py      # vote gains from the 1st to the 2nd round
python scripts/06_metadados.py            # file size, integrity and dates
```

Each analysis script prints its tables to the terminal and saves the same numbers to `resultados/*.csv`. The data (`zips/`, `extraidos/`, `dados/`) and the outputs (`resultados/`) live inside the repository folder and are ignored by git. To use another folder, set the `ELEICOES_RAIZ` environment variable. Scripts 02 to 06 take from seconds to a few minutes; 06 takes about 4 minutes because it re-reads every CSV and queries the TSE server.

## What each script does

### `comum.py`
Shared module. It defines the folder paths, the candidate codes (Lula = 13, Flávio = 22, blank/null = 95, 96 and 97) and the state-to-region mapping. It also opens DuckDB with three views used by every script:
- **`secoes`**: one row per section and round, with the closing time already converted to Brasília time (`enc_hora`, decimal hours) and the region.
- **`votos`**: presidential votes per section, round and candidate.
- **`sv`**: one row per section and round with Lula's and Flávio's votes, valid votes, blank/null votes and the total.

**Time zone conversion:** the BU records local time. Polls officially open at 8 a.m. Brasília time, so each municipality is shifted by `8 − (its most common opening hour)`. That adds +2h for Acre and western Amazonas, and +1h for MT, MS, RO, RR and the rest of Amazonas. Abroad, the time stays relative to the schedule (normal closing at 5 p.m. local time).

### `00_baixar_e_verificar.py`
Queries the TSE open data API, downloads every `bweb_*.zip` and its `.sha512` into `zips/`, checks each file's **SHA-512** against the one published by the TSE, tests the zip integrity and extracts the CSVs into `extraidos/`. Files that already exist and pass the check are not downloaded again. Exits with an error if any file fails.

### `01_extrair.py`
Reads the 56 CSVs (Latin-1, `;`-separated), keeps only the presidential race and writes two Parquet files to `dados/`:
- `secoes.parquet`: eligible voters, turnout, opening and closing times, and voters not authenticated by biometrics for each section.
- `votos.parquet`: votes per section, round and candidate.

### `02_horarios.py` – report sections 3 and 4
- Lula's and Flávio's results in sections closed before/after **6 p.m.** and before/after **5:10 p.m.**
- **15-minute bands** from 5 p.m., with the result of each band, its share of valid votes and the cumulative result.
- **Bound test:** the result if every vote from polls closed after 5:15 p.m. went to a single candidate.
- **Electoral-zone control:** compares each late-closing section with sections in the same zone that closed by 5:15 p.m., to separate the effect of location from the effect of time.
- The same sections across both rounds, breakdowns by region, state and municipality, and minute-by-minute closings around 7 p.m. in the 2nd round.

### `03_biometria.py` – report section 2
Sums the official field `QT_ELEI_BIOM_SEM_HABILITACAO` (voters with registered biometrics who were not authenticated by them) by round, region, state and closing-time group.

### `04_repeticoes.py` – report section 5
Compares what was observed with **what chance alone would produce**. It simulates new elections in which each section votes at random using its electoral zone's proportions (binomial for Lula × Flávio, multinomial for the full result), with a **fixed seed** so the numbers are reproducible. It computes:
- Lula = Flávio ties (total, by state and expected);
- repeated Lula × Flávio counts nationwide, within each state and within the same zone;
- sections with an identical full result (every candidate).

### `05_variacao_turnos.py` – report section 6
- **Facts:** each candidate's vote gain by region and the three net sources of new votes (votes for other 1st-round candidates, higher turnout and fewer blank/null votes), checking that the arithmetic holds section by section.
- **Section by section:** sections where a candidate's gain can only be explained by voters switching from the other candidate, and the size of that excess.
- **Statistical estimate** (the ballot is secret): an ecological regression across sections, fitted state by state, with fractions bounded between 0 and 1. It also prints alternative versions (unbounded, and a single national model) to show robustness and the discarded model.
- The list of candidates who endorsed Flávio for the 2nd round is **external context**, flagged in the code. It only splits the groups in an exploratory estimate and is not reported as a result.

### `06_metadados.py` – data volume and report section 7
- Size of the zips and CSVs and the number of rows per round.
- For every zip: local SHA-512, comparison with the `.sha512` the TSE publishes **today**, the CSV's internal timestamp and the `Last-Modified` header on the TSE server.
- Dates recorded inside the CSVs: extraction (`DT_GERACAO`), voting machine setup, and BU issue and receipt.
- Use `--sem-rede` to skip the TSE server checks.

## Limitations

- A BU only contains **section totals**. There is no timestamp per vote, so it is impossible to know how many people voted after 5 p.m., or whom they voted for.
- The integrity checks prove the files **did not change after the TSE published them**. They do not prove the published content matches what each voting machine recorded. That requires checking the original, digitally signed ballot box reports.
- The vote-origin estimates (report section 6.4) are **ecological regressions**: trends across sections, not counts.
- **This work neither proves nor rules out fraud.**

## License

- **Code:** [MIT](LICENSE).
- **Report (PDF):** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

Free to use, **including commercially**, as long as the author is credited:

> José Jefferson Nascimento do Vale (dev-nordestino). *Eleições 2026 – análise dos boletins de urna do TSE.* https://github.com/Jefferson682/eleicoes-2026

The raw data belongs to Brazil's Superior Electoral Court (TSE).

## Author

**José Jefferson Nascimento do Vale** · dev-nordestino
