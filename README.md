# Incident email IE pipeline

A small pipeline that reads incident `.eml` files, extracts incidents, sites, organisations, their relations and time-stamped site status observations, links them to the reference lists, and writes the result to SQLite.

## Setup

Requires Python 3.9 or later (the code uses `tuple[str, bool]` type hints).

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install rapidfuzz
```

Everything else is from the standard library (`email`, `csv`, `sqlite3`, `re`, `argparse`, `glob`).

Expected layout:

```
data/emails/       # .eml files
data/reference/    # lrfs.csv, incidents.csv, organisations.csv, sites.csv
pipeline/          # __main__.py, extract.py, transform.py, database.py
output/            # created on first run
```

Each reference CSV needs an `id` (or `<type>_id`) column and a `name` (or `title` / `label`) column. An optional `aliases` column holds `;`-separated alternative names.

## Run

From the project root (the folder that contains `pipeline/`):

```bash
python -m pipeline --emails data/emails --reference data/reference --out output
```

Emails are found recursively, falling back to the top level of the folder. Output is written to `output/output.sqlite` with three tables:

- `entities`: `id`, `entity_type`, `mention_text`, `is_new_entity`
- `relations`: `from_entity_id`, `relation_type`, `to_entity_id`
- `observations`: `entity_id`, `property_name`, `property_value`, `reported_at`, `email_id`

Example query:

```sql
SELECT e.mention_text, o.property_value, o.reported_at
FROM observations o JOIN entities e ON e.id = o.entity_id
ORDER BY o.reported_at;
```

Delete `output/output.sqlite` before re-running; the relations and observations tables are not de-duplicated, so a second run on the same output folder appends duplicates.

## Run time

*[Fill in with your measured time, for example: "N emails processed in X seconds on <machine>", from `time python -m pipeline ...`.]*

Cost is dominated by SQLite connection overhead (a new connection per insert) and by the fuzzy match, which scans the reference names for every unmatched mention. Both grow linearly with the number of mentions and are small at the scale of the sample data. For much larger volumes, the first fixes would be a single connection with batched inserts and a blocking step before fuzzy matching.

## Extending the pipeline

- **New fields or entity types:** add the extraction rule in `Extractor.extract_structured_data` (return more mentions, relations or observations), add the type to `Transformer.reference_data` and the `mapping` of reference files, and add a resolve-and-insert block in `__main__.py`.
- **New relations:** append another `relations` dict with `from_type`, `from_mention`, `relation`, `to_type`, `to_mention`. Nothing else needs to change as long as both mentions were resolved.
- **New observation properties:** append to `observations` with a different `property_name`. Observations are only attached to sites at the moment.
- **Different matching:** replace `Transformer.resolve`. It only needs to return `(entity_id, is_new)`.
- **Different extractor (for example an LLM):** return the same dictionary shape (`incidents`, `sites`, `organisations`, `relations`, `observations`) and the rest of the pipeline is unchanged.

## Private dataset

| Stage or component | Will it work on the private dataset? (Yes / Partly / No) | Why? |
|---|---|---|
| Email parsing (`parse_file`) | Partly | Handles standard RFC 5322 messages, but reads only the `text/plain` body. HTML-only emails give an empty body, and attachments and forwarded or quoted threads are ignored. |
| Incident detection | No | Hard-coded to the keyword "Fenella", and anything else becomes "Unknown Incident". It needs to match against `incidents.csv` instead. |
| Site and status extraction | Partly | Relies on `- site: status` bullet lines. Different layouts, wrapped lines or tables are missed silently. |
| Operator extraction | Partly | Only recognises `(run by X)` inside a status line. |
| Responding agencies | Partly | Needs a section headed "3. AGENCIES RESPONDING", split on commas and semicolons only, so a different numbering or heading would find nothing. |
| LRF extraction | No | `lrfs.csv` is loaded but no LRF mentions are extracted. |
| Reference loading | Partly | Works if the filenames and the `id` / `name` / `aliases` columns match what the code expects, otherwise the file is skipped without a warning. |
| Entity resolution (exact + alias) | Yes | Deterministic normalised lookup that does not depend on the dataset. |
| Entity resolution (fuzzy) | Partly | The threshold of 85 is untuned, and `token_set_ratio` can merge distinct names where one is a subset of the other. |
| New-entity IDs | Partly | Built from Python's `hash()`, which varies between runs, so IDs are not stable or comparable across runs. Identical new mentions in different emails also get no shared lookup. |
| SQLite output | Yes | Standard schema, but re-runs on the same output folder append duplicates (see Run). |
| Command-line interface | Yes | No dataset-specific logic. |

## Assumptions

- The private emails resemble the sample ones: plain-text bodies, one incident per email, sites listed as `- name: status`.
- Each email is about a single incident, and the incident is named in the subject or body.
- Reference CSVs contain an `id`-style and a `name`-style column, with optional `;`-separated aliases.
- A fuzzy score of 85 or more on `token_set_ratio` means "same entity", and anything below it is a new entity.
- The `Date` header is a good enough value for `reported_at`; it is stored as text and not normalised.
- Observations apply to sites only.
- The first mention text seen for an entity is the one stored in `entities.mention_text`.

## How I used my time

*[Adjust the split to what actually happened; the total must stay within the 4-hour cap.]*

- **Reading the brief and sample emails:** about [X] min
- **Designing the schema and stages:** about [X] min
- **Extraction rules:** about [X] min
- **Reference linking:** about [X] min
- **SQLite output and CLI:** about [X] min
- **Testing and checking output by hand:** about [X] min
- **README and design note:** about [X] min

I prioritised a working end-to-end baseline that I could explain and inspect over breadth of extraction. Things I knowingly left out are listed under "Next steps" in `DESIGN_NOTE.md`.

## Use of AI coding assistants

*[Describe your actual use honestly; the sentences below are a draft to edit.]*

I used Claude to help draft this README and `DESIGN_NOTE.md` from my code. I reviewed the content against the code for accuracy, and the limitations listed come from reading the implementation. *[State here whether and how AI assisted with the code itself, and what you checked or changed yourself.]*