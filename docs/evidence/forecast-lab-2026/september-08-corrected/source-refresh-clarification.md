# Per-game source refresh clarification

Written before the first corrected source package is built or any corrected
weekly revision is registered. The immutable training charter and completed
fit remain unchanged. This clarification repairs an operational conflict found
in independent review: requiring all 16 games to remain before T-60 would stop
Sunday updates as soon as the Wednesday opener locked.

Every source package verifies the full 16-game Week 1 schedule and all 32 team
input identities. Its issuable `games` list contains only games whose individual
T-60 cutoff is strictly later than that package's actual generation time. Reject
outcome fields for those eligible games. Already elapsed games' outcome fields
may exist in a new schedule capture; ignore them entirely in feature construction
and do not generate or issue a new forecast for those games.

A confirmed unavailable listed QB blocks its eligible matchup until a supported
replacement is selected. Record the reason and omit that matchup; it must not
block unrelated eligible games. Any retained team rating with that listed QB is
expressly conditional and unavailable for game issuance. A package with no
issuable games fails. The weekly recorder still independently rejects each
attempted revision at or after its cutoff, including a cutoff crossed during
source preparation.

The first package is expected to contain all 16 future games. Later packages may
contain fewer. Keep every earlier approved capture/qualification hash pair in
the verifier when adding a reviewed refresh pair. Never replace an old pair,
overwrite a package, extend an existing deadline, or revise a locked game.

This changes no model input formula, coefficient, training row, comparison,
scientific acceptance rule or saved research result. It implements the user's
existing per-game lock requirement.
