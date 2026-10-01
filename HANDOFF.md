# Where this is up to — 2026-10-01

`README.md` covers setup (macOS and Windows) and how the app works. This is the
state of play. Work moved from the Mac to the Windows laptop on 2026-09-29.

## Everything is merged

PRs #1–#8 are all in `main`, which is what the eight stores run at
https://ziggyz.streamlit.app:

- #1–#5 — deals correctness (deli shelf badges, family matching, 28G), week
  picker on the current week, fixed outdoor price on hook tags, the new
  navigation / Home / three-step Shelf tags flow, the Smilez × Ziggy lockup
- #6 — Windows: pdftk-java, portable date formatting, secrets.toml untracked
- #7 — break tracker: managers sign in by name (adding themselves the first
  time), every Admin change goes to an append-only history in Supabase,
  reviewed in Settings; one store picker at the top of the sidebar for the
  whole app, kept in the URL (`?store=Wayne`)
- #8 — Mix types / Sale bubbles / Only what changed also on Shelf tags' Pick
  tags step; the pinned action bar kept clear of Streamlit Cloud's corner

There is no work in flight, and `main` is the only branch — the eight merged
ones were deleted on 2026-10-01.

## Waiting on people, not code

- **A real manager's first sign-in.** Never done against the live tables (it
  writes a permanent row). Have one manager open Store tools → Break & Lunch
  Tracker → Admin and add their name, then check Settings → Break & lunch
  tracker shows the name and the sign-in.
- **Each store's tablet:** pick the store in the sidebar, then bookmark it, so
  it always opens on that store. Any tablet running a *downloaded* copy of the
  break tracker still has the old PIN version — download a fresh one from
  Store tools.

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
- **Smart App Control is now off** on the laptop. On 2026-09-30, after a
  Windows update, it began blocking pandas' own `.pyd` files, so the app could
  not start at all; it has no per-file allow-list. Before that it had blocked
  Git for Windows' HTTPS helper (`libcurl-4.dll`), which is why Git uses SSH
  through Windows' own `C:\Windows\System32\OpenSSH\ssh.exe`
  (`core.sshCommand`), with a key added to the `Shadedev4202k26` account.
- **Checking out a commit older than `863fe80` deletes your local
  `secrets.toml`.** Those commits still track the file, and Git overwrites an
  ignored file without asking — it happened on 2026-09-30 switching back to a
  stale local `main`. Pull `main` rather than checking out old history, and
  keep the key somewhere else too.
- **`gh` has two accounts on the laptop.** `SmilezMedia` is the active one and
  can only read this repo; pushing, opening and merging PRs need
  `gh auth switch -u Shadedev4202k26`.
- **Streamlit started from the Claude app inherits the PATH from before the
  installs**, so pdftk/pdftoppm go missing at Generate until the app (or the
  launcher) reloads PATH.
- Unconfirmed: the two BULK · OG FARMS outdoor hook tags print no price. May be
  intended — compare against a Mac print before calling it a bug.

## Open work, roughly by value

- **Curbside and break/lunch rosters**, shared across computers. Both are
  standalone HTML using `localStorage`, so the roster never leaves one
  browser. The break tracker's sign-in and history are already in Supabase
  (README → Break & lunch tracker); the roster itself is still per tablet, and
  its Break tab's Start / Back are not recorded.
- **Streamlit's `use_container_width` is deprecated** and logs a warning on
  every use; new code uses `width="stretch"`. The old calls will break on a
  future Streamlit upgrade.
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
- **Streamlit Cloud covers the bottom-right corner** with its own controls —
  "Manage app" for the owner, a badge and avatar (137 × 46px) for everyone
  else — outside the app's frame, so app CSS cannot move or hide them. Pinned
  UI has to keep out of that corner; `studio.CLOUD_CSS` does, applied only when
  `st.context.url` is on `*.streamlit.app`. It only shows once deployed.
- **The store is app-wide state.** `studio.context()` owns it (session state
  plus the `?store=` query param); pages read `ctx["store"]` rather than
  drawing their own store picker. `KNOWN_STORES` lists all eight so pages that
  don't need deals still have them with no sheet loaded.
- **The break tracker is configured by string replacement.** Store tools swaps
  the line `const CONFIG = null; // ZB_CONFIG` for the URL, key and store. Keep
  that line exactly as it is; the page says so if it goes missing.
- **Editing `studio.py` or `shell.py` needs a server restart locally** — a
  browser reload re-runs `app.py` but keeps the old imported modules.
- **Testing the CSV upload without a person:** serve the file from a local
  port with CORS for `localhost:8501`, then `fetch` it in the page and set it
  on the uploader's `input[type=file]` with a `DataTransfer`. Streamlit's
  toggles respond to `input.click()`, not to clicking their label from script.
- `tools/strip_logo.py --check` reports whether a re-exported template has
  brought the Smilez wordmark back.

## Settled: the leaked key

The Supabase **anon** key committed on 2026-09-25 (`f93ab28`, emptied in
`786392a`) is still readable in this public repo's history, but it was rotated
before the move to Windows, so it no longer opens anything. The app now uses a
publishable key, which is meant to be public.

Two things follow from that key being public:

- `deal_sheets` still lets it read, write and delete, so anyone who pulls the
  key out of the break tracker's page could wipe the stored weeks. They are
  re-uploadable, so this was accepted rather than locked down.
- The break tracker tables were designed for it: history is insert-only and the
  database stamps the time. See README → Break & lunch tracker.

If the key is rotated again, update Streamlit Cloud's secrets and each
machine's `.streamlit/secrets.toml`, and re-download the break tracker on every
tablet that runs a downloaded copy — the key is baked in at download time.
