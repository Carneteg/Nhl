# Publik driftsättning

## Render Blueprint

Repositoryt innehåller `render.yaml`, `Dockerfile` och `scripts/start-public.sh`. Skapa en ny **Blueprint** i Render och anslut repositoryt. Render bygger containern, monterar en beständig 2 GB-disk och använder `/health` för hälsokontroll. Servern läser alltid den `PORT` som Render injicerar och binder till `0.0.0.0:$PORT`; lokalt används port 8000 om variabeln saknas. Tjänsten får därefter en stabil publik `https://<service>.onrender.com`-adress.

Den första starten hämtar 32-lagsbaslinjen och kontrakt med cache/rate limiting, skapar en ren Edmonton-simulation och kan därför ta flera minuter. Under importen håller en minimal bootstrap-listener Render-porten öppen och svarar på `/health`; därefter övertar den riktiga webbservern samma port. Senare omstarter återanvänder SQLite-databasen på den beständiga disken.

## Docker

```bash
docker build -t nhl-gm .
docker volume create nhlgm-data
docker run --rm -p 8000:8000 -v nhlgm-data:/var/lib/nhlgm nhl-gm
```

Öppna `http://localhost:8000`. På annan containerplattform ska `NHLGM_DB` peka på en beständig volym och `PORT` sättas till plattformens tilldelade port.

## Viktigt

En publik produktionstjänst behöver beständig lagring; ephemeral filesystem skulle radera simulationen vid omstart. Nuvarande spel är ett single-GM-system utan användarautentisering. Publicera därför inte en skrivbar instans för obetrodda användare innan autentisering och CSRF-skydd har lagts till.
