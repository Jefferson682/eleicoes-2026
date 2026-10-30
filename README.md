# Eleições 2026 – análise dos boletins de urna do TSE

🇧🇷 Português | [🇺🇸 English](README.en.md)

Análise **independente e imparcial** dos boletins de urna (BU) da eleição presidencial de 2026 (1º e 2º turno), feita **exclusivamente com os dados brutos publicados pelo TSE** no [portal de dados abertos](https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna).

- 📄 **Relatório completo (PDF):** [Google Drive](https://drive.google.com/file/d/1lvo6YSrL5hZp1svr5e6W5HquW7BvZeIv/view?usp=sharing)
- 🧮 **Este repositório:** o código da análise e os resultados de referência ([`resultados/`](resultados/)). Os dados são baixados direto do TSE pelo primeiro script.

> **Declaração de independência.** Trabalho feito por iniciativa própria do autor, **sem contrapartida de qualquer natureza** e **sem a intenção de validar ou invalidar o processo eleitoral**. Nenhum dado, notícia ou opinião externa é usado nos cálculos. A única informação externa, citada apenas como contexto (apoios declarados no 2º turno), está sinalizada na seção 6.3 do relatório e no script `05_variacao_turnos.py`.

O objetivo deste repositório é permitir que **qualquer pessoa refaça a análise do zero, confira cada número, ajuste a metodologia e teste outras hipóteses**.

## Requisitos

- Python 3.10 ou superior
- ~45 GB livres em disco: 5,2 GB de zips + 32,4 GB de CSVs + dados intermediários
- 8 GB de RAM ou mais (o DuckDB processa os CSVs sem carregar tudo na memória)
- Conexão com a internet para o download e para a checagem de metadados

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Como rodar

Execute os scripts em ordem, a partir da raiz do repositório:

```bash
python scripts/00_baixar_e_verificar.py   # baixa e confere os 56 arquivos do TSE (~5 GB)
python scripts/01_extrair.py              # monta a base de seções e votos (Presidente)
python scripts/02_horarios.py             # horário de fechamento x resultado
python scripts/03_biometria.py            # eleitores não habilitados por biometria
python scripts/04_repeticoes.py           # empates e placares repetidos x acaso
python scripts/05_variacao_turnos.py      # ganho de votos do 1º para o 2º turno
python scripts/06_metadados.py            # volume, integridade e datas dos arquivos
```

Cada script de análise imprime as tabelas no terminal e salva os mesmos números em `resultados/*.csv`. Os dados (`zips/`, `extraidos/`, `dados/`) ficam dentro da pasta do repositório e são ignorados pelo git. Para usar outra pasta, defina a variável de ambiente `ELEICOES_RAIZ`. Os scripts 02 a 06 levam de segundos a poucos minutos; o 06 leva cerca de 4 minutos porque relê todos os CSVs e consulta o servidor do TSE.

## Resultados de referência

A pasta [`resultados/`](resultados/) traz os CSVs gerados pela execução usada no relatório. Eles servem de gabarito: depois de rodar os scripts, compare a sua saída com a versão do repositório.

```bash
git diff --stat -- resultados/   # nenhuma diferença = mesmos números do relatório
```

As simulações do script 04 usam semente fixa, então os números devem sair idênticos. Os arquivos começam com o número do script que os gera (`02_*.csv` vem de `02_horarios.py`, e assim por diante).

## O que cada script faz

### `comum.py`
Módulo compartilhado. Define os caminhos das pastas, os códigos de votável (Lula = 13, Flávio = 22, brancos/nulos = 95, 96 e 97), a divisão das UFs por região e abre o DuckDB com três visões usadas por todos os scripts:
- **`secoes`**: uma linha por seção e turno, com o horário de encerramento já convertido para Brasília (`enc_hora`, em horas decimais) e a região.
- **`votos`**: votos de Presidente por seção, turno e votável.
- **`sv`**: uma linha por seção e turno com os votos de Lula, de Flávio, os válidos, os brancos/nulos e o total.

**Conversão de fuso:** o BU registra a hora local. Como a abertura oficial é às 8h de Brasília, o ajuste de cada município é `8 − (hora de abertura mais comum no município)`. Com isso, AC e o oeste do AM somam +2h, e MT, MS, RO, RR e o restante do AM somam +1h. No exterior, o horário fica relativo ao previsto (fechamento normal às 17h locais).

### `00_baixar_e_verificar.py`
Consulta a API do portal de dados abertos do TSE, baixa cada `bweb_*.zip` e o `.sha512` correspondente para `zips/`, confere o **SHA-512** de cada arquivo com o publicado pelo TSE, testa a integridade do zip e extrai os CSVs em `extraidos/`. Se o arquivo já existir e estiver íntegro, não baixa de novo. Termina com erro se algum arquivo falhar.

### `01_extrair.py`
Lê os 56 CSVs (codificação Latin-1, separados por `;`), filtra o cargo Presidente e gera dois arquivos Parquet em `dados/`:
- `secoes.parquet`: aptos, comparecimento, abertura, encerramento e eleitores não habilitados por biometria de cada seção.
- `votos.parquet`: votos por seção, turno e votável.

### `02_horarios.py` – seções 3 e 4 do relatório
- Resultado de Lula e Flávio nas seções fechadas até/após **18h** e até/após **17h10**.
- Faixas de **15 minutos** a partir das 17h, com o resultado de cada faixa, o peso nos votos válidos e o acumulado.
- **Teste de limite:** o resultado se todos os votos das urnas fechadas após 17h15 fossem para um só candidato.
- **Controle por zona eleitoral:** compara cada seção que fechou tarde com as seções da mesma zona que fecharam até 17h15, para separar o efeito do lugar do efeito do horário.
- As mesmas seções nos dois turnos, a distribuição por região, UF e município, e os encerramentos minuto a minuto em torno das 19h no 2º turno.

### `03_biometria.py` – seção 2 do relatório
Soma o campo oficial `QT_ELEI_BIOM_SEM_HABILITACAO` (eleitores com biometria cadastrada que não foram habilitados por ela) por turno, região, UF e grupo de horário de fechamento.

### `04_repeticoes.py` – seção 5 do relatório
Compara o observado com o **esperado por acaso**. Para isso simula novas eleições em que cada seção vota aleatoriamente com as proporções da sua zona eleitoral (binomial para Lula × Flávio, multinomial para o resultado completo), com **semente fixa** para que os números sejam reproduzíveis. Calcula:
- empates Lula = Flávio (total, por UF e esperado);
- placares Lula × Flávio repetidos no país, no estado e na mesma zona;
- seções com resultado completo idêntico (todos os votáveis).

### `05_variacao_turnos.py` – seção 6 do relatório
- **Fatos:** ganho de votos de cada candidato por região e as três fontes líquidas de votos novos (votos dos outros candidatos do 1º turno, aumento do comparecimento e redução de brancos/nulos), com a verificação de que a conta fecha seção a seção.
- **Seção a seção:** seções em que o ganho de um candidato só se explica com eleitores do outro candidato trocando de voto, e o tamanho desse excedente.
- **Estimativa estatística** (o voto é secreto): regressão ecológica seção a seção, feita estado por estado, com frações entre 0 e 1. Também imprime versões alternativas (sem restrição e modelo nacional único) para mostrar a robustez e o modelo descartado.
- A lista de candidatos que declararam apoio a Flávio no 2º turno é **contexto externo**, marcada no código. Ela só separa os grupos numa estimativa exploratória e não entra no relatório como resultado.

### `06_metadados.py` – volume de dados e seção 7 do relatório
- Tamanho dos zips e dos CSVs e número de linhas por turno.
- Para cada zip: SHA-512 local, comparação com o `.sha512` publicado **hoje** pelo TSE, data interna do CSV e `Last-Modified` no servidor do TSE.
- Datas registradas dentro dos CSVs: extração (`DT_GERACAO`), carga das urnas, emissão e recebimento dos boletins.
- Use `--sem-rede` para rodar sem consultar o servidor do TSE.

## Limites da análise

- O boletim de urna traz só os **totais de cada seção**. Não existe horário de cada voto, então não dá para saber quantas pessoas votaram depois das 17h, nem em quem votaram.
- A verificação de integridade prova que os arquivos **não mudaram depois de publicados** pelo TSE. Ela não prova que o conteúdo publicado corresponde ao que cada urna registrou. Isso exige conferir os boletins originais assinados digitalmente.
- As estimativas de origem dos votos (seção 6.4 do relatório) são **regressões ecológicas**, ou seja, tendências entre seções, não contagens.
- **Este trabalho não comprova nem descarta fraude.**

## Licença

- **Código:** [MIT](LICENSE).
- **Resultados e relatório (PDF):** [CC BY 4.0](LICENSE-CONTENT.md).

O uso é livre, **inclusive comercial**, desde que o autor seja citado:

> José Jefferson Nascimento do Vale (dev-nordestino). *Eleições 2026 – análise dos boletins de urna do TSE.* https://github.com/Jefferson682/eleicoes-2026

Os dados brutos pertencem ao Tribunal Superior Eleitoral (TSE).

## Autor

**José Jefferson Nascimento do Vale** · dev-nordestino
