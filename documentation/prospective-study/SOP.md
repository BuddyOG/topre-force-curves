# Operator SOP — dome perception validation

SOP ID: `perception-validation-v1`  
Status: frozen pre-enrollment  
Effective date: 2026-08-31

This is the document to follow while running the study. The longer
[`PROTOCOL.md`](PROTOCOL.md) and [`ANALYSIS_PLAN.md`](ANALYSIS_PLAN.md) explain
why the study is designed this way; this SOP explains exactly what to do.

## The entire job in one sentence

Show one coded dome at a time in the same physical assembly, allow no more
than five presses, record one Weight score and one Tactility-sharpness score,
and never reveal the dome's identity or expected result.

## The two scores

- **Weight:** `1` = feather-lightest in this 25-dome panel; `10` = heaviest in
  this panel.
- **Tactility sharpness:** `1` = linear/off; `10` = sharpest collapse in this
  panel.

Only whole numbers from 1 through 10 are valid. Weight and sharpness are
separate judgments.

## Standard physical setup

Before the dry run, choose and physically label these exact study parts:

| Label | Physical item |
|---|---|
| `PV1-H1` | The one Topre housing used for every presentation. |
| `PV1-S1` | The one Topre slider used for every presentation. |
| `PV1-CS1` | The one conical spring used for every presentation. |
| `PV1-K1` | The one keycap used for every presentation. |
| `PV1-M1` | The one holder or mounting fixture used for every presentation. |
| `PV1-A1` | The complete assembly made from the five items above. |

Record these items in [`apparatus_record.csv.template`](apparatus_record.csv.template).
Do not swap one for a visually matching replacement during the study. If a
replacement becomes necessary, stop enrollment and use the exception and
amendment procedures.

Do not add precompression, silencing rings, alternate springs, alternate
housings, or alternate keycaps. Keep branding and specimen identity out of the
participant's view.

## One-time preparation

1. Confirm that the 25 physical specimens are the same specimens in
   [`../subjective-pilot/grid_mapping.json`](../subjective-pilot/grid_mapping.json).
2. Give every specimen a unique physical specimen ID in the private code-key
   file. Do not write a brand or nominal weight where a participant can see it.
3. Generate the private code key and randomized schedules with
   [`generate_schedules.py`](generate_schedules.py). Store the private key and
   operator schedule outside the public repository.
4. Print or prepare the participant-facing schedule. It must contain only
   participant ID, session, order, and opaque code.
5. Prepare a clean ratings CSV or one printed
   [`SESSION_RECORDING_SHEET.md`](SESSION_RECORDING_SHEET.md) per scored session.
6. Keep the scale definitions visible to the participant.
7. Complete every item in [`FREEZE_CHECKLIST.md`](FREEZE_CHECKLIST.md) before
   participant 1.

## Assigning a participant

1. Complete the appropriate consent process before study activity.
2. Assign the next opaque ID: `P001`, `P002`, and so on. Never use a name,
   initials, email address, phone number, or customer number in study data.
3. Record one experience band: `none`, `some_keyboard`, `ec_familiar`, or
   `prefer_not_to_say`.
4. Read [`PARTICIPANT_SCRIPT.md`](PARTICIPANT_SCRIPT.md) exactly as written.

## Practice pass

1. Present all 25 domes once in a randomized practice order.
2. Practice scores are optional and are never used in the analysis.
3. Correct only misunderstandings of the two scale definitions. Do not say
   what score a dome should receive.
4. After practice, ask whether the participant understands that Weight and
   Tactility sharpness are separate. Restate the definitions if needed.
5. Give a neutral five-minute break before scored session 1.

## Scored-session setup

Before trial 1, record:

- study ID `perception-validation-v1`;
- participant ID and experience band;
- session `1` or `2`;
- local start time with UTC offset;
- hours since scored session 1 when this is session 2;
- operator ID;
- apparatus ID `PV1-A1`; and
- approximate room temperature in °C.

Scored session 2 should occur at least 24 hours after scored session 1. If it
occurs sooner, do not hide or round the interval: record the actual hours and
mark a protocol deviation. The data are not automatically invalid for this
reason.

## Every scored trial

Follow these steps in order:

1. Read the next opaque code from the operator schedule.
2. Confirm that the specimen in hand has that exact code.
3. Inspect `PV1-A1`; seat the dome and conical spring consistently.
4. If a seating or equipment problem is found before presentation, correct it
   before continuing. This is not an invalid trial because the participant has
   not been exposed.
5. Present the assembly without comment about the dome.
6. Allow the participant between one and five presses.
7. Ask: **“Weight, from 1 to 10?”** Record the whole number.
8. Ask: **“Tactility sharpness, from 1 to 10?”** Record the whole number.
9. Record press count and whether the trial was valid.
10. Once you advance, do not return to that dome or invite comparison with a
    prior trial.
11. Remove the specimen, inspect the assembly, and continue in the generated
    order.

Offer a short neutral break after trials 8 and 16. Record any additional break.

## What you may say

You may repeat the scale definitions, remind the participant that the two
scores are separate, ask for a whole number, or offer a break.

Do not identify a product, answer whether a score is correct, mention a prior
score, describe a dome as heavy/light/sharp/smooth, reveal a force curve or
index, or react approvingly or negatively.

## If something goes wrong

Use [`EXCEPTION_CHECKLIST.md`](EXCEPTION_CHECKLIST.md). Do not improvise an
exclusion and do not repeat an exposed scored trial. Record what happened in
neutral factual language.

## End of a scored session

1. Confirm that trials 1–25 each have an opaque code and press count.
2. Confirm that every valid trial has both ratings from 1 through 10.
3. Confirm that every invalid trial has one declared reason.
4. Record deviations and extra breaks before the participant leaves.
5. Save the data without changing prior rows. If paper was used, enter it once
   and independently compare the electronic rows against the paper.
6. Back up the controlled study folder. Keep the private code key separate
   from the blinded analysis copy.

Never fill a blank score from memory, replace a missing score with zero, or
remove a score because it disagrees with expectations.
