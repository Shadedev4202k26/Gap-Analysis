# ZiggyBot

Streamlit app for Smilez: shelf tags, inventory tools and store utilities.

Runs on Streamlit Cloud at https://ziggyz.streamlit.app, deployed from
`app.py` on `main` — a change is not live until it is merged there. Templates, assets and the tag engine all
live at the repo root because the app imports them by bare name.

```
/            app.py preroll_tags.py combine_tags.py build_dual.py
             deals.py deal_store.py sale_badges.py build_split.py
             packages.txt requirements.txt
             *.pdf (9 tag templates)  smilez-wordmark-white.png  *.html
/tools/      strip_logo.py build_wide.py build_hook.py tune_text.py
```

`tools/` is build-time only and never imported by the app.

## Running it locally

Needs Python 3.10+ (`streamlit` requires it), plus two command-line tools the
tag builders shell out to: **pdftk** fills the template forms and **pdftoppm**
(from poppler) rasterises pages for the mixed-type sheets. Both must be on PATH
or the builders fail at the point of generating a PDF, not at startup.

### macOS

```bash
brew install python@3.12 pdftk-java poppler
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

### Windows

Use **pdftk-java**, the same pdftk as macOS and Streamlit Cloud. Do not install
PDFtk Server (`PDFLabs.PDFtk.Server` in winget): it is the old 2.02 native build
and cannot fill these templates at all — every builder fails with
`Unhandled Java Exception in create_output(): java.io.CharConversionException`,
even for plain ASCII text. pdftk-java is not in winget, so it needs a Java
runtime plus the jar. In PowerShell:

```powershell
winget install --id Python.Python.3.12 -e
winget install --id EclipseAdoptium.Temurin.21.JRE -e
```

Download `pdftk-all.jar` from the latest
[pdftk-java release](https://gitlab.com/pdftk-java/pdftk/-/releases) into
`C:\pdftk-java`, create `C:\pdftk-java\pdftk.cmd` containing

```bat
@echo off
java -jar "%~dp0pdftk-all.jar" %*
```

and add `C:\pdftk-java` to PATH. `preroll_tags.py` looks pdftk up with
`shutil.which`, which is what lets it find a `.cmd` wrapper at all.

poppler is not in winget. Download the latest `Release-*.zip` from
[oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases),
unzip it somewhere permanent such as `C:\poppler`, and add its `Library\bin`
folder to PATH. Then:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\streamlit run app.py
```

**pdftk is not optional.** `preroll_tags._fill_template` shells out to it to
fill the template forms and there is no fallback, so every builder needs it.
The app starts happily without it and fails only when you press Generate, which
is why it is worth checking both tools are visible first:

```powershell
pdftk --version
pdftoppm -v
```

