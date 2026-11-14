"""Activity: every N minutes the notch asks what you did in that window.

Pick a category (a note is optional) and the entry is saved in NOOK_DATA_DIR.
The page has three tabs: Log, Today and Insights. The chart button writes a
full HTML dashboard of everything you logged and opens it in your browser.
"""

import datetime
import html
import os
import time

import nook

app = nook.Plugin()

CATEGORIES = [("deep", "Deep work"), ("admin", "Learning / planning"), ("break", "Break / did nothing"),
              ("other", "Other")]
CAT_LABEL = dict(CATEGORIES)
TABS = ["Log", "Today", "Insights"]

data = app.load("activity", {})
settings = {"minutes": 15, **data.get("settings", {})}
entries = data.get("entries", [])        # {"start", "end", "cat", "note"} in epoch seconds
next_at = data.get("next_at")            # when the next prompt is due
pending = data.get("pending", False)     # the prompt is on screen and waiting
pending_since = data.get("pending_since")
rev = data.get("rev", 0)                 # bumped to reset the settings input

tab = 0
note = ""                                # typed note, kept until an entry is saved
note_rev = 0                             # bumped to clear the note input
error = ""
pulse_until = 0
last_tile = None
last_page = None


def save():
    app.save("activity", {"settings": settings, "entries": entries, "next_at": next_at,
                          "pending": pending, "pending_since": pending_since, "rev": rev})


def clock(epoch):
    return time.strftime("%H:%M", time.localtime(epoch))


