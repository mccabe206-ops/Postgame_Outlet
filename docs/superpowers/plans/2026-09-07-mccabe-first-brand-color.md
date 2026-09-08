# McCabe first and livelier PGO colors

User direction: keep the homepage layout McCabe likes, make its bland colors more fun, and display his rankings first. Existing authorization covers implementing and publishing site updates.

## Constraints

- Preserve the homepage section order and responsive layout.
- Lead the homepage ratings preview and initial full board with Sean McCabe's actual ratings. Preserve PGO Model and Fantasy as separately labeled, usable tabs.
- Do not change statistical ratings, fantasy projections, scoring math, practice annotations, evidence receipts, or protected challenger files.
- Use the existing theme and native CSS. Default palette: bold orange, deep navy, warm white.
- Preserve commerce, newsletter and integration behavior. Capture current live theme files before a scoped publication.

## Work

1. Board: change tab order/default state at the render and refresh sources; retain strict validation and preserve existing panel contents. Add focused regression coverage and check keyboard navigation.
2. Site: verify McCabe's top five against current published source, update the homepage preview and native ratings-page context. Refresh theme and board colors while keeping the layout.
3. Review and verify: focused and required tests, real refresh preservation, desktop/mobile visual and keyboard checks, scoped Theme Check comparison, independent code review.
4. Publish the reviewed board and theme changes; verify the live homepage, rankings default, secondary tabs and unchanged scoring receipt. Record exact commits and release evidence.

## Progress

- McCabe-first rendering, legacy refresh migration, full tab-state validation, and the shared palette are implemented and independently reviewed.
- The theme preview preserves the approved layout and uses McCabe's actual top five. Thirteen theme checks and native desktop/mobile review passed; Theme Check introduces no offenses against the current live baseline.
- Final focused board suites: 67 passed. Fantasy contents, all rating cells, scoring scripts, and the public receipt are preserved. Full-suite and publication evidence is recorded in `output/mccabe-color-release/`.
