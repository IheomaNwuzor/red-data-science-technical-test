# Design note

> About 1,000 words

## 1. Approach and alternatives

The pipeline is three small stages with a narrow interface between them, so any one can be replaced without touching the others.

**Extract (`extract.py`).** Each `.eml` file is parsed with the standard-library `email` package (`policy=default`), taking the plain-text body, `Date`, `Subject`, `From`, `To` and `Message-ID`. Rule-based extraction then pulls out four kinds of thing:

- **Incident mention.** A keyword check on subject and body.
- **Sites and their status.** Bullet lines of the form `- <site>: <status>`.
- **Operating organisations.** A `(run by <org>)` pattern inside a status.
- **Responding agencies.** The numbered "AGENCIES RESPONDING" section.

The output is a dictionary of raw *mentions*, plus typed relations (`OPERATES`, `AFFECTS`, `RESPONDS_TO`) and time-stamped observations.

**Transform (`transform.py`).** Each mention is linked to the reference lists (`lrfs.csv`, `incidents.csv`, `organisations.csv`, `sites.csv`). Text is normalised (lower-cased, leading "the/a/an" removed) and then matched in order: exact match on name or alias, then fuzzy match with RapidFuzz `token_set_ratio` at a threshold of 85, otherwise a new identifier (`NEW_<TYPE>_…`) is minted and the entity is flagged `is_new`. Matching to a reference entry is treated as the normal case and creating a new entity as the fallback, because the reference lists are the authoritative vocabulary.

**Load (`database.py`).** Results go to SQLite with three tables:

- `entities` holds the resolved ID, type, first mention text and the `is_new_entity` flag.
- `relations` holds typed edges between entity IDs.
- `observations` holds property values attached to an entity, each with `reported_at` and the source `email_id`.

I modelled site status as an **observation** rather than an attribute on the site. Incident emails are updates over time ("closed", then "reopened", then "operating normally"), so overwriting would lose the history, and keeping the email ID gives provenance for every claim. Relations are a plain triple store because the graph is small and SQLite is easy for a reviewer to query without extra tooling.

**Alternatives considered.**

| Alternative | Why not (for now) |
|---|---|
| LLM-based extraction | Handles free-form, unseen phrasing far better and could extract LRFs and incident names without hard-coding. But it is non-deterministic, harder to audit, costs money per email, and raises data-handling questions for incident data. Under a 4-hour cap, a deterministic baseline I can explain line by line seemed the better first deliverable. |
| Off-the-shelf NER (spaCy and similar) | Generic models tag locations and organisations, but not "which of our reference sites", and still need a linking step. |
| Gazetteer scan of the whole body | Search the body for every reference name and alias, instead of relying on layout. Higher recall on unstructured emails and independent of formatting. It is the first thing I would add (see section 3). |
| Learned entity linking / embeddings | Overkill for a few hundred reference entries, and no labelled data to train on. |

The main trade-off I accepted is **precision and auditability over recall and generality**. The extractor works because the synthetic emails follow a regular layout, and that is also its biggest weakness.

## 2. Evaluation

**What I can claim.** No labelled ground truth was supplied, and I have not measured accuracy against one. Any results here come from manual inspection of sample output rather than from computed metrics. *[Replace this paragraph with what you actually checked, for example: "I read N emails and compared the SQLite rows against the text by hand; I found X."]*

**How I would evaluate properly.** I would hand-label a sample of about 30 to 50 emails, stratified by sender, length and layout, with gold mentions, gold reference IDs (or "new"), gold relations and gold status observations. I would then score each stage separately so errors can be attributed:

1. **Mention extraction:** precision and recall per entity type, using exact span match and a lenient match.
2. **Entity linking:** accuracy of the resolved ID given a correct mention, plus precision and recall of the `is_new` decision. A wrong merge and a wrong "new" are different failures with different downstream costs.
3. **Relations:** precision and recall on (from, relation, to) triples after linking.
4. **Observations:** exact match on property value and the correct `reported_at`.

I would report these separately for the template-conforming emails and for the rest, since a single aggregate would hide the generalisation gap.

**Known failure modes I would test for, from reading the code.**

- **Over-merging in fuzzy matching.** `token_set_ratio` returns 100 whenever one string's tokens are a subset of the other's, so "Cardiff" can match "Cardiff Reception Centre" and distinct sites can collapse into one. I would sweep the threshold on labelled data and compare it against `token_sort_ratio` or `WRatio`.
- **Layout dependence.** Anything not written as a `- site: status` bullet is silently missed, and there is no signal that it was missed.
- **Incident handling.** The incident is detected by one hard-coded keyword, with "Unknown Incident" as the fallback. Any other incident would be mislabelled.
- **LRFs.** `lrfs.csv` is loaded, but no LRF mentions are extracted, so that entity type is currently never populated.
- **Agency splitting.** Splitting on commas and semicolons breaks names that contain commas, and "and" lists are not split.
- **Dates.** `reported_at` stores the raw `Date` header, with no timezone normalisation.

An end-to-end sanity check I would also add is that every relation and observation refers to an entity that exists in `entities`, and that re-running the pipeline gives identical output.

## 3. Next steps

In priority order:

1. **Remove the debugging limit and make runs idempotent.** The main loop processes the emails. New-entity IDs use Python's built-in `hash()`, which is randomised per process, so the same mention gets a different ID on each run. Replace it with a stable hash (for example SHA-1 of the cleaned text) or a counter. Add a uniqueness constraint on relations and observations so that a re-run does not duplicate rows.
2. **Deduplicate new entities within a run.** Two spellings of the same unknown site in different emails should resolve to one new entity, so the resolver needs to add newly minted entities to its own lookup.
3. **Generalise incident and LRF extraction.** Detect incidents by matching against `incidents.csv` (names and aliases), and fall back to the subject line. Extract LRFs the same way.
4. **Add a gazetteer pass over the body** to catch reference entities that appear outside the expected layout, and keep the rule-based results as high-confidence labels.
5. **Build the labelled sample and metrics harness** described above, and use it to set the fuzzy threshold rather than the current untested 85.
6. **Make low-confidence decisions visible.** Store the match score and method (exact, alias, fuzzy, new) on each entity, and write unresolved or borderline cases to a review file.
7. **Optionally add an LLM fallback** for emails where the rules find nothing. It would run only on those emails, return structured JSON with a fixed schema, and pass through the same resolver so that identifiers stay controlled. That limits cost and keeps the audit trail.
8. **Engineering hygiene.** Use a single database connection and batched inserts, a `requirements.txt` with pinned versions, and unit tests for the regexes and the resolver.