Note the venv layout differs: `.venv\Scripts\` on Windows against
`.venv/bin/` on macOS. Every command in this README that starts `.venv/bin/`
becomes `.venv\Scripts\` on Windows.

### Local secrets

`streamlit run` reads `.streamlit/secrets.toml`, which is gitignored and must be
created by hand on each machine — see **Weekly deals storage** below. Without it
the app still runs; the deals panel says storage is unavailable and explains
why.

## Weekly deals storage

The deals sheet is uploaded once a week and kept in Supabase, so whoever opens
the app next picks a week instead of hunting for the export again. Two weeks are
held: the one being printed, and the one before it — that second week is what
makes "only what changed" answerable.

Without the table the app still works; the deals panel falls back to a
per-session upload and says so.

### Creating the table

1. Open [supabase.com](https://supabase.com), sign in, and pick the project this
   app already uses — the same one behind `SUPABASE_URL` in the Streamlit Cloud
   secrets, the one holding `checklist_tasks` and `messages`.
2. In the left sidebar choose **SQL Editor**, then **New query**.
3. Paste this in and press **Run**:

   ```sql
   create table if not exists public.deal_sheets (
       week_start  date primary key,
       name        text        not null default '',
       payload     jsonb       not null,
       uploaded_at timestamptz not null default now()
   );

   -- Privileges first. RLS policies decide WHICH ROWS a role may see; these
   -- decide whether it may touch the table at all. Creating a table through
   -- the Table Editor adds them for you, raw SQL does not, and without them
   -- every request fails with "permission denied for table deal_sheets".
   grant usage on schema public to anon, authenticated;
   grant select, insert, update, delete on public.deal_sheets to anon, authenticated;

   alter table public.deal_sheets enable row level security;

   -- The app connects with the key in the Streamlit secrets, the same one the
   -- checklist and messages tables use, so that role needs read and write here.
   -- Granted to both roles so it works whichever key is in the secrets.
   -- Dropped first so this whole block can be run again safely.
   drop policy if exists "deal sheets read"   on public.deal_sheets;
   drop policy if exists "deal sheets insert" on public.deal_sheets;
   drop policy if exists "deal sheets update" on public.deal_sheets;
   drop policy if exists "deal sheets delete" on public.deal_sheets;

   create policy "deal sheets read"
       on public.deal_sheets for select to anon, authenticated using (true);
   create policy "deal sheets insert"
       on public.deal_sheets for insert to anon, authenticated with check (true);
   create policy "deal sheets update"
       on public.deal_sheets for update to anon, authenticated
       using (true) with check (true);
   create policy "deal sheets delete"
       on public.deal_sheets for delete to anon, authenticated using (true);
   ```

   This lets anyone holding the app's key read and write the deals sheets, which
   is the same posture as the checklist and messages tables already in the
   project. There is nothing sensitive in a deals export.

4. It should report success with no rows. Check it under **Table Editor** →
   `deal_sheets`.
5. Reload the app. The deals panel should stop showing the "not being saved
   between visits" note.

If your Streamlit secrets hold the `service_role` key, the policies are
unnecessary — that role bypasses row level security — but running them anyway
does no harm, and they are what makes the `anon` key work.

To confirm it worked without touching the app, run this in the SQL Editor; it
should return one row and then remove it again:

```sql
insert into public.deal_sheets (week_start, name, payload)
values ('1999-01-04', 'connection test', '{}'::jsonb);
select week_start, name from public.deal_sheets where week_start = '1999-01-04';
delete from public.deal_sheets where week_start = '1999-01-04';
```

### Using it

* **Upload** — the export's filename sets the week, so keep the date in it
  (`9-28-26 Weekly Deals-Smilez.csv` files under the week of Sep 28). Drop it in
  and press **Save**; anything older than the last two weeks is dropped
  automatically. Re-uploading a corrected export for a week already stored
  replaces it rather than pushing the other week out.
* **Week** — pick which stored week the tags print from. A week that does not
  cover today is flagged in the picker and warned about above the tags.
* **Store** — the export carries a column per location and some deals genuinely
  differ, so tags read the selected store's column.
* **Only what changed** — compares the two stored weeks and prints just the tags
  whose deal is new, different, or has ended. An ended deal counts: that shelf
  tag is still advertising a discount the store no longer honours.

## Break & lunch tracker

`break-lunch-tracker.html` runs under **Store tools**. Its **Admin** tab — adding
associates and changing their breaks — opens only after a manager taps their
name from that store's list. The first time, they type it in and it is added to
the list. There is no PIN: every Admin change is recorded with the manager's
name and the time instead, and reviewed under **Settings → Break & lunch
tracker**, which is also where a typo or a leaver is taken off a store's list.

The roster itself still lives in the tablet's browser; only the manager lists
and the history are in Supabase.

### Creating the tables

Run this in the Supabase **SQL Editor**, the same way as the deals table above.
It is safe to run again.

```sql
create table if not exists public.break_managers (
    id         bigint generated always as identity primary key,
    store      text        not null check (length(store) between 1 and 60),
    name       text        not null check (length(name) between 1 and 40),
    active     boolean     not null default true,
    created_at timestamptz not null default now(),
    unique (store, name)
);

create table if not exists public.break_audit (
    id        bigint generated always as identity primary key,
    at        timestamptz not null default now(),   -- set by the database, never the tablet
    device_at timestamptz,                          -- the tablet's own clock, for comparison
    store     text not null check (length(store)   between 1 and 60),
    manager   text not null check (length(manager) between 1 and 60),
    action    text not null check (length(action)  between 1 and 60),
    detail    text not null default '' check (length(detail) <= 2000),
    device    text not null default '' check (length(device) <= 60)
);
create index if not exists break_audit_store_at on public.break_audit (store, at desc);

