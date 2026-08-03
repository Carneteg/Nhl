# Synkarkitektur och migrationsplan

Det ursprungliga repositoryt innehöll inga applikations- eller arbetsboksfiler. Migreringen är därför en ny, normaliserad SQLite-bas med fyra lager: källregister, real-world-tabeller, isolerade simulationstabeller och rapport/export.

Flödet är `official NHL season stats + season roster + player landing → cache → stable-ID upsert → public CapWages contract page → provenance → baseline → explicit simulation copy`. Upsert är idempotent. NHL-ID prioriteras över namn; namn+DOB används bara till deterministiskt internt ID när officiellt ID saknas. Tomma eller strukturändrade svar skapar inga påhittade poster utan fyller `verification_queue`. Konflikter lagras i `data_conflicts`; canon-lås finns i `canon_locks` men rensas vid en uttrycklig full baseline-reset.

Prioritet: användarlås, simulationstransaktion, simulationskontrakt/draft, verifierad realdata, antagande, `UNKNOWN`. Synk skriver endast baslinjen. Daglig AI-loop loggas som `simulation_events` och utvärderar alla 32 klubbar.

En ny adapter implementerar samma kontrakt som `NHLClient.get`, registrerar en source record, använder stabila ID:n och kompletteras med offlinefixture, parsertest, tomt/felaktigt svar och ändrad struktur.
