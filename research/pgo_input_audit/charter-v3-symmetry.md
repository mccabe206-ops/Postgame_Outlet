# Neutral-field symmetry repair: pre-fit seventh arm

Written before any follow-up fitting. The implementer confirmed the six-arm
code and checks exist but no arm has been fitted. This amendment supersedes
only the addendum's six-arm limit. Both earlier charter files and all other
rules remain unchanged; this new issue was discovered by an algebraic invariant,
not by inspecting new model rankings or held-out candidate scores.

## Evidence and required invariant

In the issued September fit, equal full-strength team states, neutral venue and
equal rest predict home-minus-away margin -0.8011250871. NE versus LAR predicts
-0.5138050318, while LAR versus NE predicts -1.0884451425. The fitted intercept
minus standardized-median offsets creates a common neutral constant. The saved
starter/recency/full candidates also have nonzero constants. This is inconsistent
with interpreting neutral team strength as an antisymmetric price difference.

Require f(A,A,neutral,equal-rest)=0 and
f(A,B,neutral,equal-rest)=-f(B,A,neutral,equal-rest). More generally, swapping
team labels must swap the signs of team differences, rest and the signed venue
advantage. Reversing a home game does not mean giving the other team a new home
stadium: the venue indicator reverses from +1 to -1 for that training perspective.

## One additional arm

**active4_symmetric** uses the same inputs as active4_clean. At each training
fold only, augment every original game with one reversed perspective: negate
every finite matchup feature and the target; retain missing features as missing.
This includes changing home_field from +1 to -1 (neutral remains zero) and
negating rest_difference. Fit preprocessing on the augmented training rows only,
and fit the same Huber-ridge routine with alpha 200, twice the existing 100,
because duplicated training residuals must not halve the effective penalty.
Keep Huber delta 1 and the existing convergence settings.

Evaluation retains each original game exactly once, with its original venue and
rest. Report original game count separately from augmented training row count.
No source, label, fold or current input changes. Current ratings use this arm's
own symmetric final preprocessor and coefficients. Check the effective intercept
and missing-indicator coefficients are negligible, and directly test predictions
for identical and reversed neutral matchups, including missing inputs. Reject
the arm if the invariants fail at absolute tolerance 1e-8.

Compare against active4_clean and reference4 with the same primary MAE, secondary
metrics, season-block intervals, team/early-season slices and HOLD screen. Publish
all seven arms; no choosing between models based on NE's rank. This is a structural
repair candidate, not probability calibration or retrospective validation of
the issued neutral-field prices. No eighth arm or parameter search is allowed.
