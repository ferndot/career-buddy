# Override the writing rules

Use this to change the general rules the writer follows for every resume or letter, for example a different bullet count or no closing line.

## Steps

1. Open **Settings** and choose the **Writing** tab.
2. Under **Resume** or **Letter**, edit a rule, remove it, or press **Add a rule**. Each rule is one plain sentence of at most 300 characters. A kind holds at most 20 rules.
3. Press **Save resume rules** (or **Save letter rules**). The next document you generate uses your list in place of the default.

Blank rules are dropped when you save. Saving an empty list returns that kind to the default.

## Set how strictly the wording follows your facts

At the top of the **Writing** tab, **Strictness** has three levels. It applies at once to the next document, for resumes and letters.

- **Strict**: the wording stays close to your facts (a text may run to 1.3 times the length of the facts it cites for a bullet).
- **Balanced** (default): the writer may paraphrase, use stronger verbs and merge two achievements into one bullet.
- **Loose**: wording may go further still.

At every level the specifics stay exact: numbers and metrics, job titles, employers, dates, degrees, schools, and any tool, skill or
certification your facts do not name. A text that adds one is rejected and shows your own words instead. A looser level never lets one through.

Separately from the level, after the first draft the writer is told when the draft fits the posting weakly (the posting's terms are missing from the text, the summary or the first bullets) and gets one revision to fix it.

## Go back to the defaults

Press **Reset to defaults** under the kind and confirm. Your list for that kind is deleted. The other kind is unchanged.

## What still wins

The rules are defaults, not commands. The template's own instructions and the resume length (`resume_pages`) win where they differ, and
nothing here lets the writer state a fact you have not given: the grounding check still applies.

## Where they are kept

In `writing-rules.json` in the data folder, for example `{"letter": ["Be brief."], "strictness": "loose"}`. A kind with no entry uses the defaults. See [Documents API](../reference/documents-api.md) for the routes.
