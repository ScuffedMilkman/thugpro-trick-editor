"""THUG Pro Trick Editor - desktop app (tkinter).

Open a THUG Pro skater (.SKA) and edit its special tricks and its standard
grab / flip / lip trick mappings. Drag a .SKA onto the .exe, or use Open,
to edit that file only.
"""
import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import thugsave as ts

APP_NAME = 'THUG Pro Trick Editor'

C = {
    'bg': '#0b0b0d', 'panel': '#16161b', 'field': '#1e1e25', 'line': '#2c2c34', 'text': '#ececf1',
    'muted': '#8d8d98', 'accent': '#2f9e5b', 'warn': '#e0a030', 'bad': '#e5605d',
    'tri': '#3fc7a5', 'cir': '#ef5b5b', 'sq': '#e27fc0', 'dup': '#4d8ef0',
}
ARROW = {'U': '↑', 'D': '↓', 'L': '←', 'R': '→'}
ARROW_REV = {v: k for k, v in ARROW.items()}
DIAG = {'U': '↑', 'D': '↓', 'L': '←', 'R': '→', 'UL': '↖', 'UR': '↗', 'DL': '↙', 'DR': '↘'}
TYPE_LABEL = {'': 'Empty', 'grind': 'Grind', 'manual': 'Manual', 'air': 'Air', 'lip': 'Lip', 'unknown': 'Unknown'}
TYPE_REV = {v: k for k, v in TYPE_LABEL.items()}
KP = {'Triangle': 'KP8', 'Circle': 'KP6', 'Square': 'KP4'}
BTN_COLOR = {'Triangle': C['tri'], 'Circle': C['cir'], 'Square': C['sq']}
TABS = [('special', 'Special Tricks'), ('grab', 'Grab Tricks'), ('flip', 'Flip Tricks'), ('lip', 'Lip Tricks')]
TAB_BUTTON = {'grab': 'Circle', 'flip': 'Square', 'lip': 'Triangle'}
POLL_MS = 2000

# ------------------------------------------------------------------ data ---


def build_special_lists():
    """type -> (display names, display->id, id->display)."""
    out = {}
    for typ in ts.TYPES:
        # The game's grab/flip tag on air specials is about how the trick is
        # performed (held vs one-shot), not how it looks, so list them together.
        want = ('grab', 'flip') if typ == 'air' else (typ,)
        items = sorted(((t['name'], t['id']) for t in ts.CATALOG if t['type'] in want),
                       key=lambda x: x[0].lower())
        seen, fixed = {}, []
        for disp, tid in items:
            if disp in seen:
                disp = '%s [%s]' % (disp, tid.replace('Trick_', ''))
            seen[disp] = tid
            fixed.append((disp, tid))
        out[typ] = ([d for d, _ in fixed], dict(fixed), {tid: d for d, tid in fixed})
    return out


SPECIALS = build_special_lists()


def standard_label(t):
    return '%s  /  %s' % (t['name'], t['extra']) if t.get('extra') else t['name']


def slot_combo(slot):
    """'Air_CircleUL' -> ('↖', 'Circle'); 'Air_U_U_Square' -> ('↑ ↑', 'Square')."""
    if slot.startswith('Air_') and slot.count('_') == 3:
        _, a, b, btn = slot.split('_')
        return '%s %s' % (ARROW[a], ARROW[b]), btn.capitalize()
    for btn in ('Circle', 'Square', 'Triangle'):
        if btn in slot:
            return DIAG[slot.split(btn)[1]], btn
    return slot, 'Triangle'


def row_from_entry(e):
    if e['slot'] == ts.UNASSIGNED and e['trick'] == ts.UNASSIGNED:
        return {'type': '', 'trick': '', 'a': 'L', 'b': 'R', 'button': 'Square'}
    p = ts.parse_slot(e['slot'])
    if not p or (e['trick'] != ts.UNASSIGNED and e['trick'] not in ts.TRICK_BY_ID):
        return {'type': 'unknown', 'raw_slot': e['slot'], 'raw_trick': e['trick']}
    typ, a, b, button = p
    return {'type': typ, 'trick': e['trick'], 'a': a, 'b': b, 'button': button}


def entry_from_row(r):
    if r['type'] == 'unknown':
        return {'slot': r['raw_slot'], 'trick': r['raw_trick']}
    if not r['type']:
        return {'slot': ts.UNASSIGNED, 'trick': ts.UNASSIGNED}
    return {'slot': ts.slot_name(r['type'], r['a'], r['b'], r['button']), 'trick': r['trick'] or None}

# --------------------------------------------------------------- widgets ---


def draw_icon(cv, shape, x, y, size, color, width=2.2):
    h = size / 2
    if shape == 'Triangle':
        cv.create_polygon(x, y - h, x + h * 1.1, y + h * 0.8, x - h * 1.1, y + h * 0.8,
                          outline=color, fill='', width=width, joinstyle='round')
    elif shape == 'Circle':
        cv.create_oval(x - h, y - h, x + h, y + h, outline=color, width=width)
    else:
        cv.create_rectangle(x - h * 0.9, y - h * 0.9, x + h * 0.9, y + h * 0.9, outline=color, width=width)


class ButtonChip(tk.Canvas):
    """PlayStation-style button icon + KP label; optionally a toggle."""

    def __init__(self, master, shape, on_click=None):
        super().__init__(master, width=74, height=30, bg=C['bg'], highlightthickness=0,
                         cursor='hand2' if on_click else '')
        self.shape, self.on_click, self.selected, self.fixed = shape, on_click, False, on_click is None
        if on_click:
            self.bind('<Button-1>', lambda e: on_click(shape))
        self.redraw()

    def set_selected(self, sel):
        if sel != self.selected:
            self.selected = sel
            self.redraw()

    def redraw(self):
        self.delete('all')
        active = self.selected or self.fixed
        col = BTN_COLOR[self.shape] if active else '#5a5a63'
        border = BTN_COLOR[self.shape] if self.selected else C['line']
        r, x0, y0, x1, y1 = 13, 2, 2, 72, 28
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
               x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        self.create_polygon(pts, smooth=True, fill='#26262e' if active else C['field'],
                            outline=border, width=2 if self.selected else 1)
        draw_icon(self, self.shape, 20, 15, 13, col)
        self.create_text(48, 15, text=KP[self.shape], fill=C['text'] if active else C['muted'],
                         font=('Segoe UI', 9, 'bold' if self.selected else 'normal'))


