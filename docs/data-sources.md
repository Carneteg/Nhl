# Datakällor

1. NHL:s officiella JSON-API: `https://api-web.nhle.com/v1/roster/{TEAM}/{SEASON}` för identitet, roster, position och biografiska fält.
2. NHL:s `club-stats/{TEAM}/{SEASON}/2` ger alla spelare som representerat klubben under grundserien. Detta slås ihop med rosterendpointen och `player/{ID}/landing` för biografi, nationalitet och fysisk data.
3. CapWages publika spelarsidor används för 2025–26 cap hit, lön, kontraktsperiod, UFA/RFA och klausuler när de finns. Varje värde länkas till exakt spelarsida och sparas med parser-version.
4. NHL.com/NHL Central Scouting används för versionslagrade draftlistor. Repo-fixturen är ett litet, uttryckligen ofullständigt test/starturval och okända scoutingfält markeras `UNKNOWN`.
5. Officiella klubb-, AHL-, junior-, NCAA- och europeiska källor är nästa tillåtna nivå när adapters tillförs.

Varje import får en `source_records`-post med URL, endpoint/parser, hämtningstid, verifieringstid, confidence och payload-hash. HTTP-klienten har identifierande user-agent, lokal cache, 120 ms NHL-fördröjning, 200 ms CapWages-fördröjning och exponentiell retry. `--force` ignorerar cache. CapWages `robots.txt` anger `Allow: /` för generella klienter; importeraren använder endast publika `/players/{slug}`-sidor och kringgår aldrig spärrar. Elite Prospects används inte: deras professionella API är uttryckligen disallow-listat och ingen licens har antagits. HockeyDB används inte.

NHL:s rosterendpoint är inte ett historiskt transaktionsregister. Ligabaslinjen definieras därför som **verklig NHL-klubbtillhörighet under säsongen 2025–26**: unionen av officiell säsongsstatistik och säsongsrostern. Endast rosterendpointens spelare får `ACTIVE`; spelare som enbart finns i säsongsstatistiken bevaras som `HISTORICAL` och belastar inte aktiv cap. Baslinjen får inte beskrivas som en exakt midnatts-snapshot 2025-07-01. En spelare som representerade två lag under säsongen ger en explicit konflikt och båda säsongsmedlemskapen bevaras; exakta opening-night-rosters kräver en daterad officiell transaktionskälla.
