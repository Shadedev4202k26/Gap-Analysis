# Picking this up on another machine — 2026-09-29

`README.md` covers setup (macOS and Windows) and how the app works. This is the
state of play.

## Everything is merged

PRs #1–#5 are all in `main`, which is what the eight stores run:

- deals correctness — deli shelf badges, family matching, 28G
- week picker starts on the current week
- fixed outdoor price on hook tags
- the new navigation, Home dashboard and three-step Shelf tags flow
- the Smilez × Ziggy lockup in the top bar

There is no work in flight. Branches `deli-fixes`, `week-default`,
`outdoor-price`, `ui-shell` and `collab-banner` are merged and can be deleted.

## First thing on a new machine

1. Install the tools — **README → Running it locally**. On Windows the two
   command-line dependencies (pdftk, pdftoppm) are the fiddly part; check
   `pdftk --version` and `pdftoppm -v` both answer before running the app.
2. Create `.streamlit/secrets.toml` from Supabase → Project Settings → API.
   It is gitignored and does not travel with the repo.
3. `.venv/bin/python tools/check_supabase.py` (`.venv\Scripts\python` on
   Windows) — proves storage works end to end without printing the key.
4. `.venv/bin/python tools/smoke_tags.py "<a weekly deals CSV>"` — builds every
   tag combination. If this passes, the toolchain is sound. On Windows it passed
   20/20 only with pdftk-java; PDFtk Server failed every build (see README).

## Windows, as actually tested — 2026-09-29

Set up from scratch on the Windows 11 laptop and verified: `check_supabase.py`
passes, `smoke_tags.py` passes 20/20, and a 41-tag hook sheet generated and
previewed in the running app. What that took, and what the earlier notes got
wrong:

- **pdftk must be pdftk-java, and it does need Java.** PDFtk Server 2.02 (the
  winget package) failed every build with `java.io.CharConversionException` in
  `create_output()` — even filling one field of the untouched
  `Hybrid_Prerolls.pdf` with plain ASCII. pdftk-java 3.3.3 on Temurin 21 passes
  everything. Setup is in README → Windows.
- **`subprocess.run(["pdftk", …])` cannot find a `.cmd` wrapper on Windows**,
  so `preroll_tags.PDFTK` resolves it with `shutil.which` first. No change on
  macOS or Streamlit Cloud.
- **`%-d` / `%-I` in strftime are glibc/BSD only; Windows raises
  `ValueError: Invalid format string`.** Fixed in `deal_store.week_label`, the
  aged-stock report date and `fmt_ts` in `app.py` by using `.day` / `.hour`.
  Output is identical on every platform. Do not reintroduce `%-`.
- **Smart App Control is on** and blocks Git for Windows' HTTPS helper
  (`libcurl-4.dll`). Git uses SSH through Windows' own
  `C:\Windows\System32\OpenSSH\ssh.exe` (`core.sshCommand`), with a key added
  to the `Shadedev4202k26` account.
- **Streamlit started from the Claude app inherits the PATH from before the
  installs**, so pdftk/pdftoppm go missing at Generate until the app (or the
  launcher) reloads PATH.
- Unconfirmed: the two BULK · OG FARMS outdoor hook tags print no price. May be
  intended — compare against a Mac print before calling it a bug.

## Open work, roughly by value

- **Curbside and break/lunch trackers**, shared across computers and separated
  by store. Both are standalone HTML using `localStorage`, so state never
  leaves one browser. Needs Supabase tables and a rewrite away from local
  storage. The break/lunch one keeps a manager PIN in local storage that should
  not move across as-is.
- **A draft flag for a stored week.** A sheet still being written becomes the
  printing week automatically at midnight on its start date.
- **Deep links to the default page 404.** Streamlit serves the default page at
  `/` and does not route its own `url_path`.
- `video.mp4` and `image.png` are unreferenced since the hero became a bar —
  4.3MB carried in every clone and deploy.

## Things that cost time to learn

- **The deployed app is `main`.** Several "something broke" reports turned out
  to be fixes that had never been merged. Check the branch before believing a
  regression.
- **A product's category is what it IS; its name is just words.** Matching deal
  rules against product text put the concentrate deal on 316 infused prerolls
  ("Live Resin" in the name) and the edibles deal on flower called "Orange
  Gummi". Category only. The same trap is why shelf colours are never read from
  the product name — 376 rows say "blue", mostly Blue Dream.
- **Streamlit `data-testid` selectors are version-specific** and a wrong one
  matches nothing, silently. `stAppDeployButton` and `stMainMenu` are real;
  `stToolbarActions` is not. Never `display:none` the header — it holds the
  button that reopens a collapsed sidebar.
- **`st.navigation`'s own menu renders collapsible groups**, drops the links
  from the DOM when collapsed, and persists that across reloads. Hence the
  hand-built `st.page_link` nav in `shell.py`.
- **Verify in the running app, not in a screenshot.** Five CSS bugs in this
  work were invisible to the eye and obvious to `getComputedStyle`.
- `tools/strip_logo.py --check` reports whether a re-exported template has
  brought the Smilez wordmark back.

## One thing to settle

The Supabase **anon** key was committed to this public repo on 2026-09-25
(`f93ab28`) and emptied again in `786392a`. Emptying the file does not remove it
from history: it is still readable at that commit by anyone.

It is the anon key, which Supabase intends to be public — but this project's
policies give `anon` full read, write and delete on `deal_sheets`, so anyone who
finds it can tamper with or wipe the stored weekly deals. No customer data is
exposed. Decide between rotating the key, tightening the policies, or accepting
it; see the note in the session that raised it.