class Tooltip:
    """Small hover tooltip for any widget."""

    def __init__(self, widget, text, delay=400):
        self.widget, self.text, self.delay = widget, text, delay
        self.tip = self.job = None
        widget.bind('<Enter>', self.schedule, add='+')
        widget.bind('<Leave>', self.hide, add='+')
        widget.bind('<ButtonPress>', self.hide, add='+')

    def schedule(self, _e=None):
        self.cancel()
        self.job = self.widget.after(self.delay, self.show)

    def cancel(self):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None

    def show(self):
        if self.tip:
            return
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.attributes('-topmost', True)
        tk.Label(self.tip, text=self.text, bg='#2a2a33', fg=C['text'], font=('Segoe UI', 9),
                 padx=10, pady=6, wraplength=320, justify='left',
                 highlightthickness=1, highlightbackground=C['line']).pack()
        self.tip.update_idletasks()
        # keep it on screen
        sw = self.widget.winfo_screenwidth()
        w = self.tip.winfo_width()
        self.tip.wm_geometry('+%d+%d' % (max(4, min(x, sw - w - 4)), y))

    def hide(self, _e=None):
        self.cancel()
        if self.tip:
            self.tip.destroy()
            self.tip = None


class HelpDialog:
    """Explains how THUG Pro stores custom skaters and where the saves live."""

    def __init__(self, parent):
        top = self.top = tk.Toplevel(parent)
        top.title('About skater saves')
        top.configure(bg=C['bg'])
        top.transient(parent)
        top.resizable(False, False)
        pad = dict(padx=20, anchor='w')

        lbl(top, 'How THUG Pro saves custom skaters', font=('Segoe UI', 13, 'bold')).pack(pady=(16, 8), **pad)
        lbl(top, 'Every custom skater you save in THUG Pro becomes its own .SKA file, named after what you '
                 'typed when saving (for example Skater.SKA).', wraplength=520, justify='left').pack(pady=(0, 10), **pad)

        lbl(top, 'Each .SKA file holds:', font=('Segoe UI', 10, 'bold')).pack(**pad)
        for line in ('One custom skater: name, look and stance',
                     'Their trick setup: special, grab, flip and lip tricks',
                     'Up to 10 created tricks, shared by that save'):
            lbl(top, '•  ' + line, wraplength=500, justify='left').pack(padx=(32, 20), anchor='w')

        custom = ts.save_dir_is_custom()
        lbl(top, 'Save folder', font=('Segoe UI', 10, 'bold')).pack(pady=(12, 2), **pad)
        lbl(top, (r'Default: %LOCALAPPDATA%\THUG Pro\Save' + ('   (you changed this)' if custom else '')),
            fg=C['muted'], font=('Consolas', 10)).pack(**pad)
        row = tk.Frame(top, bg=C['bg'])
        row.pack(fill='x', padx=20, pady=(4, 0))
        box = tk.Frame(row, bg=C['field'], highlightthickness=1, highlightbackground=C['line'])
        box.pack(side='left', fill='x', expand=True)
        path = ts.get_save_dir()
        exists = os.path.isdir(path)
        tk.Label(box, text=path, bg=C['field'], fg=C['text'], font=('Consolas', 10), padx=10, pady=6,
                 anchor='w', justify='left', wraplength=380).pack(fill='x')
        ttk.Button(row, text='Change…', command=self.change_folder).pack(side='left', padx=(8, 0))
        if custom:
            ttk.Button(row, text='Use default', command=self.reset_folder).pack(side='left', padx=(6, 0))
        lbl(top, ('on this PC' if exists else 'not found here; if THUG Pro saves somewhere else, use Change…'),
            fg=C['muted'] if exists else C['warn'], font=('Segoe UI', 9)).pack(**pad)
        self.parent = parent

        # backup reminder callout
        note = tk.Frame(top, bg='#3a2c10', highlightthickness=1, highlightbackground=C['warn'])
        note.pack(fill='x', padx=20, pady=(14, 0))
        tk.Label(note, text='⚠  Back up your .SKA first', bg='#3a2c10', fg=C['warn'],
                 font=('Segoe UI', 10, 'bold'), anchor='w', padx=10, pady=(6)).pack(fill='x')
        tk.Label(note, text='Before editing, copy your .SKA file somewhere safe so you always have a '
                            'return point, just in case. This editor also makes a backup each time you '
                            'save, but your own copy is the safest way back.',
                 bg='#3a2c10', fg=C['text'], font=('Segoe UI', 9), anchor='w', justify='left',
                 wraplength=490, padx=10).pack(fill='x', pady=(0, 8))

        btns = tk.Frame(top, bg=C['bg'])
        btns.pack(fill='x', padx=20, pady=16)
        ttk.Button(btns, text='Close', style='Accent.TButton', command=top.destroy).pack(side='right')
        if exists:
            ttk.Button(btns, text='Open save folder', command=lambda: os.startfile(path)).pack(side='right', padx=8)
        top.bind('<Escape>', lambda e: top.destroy())
        top.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - top.winfo_width()) // 2
        y = parent.winfo_rooty() + 60
        top.geometry('+%d+%d' % (max(0, x), max(0, y)))
        top.grab_set()
        top.focus_set()

    def change_folder(self):
        start = ts.get_save_dir()
        p = filedialog.askdirectory(parent=self.top, title='Choose the THUG Pro save folder',
                                    initialdir=start if os.path.isdir(start) else None, mustexist=True)
        if not p:
            return
        if not any(f.upper().endswith('.SKA') for f in os.listdir(p)):
            if not messagebox.askyesno(APP_NAME, 'There are no .SKA files in that folder.\n\n'
                                       'Use it as the save folder anyway?', parent=self.top):
                return
        ts.set_save_dir(p)
        self.reopen()

    def reset_folder(self):
        ts.set_save_dir(None)
        self.reopen()

    def reopen(self):
        parent = self.parent
        self.top.destroy()
        HelpDialog(parent)


def lbl(parent, text='', fg=None, font=None, bg=None, **kw):
    return tk.Label(parent, text=text, fg=fg or C['text'], bg=bg or C['bg'],
                    font=font or ('Segoe UI', 10), **kw)

# ------------------------------------------------------------ pages ---


