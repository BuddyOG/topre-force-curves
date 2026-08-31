# Exception checklist

Study ID: `perception-validation-v1`

Use the first matching row. Record facts, not interpretations. A surprising or
inconvenient score is never an exception.

## Before the participant presses

| Situation | Action | Trial status |
|---|---|---|
| Wrong coded specimen selected | Put it away, select the scheduled code, and verify again. | No trial has occurred. |
| Dome, spring, slider, or housing is not seated | Correct the assembly before presentation. | No trial has occurred. |
| Apparatus is damaged or the designated component is unavailable | Stop the session. Do not substitute a matching-looking part. | Record interruption; amend before resuming enrollment if replacement is required. |
| Participant can see identity or bench information | Hide the information before presentation. | No trial has occurred. |

## After the participant presses or receives information

Do not repeat an exposed scored trial.

| Situation | `valid_trial` | `invalid_reason` | What to do |
|---|:---:|---|---|
| No rating is provided | `false` | `missing` | Leave the missing numeric field blank and continue if the participant wishes. |
| Wrong specimen was presented | `false` | `wrong_specimen` | Record the presented and scheduled codes in the deviation field; do not substitute later. |
| Identity, nominal weight, curve, metric, index, or prior result was revealed before rating | `false` | `unblinded` | Record exactly what was revealed. |
| Equipment failed during the presentation | `false` | `equipment_fault` | Stop and correct the equipment before a later scheduled trial. |
| Assembly or seating fault was discovered after exposure | `false` | `assembly_fault` | Record the fault; do not repeat this trial. |
| More than five presses occurred | `false` | `press_limit_exceeded` | Record the actual press count and continue only after restating the five-press limit. |
| Trials were presented out of generated order | `false` for the affected exposure | `order_error` | Record scheduled and actual order; resume at the next unpresented scheduled trial. |
| Participant withdraws the rating or study participation | `false` | `withdrawn` | Stop immediately if requested; retain or remove prior data according to the consent terms. |

`other_declared` may be used only for an exception added by a dated amendment
before the affected data are viewed. It is not a catch-all for an unexpected
score.

## Corrections

- If the participant immediately corrects their own score before the next
  trial begins, record the corrected score and note the correction. It remains
  valid.
- If a transcription error is found from a paper source, correct the
  electronic row with a dated audit note. Preserve the original paper.
- Never change a score from memory after the next trial begins.
- Never turn missing into zero, average, or a guessed score.

## Deviations that do not automatically invalidate a trial

- scored session 2 occurred less than 24 hours after session 1;
- an additional neutral break occurred;
- room temperature was unavailable;
- identity was revealed only after both ratings were locked; or
- a neutral interruption occurred without changing the presentation.

Record these as deviations. The frozen analysis will report them and can use
them in a declared sensitivity analysis.
