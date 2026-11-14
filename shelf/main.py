"""Shelf: a wide Nook tile that keeps the texts and prompts you paste often.

Add a title and the text. Copy puts the text on your clipboard in one click;
Edit and Delete keep the list current. Items are saved in NOOK_DATA_DIR.
"""

import re

import nook

app = nook.Plugin()

data = app.load("shelf", {})
items = [i for i in data.get("items", [])
         if isinstance(i, dict) and "id" in i and "title" in i and "text" in i]
next_id = max(data.get("next", 1), max((i["id"] for i in items), default=0) + 1)

mode = "list"            # "list", "new" or "edit"
editing_id = None        # id of the item being edited
draft = {"title": "", "text": ""}
rev = 0                  # bumped each time the form opens, so the inputs reset
error = ""
flash = ""               # last result, e.g. "Copied: Sales reply"
last_tile = None


def save():
    app.save("shelf", {"items": items, "next": next_id})


def find(item_id):
    return next((i for i in items if i["id"] == item_id), None)


def preview(text):
    flat = " ".join(text.split())
    return flat if len(flat) <= 90 else flat[:87] + "..."


def draw_tile():
    global last_tile
    sig = str(len(items))
    if sig == last_tile:
        return
    last_tile = sig
    app.tile(nook.row([
        nook.icon("clipboard", size=22, color="accent"),
        nook.column([
            nook.text("Shelf", size="small", color="dim"),
            nook.text(f"{len(items)} saved", size="title"),
        ], gap=0),
    ], gap=8, align="center"))


def form_view():
    children = [
        nook.text("Title", color="dim"),
        nook.text_input(f"title:{rev}", draft["title"], hint="Name for this item", live=True),
        nook.text("Text to copy", color="dim"),
        nook.text_input(f"text:{rev}", draft["text"], hint="The text itself", live=True),
        nook.row([
            nook.button("save", label="Save", primary=True),
            nook.button("cancel", label="Cancel"),
            nook.spacer(),
            nook.text(error, size="small", color="red") if error else nook.spacer(),
        ], gap=8, align="center"),
    ]
    return nook.column(children, gap=6)


def list_view():
    if not items:
        return nook.text("Nothing saved yet. Press New to add your first text.", color="dim")
    rows = []
    for item in items:
        rows.append(nook.row([
            nook.column([
                nook.text(item["title"], bold=True),
                nook.text(preview(item["text"]), size="small", color="dim"),
            ], gap=2),
            nook.spacer(),
            nook.button(f"copy:{item['id']}", label="Copy", primary=True),
            nook.button(f"edit:{item['id']}", label="Edit"),
            nook.button(f"del:{item['id']}", label="Delete"),
        ], gap=6, align="center"))
        rows.append(nook.divider())
    return nook.column(rows, gap=6)


def draw_page():
    if mode == "list":
        title, body = "Shelf", list_view()
        head_action = nook.button("new", label="New", primary=True)
    else:
        title = "New item" if mode == "new" else "Edit item"
        body = form_view()
        head_action = nook.spacer()
    footer = nook.text(flash, size="small", color="dim") if flash else nook.spacer()
    app.page(nook.column([
        nook.row([nook.text(title, size="title"), nook.spacer(), head_action],
                 gap=8, align="center"),
        body,
        footer,
    ], gap=10, scroll=True))


def open_form(new_mode, item=None):
    global mode, editing_id, draft, rev, error, flash
    mode = new_mode
    editing_id = item["id"] if item else None
    draft = {"title": item["title"], "text": item["text"]} if item else {"title": "", "text": ""}
    rev += 1
    error = ""
    flash = ""


def close_form():
    global mode, editing_id, error
    mode = "list"
    editing_id = None
    error = ""


@app.on_message("event")
def on_event(e):
    global next_id, flash, error
    eid = str(e.get("id", ""))
    kind = e.get("kind")

    field = re.fullmatch(r"(title|text):(\d+)", eid)
    if field:
        # Typing only updates the draft. Ignore inputs from an older form.
        if kind == "change" and int(field.group(2)) == rev:
            draft[field.group(1)] = str(e.get("value", ""))
        return
    if kind != "click":
        return

    if eid == "new":
        open_form("new")
    elif eid == "cancel":
        close_form()
    elif eid == "save":
        title, text = draft["title"].strip(), draft["text"].strip()
        if not title or not text:
            error = "Add a title and some text."
        else:
            if mode == "edit" and find(editing_id):
                item = find(editing_id)
                item["title"], item["text"] = title, text
                flash = f"Saved: {title}"
            else:
                items.append({"id": next_id, "title": title, "text": text})
                next_id += 1
                flash = f"Added: {title}"
            close_form()
            save()
    else:
        action, _, raw = eid.partition(":")
        item = find(int(raw)) if raw.isdigit() else None
        if item is None:
            return
        if action == "copy":
            app.copy(item["text"])
            flash = f"Copied: {item['title']}"
        elif action == "edit":
            open_form("edit", item)
        elif action == "del":
            items.remove(item)
            save()
            flash = f"Deleted: {item['title']}"

    draw_tile()
    draw_page()


@app.on_message("page_open")
def on_page_open(_):
    draw_page()


draw_tile()
draw_page()
app.run()