class SpecialsPage:
    """The 12 special-trick slots."""

    def __init__(self, app, parent):
        self.app = app
        self.frame = tk.Frame(parent, bg=C['bg'])
        self.original, self.current = [], []
        grid = tk.Frame(self.frame, bg=C['bg'])
        grid.pack(fill='both', expand=True)
        grid.columnconfigure(2, weight=1)
        grid.columnconfigure(0, minsize=40)  # fixed so bold (changed) numbers don't shift the row
        for col, text in enumerate(['#', 'Type', 'Trick', 'Combo']):
            lbl(grid, text, fg=C['muted'], font=('Segoe UI', 9)).grid(row=0, column=col, sticky='w', padx=6, pady=(0, 4))
        self.rows = [self._build_row(grid, i) for i in range(12)]

    def _build_row(self, grid, i):
        # each slot uses two grid rows: an error line (hidden unless needed) and the controls
        r = 2 * i + 2
        w = {}
        w['msg'] = lbl(grid, '', fg=C['bad'], font=('Segoe UI', 9, 'bold'), anchor='w')
        w['msg'].grid(row=r - 1, column=1, columnspan=3, padx=6, pady=(6, 0), sticky='w')
        w['msg'].grid_remove()
        w['num'] = lbl(grid, str(i + 1), fg=C['muted'], anchor='e')
        w['num'].grid(row=r, column=0, padx=6, pady=3, sticky='e')
        w['type'] = ttk.Combobox(grid, state='readonly', width=9,
                                 values=[TYPE_LABEL[t] for t in ('', 'grind', 'manual', 'air', 'lip')])
        w['type'].grid(row=r, column=1, padx=6, pady=3, sticky='w')
        w['type'].bind('<<ComboboxSelected>>', lambda e, i=i: self.on_type(i))
        w['trick'] = ttk.Combobox(grid, state='readonly', width=34, height=20)
        w['trick'].grid(row=r, column=2, padx=6, pady=3, sticky='we')
        w['trick'].bind('<<ComboboxSelected>>', lambda e, i=i: self.on_trick(i))
        # thin frame around the combo so it can be outlined in red on errors
        combo = tk.Frame(grid, bg=C['bg'], highlightthickness=2, highlightbackground=C['bg'],
                         highlightcolor=C['bg'], padx=2, pady=1)
        combo.grid(row=r, column=3, padx=4, pady=2, sticky='w')
        w['combo'] = combo
        arrow_font = ('Segoe UI Symbol', 13, 'bold')
        w['a'] = ttk.Combobox(combo, state='readonly', width=3, values=list(ARROW.values()), font=arrow_font)
        w['b'] = ttk.Combobox(combo, state='readonly', width=3, values=list(ARROW.values()), font=arrow_font)
        w['a'].bind('<<ComboboxSelected>>', lambda e, i=i: self.on_dir(i, 'a'))
        w['b'].bind('<<ComboboxSelected>>', lambda e, i=i: self.on_dir(i, 'b'))
        w['plus'] = lbl(combo, '+', fg=C['muted'])
        w['tri'] = ButtonChip(combo, 'Triangle')
        w['sq'] = ButtonChip(combo, 'Square', lambda s, i=i: self.on_button(i, s))
        w['cir'] = ButtonChip(combo, 'Circle', lambda s, i=i: self.on_button(i, s))
        w['raw'] = lbl(combo, '', fg=C['muted'], font=('Segoe UI', 9))
        return w

    def load(self, skater):
        self.original = [row_from_entry(e) for e in skater['slots']]
        self.current = [dict(r) for r in self.original]
        self.refresh()

    def revert(self):
        self.current = [dict(r) for r in self.original]
        self.refresh()

    def on_type(self, i):
        typ = TYPE_REV[self.rows[i]['type'].get()]
        old = self.current[i]
        if typ == old.get('type'):
            return
        new = {'type': typ, 'trick': '', 'a': old.get('a', 'L'), 'b': old.get('b', 'R'),
               'button': old.get('button', 'Square')}
        if typ and ts.trick_category(old.get('trick')) == typ:
            new['trick'] = old['trick']
        self.current[i] = new
        self.app.changed()

    def on_trick(self, i):
        r = self.current[i]
        r['trick'] = SPECIALS[r['type']][1].get(self.rows[i]['trick'].get(), '')
        self.app.changed()

    def on_dir(self, i, which):
        self.current[i][which] = ARROW_REV[self.rows[i][which].get()]
        self.app.changed()

    def on_button(self, i, shape):
        self.current[i]['button'] = shape
        self.app.changed()

    def errors(self):
        """Per slot: None or (message, part) where part is 'trick', 'arrows' or 'combo'."""
        errs, seen = [None] * 12, {}
        for i, r in enumerate(self.current):
            if r['type'] in ('', 'unknown'):
                continue
            if not r['trick']:
                errs[i] = ('Pick a trick for this slot', 'trick')
                continue
            if r['a'] == r['b']:
                errs[i] = ('The two arrows must be different', 'arrows')
                continue
            k = ts.slot_name(r['type'], r['a'], r['b'], r['button']).lower()
            if k in seen:
                errs[i] = ('Same combo as slot %d' % (seen[k] + 1), 'combo')
                errs[seen[k]] = errs[seen[k]] or ('Same combo as slot %d' % (i + 1), 'combo')
            else:
                seen[k] = i
        return errs

    def row_dirty(self, i):
        return entry_from_row(self.current[i]) != entry_from_row(self.original[i])

    def dirty(self):
        return bool(self.current) and any(self.row_dirty(i) for i in range(12))

    def payload(self):
        return [entry_from_row(r) for r in self.current] if self.dirty() else None

    def duplicates(self):
        """Row indexes whose trick is also used by another special slot."""
        seen = {}
        for i, r in enumerate(self.current):
            if r['type'] not in ('', 'unknown') and r['trick']:
                seen.setdefault(r['trick'], []).append(i)
        return {i for rows in seen.values() if len(rows) > 1 for i in rows}

    def refresh(self):
        errs = self.errors()
        dups = self.duplicates()
        for i, (r, w) in enumerate(zip(self.current, self.rows)):
            typ = r['type']
            w['type'].config(values=[TYPE_LABEL[t] for t in ('', 'grind', 'manual', 'air', 'lip')]
                             + (['Unknown'] if typ == 'unknown' else []))
            w['type'].set(TYPE_LABEL[typ])
            for k in ('a', 'b', 'plus', 'tri', 'cir', 'sq', 'raw'):
                w[k].pack_forget()
            if typ in ('', 'unknown'):
                w['trick'].config(values=[], state='disabled')
                w['trick'].set('' if typ == '' else r['raw_trick'])
                if typ == 'unknown':
                    w['raw'].config(text='%s (left as is)' % r['raw_slot'])
                    w['raw'].pack(side='left')
            else:
                names, _, by_id = SPECIALS[typ]
                w['trick'].config(values=names, state='readonly')
                w['trick'].set(by_id.get(r['trick'], 'Choose a trick…'))
                w['a'].set(ARROW[r['a']]); w['b'].set(ARROW[r['b']])
                w['a'].pack(side='left'); w['b'].pack(side='left', padx=(4, 0))
                w['plus'].pack(side='left', padx=6)
                if typ == 'air':
                    w['sq'].set_selected(r['button'] == 'Square')
                    w['cir'].set_selected(r['button'] == 'Circle')
                    w['sq'].pack(side='left'); w['cir'].pack(side='left', padx=(4, 0))
                else:
                    w['tri'].pack(side='left')
            err = errs[i]
            part = err[1] if err else None
            if err:
                w['msg'].config(text='⚠  ' + err[0])
                w['msg'].grid()
            else:
                w['msg'].grid_remove()
            w['trick'].configure(style='Bad.TCombobox' if part == 'trick'
                                 else 'Dup.TCombobox' if i in dups else 'TCombobox')
            for k in ('a', 'b'):
                w[k].configure(style='Bad.TCombobox' if part == 'arrows' else 'TCombobox')
            edge = C['bad'] if part == 'combo' else C['bg']
            w['combo'].config(highlightbackground=edge, highlightcolor=edge)
            d = self.row_dirty(i)
            w['num'].config(fg=C['warn'] if d else C['muted'], font=('Segoe UI', 10, 'bold' if d else 'normal'))


