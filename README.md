# AlphaForge

AlphaForge e uma interface Streamlit para montar estrategias, rodar backtests e executar campanhas de mineracao de estrategias com persistencia local ou Supabase.

## O que o projeto entrega

- Builder visual de estrategia com conexao MT5.
- Backtest local para validar a estrategia montada.
- Persistencia de estrategias, versoes, runs, metricas e trades.
- Campanhas de mineracao executadas pela interface ou por CLI.
- Backend local em arquivo por padrao, compartilhado entre UI e worker.
- Backend Supabase opcional.

## Requisitos

- Python 3.11
- MetaTrader 5 instalado, aberto e logado para uso da aba MT5

## Setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configuracao de backend

Por padrao o projeto usa um backend local em arquivo em `data/alphaforge_db.json`.

Variaveis suportadas:

- `ALPHAFORGE_DB_BACKEND=auto|file|memory|supabase`
- `ALPHAFORGE_DB_PATH=./data/alphaforge_db.json`
- `SUPABASE_URL`
- `SUPABASE_KEY`

Use `.env.example` como referencia. Se preferir Streamlit secrets, defina `ALPHAFORGE_DB_BACKEND` em `.streamlit/secrets.toml`.

## Rodando a interface

```powershell
streamlit run app.py
```

Interface Flask paralela:

```powershell
python flask_app.py
```

Desktop local com pywebview:

```powershell
python desktop_app.py
```

Fluxo recomendado:

1. Conecte ao MT5 e carregue candles no builder.
2. Monte a estrategia.
3. Use `Salvar no Backend` para persistir a estrategia.
4. Use `Persistir Backtest` para gravar o run e abrir o detalhe da estrategia.
5. Em `Campanhas`, rode uma nova campanha com candles do builder ou com CSV.

## Rodando o minerador por CLI

```powershell
python workers\miner_worker.py --dataset .\data\candles.csv --db auto
```

Opcoes relevantes:

- `--mode simple|robust|robust_walk_forward`
- `--quantity 100`
- `--top-k 5`
- `--symbol EURUSD`
- `--timeframe M5`
- `--db auto|file|memory|supabase`

## Testes

```powershell
pytest -q
```

`tests/conftest.py` ja ajusta o path do projeto, entao nao e necessario exportar `PYTHONPATH`.
