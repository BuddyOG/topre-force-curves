# Data dictionary

Store one row per scored participant-session-trial. Use UTF-8 CSV with the
header in `participant_ratings.csv.template`. Copy the template to a working
`.csv` file before collection. Blank means missing; do not use
zero or a word such as `NA` in numeric columns.

| Field | Type | Meaning |
|---|---|---|
| `study_id` | text | Frozen protocol/study identifier. |
| `participant_id` | text | Opaque research ID; never a name or contact detail. |
| `experience_band` | category | `none`, `some_keyboard`, `ec_familiar`, or `prefer_not_to_say`. |
| `session` | integer | Scored session `1` or `2`; practice is stored separately if retained. |
| `session_started_at` | ISO 8601 | Local timestamp with UTC offset. |
| `hours_since_prior_session` | decimal | Blank for session 1. |
| `operator_id` | text | Opaque operator code. |
| `apparatus_id` | text | Identifier for the frozen assembly/fixture. |
| `room_temp_c` | decimal | Approximate temperature; blank only if unavailable. |
| `trial_order` | integer | Presentation position `1` through `25`. |
| `blinded_code` | text | Opaque physical-specimen code. |
| `press_count` | integer | Number of presses used, `1` through `5`. |
| `weight_rating` | integer | `1` through `10`; blank if not provided. |
| `tactility_rating` | integer | `1` through `10`; blank if not provided. |
| `valid_trial` | boolean | `true` or `false` under prospective rules. |
| `invalid_reason` | category | Blank when valid; otherwise `missing`, `wrong_specimen`, `unblinded`, `equipment_fault`, `assembly_fault`, `withdrawn`, or `other_declared`. |
| `break_before` | boolean | Whether a break immediately preceded this trial. |
| `protocol_deviation` | text | Neutral factual description; blank if none. |
| `notes` | text | Nonidentifying operational note only. |

The private code key adds `canonical_set`, `dome_label`, `position`, and
`test_id`. Do not add predictor values to the participant-facing schedule.

The public deidentified release should remove exact timestamps and free-text
notes if they could indirectly identify a participant. Publish an explicit
redaction record rather than silently editing values.