class MappingPage:
    """Standard grab / flip / lip button mapping."""

    def __init__(self, app, parent, kind):
        self.app, self.kind = app, kind
        self.slots = ts.MAPPING_SLOTS[kind]
        self.frame = tk.Frame(parent, bg=C['bg'])
        self.original, self.current = {}, {}
        self.created = []
        self.includes = []
        self.error = None
        self.note = lbl(self.frame, '', fg=C['muted'], font=('Segoe UI', 9), anchor='w', justify='left')
        self.note.pack(fill='x', pady=(0, 6))
        grid = tk.Frame(self.frame, bg=C['bg'])
        grid.pack(fill='both', expand=True)
        grid.columnconfigure(2, weight=1)
        grid.columnconfigure(0, minsize=40)  # fixed so bold (changed) numbers don't shift the row
        self.grid = grid
        for col, text in enumerate(['#', 'Combo', 'Trick']):
            lbl(grid, text, fg=C['muted'], font=('Segoe UI', 9)).grid(row=0, column=col, sticky='w', padx=6, pady=(0, 4))
        self.rows = []
        for i, slot in enumerate(self.slots):
            w = {}
            w['num'] = lbl(grid, str(i + 1), fg=C['muted'], anchor='e')
            w['num'].grid(row=i + 1, column=0, padx=6, pady=3, sticky='e')
            arrows, btn = slot_combo(slot)
            combo = tk.Frame(grid, bg=C['bg'])
            combo.grid(row=i + 1, column=1, padx=6, pady=3, sticky='w')
            tk.Label(combo, text=arrows, width=4, fg=C['text'], bg=C['field'],
                     font=('Segoe UI Symbol', 13, 'bold'), padx=4).pack(side='left')
            lbl(combo, '+', fg=C['muted']).pack(side='left', padx=6)
            ButtonChip(combo, btn).pack(side='left')
            if '_' in slot[4:] and slot.count('_') == 3:
                lbl(combo, 'double tap', fg=C['muted'], font=('Segoe UI', 9)).pack(side='left', padx=8)
            w['trick'] = ttk.Combobox(grid, state='readonly', width=44, height=24)
            w['trick'].grid(row=i + 1, column=2, padx=6, pady=3, sticky='we')
            w['trick'].bind('<<ComboboxSelected>>', lambda e, s=slot: self.on_pick(s))
            self.rows.append(w)

    # options for one slot: list of (label, value) where value is a mapping dict or None (default)
    def options(self, slot):
        opts = []
        orig = self.original.get(slot, {})
        cur = self.current.get(slot, {})
        if 'default' in orig or 'default' in cur:
            d = self.default_for(slot)
            opts.append(('Default%s' % (': ' + ts.trick_display(d) if d else ''), None))
        known = {t['id'] for t in ts.STANDARD if t['type'] == self.kind}
        for v in (orig, cur):
            if 'trick' in v and v['trick'] not in known:
                opts.append(('%s (current)' % ts.trick_display(v['trick']), {'trick': v['trick']}))
        for t in sorted((t for t in ts.STANDARD if t['type'] == self.kind), key=lambda t: t['name'].lower()):
            opts.append((standard_label(t), {'trick': t['id']}))
        if self.kind != 'lip':
            for n, name in enumerate(self.created):
                if n == 0:
                    continue  # index 0 is the game's scratch copy
                opts.append(('★ Created: %s (#%d)' % (name, n), {'created': n}))
        for v in (orig, cur):
            if 'created' in v and not (1 <= v['created'] < len(self.created)):
                opts.append(('★ Created trick #%d' % v['created'], {'created': v['created']}))
        seen, out = set(), []
        for label, val in opts:
            key = repr(val)
            if key not in seen:
                seen.add(key)
                out.append((label, val))
        return out

    @staticmethod
    def as_value(v):
        if 'trick' in v:
            return {'trick': v['trick']}
        if 'created' in v:
            return {'created': v['created']}
        return None

    def load(self, skater, created):
        self.created = created
        self.error = skater.get('mapping_error')
        self.includes = skater.get('includes', [])
        m = skater.get('mapping') or {}
        self.original = {s: dict(m.get(s, {'default': None})) for s in self.slots}
        self.current = {s: dict(v) for s, v in self.original.items()}
        if self.error:
            self.note.config(text='This skater\'s %s tricks can\'t be edited: %s' % (self.kind, self.error), fg=C['bad'])
        elif self.kind == 'lip' and self.includes:
            self.note.config(text='"Default" slots use the %s lip set. Picking a trick overrides it; choosing Default puts it back.'
                             % ', '.join(self.includes), fg=C['muted'])
        elif self.kind != 'lip' and len(self.created) > 1:
            self.note.config(text='★ entries are this save\'s created tricks.', fg=C['muted'])
        else:
            self.note.config(text='')
        self.refresh()

    def revert(self):
        self.current = {s: dict(v) for s, v in self.original.items()}
        self.refresh()

    def default_for(self, slot):
        """The trick this skater gets in a slot when it isn't set explicitly (lip sets only)."""
        o = self.original.get(slot, {})
        if 'default' in o:
            return o['default']
        for inc in self.includes:
            for k, v in ts.LIP_PRESETS.get(inc, {}).items():
                if k.lower() == slot.lower():
                    return v
        return None

    def apply_from(self, src_view, src_created):
        """Replace every slot with the source skater's value. Returns notes about slots that
        couldn't be copied exactly."""
        notes = []
        if self.error:
            return ['%s tricks: not editable for this skater' % self.kind]
        for s in self.slots:
            v = src_view.get(s, {'default': None})
            mine = self.default_for(s)
            if 'trick' in v:
                new = {'trick': v['trick']}
            elif 'created' in v:
                n = v['created']
                name = src_created[n] if 0 <= n < len(src_created) else None
                if name and 0 < n < len(self.created) and self.created[n] == name:
                    idx = n  # same slot, same name: keep it (names can repeat)
                else:
                    idx = next((i for i, nm in enumerate(self.created) if i > 0 and nm == name), None) if name else None
                if idx is not None:
                    new = {'created': idx}
                else:
                    new = {'default': mine}
                    notes.append('%s %s: created trick "%s" isn\'t in this save, set to Default'
                                 % (self.kind, slot_combo(s)[0], name or '#%d' % n))
            elif 'default' in v:
                d = v['default']
                # same default here -> leave it on Default; otherwise copy the trick it stood for
                new = {'default': mine} if (d is None or d == mine) else {'trick': d}
            else:
                notes.append('%s %s: unknown value, left unchanged' % (self.kind, slot_combo(s)[0]))
                continue
            if 'default' in new and 'default' not in self.original.get(s, {}):
                new = {'default': mine}
            self.current[s] = new
        return notes

    def on_pick(self, slot):
        i = self.slots.index(slot)
        label = self.rows[i]['trick'].get()
        for lab, val in self.options(slot):
            if lab == label:
                if val is None:
                    self.current[slot] = {'default': self.default_for(slot)}
                else:
                    self.current[slot] = dict(val)
                break
        self.app.changed()

    def slot_dirty(self, s):
        return self.as_value(self.current.get(s, {})) != self.as_value(self.original.get(s, {}))

    def dirty(self):
        return any(self.slot_dirty(s) for s in self.slots)

    def payload(self):
        return {s: self.as_value(self.current[s]) for s in self.slots if self.slot_dirty(s)}

    def effective(self, s):
        """What a slot actually does, for spotting duplicates (Default counts as its real trick)."""
        v = self.current.get(s, {})
        if 'trick' in v:
            return ('trick', v['trick'])
        if 'created' in v:
            return ('created', v['created'])
        d = self.default_for(s)
        return ('trick', d) if d else None

    def duplicates(self):
        seen = {}
        for s in self.slots:
            e = self.effective(s)
            if e:
                seen.setdefault(e, []).append(s)
        return {s for slots in seen.values() if len(slots) > 1 for s in slots}

    def refresh(self):
        dups = self.duplicates()
        for i, s in enumerate(self.slots):
            w = self.rows[i]
            opts = self.options(s)
            w['trick'].config(values=[l for l, _ in opts], state='disabled' if self.error else 'readonly')
            cur = self.as_value(self.current.get(s, {}))
            w['trick'].set(next((l for l, v in opts if v == cur), ''))
            w['trick'].configure(style='Dup.TCombobox' if s in dups else 'TCombobox')
            d = self.slot_dirty(s)
            w['num'].config(fg=C['warn'] if d else C['muted'], font=('Segoe UI', 10, 'bold' if d else 'normal'))