def fmt(minutes):
    h, m = divmod(int(round(minutes)), 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def duration(e):
    return (e["end"] - e["start"]) / 60


def today_entries():
    now = datetime.datetime.now()
    start = datetime.datetime(now.year, now.month, now.day).timestamp()
    return [e for e in entries if e["end"] > start]


def minutes_for(items, key=None):
    return sum(duration(e) for e in items if key is None or e["cat"] == key)


def record(cat):
    """Saves the window that just ended. The prompt schedule is not changed."""
    global note, note_rev, pending, pending_since, pulse_until
    now = time.time()
    end = pending_since if pending and pending_since else now
    start = end - settings["minutes"] * 60
    if entries:
        start = max(start, entries[-1]["end"])   # never overlap the entry before it
    if end - start >= 60:
        entries.append({"start": round(start), "end": round(end), "cat": cat, "note": note.strip()})
    note = ""
    note_rev += 1
    pending = False
    pending_since = None
    pulse_until = now + 3
    save()
    app.badge_pulse()
    refresh()
    app.close_page()


def set_minutes(value):
    global error, rev, next_at
    text = str(value).strip()
    error = ""
    if text.isdigit() and 1 <= int(text) <= 120:
        settings["minutes"] = int(text)
        if next_at and not pending:
            next_at = time.time() + settings["minutes"] * 60
    else:
        error = "Enter a whole number from 1 to 120."
    rev += 1          # new input id, so the field shows the stored value again
    save()
    refresh()


def refresh():
    app.active(pending)
    draw_tile()
    draw_page()


def draw_tile():
    global last_tile
    if pending:
        sub, label = "Activity", clock(pending_since or time.time())
    elif next_at:
        sub, label = "Next", clock(next_at)
    else:
        sub, label = "Off", "--:--"
    sig = f"{sub}|{label}"
    if sig == last_tile:
        return
    last_tile = sig
    app.tile(nook.row([
        nook.icon("list-checks", size=22, color="accent"),
        nook.column([
            nook.text(sub, size="small", color="dim"),
            nook.text(label, size="title"),
        ], gap=0),
    ], gap=8, align="center"))


def draw_page():
    global last_page
    sig = repr((pending, pending_since, next_at, tab, note_rev, rev, error, len(entries)))
    if sig == last_page:
        return
    last_page = sig
    body = [log_view, today_view, insights_view][tab]()
    app.page(nook.column([nook.chips("tab", TABS, selected=tab), body], gap=8, scroll=True),
             actions=[{"id": "dashboard", "icon": "chart-bar", "tooltip": "Open full dashboard"}])


def log_view():
    if pending:
        sub, head = "What did you do?", f"Last {settings['minutes']} min"
    elif next_at:
        sub, head = "Next check", clock(next_at)
    else:
        sub, head = "Starting", "--:--"
    buttons = [nook.button(f"cat:{key}", label=label, primary=(key == "deep"), width=0)
               for key, label in CATEGORIES]
    return nook.column([
        nook.row([
            nook.column([
                nook.text(sub, size="small", color="dim"),
                nook.text(head, size="title"),
            ], gap=0),
            nook.spacer(),
            nook.row([
                nook.text("Window", size="small", color="dim"),
                nook.text_input(f"minutes:{rev}", str(settings["minutes"]), hint="1-120", width=56),
            ], gap=6, align="center"),
        ], align="center"),
        nook.text_input(f"note:{note_rev}", "", live=True,
                        hint=f"Activity in last {settings['minutes']} minutes"),
        nook.grid(2, buttons, gap=6),
        nook.text(error or "Entries save when you pick a category", size="small",
                  color="red" if error else "dim"),
    ], gap=8)


MOSAIC_COLORS = {"deep": "accent", "admin": "green", "break": "dim", "other": "purple"}
EMPTY_SLOT = "#8888882A"
SLOT = 900                                # one 15-minute slot, in seconds
HOURS_SHOWN = list(range(0, 24))          # 00:00 to 23:45, all 24 hours


def day_mosaic():
    """Each square is one 15-minute slot, coloured by the category logged for it."""
    now = datetime.datetime.now()
    first = datetime.datetime(now.year, now.month, now.day, HOURS_SHOWN[0]).timestamp()
    cell_w, cell_h, gap, top = 18, 14, 4, 16    # 24 columns must fit the 568px page
    shapes = []
    for col, hour in enumerate(HOURS_SHOWN):
        if hour % 3 == 0:
            shapes.append(nook.label(col * (cell_w + gap) + cell_w / 2, 7, f"{hour:02d}",
                                     size=9, color="dim", anchor="center"))
    for row in range(4):                  # :00, :15, :30, :45 down each column
        for col in range(len(HOURS_SHOWN)):
            a = first + (col * 4 + row) * SLOT
            b = a + SLOT
            best, best_overlap = None, 0
            for e in entries:             # the entry that covers most of this slot
                overlap = min(b, e["end"]) - max(a, e["start"])
                if overlap > best_overlap:
                    best, best_overlap = e, overlap
            fill = MOSAIC_COLORS.get(best["cat"], "dim") if best else EMPTY_SLOT
            shapes.append(nook.rect(col * (cell_w + gap), top + row * (cell_h + gap),
                                    cell_w, cell_h, fill=fill, radius=3))
    height = top + 4 * (cell_h + gap)
    width = len(HOURS_SHOWN) * (cell_w + gap) - gap
    return nook.canvas(height, shapes, width=width)


def today_view():
    items = today_entries()
    legend = nook.row([
        nook.text("■ Deep work", size="small", color="accent"),
        nook.text("■ Learning", size="small", color="green"),
        nook.text("■ Break", size="small", color="dim"),
        nook.text("■ Other", size="small", color="purple"),
        nook.text("■ Not logged", size="small", color="faint"),
    ], gap=12)
    parts = [legend, day_mosaic()]
    if items:
        rows = [nook.item(
            f"e:{i}",
            title=CAT_LABEL.get(e["cat"], e["cat"]) + (f" - {e['note']}" if e["note"] else ""),
            subtitle=f"{clock(e['start'])} - {clock(e['end'])}",
            trailing=fmt(duration(e)),
        ) for i, e in enumerate(items)]
        parts.append(nook.list_view(rows))
    else:
        parts.append(nook.text("Nothing logged yet today.", color="dim"))
    return nook.column(parts, gap=8)


def insights_view():
    today = today_entries()
    total = minutes_for(today)
    rows = [nook.text(f"Logged today: {fmt(total)}", size="title")]
    for key, label in CATEGORIES:
        mins = minutes_for(today, key)
        rows.append(nook.column([
            nook.row([nook.text(label), nook.spacer(), nook.text(fmt(mins), color="dim")],
                     align="center"),
            nook.progress(mins / total if total else 0),
        ], gap=3))
    return nook.column(rows, gap=10)


@app.on_message("event")
def on_event(e):
    global tab, note
    eid, kind, value = e.get("id", ""), e.get("kind"), e.get("value")
    if eid == "tab" and kind == "change":
        tab = int(value.get("index", 0)) if isinstance(value, dict) else 0
        draw_page()
    elif eid.startswith("note:") and kind in ("change", "submit"):
        note = str(value or "")
    elif eid.startswith("cat:") and kind == "click":
        record(eid[4:])
    elif eid.startswith("minutes:") and kind == "submit":
        set_minutes(value)
    elif eid == "dashboard" and kind == "click":
        open_dashboard()


TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Activity dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root { --bg:#f6f7fb; --fg:#1d2233; --dim:#6b7288; --card:#ffffff; --line:#e5e8f0; --accent:#6d5efc; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#0f1220; --fg:#e8ebf5; --dim:#9aa1b8; --card:#171b2e; --line:#262b42; }
}
body { margin:0; font:15px/1.5 system-ui, "Segoe UI", sans-serif; background:var(--bg); color:var(--fg); }
main { max-width:860px; margin:0 auto; padding:32px 20px; }
h1 { margin:0; font-size:26px; }
.sub { color:var(--dim); margin:2px 0 24px; }
.stats { display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:12px; margin-bottom:28px; }
.card, section { background:var(--card); border:1px solid var(--line); border-radius:14px; }
.card { padding:16px; }
.label { color:var(--dim); font-size:13px; }
.value { font-size:22px; font-weight:600; margin-top:4px; }
section { padding:6px 18px 12px; margin-bottom:16px; }
h2 { font-size:16px; margin:12px 0 6px; }
h2 small { color:var(--dim); font-weight:400; margin-left:8px; }
table { width:100%; border-collapse:collapse; }
td { padding:9px 6px; border-top:1px solid var(--line); vertical-align:top; }
td.time { color:var(--dim); white-space:nowrap; width:110px; font-variant-numeric:tabular-nums; }
td.dur { text-align:right; white-space:nowrap; color:var(--dim); }
.tag { display:inline-block; padding:2px 10px; border-radius:999px; background:var(--accent); color:#fff; font-size:12px; }
.tag.admin { background:#22c55e; }
.tag.break { background:#8a93a8; }
.cats { display:flex; flex-wrap:wrap; gap:6px 16px; font-size:13px; color:var(--dim); margin:0 0 4px; }
.cats b { color:var(--fg); font-weight:600; }
.empty { color:var(--dim); padding:40px 0; text-align:center; }
</style></head>
<body><main>
<h1>Activity</h1>
<div class="sub">Generated __NOW__</div>
<div class="stats">__STATS__</div>
__SECTIONS__
</main></body></html>
"""


def open_dashboard():
    days = {}
    for e in sorted(entries, key=lambda x: x["start"], reverse=True):
        day = time.strftime("%A, %d %B %Y", time.localtime(e["start"]))
        days.setdefault(day, []).append(e)
    sections = []
    for day, items in days.items():
        rows = "".join(
            "<tr><td class='time'>{}-{}</td><td><span class='tag {}'>{}</span></td>"
            "<td>{}</td><td class='dur'>{}</td></tr>".format(
                clock(e["start"]), clock(e["end"]), e["cat"],
                html.escape(CAT_LABEL.get(e["cat"], e["cat"])),
                html.escape(e["note"]), fmt(duration(e)))
            for e in items)
        cats = "".join("<span>{} <b>{}</b></span>".format(
            html.escape(label), fmt(minutes_for(items, key))) for key, label in CATEGORIES)
        sections.append("<section><h2>{} <small>{}</small></h2><div class='cats'>{}</div>"
                        "<table>{}</table></section>"
                        .format(day, fmt(minutes_for(items)), cats, rows))
    stats = "".join(
        "<div class='card'><div class='label'>{}</div><div class='value'>{}</div></div>"
        .format(html.escape(label), fmt(minutes_for(entries, key)))
        for key, label in CATEGORIES)
    page = (TEMPLATE.replace("__NOW__", time.strftime("%d %b %Y, %H:%M"))
                    .replace("__STATS__", stats)
                    .replace("__SECTIONS__", "".join(sections) or "<div class='empty'>Nothing logged yet.</div>"))
    path = os.path.join(app.data_dir, "dashboard.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    app.open(path)


@app.every(5)
def tick():
    global next_at, pending, pending_since, pulse_until
    now = time.time()
    if pulse_until and now >= pulse_until:
        pulse_until = 0
        app.clear_badge()
    if next_at and now >= next_at:
        # The schedule runs on its own clock, whether or not the last prompt was answered.
        due = next_at
        step = settings["minutes"] * 60
        next_at = due + step
        while next_at <= now:             # plugin was off: skip the missed slots
            next_at += step
        if not pending:
            # Show the prompt once. If it is still unanswered, the next slot is skipped.
            pending, pending_since = True, due
            app.show()
        save()
        refresh()
    draw_tile()


if next_at is None:
    next_at = time.time() + settings["minutes"] * 60
    save()
refresh()
if pending:
    # The prompt was waiting when the plugin restarted: show it again.
    app.show()
app.run()
