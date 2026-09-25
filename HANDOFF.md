# Where this is up to — 2026-09-25

State of play for picking this up in a fresh session. `README.md` covers setup
and how the app works; this is only what is in flight.

## Branches

`main` is what the eight stores run. Everything below is off it.

| branch | PR | what |
|---|---|---|
| `deli-fixes` | [#1](https://github.com/Shadedev4202k26/Gap-Analysis/pull/1) | deals correctness — deli shelves, family matching, 28G |
| `week-default` | [#2](https://github.com/Shadedev4202k26/Gap-Analysis/pull/2) | week picker starts on the current week |
| `ui-shell` | — | sidebar navigation + top bar, plus the deli commits |

Both PRs are off `main` and touch different functions, so either can merge first.

**`ui-shell` is behind.** It carries the deli commits but not `737610d`
(family matching, bulk-by-category, 28G). After #1 and #2 merge, rebase
`ui-shell` onto `main` — it will drop the duplicated deli commits and pick up
the rest.

## Next actions, in order

1. **Print one sheet from `deli-fixes`** before merging. Deli tags now show a
   shelf badge where a deal bubble was, and a lot of tags lose badges they
   should never have had. Both intended, both visible in every store.
2. **Merge #1 and #2.** Every sheet printed until then carries the wrong deals.
3. **Rebase `ui-shell`** onto the new `main`.
4. Review the navigation rebuild on `ui-shell` — run it locally, it is only the
   shell so far, every page keeps the content it had.

## Open work, roughly by value

- **The tag flow itself.** The mockup's three steps (source & format → pick tags
  → review & print), the two-pane picker with a live sheet preview, and the
  week/store controls in the top bar. This is the actual behaviour change users
  asked for; only the shell exists.
- **Curbside and break/lunch trackers** shared across computers, per store.
  Both are standalone HTML using `localStorage`, so state never leaves one
  browser. Needs Supabase tables and a rewrite away from local storage. The
  break/lunch one keeps a manager PIN in local storage which should not move
  as-is.
- **A draft flag for a stored week.** A sheet still being written becomes the
  printing week automatically at midnight on its start date.
- **Deep links to the default page 404.** Streamlit serves the default page at
  `/` and does not route its own `url_path`. A small landing page as the default
  would fix it and give the mockup's home screen somewhere to live.
- `video.mp4` and `image.png` are unreferenced since the hero became a bar —
  4.3MB carried in every clone and deploy.

## Things that cost time to learn

- **The deployed app is `main`.** Several "something broke" reports turned out
  to be fixes that had never been merged. Check which branch a change is on
  before believing a regression.
- **A product's category is what it IS; its name is just words.** Matching deal
  rules against product text put the concentrate deal on 316 infused prerolls
  ("Live Resin" in the name) and the edibles deal on flower called "Orange
  Gummi". Category only. The same trap is why shelf colours are never read from
  the product name — 376 rows say "blue", mostly Blue Dream.
- **Streamlit `data-testid` selectors are version-specific**, and a wrong one
  matches nothing silently. `stAppDeployButton` and `stMainMenu` are real;
  `stToolbarActions` is not. Never `display:none` the header — it holds the
  button that reopens a collapsed sidebar.
- **`st.navigation`'s own menu renders collapsible groups**, drops the links
  from the DOM when collapsed, and persists that across reloads. Hence the
  hand-built `st.page_link` nav in `shell.py`.
- **Verify in the running app, not in a screenshot.** Five CSS bugs in this
  work were invisible to the eye and obvious to `getComputedStyle`.
- `tools/check_supabase.py` diagnoses deals storage end to end without printing
  the key. `tools/strip_logo.py --check` reports whether a re-exported template
  has brought the Smilez wordmark back.

## Verification on hand

A headless smoke test covering all three builders × both sizes × mix on/off ×
deals on/off lives in the session scratch, not the repo — worth moving in. The
figures quoted in commit messages come from the 2026-09-15, 09-22 and 09-25
inventory exports in `~/Downloads` against the 9/21 and 9/28 deals sheets.