-- The app's key is in every tracker page, so it gets the least that works.
-- Managers: read, add, and switch active on or off — never delete, so a
-- removed manager's name still matches their history.
-- History: read and add only. No update, no delete, and `at` and `id` are not
-- insertable, so nothing holding the key can rewrite or backdate a change.
grant usage on schema public to anon, authenticated;
revoke all on public.break_managers, public.break_audit from anon, authenticated;
grant select on public.break_managers, public.break_audit to anon, authenticated;
grant insert (store, name) on public.break_managers to anon, authenticated;
grant update (active)      on public.break_managers to anon, authenticated;
grant insert (device_at, store, manager, action, detail, device)
      on public.break_audit to anon, authenticated;

alter table public.break_managers enable row level security;
alter table public.break_audit    enable row level security;

drop policy if exists "break managers read"   on public.break_managers;
drop policy if exists "break managers insert" on public.break_managers;
drop policy if exists "break managers update" on public.break_managers;
drop policy if exists "break audit read"      on public.break_audit;
drop policy if exists "break audit insert"    on public.break_audit;

create policy "break managers read"   on public.break_managers
    for select to anon, authenticated using (true);
create policy "break managers insert" on public.break_managers
    for insert to anon, authenticated with check (true);
create policy "break managers update" on public.break_managers
    for update to anon, authenticated using (true) with check (true);
create policy "break audit read"      on public.break_audit
    for select to anon, authenticated using (true);
create policy "break audit insert"    on public.break_audit
    for insert to anon, authenticated with check (true);
```

Nothing else to set up: each store's list fills in as its managers sign in.

### What the history can and can't tell you

* **When** is the tablet's clock and **Received** is the database's. The tablet
  can't change Received, so a tablet clock set wrong shows up as "tablet clock
  was ahead", and a change made offline shows as "sent N min late" — the tracker
  holds changes while offline and sends them when the connection is back.
* Signing in is picking or typing a name, not proving it. Anyone at the tablet
  can tap any manager's name or add a new one, and removing someone in Settings
  only takes them off the list — they can type their name again. The history
  makes all of that visible afterwards rather than preventing it.
* A typed name that matches one on the list, ignoring case, signs in as that
  person, so "jess" doesn't become a second Jess. "Jessica" still would.
* The Break tab's **Start** and **Back** buttons are floor actions and are not
  signed in or recorded. Marking a break done or undoing it from **Admin** is.
* The key in the page can add history rows as well as read them, so a row could
  be forged by someone who pulls the key out of the page source. It cannot
  remove or change a real one.
* Clearing the tablet's browser data loses the roster and anything still
  waiting to be sent. Everything already received stays.

## Tags

Three builders, all filling the same nine templates through `pdftk`:

* `preroll_tags.build_separate` — a page per strain type
* `combine_tags.build_combined` — strain types mixed on one page
* `build_dual.build_sheet` — two strains per tag, each half in its own colour

`sale_badges` draws the badges over the filled page: red for a weekly sale,
violet for the standing bulk deals that run every week, plus the cut guides.

The Smilez wordmark is **not** in the templates. It used to be, and covering it
at fill time could not work on the hook tags — it sat in the same band as the
strain, so a patch large enough to hide it clipped large strain text and a patch
small enough to spare the text left a sliver showing. `tools/strip_logo.py`
removes it from the art instead. Re-export a template from Illustrator and you
have to run that script again:

```bash
python tools/strip_logo.py            # rewrite all nine templates in place
python tools/strip_logo.py --check    # report only
```

## Known gaps

* Badges render in Helvetica-Bold, not the tags' embedded Paralucent-Heavy.
* No live deal source. Dutchie's POS API could feed this later, but keys are
  partner-gated and there is no report that exports "products currently on
  sale". Do not build on Dutchie Plus — it is being sunset in 2026.
* Custom tags carry no category, so they get no bulk-deal badge.
