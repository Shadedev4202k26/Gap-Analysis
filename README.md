# ZiggyBot

Streamlit app for Smilez: shelf tags, inventory tools and store utilities.

Runs on Streamlit Cloud from `app.py`. Templates, assets and the tag engine all
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

Needs Python 3.10+ (`streamlit` requires it), plus `pdftk` and `poppler` for the
tag builders:

```bash
brew install python@3.12 pdftk-java poppler
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

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
