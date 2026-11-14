"""Water: a wide Nook tile that reminds you to drink water.

Every N minutes the notch opens by itself on this plugin's page with a
Snooze and a Drank button. A reminder pops up once and waits until you
answer. Snooze pushes the next reminder out; Drank restarts the cycle only
when a reminder is pending, and pulses the pill. Interval, snooze and the
active hours are set on the page and kept in NOOK_DATA_DIR.
"""

import re
import time

import nook

app = nook.Plugin()

DEFAULTS = {"interval": 15, "snooze": 10, "goal": 2000, "start": "00:00", "end": "23:59"}
LIMITS = {"interval": (1, 240), "snooze": (1, 120), "goal": (100, 10000)}
DRINK_ML = 250                          # one glass

data = app.load("water", {})
settings = {**DEFAULTS, **data.get("settings", {})}
drinks = data.get("drinks", [])         # {"t": epoch seconds, "ml": amount}
next_at = data.get("next_at")           # epoch seconds of the next reminder
pending = data.get("pending", False)    # a reminder is waiting to be answered
rev = data.get("rev", 0)                # bumped to refresh the setting inputs
pulse_until = 0
error = ""                              # last settings error, shown under the inputs

last_tile = None
last_page = None


def save():
    app.save("water", {"settings": settings, "next_at": next_at, "drinks": drinks,
                       "pending": pending, "rev": rev})


def parse_hhmm(value):
    """'9:30' -> minutes since midnight, or None."""
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", str(value).strip())
    if not m:
        return None
    h, minute = int(m.group(1)), int(m.group(2))
    if h > 23 or minute > 59:
        return None
    return h * 60 + minute


def in_window(when=None):
    """True when `when` (epoch, default now) falls inside the active hours."""
    start = parse_hhmm(settings["start"])
    end = parse_hhmm(settings["end"])
    if start is None or end is None:
        return True
    t = time.localtime(when if when is not None else time.time())
    minutes = t.tm_hour * 60 + t.tm_min
    if start <= end:
        return start <= minutes <= end
    return minutes >= start or minutes <= end


def clock(epoch):
    return time.strftime("%H:%M", time.localtime(epoch))


def field(label, id_, value, hint):
    return nook.column([
        nook.text(label, size="small", color="dim"),
        nook.text_input(id_, value, hint=hint, width=90),
    ], gap=2)


def set_setting(key, value):
    global next_at
    settings[key] = value
    if key == "interval" and next_at is not None and not pending:
        # Restart the countdown so the new interval applies now.
        next_at = time.time() + settings["interval"] * 60


def draw_tile():
    global last_tile
    if next_at is None:
        label, sub = "--:--", "off"
    else:
        label = clock(next_at)
        sub = "held" if not in_window() else ("Water" if not pending else "Drink!")
    sig = f"{label}|{sub}|{settings['snooze']}"
    if sig == last_tile:
        return
    last_tile = sig
    app.tile(nook.row([
        nook.column([
            nook.text(sub, size="small", color="dim"),
            nook.text(label, size="title"),
        ], gap=0),
        nook.spacer(),
        nook.button("snooze", icon="alarm", tooltip=f"Snooze {settings['snooze']} min"),
        nook.button("drank", icon="check", tooltip="Drank"),
    ], gap=6, align="center"))


def today_drinks():
    now = time.localtime()
    midnight = time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 0, 0, 0, 0, 0, -1))
    return [d for d in drinks if d["t"] >= midnight]


CHART_W, CHART_H = 300, 100
HOURS = list(range(6, 23))              # bars for 06:00 to 22:00


