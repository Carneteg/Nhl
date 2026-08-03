# Trade AI

Every NHL team has an active GM profile. A proposed trade is validated against asset ownership, no-move/no-trade clauses, confirmed draft-pick status, both teams' post-trade cap positions, roster balance, positional needs, and a transparent asset-value model. The CPU requires a value premium and rejects both underpayments and implausibly large overpayments. Accepted trades move simulation players, contracts, and draft-pick ownership atomically while leaving the sourced real-world baseline unchanged.

The value model is deliberately conservative and explainable; it uses age, position, contract cost, draft year/round, and roster construction rather than random acceptance. It is not a substitute for proprietary scouting ratings, and all rejections return specific reasons to the UI.
