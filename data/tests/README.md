# Hands-on test results

One JSON file per platform, e.g. `kit.json`. **Only TA writes or confirms these results** — never add a file
for a test that wasn't actually run. With no `.json` files here, the site shows no test claims.

```json
{
  "platform_id": "kit",
  "tester": "TA",
  "tested_on": "2026-12-01",
  "plan": "Free",
  "results": {
    "signup_to_first_issue_minutes": 25,
    "signup_form": {"done": true, "minutes": 10, "note": ""},
    "inbox_placement": {"gmail": "inbox", "outlook": "spam", "yahoo": "not_tested"},
    "import_export": {"imported": 10, "exported_fields": "email, first name, tags", "note": ""},
    "welcome_sequence": {"possible_on_plan": false, "note": ""}
  },
  "problems": ["Anything that went wrong, in TA's words"],
  "notes": "Optional short comment from TA"
}
```

`inbox_placement` values: `inbox`, `promotions`, `spam`, `not_tested`. Any result key can be left out.
Protocol: see `docs/hands-on-test-protocol-ja.md`.

Optional extra keys: `"tester_comment"` (TA's own one-line impression, shown as a quote) and
`"screenshots": [{"file": "kit/01-dashboard.webp", "caption": "...", "w": 1100, "h": 756}]`
(images live in `assets/tests/<platform>/`; black out personal names and email addresses before adding).
