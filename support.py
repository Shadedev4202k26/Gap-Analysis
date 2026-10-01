"""Request support: the sidebar button, its window, and the Settings inbox.

Anyone using the app can report a problem or suggest something without
leaving it. The window offers two ways and both reach Chad: a short form saved
to Supabase and reviewed under Settings → Support requests, or an email
pre-filled with whatever was typed.

Requests are kept like the break tracker's history: the app's key can add them
and mark them done, never edit or delete them, and the database stamps the
time. The key is public (it sits in the break tracker's page), so the form
asks people not to put anything private in it.

Table and policies: README → "Support requests".
"""
import datetime
from urllib.parse import quote

import streamlit as st

TABLE = "support_requests"
EMAIL = "chad@shopsmilez.com"
KINDS = ["Something's not working", "Suggestion", "Question"]
MESSAGE_MAX = 4000

_deps = {}


def configure(**kw):
    """init_db, context (-> {'store'}), page_title (-> str)."""
    _deps.update(kw)


class StoreError(RuntimeError):
    """Supabase refused the call — usually the table has not been created."""


def submit(db, kind, message, name="", contact="", store="", page=""):
    try:
        db.table(TABLE).insert({
            "kind": kind, "message": message.strip()[:MESSAGE_MAX],
            "name": name.strip()[:80], "contact": contact.strip()[:120],
            "store": (store or "")[:60], "page": (page or "")[:80]}).execute()
    except Exception as e:                                   # noqa: BLE001
        raise StoreError(str(e)) from e


def requests(db, status=None, limit=500):
    try:
        q = db.table(TABLE).select("*")
        if status:
            q = q.eq("status", status)
        return q.order("at", desc=True).limit(limit).execute().data or []
    except Exception as e:                                   # noqa: BLE001
        raise StoreError(str(e)) from e


def set_status(db, request_id, status):
    try:
        db.table(TABLE).update({"status": status}).eq("id", request_id).execute()
    except Exception as e:                                   # noqa: BLE001
        raise StoreError(str(e)) from e


def _mailto(kind, message, name, store, page):
    body = message.strip() or "(Describe the problem or idea here.)"
    meta = [f"Store: {store}" if store else "", f"Page: {page}" if page else "",
            f"From: {name.strip()}" if name.strip() else ""]
    body += "\n\n—\n" + "\n".join(m for m in meta if m)
    subject = f"ZiggyBot — {kind}" + (f" ({store})" if store else "")
    return f"mailto:{EMAIL}?subject={quote(subject)}&body={quote(body)}"


def button():
    """The sidebar entry, under Settings."""
    with st.container(key="zbsupport"):
        if st.button("Request support", icon=":material/support_agent:",
                     width="stretch", key="zb_support_open"):
            _window()


@st.dialog("Request support", width="large")
def _window():
    ss = st.session_state
    store = (_deps["context"]() or {}).get("store") or ""
    page = _deps["page_title"]() if _deps.get("page_title") else ""

    if ss.pop("zb_support_sent", False):
        st.success("Thanks — your request is in. Chad reads every one. If it's urgent, "
                   f"email **{EMAIL}** as well.")
        if st.button("Send another", key="zb_support_again"):
            st.rerun(scope="fragment")
        return

    st.markdown(
        "Something not working, a tag printing wrong, or an idea that would make "
        "ZiggyBot easier to use? **Tell us — no request is too small.** Every one "
        "is read.")

    kind = st.segmented_control("What is it?", KINDS, default=KINDS[0],
                                key="zb_support_kind") or KINDS[0]
    message = st.text_area(
        "What happened, or what would help?", key="zb_support_msg", height=150,
        max_chars=MESSAGE_MAX,
        placeholder="e.g. The Wayne hook tags printed the old price for Glacier Heavy Z. "
                    "Or: it would help if the break tracker showed who is late back.")
    c1, c2 = st.columns(2)
    name = c1.text_input("Your name (optional)", key="zb_support_name", max_chars=80)
    contact = c2.text_input("Phone or email for a reply (optional)",
                            key="zb_support_contact", max_chars=120)
    st.caption(f"Sent with: **{store or 'no store'}** · **{page or 'this page'}**. "
               "Please don't include passwords or customer details.")

    db = _deps["init_db"]()
    b1, b2 = st.columns(2)
    with b1:
        sent = st.button("Send in ZiggyBot", type="primary", icon=":material/send:",
                         width="stretch", key="zb_support_send",
                         disabled=db is None or not message.strip())
    with b2:
        st.link_button("Email Chad instead", _mailto(kind, message, name, store, page),
                       icon=":material/mail:", width="stretch")
    if db is None:
        st.caption(f"Sending in ZiggyBot isn't available right now — please email "
                   f"**{EMAIL}**.")
    if sent:
        try:
            submit(db, kind, message, name, contact, store, page)
        except StoreError as e:
            st.error("Couldn't send that in ZiggyBot — please use **Email Chad instead** "
                     f"so it isn't lost. (`{e}`)")
            return
        for k in ("zb_support_msg", "zb_support_name", "zb_support_contact"):
            ss.pop(k, None)
        ss["zb_support_sent"] = True
        st.rerun(scope="fragment")


def settings_inbox(tz_name):
    """Settings → Support requests: newest first, open ones on top."""
    from zoneinfo import ZoneInfo
    import pandas as pd

    st.markdown('<div class="cat-hdr">📬 Support requests</div>', unsafe_allow_html=True)
    db = _deps["init_db"]()
    if db is None:
        st.warning("No Supabase connection — support requests live there.")
        return
    try:
        rows = requests(db)
    except StoreError as e:
        st.error("The support requests table isn't set up in Supabase yet — run the SQL "
                 f"in README → **Support requests**. (`{e}`)")
        return

    open_rows = [r for r in rows if r["status"] == "open"]
    st.markdown(f"Sent from the **Request support** button. **{len(open_rows)}** open"
                f" · {len(rows) - len(open_rows)} done. Mark one done once it's dealt "
                "with; nothing here can be deleted.")
    if not rows:
        st.caption("Nothing yet.")
        return
    show_done = st.toggle("Show done ones too", key="zb_sup_done")
    tz = ZoneInfo(tz_name)
    for r in rows if show_done else open_rows:
        at = datetime.datetime.fromisoformat(str(r["at"]).replace("Z", "+00:00")).astimezone(tz)
        when = f"{at:%b} {at.day}, {at.hour % 12 or 12}:{at:%M %p}"
        who = " · ".join(x for x in (r.get("name"), r.get("store"), r.get("page")) if x)
        with st.container(border=True):
            h1, h2 = st.columns([5, 1.3], vertical_alignment="center")
            h1.markdown(f"**{r['kind']}** · {when}" + (f" · {who}" if who else "")
                        + ("  ·  :green[done]" if r["status"] == "done" else ""))
            nxt = "open" if r["status"] == "done" else "done"
            if h2.button("Reopen" if nxt == "open" else "Mark done", key=f"zb_sup_{r['id']}",
                         width="stretch"):
                try:
                    set_status(db, r["id"], nxt)
                except StoreError as e:
                    st.error(f"Could not update: {e}")
                else:
                    st.rerun()
            st.text(r["message"])
            if r.get("contact"):
                st.caption(f"Reply to: {r['contact']}")
    df = pd.DataFrame(rows)[["at", "status", "kind", "store", "page", "name", "contact",
                             "message"]]
    st.download_button("⬇️  Download all as CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name="support-requests.csv", mime="text/csv",
                       key="zb_sup_csv")