# ------------------------------------------------------------------- app ---


class App:
    def __init__(self, root, start_file=None):
        self.root = root
        self.path = None
        self.stamp = None
        self.skaters = []
        self.skater = None
        self.tab = 'special'
        root.title(APP_NAME)
        root.configure(bg=C['bg'])
        root.minsize(900, 720)
        root.geometry('1040x%d' % min(940, root.winfo_screenheight() - 80))
        self._style()
        self._build()
        root.protocol('WM_DELETE_WINDOW', self.on_close)
        root.bind('<Control-s>', lambda e: self.save())
        root.bind('<Control-o>', lambda e: self.open_dialog())
        root.bind('<F5>', lambda e: self.reload())
        root.after(POLL_MS, self.poll_file)

        if start_file:
            self.open_file(start_file)
        else:
            default = self._default_file()
            if default:
                self.open_file(default)
            else:
                self.message('warn', 'Click "Open .SKA…" to choose a skater file.')

    # ------------------------------------------------------------- styling --
    def _style(self):
        s = ttk.Style(self.root)
        s.theme_use('clam')
        f = ('Segoe UI', 10)
        s.configure('.', background=C['bg'], foreground=C['text'], fieldbackground=C['field'],
                    bordercolor=C['line'], lightcolor=C['line'], darkcolor=C['line'], font=f)
        s.configure('TCombobox', fieldbackground=C['field'], background=C['field'], foreground=C['text'],
                    arrowcolor=C['text'], bordercolor=C['line'], padding=4)
        s.map('TCombobox',
              fieldbackground=[('readonly', C['field']), ('disabled', C['bg'])],
              foreground=[('disabled', C['muted']), ('readonly', C['text'])],
              selectbackground=[('readonly', C['field'])], selectforeground=[('readonly', C['text'])],
              bordercolor=[('focus', C['accent'])], arrowcolor=[('disabled', C['muted'])])
        # scrollbars (used by the dropdown lists): trough a bit lighter than the app, grey slider
        for sb in ('Vertical.TScrollbar', 'Horizontal.TScrollbar'):
            s.configure(sb, troughcolor='#24242c', background='#6b6b76', bordercolor='#24242c',
                        lightcolor='#6b6b76', darkcolor='#6b6b76', arrowcolor='#c8c8d0',
                        gripcount=0, relief='flat', arrowsize=14)
            s.map(sb, background=[('pressed', '#9a9aa6'), ('active', '#83838f')],
                  lightcolor=[('pressed', '#9a9aa6'), ('active', '#83838f')],
                  darkcolor=[('pressed', '#9a9aa6'), ('active', '#83838f')],
                  arrowcolor=[('disabled', '#55555e')])
        bad = C['bad']
        s.configure('Bad.TCombobox', fieldbackground=C['field'], background=C['field'], foreground=C['text'],
                    arrowcolor=C['text'], bordercolor=bad, lightcolor=bad, darkcolor=bad, padding=4)
        s.map('Bad.TCombobox',
              fieldbackground=[('readonly', '#2a1717')], foreground=[('readonly', C['text'])],
              selectbackground=[('readonly', '#2a1717')], selectforeground=[('readonly', C['text'])],
              bordercolor=[('focus', bad), ('!focus', bad)], lightcolor=[('focus', bad), ('!focus', bad)],
              darkcolor=[('focus', bad), ('!focus', bad)])
        # same trick used in more than one slot: blue outline, no message
        dup = C['dup']
        s.configure('Dup.TCombobox', fieldbackground=C['field'], background=C['field'], foreground=C['text'],
                    arrowcolor=C['text'], bordercolor=dup, lightcolor=dup, darkcolor=dup, padding=4)
        s.map('Dup.TCombobox',
              fieldbackground=[('readonly', '#17202e')], foreground=[('readonly', C['text'])],
              selectbackground=[('readonly', '#17202e')], selectforeground=[('readonly', C['text'])],
              bordercolor=[('focus', dup), ('!focus', dup)], lightcolor=[('focus', dup), ('!focus', dup)],
              darkcolor=[('focus', dup), ('!focus', dup)])
        s.configure('TButton', background=C['field'], foreground=C['text'], bordercolor=C['line'],
                    focuscolor=C['accent'], padding=(12, 6))
        s.map('TButton', background=[('active', '#2a2a33'), ('disabled', C['bg'])],
              foreground=[('disabled', C['muted'])])
        s.configure('Accent.TButton', background=C['accent'], foreground='white', bordercolor=C['accent'],
                    font=('Segoe UI', 10, 'bold'))
        s.map('Accent.TButton', background=[('active', '#38b56a'), ('disabled', '#1d3a28')],
              foreground=[('disabled', '#7d9c88')])
        self.root.option_add('*TCombobox*Listbox.background', C['field'])
        self.root.option_add('*TCombobox*Listbox.foreground', C['text'])
        self.root.option_add('*TCombobox*Listbox.selectBackground', C['accent'])
        self.root.option_add('*TCombobox*Listbox.selectForeground', 'white')
        self.root.option_add('*TCombobox*Listbox.font', f)

    # -------------------------------------------------------------- layout --
    def _build(self):
        top = tk.Frame(self.root, bg=C['panel'], padx=16, pady=10)
        top.pack(fill='x')
        lbl(top, APP_NAME, font=('Segoe UI', 14, 'bold'), bg=C['panel']).pack(side='left', padx=(0, 18))
        ttk.Button(top, text='Open .SKA…', command=self.open_dialog).pack(side='left')
        # small round "?" (about a third of a normal button), vertically centred on the row
        help_btn = tk.Canvas(top, width=20, height=20, bg=C['panel'], highlightthickness=0, cursor='hand2')
        oval = help_btn.create_oval(1, 1, 19, 19, fill=C['field'], outline=C['line'], width=1)
        help_btn.create_text(10, 10, text='?', fill=C['text'], font=('Segoe UI', 9, 'bold'))
        help_btn.bind('<Button-1>', lambda e: self.show_help())
        help_btn.bind('<Enter>', lambda e: help_btn.itemconfig(oval, fill='#2a2a33', outline=C['accent']), add='+')
        help_btn.bind('<Leave>', lambda e: help_btn.itemconfig(oval, fill=C['field'], outline=C['line']), add='+')
        help_btn.pack(side='left', padx=(6, 0))
        Tooltip(help_btn, 'How THUG Pro saves custom skaters, and where to find them')
        lbl(top, 'Skater', fg=C['muted'], bg=C['panel']).pack(side='left', padx=(18, 6))
        # one custom skater per .SKA, so just show its name
        self.skater_name = tk.Label(top, text='—', bg=C['field'], fg=C['text'], font=('Segoe UI', 10, 'bold'),
                                    padx=12, pady=5, highlightthickness=1, highlightbackground=C['line'])
        self.skater_name.pack(side='left')
        self.save_btn = ttk.Button(top, text='Save to file', style='Accent.TButton', command=self.save)
        self.save_btn.pack(side='right')
        self.refresh_btn = ttk.Button(top, text='⟳ Refresh', command=self.reload)
        self.refresh_btn.pack(side='right', padx=(8, 8))
        self.overwrite_btn = ttk.Button(top, text='Overwrite', command=self.overwrite)
        self.overwrite_btn.pack(side='right', padx=(8, 0))
        Tooltip(self.overwrite_btn,
                'Replace ALL tricks on currently selected skater with tricks from another saved skater.')
        self.revert_btn = ttk.Button(top, text='Revert', command=self.revert)
        self.revert_btn.pack(side='right')

        body = tk.Frame(self.root, bg=C['bg'], padx=18, pady=12)
        body.pack(fill='both', expand=True)

        cur = tk.Frame(body, bg=C['panel'], highlightbackground=C['line'], highlightthickness=1)
        cur.pack(fill='x')
        tk.Frame(cur, bg=C['accent'], width=5).pack(side='left', fill='y')
        inner = tk.Frame(cur, bg=C['panel'], padx=12, pady=8)
        inner.pack(side='left', fill='x', expand=True)
        lbl(inner, 'CURRENTLY EDITING', fg=C['muted'], bg=C['panel'], font=('Segoe UI', 8, 'bold')).pack(anchor='w')
        line = tk.Frame(inner, bg=C['panel'])
        line.pack(anchor='w')
        self.cur_file = lbl(line, 'No file open', bg=C['panel'], font=('Segoe UI', 13, 'bold'))
        self.cur_file.pack(side='left')
        self.cur_skater = lbl(line, '', fg=C['muted'], bg=C['panel'], font=('Segoe UI', 12))
        self.cur_skater.pack(side='left', padx=(8, 0))
        self.cur_path = lbl(inner, '', fg=C['muted'], bg=C['panel'], font=('Segoe UI', 9),
                            anchor='w', justify='left', wraplength=840)
        self.cur_path.pack(anchor='w', fill='x')

        self.banner = lbl(body, '', anchor='w', justify='left', padx=12, pady=6, wraplength=860)

        legend = tk.Frame(body, bg=C['bg'])
        legend.pack(fill='x', pady=(10, 4))
        self.legend = legend
        for shape in ('Triangle', 'Square', 'Circle'):
            cv = tk.Canvas(legend, width=22, height=22, bg=C['bg'], highlightthickness=0)
            draw_icon(cv, shape, 11, 12, 12, BTN_COLOR[shape])
            cv.pack(side='left')
            lbl(legend, KP[shape], fg=C['muted']).pack(side='left', padx=(2, 14))
        self.legend_text = lbl(legend, '', fg=C['muted'])
        self.legend_text.pack(side='left')

        # tab bar
        tabbar = tk.Frame(body, bg=C['bg'])
        tabbar.pack(fill='x', pady=(8, 0))
        self.tab_widgets = {}
        for key, title in TABS:
            f = tk.Frame(tabbar, bg=C['bg'], cursor='hand2')
            f.pack(side='left', padx=(0, 4))
            t = tk.Label(f, text=title, bg=C['bg'], fg=C['muted'], font=('Segoe UI', 11), padx=14, pady=6,
                         cursor='hand2')
            t.pack()
            bar = tk.Frame(f, height=3, bg=C['bg'])
            bar.pack(fill='x')
            for wdg in (f, t):
                wdg.bind('<Button-1>', lambda e, k=key: self.show_tab(k))
            self.tab_widgets[key] = (t, bar)
        tk.Frame(body, height=1, bg=C['line']).pack(fill='x', pady=(0, 10))

        pages = tk.Frame(body, bg=C['bg'])
        pages.pack(fill='both', expand=True)
        self.pages = {'special': SpecialsPage(self, pages)}
        for k in ('grab', 'flip', 'lip'):
            self.pages[k] = MappingPage(self, pages, k)
        self.show_tab('special')

    def show_tab(self, key):
        self.tab = key
        for k, page in self.pages.items():
            page.frame.pack_forget()
        self.pages[key].frame.pack(fill='both', expand=True)
        for k, (t, bar) in self.tab_widgets.items():
            on = k == key
            t.config(fg=C['text'] if on else C['muted'], font=('Segoe UI', 11, 'bold' if on else 'normal'))
            bar.config(bg=C['accent'] if on else C['bg'])
        self.legend_text.config(text={
            'special': 'Grind, manual and lip use KP8. Air uses KP4 or KP6.',
            'grab': 'Grab tricks: direction + KP6. Double tap = press the direction twice.',
            'flip': 'Flip tricks: direction + KP4. Double tap = press the direction twice.',
            'lip': 'Lip tricks: direction + KP8 on a lip.'}[key])
        self.update_tab_titles()

    def update_tab_titles(self):
        for k, title in TABS:
            t, _ = self.tab_widgets[k]
            t.config(text=title + ('  •' if self.pages[k].dirty() else ''))

    # --------------------------------------------------------------- files --
    def _default_file(self):
        d = ts.get_save_dir()
        if not os.path.isdir(d):
            return None
        files = sorted(f for f in os.listdir(d) if f.upper().endswith('.SKA'))
        pref = [f for f in files if f.lower() != 'fullsavegame.ska'] or files
        return os.path.join(d, pref[0]) if pref else None

    def show_help(self):
        HelpDialog(self.root)

    def open_dialog(self):
        if not self.confirm_discard():
            return
        start = os.path.dirname(self.path) if self.path else ts.get_save_dir()
        p = filedialog.askopenfilename(parent=self.root, title='Open a THUG Pro skater (.SKA)',
                                       initialdir=start if os.path.isdir(start) else None,
                                       filetypes=[('THUG Pro skater', '*.ska *.SKA'), ('All files', '*.*')])
        if p:
            self.open_file(p)

    def open_file(self, path, quiet=False):
        path = os.path.abspath(path)
        try:
            skaters = ts.load_save(path)
            created = ts.load_created_tricks(path)
            stamp = ts.file_stamp(path)
        except (OSError, ts.SaveError) as e:
            if quiet:
                self.message('bad', 'Could not reload: %s' % e)
            else:
                messagebox.showerror(APP_NAME, 'Could not open %s\n\n%s' % (path, e), parent=self.root)
            return False
        self.path, self.skaters, self.created, self.stamp = path, skaters, created, stamp
        self.cur_file.config(text=os.path.basename(path))
        self.cur_path.config(text=path + '   —   saves go to this file only')
        self.root.title('%s — %s' % (APP_NAME, os.path.basename(path)))
        custom = next((n for n, s in enumerate(skaters) if s['custom']), len(skaters) - 1)
        self.skater_name.config(text=skaters[custom]['label'])
        self.select_skater(custom)
        self.message(None)
        if ts.in_game_save_dir(path) and ts.game_running():
            self.message('warn', 'THUG Pro is running. Close it before saving, or the game will overwrite your changes.')
        return True

    def reload(self, auto=False):
        if not self.path:
            return
        if not auto and not self.confirm_discard():
            return
        if self.open_file(self.path, quiet=True):
            self.message('ok', ('The file changed on disk, so it was reloaded.' if auto else 'Reloaded from disk.'))

    def poll_file(self):
        try:
            if self.path and os.path.exists(self.path) and ts.file_stamp(self.path) != self.stamp:
                if self.is_dirty():
                    self.message('warn', 'The file changed on disk (maybe the game saved). '
                                 'Press Refresh to load it; your unsaved edits here would be discarded.')
                    self.stamp = ts.file_stamp(self.path)
                else:
                    self.reload(auto=True)
        finally:
            self.root.after(POLL_MS, self.poll_file)

    def select_skater(self, idx):
        self.skater = self.skaters[idx]
        self.cur_skater.config(text='·  ' + self.skater['label'])
        self.created_imports = {}
        self.pages['special'].load(self.skater)
        created = self.created  # the save's created tricks
        for k in ('grab', 'flip', 'lip'):
            self.pages[k].load(self.skater, created)
        self.changed()

    def set_created_view(self, names):
        for k in ('grab', 'flip'):
            self.pages[k].created = list(names)

    # ---------------------------------------------------------- state --
    def is_dirty(self):
        return bool(getattr(self, 'created_imports', None)) or any(p.dirty() for p in self.pages.values())

    def changed(self):
        for p in self.pages.values():
            p.refresh()
        self.update_tab_titles()
        errs = any(self.pages['special'].errors())
        dirty = self.is_dirty()
        self.save_btn.state(['!disabled'] if dirty and not errs and self.path else ['disabled'])
        self.revert_btn.state(['!disabled'] if dirty else ['disabled'])
        self.overwrite_btn.state(['!disabled'] if self.path else ['disabled'])

    def message(self, kind, text=''):
        if not kind:
            self.banner.pack_forget()
            return
        bg = {'warn': '#3a2c10', 'bad': '#3a1414', 'ok': '#12301f'}[kind]
        self.banner.config(text=text, bg=bg, fg=C['text'])
        self.banner.pack(fill='x', pady=(10, 0), before=self.legend)

    # ---------------------------------------------------------- save/close --
    def revert(self):
        self.created_imports = {}
        self.set_created_view(self.created)
        for p in self.pages.values():
            p.revert()
        self.changed()

    def plan_created_imports(self, donor, src, src_created):
        """Work out which of the donor's created tricks must be copied into this save and which
        created-trick slots they go in. Returns (imports {idx: (blob, name)}, replaced [(idx, old, new)], notes)."""
        needed = {}  # donor index -> name, for created tricks the donor uses that this save lacks
        for v in (donor.get('mapping') or {}).values():
            n = v.get('created')
            if n is None:
                continue
            name = src_created[n] if 0 <= n < len(src_created) else None
            same_slot = 0 < n < len(self.created) and self.created[n] == name
            if name and not same_slot and name not in self.created[1:]:
                needed[n] = name
        if not needed:
            return {}, [], []
        mine = {v['created'] for v in (self.skater.get('mapping') or {}).values() if 'created' in v}
        # prefer created-trick slots the skater doesn't use, then the ones it did (being replaced anyway)
        free = sorted(range(1, len(self.created)), key=lambda i: (i in mine, i))
        imports, replaced, notes = {}, [], []
        for n, name in sorted(needed.items()):
            if not free:
                notes.append('created trick "%s": no free created-trick slot in this save, set to Default' % name)
                continue
            idx = free.pop(0)
            try:
                blob, _ = ts.created_trick_blob(src, n)
            except (OSError, ts.SaveError) as e:
                notes.append('created trick "%s": could not be read (%s), set to Default' % (name, e))
                continue
            imports[idx] = (blob, name)
            replaced.append((idx, self.created[idx], name))
        return imports, replaced, notes

    def overwrite(self):
        """Load every trick from another saved skater into the current skater (unsaved until Save)."""
        if not self.path or not self.skater:
            self.message('warn', 'Open a skater first, then use Overwrite.')
            return
        start = os.path.dirname(self.path)
        src = filedialog.askopenfilename(parent=self.root, title='Overwrite with tricks from… (.SKA)',
                                         initialdir=start if os.path.isdir(start) else None,
                                         filetypes=[('THUG Pro skater', '*.ska *.SKA'), ('All files', '*.*')])
        if not src:
            return
        try:
            src_skaters = ts.load_save(src)
            src_created = ts.load_created_tricks(src)
        except (OSError, ts.SaveError) as e:
            messagebox.showerror(APP_NAME, 'Could not read %s\n\n%s' % (src, e), parent=self.root)
            return
        # each .SKA holds one custom skater: that's the one we copy from
        donor = next((s for s in src_skaters if s['custom']), src_skaters[-1])
        target = self.skater['label']
        imports, replaced, notes = self.plan_created_imports(donor, src, src_created)
        prompt = ('Replace ALL tricks on %s with the tricks from %s (%s)?\n\n'
                  'This covers special, grab, flip and lip tricks.\n\n'
                  '⚠ WARNING: this may overwrite your created tricks.'
                  % (target, donor['label'], os.path.basename(src)))
        if replaced:
            prompt += ('\nThese created tricks in %s will be replaced so the copied tricks can come with them:\n'
                       % os.path.basename(self.path))
            prompt += '\n'.join('   #%d  "%s"  →  "%s"' % r for r in replaced)
        else:
            prompt += ('\nNo created tricks need to be replaced for this one, but any created tricks '
                       'this skater used are swapped for the copied ones.')
        prompt += '\n\nNothing is written until you press Save; Revert undoes it.'
        if not messagebox.askyesno(APP_NAME, prompt, icon='warning', parent=self.root):
            return

        self.created_imports = {i: blob for i, (blob, _) in imports.items()}
        names = list(self.created)
        for i, (_, name) in imports.items():
            names[i] = name
        self.set_created_view(names)

        sp = self.pages['special']
        sp.current = [row_from_entry(e) for e in donor['slots']]
        if donor.get('mapping') is None:
            notes.append('grab/flip/lip: the source skater has no readable mapping, left unchanged')
        else:
            for k in ('grab', 'flip', 'lip'):
                notes += self.pages[k].apply_from(donor['mapping'], src_created)
        self.changed()
        if replaced:
            notes_ok = ['created trick #%d "%s" will be replaced by "%s"' % r for r in replaced]
        else:
            notes_ok = []
        text = ('Loaded all tricks from %s (%s) into %s. Review them, then press Save to write them '
                'to %s, or Revert to undo.' % (donor['label'], os.path.basename(src), target,
                                               os.path.basename(self.path)))
        if notes_ok:
            text += '\n• ' + '\n• '.join(notes_ok)
        if notes:
            text += '\nNot copied exactly:\n• ' + '\n• '.join(notes)
        self.message('warn' if notes or notes_ok else 'ok', text)

    def save(self):
        if not self.path or not self.is_dirty():
            return
        if any(self.pages['special'].errors()):
            self.show_tab('special')
            return
        if ts.in_game_save_dir(self.path) and ts.game_running():
            self.message('bad', 'Close THUG Pro first. It would overwrite these changes when it saves.')
            return
        mapping = {}
        for k in ('grab', 'flip', 'lip'):
            mapping.update(self.pages[k].payload())
        try:
            backup = ts.write_skater(self.path, self.skater['offset'],
                                     specials=self.pages['special'].payload(), mapping=mapping or None,
                                     created_imports=self.created_imports or None)
        except (OSError, ts.SaveError) as e:
            self.message('bad', 'Not saved: %s' % e)
            return
        self.open_file(self.path)
        self.message('ok', 'Saved to %s\nBackup of the previous version: %s' % (os.path.basename(self.path), backup))

    def confirm_discard(self):
        return not self.is_dirty() or messagebox.askyesno(
            APP_NAME, 'You have unsaved changes. Discard them?', parent=self.root)

    def on_close(self):
        if self.confirm_discard():
            self.root.destroy()


def main():
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    try:
        root.iconbitmap(ts.resource_path('icon.ico'))
    except Exception:
        pass
    start = sys.argv[1] if len(sys.argv) > 1 else None
    App(root, start)
    root.mainloop()


if __name__ == '__main__':
    main()
