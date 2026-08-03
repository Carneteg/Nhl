# Lönetaksmodell

`cap_summary` summerar endast kontrakt vars simulationsspelare har NHL-nivå och status `ACTIVE`, `IR` eller `LTIR`. `TRADED`, `AHL`, `JUNIOR`, `EUROPE`, `UNSIGNED`, `RETIRED` och `HISTORICAL` exkluderas från aktiv cap. Retained och buried summeras separat och exakt en gång. Total charge är aktiv cap + retained + buried + explicit dead cap/overage. Okänd cap hit behandlas inte som ett påhittat nollvärde: audit lägger spelaren i Verification Queue. Capgränsen är en konfigurerbar parameter, inte ett dashboardfält.

