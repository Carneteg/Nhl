# 2025 start state

The default date is `2025-07-01`, phase `FREE_AGENCY`, with the user controlling the Edmonton Oilers. `bootstrap:2025 --team ALL` archives active simulations, removes alternate-timeline canon locks, and rebuilds all 32 organizations from official NHL 2025-26 roster, season-statistics, and player endpoints. Roster-endpoint membership determines `ACTIVE` players; season-statistics-only records remain `HISTORICAL` and do not count against active cap. Verified public contract records supply 2025-26 cap hits and clauses.

`simulation:new` copies that baseline into isolated simulation player, contract, and draft-pick tables. Real-world records never move when the user later completes a simulation trade. Audits explicitly reject a baseline that places Connor McDavid or Leon Draisaitl outside Edmonton.

The Render startup script stores a `2025-26-real-v2` marker beside the persistent database. A deployment created by an older baseline importer is rebuilt once; subsequent restarts reuse the verified database and do not repeatedly reset the simulation.
