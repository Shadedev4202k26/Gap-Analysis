"""The "Dutchie names" tab of Transfer check.

Lists each product on the manifest once, with the Dutchie name to enter it
under. Only an exact match is pre-approved; anything else is a suggestion that
somebody has to tick (or type over) first. Approved names can be remembered, so
the same wording is an exact match next time.
"""
import re
from io import BytesIO

import pandas as pd
import streamlit as st

import live_stock
import naming

_deps = {}
_BADGE = {"exact": "✅ Exact", "suggested": "🟡 Check it", "none": "🔴 Type it"}


def configure(**kw):
    """context (-> studio.context())."""
    _deps.update(kw)


@st.cache_resource(ttl=900, show_spinner=False, max_entries=2)
def _catalog(_db, stores):
    """Every product name any store has in Dutchie right now."""
    names = set()
    for s in stores:
        got = live_stock.latest(_db, s)
        if got and "Product" in got[0].columns:
            names.update(got[0]["Product"].dropna().astype(str).unique())
    return naming.Catalog(sorted(names)), len(names)


def _amount(q):
    m = re.match(r"\s*([\d,]*\.?\d+)\s*(\S*)", str(q or ""))
    return (float(m.group(1).replace(",", "")), m.group(2)) if m else (0.0, "")


def _groups(rows):
    """One line per product wording, in manifest order: packages and total quantity."""
    out = {}
    for r in rows:
        if not r.get("item"):
            continue
        g = out.setdefault(r["item"], {"item": r["item"], "packages": 0, "qty": 0.0, "unit": "",
                                       "sender": r.get("sender", "")})
        n, u = _amount(r.get("qty"))
        g["packages"] += 1
        g["qty"] += n
        g["unit"] = g["unit"] or u
    return list(out.values())


def _qty_text(g):
    q = f"{g['qty']:g}"
    return f"{q} {g['unit']}".strip()


def render(rows, sig):
    ss = st.session_state
    st.markdown("**Dutchie names for this transfer.** Exact matches are ready. "
                "Everything else is a suggestion: tick it when it is right, or change the name first. "
                "Nothing is approved for you.")
    groups = _groups(rows)
    if not groups:
        st.info("This manifest has no product names in it (pasted tags, or a file without an Item "
                "column). Upload the manifest PDF or the Metrc download to get names.")
        return

    ctx = _deps["context"]()
    db = ctx["db"]
    if db is None:
        catalog, n_names = naming.Catalog([]), 0
        st.warning("No Supabase connection, so there are no Dutchie names to compare with. "
                   "Every name has to be typed.")
    else:
        catalog, n_names = _catalog(db, tuple(ctx["stores"]))
        st.caption(f"Compared with {n_names:,} product names now in Dutchie across the stores.")

    if ss.get("tn_mem_bust", 0) != ss.get("tn_mem_seen", -1) or "tn_mem" not in ss:
        ss["tn_mem"], ss["tn_mem_err"] = naming.memory_load(db)
        ss["tn_mem_seen"] = ss.get("tn_mem_bust", 0)
    memory = ss["tn_mem"]
    if ss.get("tn_mem_err"):
        st.caption("Approved names can't be remembered yet (the names table isn't set up), "
                   "so each transfer starts fresh. See README → Transfer names.")

    sug = [naming.suggest(g["item"], catalog, memory, g["unit"]) for g in groups]
    table = pd.DataFrame({
        "Approved": [s["status"] == "exact" for s in sug],
        "Metrc item": [g["item"] for g in groups],
        "Packages": [g["packages"] for g in groups],
        "Qty": [_qty_text(g) for g in groups],
        "Dutchie name": [s["name"] for s in sug],
        "How sure": [_BADGE[s["status"]] + (f" · {s['note']}" if s["status"] != "exact" else f" · {s['note']}")
                     for s in sug],
        "Similar in Dutchie": [" · ".join(s["near"]) for s in sug],
    })
    edited = st.data_editor(
        table, key=f"tn_editor_{abs(hash(sig))}", hide_index=True, width="stretch",
        num_rows="fixed",
        disabled=["Metrc item", "Packages", "Qty", "How sure", "Similar in Dutchie"],
        column_config={
            "Approved": st.column_config.CheckboxColumn("Approved", width="small",
                                                         help="Tick when the Dutchie name is right."),
            "Dutchie name": st.column_config.TextColumn("Dutchie name", width="large",
                                                         help="Click to change it."),
            "Metrc item": st.column_config.TextColumn(width="large"),
        })

    ok = edited[edited["Approved"] & edited["Dutchie name"].str.strip().ne("")]
    look = len(edited) - len(ok)
    st.markdown(f"**{len(ok)} approved** · {look} still to check" if look else
                f"**All {len(ok)} approved**")

    entries = [(g["item"], str(n).strip(), g["sender"])
               for g, n, a in zip(groups, edited["Dutchie name"], edited["Approved"])
               if a and str(n).strip()]
    out = pd.DataFrame({
        "Dutchie name": edited["Dutchie name"], "Metrc item": edited["Metrc item"],
        "Packages": edited["Packages"], "Quantity": edited["Qty"],
        "Approved": edited["Approved"].map({True: "Yes", False: "NOT APPROVED"})})
    buf = BytesIO()
    out.to_excel(buf, index=False, sheet_name="Dutchie names")
    c1, c2 = st.columns(2)
    c1.download_button("⬇️  Download the list (Excel)", key="tn_dl", data=buf.getvalue(),
                       file_name="dutchie-names.xlsx", width="stretch",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if c2.button("Remember the names I approved", key="tn_save", width="stretch",
                 disabled=not entries or bool(ss.get("tn_mem_err")),
                 help="Next time this exact wording comes in, its name is filled in as an exact match."):
        try:
            naming.memory_save(db, entries)
            ss["tn_mem_bust"] = ss.get("tn_mem_bust", 0) + 1
            st.success(f"Remembered {len(entries)} names.")
        except Exception as e:                                # noqa: BLE001
            st.error(f"Couldn't save them: {e}")
