# Lönetaksmodell

`cap_summary` summerar endast kontrakt vars simulationsspelare har NHL-nivå och status `ACTIVE`, `IR` eller `LTIR`. `TRADED`, `AHL`, `JUNIOR`, `EUROPE`, `UNSIGNED`, `RETIRED` och `HISTORICAL` exkluderas från aktiv cap. Retained och buried summeras separat och exakt en gång. Total charge är aktiv cap + retained + buried + explicit dead cap/overage. Okänd cap hit behandlas inte som ett påhittat nollvärde: audit lägger spelaren i Verification Queue. Capgränsen är en konfigurerbar parameter, inte ett dashboardfält.

The 2025-26 upper limit is USD 95,500,000. League sync is blocked if any active roster player has a missing/non-positive cap hit or missing expiry year. Simulation audits calculate every team's total from simulation contracts and report any non-compliant team rather than silently displaying a zero value.

`gross_cap_charge` is the full sum of active contracts, retained salary, and buried charges. If that gross amount exceeds the upper limit, `ltir_relief` reports the minimum relief/opening-roster adjustment required and `total_cap_charge` remains capped at the legal upper limit. Trade validation always uses the gross amount, so the relief calculation cannot be exploited to accept an otherwise illegal acquisition.
