# Scoring Rubric

Six bands (1 = lowest, 6 = highest). Descriptors are observable — count-based or feature-based — not impressionistic. This rubric is embedded verbatim into the LLM judge prompt (see `judge.py`) and used by a human reviewer to sanity-check bands.

## Fluency (speaking only)

| Band | Descriptor |
|---|---|
| 6 | Speech rate 130-160+ wpm. Phonation ratio > 0.65. Mean length of run > 7 words. Pauses, when present, fall at clause boundaries. |
| 5 | Speech rate 110-130 wpm. Phonation ratio 0.58-0.65. Mean length of run 5-7 words. Occasional mid-clause pause. |
| 4 | Speech rate 100-110 wpm. Phonation ratio 0.50-0.58. Mean length of run 4-5 words. Pauses mid-clause more than twice per 100 words. |
| 3 | Speech rate 90-100 wpm. Phonation ratio 0.42-0.50. Mean length of run 3-4 words. Frequent short runs interrupted by silence. |
| 2 | Speech rate < 90 wpm. Phonation ratio < 0.42. Mean length of run < 3 words. Silence exceeds speech for extended stretches. |
| 1 | Speech breaks down; long silences dominate; fewer than 2-word runs sustained. |

## Grammar

| Band | Descriptor |
|---|---|
| 6 | No error patterns; occasional slip does not recur or obscure meaning. |
| 5 | Errors are isolated (tense, agreement, article) and never obscure meaning. |
| 4 | One error type recurs (e.g. subject-verb agreement) but meaning stays clear. |
| 3 | Errors recur across two or more categories; meaning occasionally requires re-reading. |
| 2 | Errors are frequent enough that meaning is regularly unclear without re-reading. |
| 1 | Grammar breakdown obscures meaning in most sentences. |

## Vocabulary

| Band | Descriptor |
|---|---|
| 6 | Precise, register-appropriate word choice; no reliance on vague fillers ("stuff", "thing"). |
| 5 | Mostly precise; one or two vague or repeated word choices. |
| 4 | Adequate for the task but noticeably repetitive or generic. |
| 3 | Limited range; frequent circumlocution or wrong-word substitution. |
| 2 | Vocabulary insufficient for the task; meaning frequently approximated. |
| 1 | Vocabulary too limited to complete the task. |

## Task Fulfilment

| Band | Descriptor |
|---|---|
| 6 | Directly and completely answers every part of the prompt; appropriate length. |
| 5 | Answers all parts of the prompt; minor omission or slight brevity/excess. |
| 4 | Answers the main point but skips a secondary part of the prompt. |
| 3 | Partial answer; misses a required element (e.g. no apology in a complaint-response task). |
| 2 | Response is tangential; only loosely related to the prompt. |
| 1 | Response does not address the prompt. |

## Tone Appropriateness (writing only)

| Band | Descriptor |
|---|---|
| 6 | Register matches a professional customer-service email throughout; empathetic where needed. |
| 5 | Register mostly appropriate; one lapse (too casual/blunt) that doesn't undermine the message. |
| 4 | Generally appropriate but flat — misses an opportunity for empathy the scenario calls for. |
| 3 | Register inconsistent — swings between too casual and stiff. |
| 2 | Register largely inappropriate (e.g. curt, accusatory, or overly casual for a business context). |
| 1 | Tone actively undermines the message (rude, dismissive, or incoherent register). |

## Explicit exclusions

- Score intelligibility, never accent conformity.
- Do not penalize regional or non-native phonology that does not impede understanding.