def chart():
    per_hour = {h: 0 for h in HOURS}
    for d in today_drinks():
        h = time.localtime(d["t"]).tm_hour
        if h in per_hour:
            per_hour[h] += d["ml"]
    top = max(300, max(per_hour.values()))
    left, right, top_y, base = 36, CHART_W - 6, 8, CHART_H - 20
    plot_h = base - top_y
    shapes = []
    for v in (0, top // 2, top):           # gridlines at 0, half and top
        y = base - v / top * plot_h
        shapes.append(nook.line([(left, y), (right, y)], color="faint", width=1))
        shapes.append(nook.label(left - 6, y, str(v), size=10, color="dim", anchor="end"))
    slot = (right - left) / len(HOURS)
    for i, h in enumerate(HOURS):
        x0 = left + i * slot
        if per_hour[h]:
            bar = per_hour[h] / top * plot_h
            shapes.append(nook.rect(x0 + slot * 0.2, base - bar, slot * 0.6, bar,
                                    fill="accent", radius=2))
        if h % 3 == 0:
            shapes.append(nook.label(x0 + slot / 2, CHART_H - 6, f"{h:02d}", size=10,
                                     color="dim", anchor="center"))
    return nook.canvas(CHART_H, shapes, width=CHART_W)


def summary_block():
    """Left side of the page: today's total, a ring for the goal, and Drank."""
    total = sum(d["ml"] for d in today_drinks())
    goal = settings["goal"]
    pct = round(100 * total / goal) if goal else 0
    return nook.column([
        nook.text(str(total), size="huge"),
        nook.text(f"/ {goal} ml", size="small", color="dim"),
        nook.ring(min(total / goal, 1) if goal else 0, label=f"{pct}%", size=44, color="accent"),
    ], gap=2)


def draw_page():
    global last_page
    sig = "|".join([str(pending), str(rev), error, str(len(drinks))]
                   + [str(settings[k]) for k in DEFAULTS])
    if sig == last_page:
        return
    last_page = sig
    notes = [nook.text("Settings - press Enter to save", size="small", color="dim")]
    if error:
        notes.append(nook.text(error, size="small", color="red"))
    if pending:
        head = "Time to drink water!"
    elif next_at:
        head = f"Next reminder at {clock(next_at)}"
    else:
        head = "Water"
    app.page(nook.column([
        nook.row([
            nook.text(head, size="title"),
            nook.spacer(),
            nook.button("snooze", label=f"Snooze {settings['snooze']} min"),
            nook.button("drank", label="Drank", primary=True),
        ], gap=8, align="center"),
        nook.row([summary_block(), chart()], gap=14, align="center"),
        nook.divider(),
        nook.column(notes, gap=2),
        nook.row([
            field("Every", f"interval:{rev}", str(settings["interval"]), "minutes"),
            field("Snooze", f"snooze:{rev}", str(settings["snooze"]), "minutes"),
            field("Goal", f"goal:{rev}", str(settings["goal"]), "ml"),
            field("From", f"start:{rev}", settings["start"], "HH:MM"),
            field("To", f"end:{rev}", settings["end"], "HH:MM"),
        ], gap=12, align="center"),
    ], gap=8, scroll=True))


@app.on("snooze")
def on_snooze(e):
    global next_at, pending
    next_at = time.time() + settings["snooze"] * 60
    pending = False
    save()
    draw_tile()
    draw_page()
    app.close_page()


@app.on("drank")
def on_drank(e):
    global next_at, pending, pulse_until
    if pending:
        # Only an answer to a pending reminder restarts the cycle.
        # A stray tile click on a quiet tile leaves the timer alone.
        next_at = time.time() + settings["interval"] * 60
        pending = False
    drinks.append({"t": round(time.time()), "ml": DRINK_ML})   # every Drank is a glass
    pulse_until = time.time() + 3
    save()
    app.badge_pulse()
    draw_tile()
    draw_page()
    app.close_page()


@app.on_message("event")
def on_setting(e):
    """Setting inputs carry an id with a revision, so the field can be reset."""
    global rev, error
    m = re.fullmatch(r"(\w+):(\d+)", e.get("id", ""))
    if not m or m.group(1) not in DEFAULTS:
        return
    key = m.group(1)
    value = e.get("value", "")
    error = ""
    if key in LIMITS:
        number = int(value) if str(value).strip().isdigit() else 0
        low, high = LIMITS[key]
        if low <= number <= high:
            set_setting(key, number)
        else:
            error = f"{key.capitalize()}: enter a whole number from {low} to {high}."
            app.log(f"{key} out of range: {value!r}", "warn")
    else:
        minutes = parse_hhmm(value)
        if minutes is None:
            error = f"{key.capitalize()}: use HH:MM, for example 09:30."
            app.log(f"{key} is not HH:MM: {value!r}", "warn")
        else:
            set_setting(key, f"{minutes // 60:02d}:{minutes % 60:02d}")
    rev += 1
    save()
    draw_tile()
    draw_page()


@app.every(5)
def tick():
    global next_at, pending, pulse_until
    now = time.time()
    if pulse_until and now >= pulse_until:
        pulse_until = 0
        app.clear_badge()
    if next_at is None:
        if in_window(now):
            next_at = now + settings["interval"] * 60
            save()
    elif now >= next_at and not pending:
        if in_window(now):
            # Due and the window is open: pop up once. The timer waits
            # until the reminder is answered, so there are no repeat pop-ups.
            pending = True
            save()
            draw_page()
            app.show()
        else:
            # Due, but the window is closed: hold it, re-check in a minute.
            next_at = now + 60
            save()
    draw_tile()


if next_at is None and in_window():
    next_at = time.time() + settings["interval"] * 60
    save()

draw_tile()
draw_page()
if pending:
    # A reminder was waiting to be answered when the plugin restarted: show it again.
    app.show()
app.run()
