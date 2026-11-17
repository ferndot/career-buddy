# Override the writing rules

Use this to change the general rules the writer follows for every resume or letter, for example a different bullet count or no closing line.

## Steps

1. Open **Settings** and choose the **Writing** tab.
2. Under **Resume** or **Letter**, edit a rule, remove it, or press **Add a rule**. Each rule is one plain sentence of at most 300 characters. A kind holds at most 20 rules.
3. Press **Save resume rules** (or **Save letter rules**). The next document you generate uses your list in place of the default.

Blank rules are dropped when you save. Saving an empty list returns that kind to the default.

## Go back to the defaults

Press **Reset to defaults** under the kind and confirm. Your list for that kind is deleted. The other kind is unchanged.

## What still wins

The rules are defaults, not commands. The template's own instructions and the resume length (`resume_pages`) win where they differ, and
nothing here lets the writer state a fact you have not given: the grounding check still applies.

## Where they are kept

In `writing-rules.json` in the data folder, for example `{"letter": ["Be brief."]}`. A kind with no entry uses the defaults. See [Documents API](../reference/documents-api.md) for the routes.
