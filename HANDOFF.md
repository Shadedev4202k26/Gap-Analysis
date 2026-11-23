# Where this is up to — 2026-11-23

`README.md` covers setup (macOS and Windows) and how the app works. This is the
state of play. The live app is `main` at https://ziggyz.streamlit.app.

## Everything is merged

Every PR up to #109 is in `main`; nothing is open. (Numbers 78, 79, 81–83 are
the morning GitHub issues Power Automate opens, not PRs.) Since the last
handoff (#17, 2026-10-22):

- **Store first (#24, #25):** nothing opens until a store is picked; the store
  rides in the URL (`?store=Wayne`), so each tablet bookmarks its own link
  (Settings → Store links).
- **Shelf tags is the only tag maker:** split tags, two strains per preroll tag
  (#27); the classic Hook / Preroll pages are retired and their old links open
  Shelf tags (#29); Custom tags is its own page with Sale price and Bubble
  columns (#26, #30, #32).
- **Sale bubbles turn themselves back on (#84):** whenever Shelf tags or Custom
  tags is opened from another page, and on *Start a new batch*, with a yellow
  warning on every step while they are off. A store's bulk bubbles "stopped
  printing" because the switch had been left off all day.
- **Live stock (#36):** Smilez Reports pushes each store's Dutchie stock to
  Supabase every ~15 min (`live_stock.py`); Shelf tags, Inventory balance,
  Aging stock and Strain Sniffer read it. CSV upload still works as a backup.
- **Deals sheet from Smilez Reports (#40):** the weekly sheet uploaded in
  Reports reaches ZiggyBot by itself; Brands of the Month and brand nicknames
  are read (#34, #35, #37).
- **Aging stock:** one line per Metrc package (#19), an age slider starting at
  90 days (#42).
- **Inventory balance is now a Missing Stock Check (#51–#60):** only zeros,
  products with nothing on the selling floor while a vault has some, as a
  short printable list with "how to work it" steps. Rules live in
  `balance_report.py`:
  - left out to start: bulk deli flower, accessories, apparel, promo,
    vaporizer batteries, retired SKUs, the Red/White/Blue tiers, Secret Stash
    (and its infused flower), Outdoor Flower, -Infused Flower, -Infused Shake.
    Plain "Shake" is still checked.
  - every store compares Sales Floor + Vault; Wayne also Curbside Room +
    Upstairs Vault.
  - a minimum-stock slider (all rooms together): Wayne starts at 20, others at
    0; every store can slide to 0.
- **Daily "Replenishment needed" emails (#73, #75, #77):** `store_mailer.py`
  builds the same lists every morning in GitHub Actions
  (`.github/workflows/replenishment.yml`) and drops one PDF per store, plus an
  All stores PDF, into Dropbox `/Replenishment`. Chad's Power Automate flow
  emails each file (addresses live only in the flow, never in this public
  repo). Start: a second flow opens a GitHub issue "Send replenishment lists"
  at 6:00, 7:00 and 8:00 AM Eastern (the later two are backups; the flow
  skipped its very first 6:00 run on 11/17). GitHub's own timer ran hours
  late 11/11–11/16, so its runs are only a further backup, and `--once-a-day`
  makes every run after the first send do nothing. On 11/18 and 11/19 the
  6:00 run sent and the rest did nothing, as intended. Goal: managers have
  their list by 9 AM.
- **Strain lookup / Strain Sniffer (#49, #62–#76):** the store's own Dutchie
  listings first; matching customers to products on our shelves by terpenes,
  with photos, "Popular here", potency filter, an AI double-check, and a
  demand report in Settings.
- **Strain type check (#72, #80)** in Settings: products with no type in
  Dutchie or the opposite of the usual type, with an Excel download to work
  through (a Done column). A store's stock under 5 units isn't listed: a few
  stray units are often "sad" items (can't be sold), not worth fixing. The
  catalog manager uses this and Strain lookup before entering products in
  Dutchie, so accuracy comes first.
- **Usage (#22, #23, #31, #46, #47, #61)** in Settings: a heat map of which
  stores use which tools. **Downloads went uncounted from 2026-11-02 to
  2026-11-09** (see "Things that cost time to learn"), so Shelf tags showed 0
  jobs for that week; those counts are lost. Old classic-page jobs now count
  under Shelf tags. Two Corunna "Downloaded Missing_Stock" lines on 11-09 are
  test clicks.
- **What's new pop-up (#20, #29):** opens once per visit on every page except
  Settings; entries retire themselves on their `until` date (`whats_new.py`).
- **Small ones since 11-19:** Aging stock can pick several categories or leave
  some out (#90, with a What's new entry); the What's new note for the sale
  bubbles coming back each visit is written (#89); Shelf tags CSV reads a
  strain type Dutchie wraps as `="Sativa"` (#103).
- **Transfers (#104–#109, 2026-11-23)** — Stock → *Transfers*
  (`transfer_scan.py`). A store manager asked for a way to tick a Metrc
  manifest off as the blue tags are scanned (Jacob Eyde, inventory manager,
  does it in Excel today, with a duplicates rule on two columns). The store
  drops in the manifest — the **PDF that comes with the delivery**, or Metrc's
  xlsx / csv download, or pasted tags — and scans each tag. Green = on the
  manifest, yellow = scanned again, red = not on the manifest; a **scan log**
  (newest first, also a sheet in the Excel download) records every scan. The
  cursor stays in the scan box (see the guard under "Things that cost time").
  Scans are **saved as they go** under store + the manifest's tags
  (`scan_store.py`, table `transfer_scans`): after a refresh or a sleeping
  tablet, drop the same manifest in again and "Picked up where this transfer
  left off" brings them back. A file that holds many transfers (Metrc's
  Packages-Transferred report had 100) asks which one is on the truck.
- **Dutchie names tab** (same page; `naming.py`, `transfer_names.py`, table
  `transfer_names`). Jacob types each product's Dutchie name by hand
  ("Infused Jeeter 1g Sugar Plum" → "Jeeter | Sugar Plum | 1G Rosin Diamond
  Infused Preroll"). There are no written rules, so the names already in
  Dutchie (every store's live stock) are the rulebook. Each product is
  **Exact** (pre-ticked: exactly one existing Dutchie product fits on brand,
  strain, size and kind, or wording a person approved before), **Check it** (a
  name built from how that brand's other products are written) or **Type it**
  (brand not recognised); only Exact is ever ticked for the user, every name is
  editable, and "Remember the names I approved" saves them. Loose flower
  shipped by weight (grams, not `ea`) is named `BULK | Brand | Strain`.
  Scored on seven real manifests (135 products already in Dutchie): 114 Exact
  and none wrong; hiding each product in turn and asking for it back, 112
  rebuilt exactly. What it can't know: Hyman puts "Eclair" last and its stylus
  names add a flavour, Jeeter's "Rosin Diamond" isn't on the manifest.

## Waiting on people, not code

- **Shake and bulk bubbles:** Dutchie's plain "Shake" category matches no
  standing bulk deal, so shake products never get a bulk bubble (≈40–45 at
  Quincy and Burton). Chad hasn't said yet whether Shake should get BUY 5 /
  15% OFF like flower (`deals.BULK_DEALS`).
- **Transfers has never been tried at a store with a real scanner.** Run
  one real transfer (Jacob or a manager), then write its What's new entry.
  Scanners that send no Enter, or send stored scans in a burst, are handled
  (see "Things that cost time"); worth confirming with the real device.
- **Jacob's case rules.** His check-in sheet shows "25 (1 Case)" / "64 (2
  Cases)" and a Curb / Sales split per product. The names tab shows only
  Metrc's quantity; case sizes need his rules before they can be built.
- **Metrc access.** Chad is asking for view-only access to current transfers.
  If it is ever turned into an API job: a dedicated view-only Metrc user per
  license, keys on the Smilez Reports server (not in this public repo), and
  keep the manifest upload as the fallback.
- **Not confirmed done, from October:** a real manager's first break-tracker
  sign-in; the first live support request; each store tablet bookmarking its
  store link. Check before repeating them.

## Small clean-ups

- Merged remote branches still on GitHub: `bubbles-default-on`,
  `replenishment-morning-trigger`, `replenishment-retries`,
  `sniffer-come-back`, `sniffer-sharper-match`, `store-zero-report-mailer`.
  Safe to delete once no other session is working in them.
- 14 calls to the deprecated `use_container_width` remain in `app.py` and
  `studio.py`; new code uses `width="stretch"`.

## How changes ship

1. Branch from an up-to-date `main`.
2. `gh auth switch -u Shadedev4202k26` (SmilezMedia can only read this repo),
   push, `gh pr create`.
3. Merge only when Chad says "merge it", then delete the branch and
   `gh auth switch -u SmilezMedia`.
4. Chad usually asks for a What's new entry for anything stores will notice.
5. The live app picks up a merge in about 4 minutes. Load a page that uses the
   new code before calling it done.

## First thing on a new machine

1. Install the tools — **README → Running it locally**. On Windows the two
   command-line dependencies (pdftk, pdftoppm) are the fiddly part; check
   `pdftk --version` and `pdftoppm -v` both answer before running the app.
2. Create `.streamlit/secrets.toml` from Supabase → Project Settings → API.
   It is gitignored and does not travel with the repo. The project is
   **Ziggybot** (ref `zorfzlsixtmrxaaitpyt`), under the **SmilezMedia**
   Supabase login — not the Shadedev4202k26 one, whose projects (ziggyretail,
   tenthcard) are different apps. Direct link to its SQL editor:
   https://supabase.com/dashboard/project/zorfzlsixtmrxaaitpyt/sql/new
3. `.venv/bin/python tools/check_supabase.py` (`.venv\Scripts\python` on
   Windows) — proves storage works end to end without printing the key.
4. `.venv/bin/python tools/smoke_tags.py "<a weekly deals sheet>"` — builds every
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
- **Git reaches GitHub on port 443, not 22.** Port 22 to github.com timed out
  on the laptop's network more than once (2026-10-01 and 10-20, leaving a push
  hanging), so `~/.ssh/config` sends `github.com` to `ssh.github.com:443` —
  GitHub's own SSH endpoint for this, same key, same remote URL — with a 15 s
  connect timeout so a dead network fails fast. It is machine config, not in
  the repo; a new machine needs the same block:

  ```
  Host github.com
      Hostname ssh.github.com
      Port 443
      User git
      IdentityFile ~/.ssh/id_ed25519
      ConnectTimeout 15
  ```
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
- **Being told about new support requests.** Today they wait in Settings until
  someone looks. An email per request needs an email-sending service (none is
  set up); a count on the Settings link would be the cheap version.
- **Scanner trial.** A browser can't see a connected scanner; most act as a
  keyboard. No Enter, Tab instead of Enter, and fast bursts of stored scans
  are handled and were tested with real key presses, but not with a real
  scanner. A scanner in a different "mode" (serial / POS rather than keyboard)
  would not type into the page at all.
- **Case counts and the Curb / Sales split** on the Dutchie names tab (needs
  Jacob's rules, above).
- **A draft flag for a stored week.** A sheet still being written becomes the
  printing week automatically at midnight on its start date.
- `video.mp4` and `image.png` are unreferenced since the hero became a bar —
  4.3MB carried in every clone and deploy.

## Things that cost time to learn

- **The deployed app is `main`.** Several "something broke" reports turned out
  to be fixes that had never been merged. Check the branch before believing a
  regression.
- **A merge can deploy half-way.** On 2026-10-21 Streamlit Cloud ran #13's new
  `app.py` against the `deals` module it had imported before the merge, so
  `deals_mod.upload_types()` raised AttributeError on the classic tag pages
  while `main` itself was correct. `app._fresh_local_modules` now reloads any
  local module whose file is newer than the copy in memory (and each one once
  per new process). An AttributeError on a function that exists on `main` means
  a stale module: if it ever recurs, **Manage app → ⋮ → Reboot app** clears it,
  and any new local module belongs in that function's list. After a merge,
  load one page that uses the new code on the live app before calling it done.
- **Never wrap a Streamlit function only once.** `usage.track_downloads`
  wraps `st.download_button` to count downloads. A deploy reloads our modules
  but keeps `st`, so a wrapper made once (guarded by a flag) kept calling the
  old copy of `usage.log()`, which failed silently: no download was counted
  for a week, and only a full restart would have fixed it. It is now wrapped
  on every run around Streamlit's own button (`_zb_original`). Test this kind
  of thing by editing the file while the app runs, not just on a fresh start.
- **A session setting outlives the moment.** Store tablets keep ZiggyBot open
  all day, so a switch turned off once stays off for every later batch. Reset
  anything risky when its page is opened (`studio._fresh_visit`).
- **One sheet section, one family.** `deals.SECTION_FAMILY` and
  `CATEGORY_FAMILY` must split wherever the sheet splits, or a deal crosses
  into the other half of a brand that sells both — that was #11, where both
  preroll sections were "preroll" and both cart sections "cart". If the sheet
  ever gains a section (infused flower, say), add a family for it and map the
  categories. The one category that can't be read alone is `Vape Carts (MISC)`
  (carts, disposables, pods and all-in-ones together): its carts may take
  either cart section's deals, everything else there only the disposable
  section's — `deals.row_families`.
- **Custom tags have no category, so they must not guess.** Rows typed by
  hand carry only brand, strain, THC and price. They take a family from the
  page (`family_hint`: the Preroll page and Shelf tags' preroll formats), then
  from a product word on the *brand* line — never the strain, which can be
  "Orange Gummi". With neither, `deals.for_row` keeps only a deal whose size
  is on the tag, or Brands of the Week. An unrecognised POS category
  (accessories, batteries) falls under the same rule.
- **The sheet's layout drifts week to week.** 9/28 wrote "Brands of the Week
  25% OFF" with bare brand names under it; 10/5 wrote the header with no
  percentage and one dated line per brand ("50% OFF Jungle Juice Oct 1-31").
  `deals.parse_column` reads both; month dates are stripped from brands
  (`MONTH_DATES`), and "(Excludes …)" becomes `Deal.excludes`. When a new
  sheet arrives, parse it and read the deal list before trusting the tags —
  the 10/5 change silently turned eight brand-wide deals into flower-only ones.
  "Mr Vapor Soar" is all Mr Vapor: for them category and size decide.
- **The deals workbook is a working file, not just the sheet.** The 10-19-26
  one has seven tabs — `Deal.` plus an inventory snapshot and Deal Map, Deal
  Rules, Deal Check, To Review and Changes — kept by whatever the deals team
  uses to maintain it. Reading every tab (pandas `sheet_name=None`) put their
  columns D, E and F into Quincy, Reading and Sturgis as extra deal lines, so
  `deals._xlsx_rows` reads the first tab only, and only as many columns as
  there are store names in row 1. Its **Changes** tab is worth reading when a
  deal looks odd: it says why each line changed — out-of-stock brands are
  *removed* ("Out: Boutiq – Removed – still out (0 sellable)"), while a strike
  marked Amnesia as covered by Brands of the Week instead. Either way struck
  text is left out (`openpyxl`, `rich_text=True`, whole-cell and per-run).
  Uploads are .xlsx-only from `deals.CSV_LAST_DAY`, because a CSV loses the
  strike; the tests and tools still read CSV directly.
- **Ziggy's top-bar run is real animation in two strips, not code.** Higgsfield
  Nano Banana Pro redrew the artwork as a side view; Kling 4.0 animated it
  running and munching on white; `tools/ziggy_frames.py` cuts the white away
  (`.copy()` before `floodfill`, or it silently does nothing) and writes
  `static/ziggy-run.webp` and `static/ziggy-munch.webp`, served by
  `enableStaticServing` (a server setting, read at start-up). Refer to them as
  `app/static/…`, **relative**: Streamlit Cloud runs the app in a frame under
  `/~/+/`, so `/app/static/…` returns the Cloud wrapper page (`text/html`)
  instead — #16. `ziggy.py` times bites to the video's jaw snaps and
  hard-codes where the wordmark sits (`LOGO_LEFT`): change the avatar, the "×"
  or the wordmark and the bites miss — re-measure it. Ziggy must also hide at
  exactly the wordmark's breakpoint (`max-width: 768px` in studio.CSS): at 900px
  an iPhone held sideways (~844px) showed the logo being eaten by nobody (#17).
  A merge took ~4 min to reach the live app on 10-22 — wait before calling a
  fix missing. Higgsfield's AutoSprite
  failed every time on 2026-10-21 (refunded); still images and Kling worked.
- **"Off" has to mean off.** The deals switch used to drop only the weekly
  sheet, leaving the standing bulk deals and shelf badges, which made it look
  broken on exactly the tags that had a category. Any future "hide X" switch
  should hide every kind of X.
- **To check a deals change, diff every tag.** Run the week's sheet against
  every store and every local export before and after, and read each group of
  changes; `tools/smoke_tags.py` holds the cases that have gone wrong before.
  #11 changed 544 of 30,960 store × product deals, and the first attempt's
  diff is what caught Platinum's and Church's MISC carts losing real deals.
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
- **Editing a local module locally** is picked up on the next page load since
  #14; before it, `studio.py` and `shell.py` edits needed a server restart.
- **Brand-line descriptors live in one list**, `BRAND_DESCRIPTORS` in
  `build_tag_rows` (`app.py`). An entry matches singular or plural and any
  spacing ("Melted Diamond", "Melted-Diamonds"). Before adding one, run every
  local export through `build_tag_rows` before and after and diff: Melted
  Diamonds changed exactly 14 of 4,520 tags, and a too-short word ("melted")
  would have hit the strain "Melted Strawberries".
- **Checking a new Supabase table without leaving rows:** send a request
  that's refused for permissions (`42501`) or for bad data (`23514`). Data is
  only checked once the permission has passed, so `23514` proves the insert is
  allowed without saving anything. Used for the break and support tables.
- **Testing the CSV upload without a person:** serve the file from a local
  port with CORS for `localhost:8501`, then `fetch` it in the page and set it
  on the uploader's `input[type=file]` with a `DataTransfer`. Streamlit's
  toggles respond to `input.click()`, not to clicking their label from script.
- `tools/strip_logo.py --check` reports whether a re-exported template has
  brought the Smilez wordmark back.
- **Manifest PDFs read in pieces.** `pypdf` hands back a tag split over several
  lines ("1 / A / 4050300020 / B / 0 / F / 000380885") with page headers
  landing between the pieces, and every package lists its **Source Package(s)**
  tags too. `transfer_scan._pdf_rows` reads each tag off the end of the text
  just before its "Lab Test:" line, spaces removed; read any other way, source
  tags count as packages on the truck. The same trap is in the xlsx: take the
  "Package" column, never "Source Package". Check a new template against the
  heading count (`N. Package | Accepted` or `| Shipped`). Fixes for font splits
  (". 7 G", "Pre- Roll") are in the same function.
- **The scan box is run by a script in the page, not by Streamlit's text box.**
  A scanner is a very fast keyboard, and Streamlit's box empties itself a
  moment after each send, so a tag typed in that moment was lost or sent twice
  (a quick burst of ten tags with Enter gave mangled and doubled entries).
  `GUARD_JS` in `transfer_scan.py` therefore catches the keys itself: they go
  into a buffer kept in the script (the box only mirrors it), Enter or a 250 ms
  pause once the buffer holds whole 24-character tags (so no Enter needed)
  sends everything in one piece: the box is set to those tags and Check is
  pressed, and `split_scans` cuts several tags apart. Hand typing (last digits,
  Backspace, Escape, paste) still works; other text boxes and other tabs are
  left alone. Two Streamlit details: the form's first button is the "?" help
  icon, so the submit button is found by `data-testid` ending `FormSubmit`; and
  the script is put into the parent document as `<script id="ts-guard">`,
  because Streamlit replaces `components.html`'s frame on every rerun and code
  from a dead frame can't be called (Firefox: "dead object"). To test it, send
  real key presses (`computer key "1 A 4 …"`, at most 100 keys per call; use
  `browser_batch` for more): the browser tool's `type` inserts text without key
  events and can't trigger it. Tested: no Enter, Enter, three tags with no
  separator, ten tags with Enter in a row, half a tag then the rest, click away
  then scan, Backspace, and typing in the paste box.
- **Don't use the server's clock for times people read.** Streamlit Cloud
  servers are expected to keep UTC (not checked online), so `time.strftime`
  would show scan times hours off there while looking right on the laptop. It
  was caught before it shipped; use a `ZoneInfo("America/Detroit")` clock
  (`transfer_scan.now_text`, `live_stock.STORE_TZ`).
- **Getting Metrc-name ↔ Dutchie-name pairs for free.** Dutchie's Package ID is
  the Metrc tag, so joining a manifest's tags to the live stock (all stores)
  gives each product's manifest wording next to its Dutchie name, as long as
  the package is still in stock. That is how `naming.py` was scored. Hide one
  product at a time from the catalog and ask for it back to test "a new strain
  of a brand we carry"; a hidden product with a near-twin (Choice's plain and
  "11pc" gummies) can look wrongly Exact, which is why more than one fit is
  shown as Check it.
- **The Supabase free plan's limits are per organisation.** On 2026-11-23 the
  SmilezMedia org showed "Exceeding usage limits": 1.068 GB of the 1 GB
  *storage*. It was all Smilez Studio's, in the separate "TV Deal Builder"
  project (this app stores no files; its database is under 10% of its limit).
  Studio's own clean-up of its `exports` bucket was running but kept 30 days of
  exports, which is itself about 1 GB; it now keeps 14 (Studio repo,
  `Media-Tools` #1, merged the same day; the clean-up ran at 12:47 PM and
  removed 144 files). Restrictions on the org could hit this app too.
  - **The Usage page lags and can't be trusted for "did it work".** It still
    said 1.066 GB (107%) more than an hour after the clean-up. Ask the database:
    in the TV Deal Builder project's SQL editor,
    `select bucket_id, count(*) as files, round(sum((metadata->>'size')::bigint)
    / 1048576.0) as mb, min(created_at)::date as oldest, max(created_at)::date
    as newest from storage.objects group by bucket_id order by mb desc;`
  - **Measured 2026-11-23 afternoon, after the clean-up:** `assets` (logos and
    artwork) 344 files, 385 MB, from 2026-09-17; `exports` 175 files, 330 MB,
    oldest created 2026-11-06. About 715 MB, roughly 70% of the 1 GB. The clean-up
    only touches `exports`. (`exports` held 175 files while Studio's Files page
    listed 125; the other 50 may have no record; not looked into.)
  - **Watch `assets`.** It grew about 40 MB a week from nothing in nine weeks.
    At that pace the org is back near 1 GB around **mid-January 2027**: a rough
    guess from one number, so run the query again at the end of December. Options
    then: delete unused artwork, have Studio clear unused assets, or Pro (~$25 a
    month, Chad's call).
- **Test rows can't be deleted by the app.** `transfer_names` and
  `transfer_scans` follow the support table's rule (add and update, never
  delete), so a real test write leaves a row; delete it in the Supabase SQL
  editor (the break and support tables were tested without leaving rows, see
  above). Both tables' SQL is in the README and was run on 2026-11-23.

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
- `support_requests` follows the same rules (add, mark done; no edit, delete
  or backdating), but anyone with the key can *read* it — so the form asks
  people to leave out passwords and customer details, and the reply contact is
  optional. See README → Support requests.

If the key is rotated again, update Streamlit Cloud's secrets and each
machine's `.streamlit/secrets.toml`, and re-download the break tracker on every
tablet that runs a downloaded copy — the key is baked in at download time.
