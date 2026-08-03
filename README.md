# Edmonton Oilers GM Simulation 2025

En datadriven, lokal webbapplikation för ett textbaserat NHL-managerspel. Systemet börjar från en **verklig baslinje 2025-07-01** och kopierar den till ett separat simulationstillstånd. Senare externa synkar kan därför aldrig skriva över GM-beslut.

## Snabbstart

```bash
python -m nhlgm bootstrap:2025 --team ALL --season 20252026
python -m nhlgm simulation:new --team EDM --date 2025-07-01
python -m nhlgm web --port 8000
```

Öppna <http://127.0.0.1:8000>. Inga tredjepartsberoenden krävs vid körning. SQLite-filen skapas i `data/nhl_gm.sqlite3`. `pytest -q` kör offlinetesterna. En full ligasynk tar tid första gången eftersom varje publik spelarsida hämtas ansvarsfullt; senare körningar använder cache.

## Kommandon

`bootstrap:2025`, `sync:nhl`, `sync:ahl`, `sync:contracts`, `sync:draft-picks`, `sync:draft-class`, `sync:prospects`, `sync:all`, `audit:rosters`, `audit:contracts`, `audit:cap`, `audit:draft`, `simulation:new`, `simulation:advance`, `export:franchise` och `web` finns via `python -m nhlgm`. Synkkommandon accepterar `--dry-run`, `--force`, `--season`, `--date`, `--team`, `--source`, `--verbose` och `--skip-contracts`. `--team ALL` är standard och synkar samtliga 32 lag.

`bootstrap:2025` och `sync:all` inaktiverar gamla simulationer, tar bort canon-lås och bygger om real-world-baslinjen. Därefter skapar `simulation:new` ett nytt tillstånd där varje spelare börjar på sitt importerade verkliga lag.

## Arkitektur och återställning

SQLite är sanningskällan; Excel är endast export. Ta backup på `data/` och kör `simulation:new` för en ren alternativ tidslinje. En befintlig simulation inaktiveras men raderas inte. Gammal arbetsboksdata importeras aldrig. Om legacyfiler senare tillförs ska de flyttas till `archive/legacy-simulation/`.

Se [databasschemat](docs/database-schema.md), [synkarkitekturen](docs/sync-architecture.md) och [källregistret](docs/data-sources.md).

## Publik driftsättning

En produktionsklar container och Render Blueprint finns i repositoryt. Se [publik driftsättning](docs/public-deployment.md). Runtime läser `PORT` och `NHLGM_DB`; den senare måste ligga på beständig lagring så att simulationen överlever omstarter.

## Genererade filer

Databaser och arbetsböcker versionshanteras inte. `bootstrap:2025` skapar SQLite-databasen vid första körningen och `export:franchise` skapar en ny `.xlsx` lokalt i `exports/`:

```bash
python -m nhlgm bootstrap:2025 --team ALL --season 20252026
python -m nhlgm simulation:new --team EDM --date 2025-07-01
python -m nhlgm export:franchise
```

Filerna kan återskapas från textbaserad källkod, fixtures och externa källor och ska därför inte läggas till i Git.
