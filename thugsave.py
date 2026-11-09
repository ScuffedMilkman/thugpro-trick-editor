"""Read and write the special-trick slots inside THUG Pro skater saves (*.SKA)."""
import datetime
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zlib

DEFAULT_SAVE_DIR = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'THUG Pro', 'Save')
SETTINGS_PATH = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')),
                             'THUG Pro Trick Editor', 'settings.json')


def _load_settings():
    try:
        with open(SETTINGS_PATH, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def get_save_dir():
    """The THUG Pro save folder: the user's choice if they set one, otherwise the default."""
    custom = _load_settings().get('save_dir')
    return custom if custom else DEFAULT_SAVE_DIR


def set_save_dir(path):
    """Remember a different save folder (None or the default folder resets it)."""
    data = _load_settings()
    if not path or os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(DEFAULT_SAVE_DIR)):
        data.pop('save_dir', None)
    else:
        data['save_dir'] = os.path.abspath(path)
    if not data and not os.path.exists(SETTINGS_PATH):
        return
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1)


def save_dir_is_custom():
    return bool(_load_settings().get('save_dir'))


def resource_path(name):
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)

# ---------------------------------------------------------------- hashing ---

def qbkey(name):
    """THUG checksum of a script name (CRC32, no final xor, case-insensitive)."""
    return zlib.crc32(name.lower().encode()) ^ 0xFFFFFFFF


def crc(data):
    return zlib.crc32(data) ^ 0xFFFFFFFF


KEY_SLOT = 0xA8   # 'trickslot' field index in the save format
KEY_TRICK = 0xA9  # 'trickname' field index
UNASSIGNED = 'Unassigned'
UNASSIGNED_KEY = qbkey(UNASSIGNED)

TYPES = ['grind', 'manual', 'air', 'lip']
SLOT_PREFIX = {'grind': 'SpGrind', 'manual': 'SpMan', 'air': 'SpAir', 'lip': 'SpLip'}
SLOT_RE = re.compile(r'^Sp(Man|Grind|Lip|Air)_([UDLR])_([UDLR])_(Triangle|Square|Circle)$', re.I)


def all_slot_names():
    names = []
    for a in 'UDLR':
        for b in 'UDLR':
            if a != b:
                p = a + '_' + b
                names += ['SpMan_%s_Triangle' % p, 'SpGrind_%s_Triangle' % p,
                          'SpLip_%s_Triangle' % p, 'SpAir_%s_Square' % p, 'SpAir_%s_Circle' % p]
    return names + ['SpLip_U_U_Triangle', 'SpAir_L_U_Triangle']


SLOT_BY_KEY = {qbkey(n): n for n in all_slot_names()}
SLOT_BY_KEY[UNASSIGNED_KEY] = UNASSIGNED

with open(resource_path('catalog.json'), encoding='utf-8') as _f:
    _CAT = json.load(_f)
CATALOG = _CAT['tricks']             # special tricks
STANDARD = _CAT['standard']          # standard grab / flip / lip tricks
LIP_PRESETS = _CAT['lip_presets']    # included lip sets, e.g. HawkLip
COMPRESS8 = _CAT['compress8']        # save-format key table (1-byte index -> name)
EXTRA_NAMES = _CAT['names']          # display names for other trick ids
STANDARD_BY_ID = {t['id']: t for t in STANDARD}
TRICK_BY_ID = {t['id']: t for t in CATALOG}
TRICK_BY_KEY = {qbkey(t['id']): t['id'] for t in CATALOG}
TRICK_BY_KEY[UNASSIGNED_KEY] = UNASSIGNED


def parse_slot(name):
    """'SpAir_L_U_Circle' -> ('air', 'L', 'U', 'Circle'); None if not a normal slot."""
    m = SLOT_RE.match(name or '')
    if not m:
        return None
    t = {'man': 'manual', 'grind': 'grind', 'lip': 'lip', 'air': 'air'}[m.group(1).lower()]
    return t, m.group(2).upper(), m.group(3).upper(), m.group(4).capitalize()


def slot_name(typ, a, b, button):
    return '%s_%s_%s_%s' % (SLOT_PREFIX[typ], a, b, button if typ == 'air' else 'Triangle')


def trick_category(trick_id):
    t = TRICK_BY_ID.get(trick_id)
    if not t:
        return None
    return 'air' if t['type'] in ('grab', 'flip') else t['type']


def name_or_hex(key, table):
    return table.get(key, '0x%08x' % key)


def key_from(value):
    if value is None or value == UNASSIGNED:
        return UNASSIGNED_KEY
    if isinstance(value, str) and value.lower().startswith('0x'):
        return int(value, 16)
    return qbkey(value)

# ------------------------------------------------------------- save format ---

BLOCK_RE = re.compile(rb'\x0a\x0c\x00((?:\x8d[\xa8\xa9].{4}\x8d[\xa8\xa9].{4}\x00){12})', re.S)
ENTRY = 13


class SaveError(Exception):
    pass


def read_header(d):
    if len(d) < 16:
        raise SaveError('This file is too small to be a THUG Pro skater.')
    h0, h1, sumlen, datalen = struct.unpack('<IIII', d[:16])
    if not (16 < datalen <= len(d)) or not (0 < sumlen < datalen):
        raise SaveError('This is not a THUG Pro skater file (unrecognised header).')
    if crc(bytes(4) + bytes(d[4:datalen])) != h0:
        raise SaveError('The save checksum does not match, so it was left alone.')
    return h0, h1, sumlen, datalen


def summary_name(d, sumlen):
    strings = re.findall(rb'[\x20-\x7e]{2,}', bytes(d[20:20 + sumlen]))
    if strings:
        name = strings[0].decode('latin1')
        return name[1:] if name.startswith('+') else name
    return 'Custom skater'


# ----------------------------------------------------- standard trick mapping ---

GRAB_SLOTS = ['Air_CircleU', 'Air_CircleD', 'Air_CircleL', 'Air_CircleR',
              'Air_CircleUL', 'Air_CircleUR', 'Air_CircleDL', 'Air_CircleDR',
              'Air_U_U_Circle', 'Air_D_D_Circle', 'Air_L_L_Circle', 'Air_R_R_Circle']
FLIP_SLOTS = [s.replace('Circle', 'Square') for s in GRAB_SLOTS]
LIP_SLOTS = ['Lip_TriangleU', 'Lip_TriangleD', 'Lip_TriangleL', 'Lip_TriangleR',
             'Lip_TriangleUL', 'Lip_TriangleUR', 'Lip_TriangleDL', 'Lip_TriangleDR']
MAPPING_SLOTS = {'grab': GRAB_SLOTS, 'flip': FLIP_SLOTS, 'lip': LIP_SLOTS}

KEY8_INDEX = {}
for _i, _n in enumerate(COMPRESS8):
    KEY8_INDEX.setdefault(_n.lower(), _i)
KEY_BY_HASH = {qbkey(n): n for n in COMPRESS8}
KEY_TRICK_MAPPING = KEY8_INDEX['trick_mapping']
ID_BY_HASH = {qbkey(t['id']): t['id'] for t in STANDARD}
ID_BY_HASH.update({qbkey(k): k for k in EXTRA_NAMES})
ID_BY_HASH.update({qbkey(k): k for k in LIP_PRESETS})
ID_BY_HASH.update(TRICK_BY_KEY)

# value sizes for the types that appear in mapping structs
VALUE_SIZE = {0x01: 4, 0x02: 4, 0x0D: 4, 0x10: 1, 0x11: 2, 0x12: 0, 0x13: 0}


def trick_display(tid):
    if tid in STANDARD_BY_ID:
        return STANDARD_BY_ID[tid]['name']
    if tid in TRICK_BY_ID:
        return TRICK_BY_ID[tid]['name']
    return EXTRA_NAMES.get(tid, tid)


def find_mapping(d, specials_off):
    """Return (start, end, entries) of the trick_mapping struct before a specials list."""
    start = d.rfind(bytes([0x8A, KEY_TRICK_MAPPING]), max(0, specials_off - 0x400), specials_off)
    if start < 0:
        raise SaveError('No trick mapping found for this skater.')
    i = start + 2
    entries = []
    while True:
        if i >= specials_off:
            raise SaveError('Could not read this skater\'s trick mapping.')
        b = d[i]
        if b == 0:
            i += 1
            break
        typ = b & 0x3F
        if b & 0x80:
            key = COMPRESS8[d[i + 1]] if d[i + 1] < len(COMPRESS8) else '#%d' % d[i + 1]
            hdr = 2
        elif b & 0x40:
            raise SaveError('Unsupported key form in trick mapping.')
        else:
            h = struct.unpack('<I', d[i + 1:i + 5])[0]
            key = '' if h == 0 else KEY_BY_HASH.get(h, '0x%08x' % h)
            hdr = 5
        if typ not in VALUE_SIZE:
            raise SaveError('Unsupported value type 0x%02x in trick mapping.' % typ)
        raw = bytes(d[i:i + hdr + VALUE_SIZE[typ]])
        val = raw[hdr:]
        e = {'key': key, 'raw': raw}
        if typ == 0x0D:
            h = struct.unpack('<I', val)[0]
            e['trick'] = ID_BY_HASH.get(h, '0x%08x' % h)
        elif typ in (0x10, 0x11):
            e['created'] = int.from_bytes(val, 'little')
        entries.append(e)
        i += len(raw)
    return start, i, entries


def mapping_view(entries):
    """slot -> {'trick': id} | {'created': n} | {'default': id-or-None} for every editable slot."""
    explicit = {e['key'].lower(): e for e in entries if e['key']}
    includes = [e['trick'] for e in entries if e['key'] == '' and 'trick' in e]
    defaults = {}
    for inc in includes:
        for k, v in LIP_PRESETS.get(inc, {}).items():
            defaults[k.lower()] = v
    view = {}
    for slots in MAPPING_SLOTS.values():
        for s in slots:
            e = explicit.get(s.lower())
            if e is not None and 'trick' in e:
                view[s] = {'trick': e['trick']}
            elif e is not None and 'created' in e:
                view[s] = {'created': e['created']}
            elif e is not None:
                view[s] = {'other': e['raw'].hex()}
            else:
                view[s] = {'default': defaults.get(s.lower())}
    return view, includes


def created_trick_names(d, datalen):
    """Names of the save's created tricks, in save order (index 0 is the game's scratch copy)."""
    try:
        return [c['name'] for c in parse_created(d, datalen)[1]]
    except SaveError:
        m = re.search(re.escape(b'\x0c' + struct.pack('<I', qbkey('tricks'))) + rb'\x0a(..)', bytes(d[:datalen]), re.S)
        if not m:
            return []
        count = struct.unpack('<H', m.group(1))[0]
        names = [n.decode('latin1') for n in re.findall(rb'\x83\x2b([\x20-\x7e]+)\x00', bytes(d[m.end():datalen]))]
        return names[:count]


# --- generic walker for the save's tagged tree (enough to find created-trick bounds) ---
TREE_SIZE = {0x01: 4, 0x02: 4, 0x05: 12, 0x06: 8, 0x0D: 4, 0x10: 1, 0x11: 2, 0x12: 0, 0x13: 0, 0x1A: 4}


def _skip_value(d, t, i, end):
    if t in TREE_SIZE:
        return i + TREE_SIZE[t]
    if t == 0x03:
        j = d.index(0, i, end)
        return j + 1
    if t == 0x0A:
        return _skip_struct(d, i, end)
    if t == 0x0C:
        et = d[i]
        n = struct.unpack('<H', d[i + 1:i + 3])[0]
        i += 3
        for _ in range(n):
            i = _skip_value(d, et, i, end)
        return i
    raise SaveError('Unsupported value type 0x%02x at 0x%x' % (t, i - 1))


def _skip_struct(d, i, end):
    while True:
        if i >= end:
            raise SaveError('Ran past the end of the save while reading a structure.')
        b = d[i]
        i += 1
        if b == 0:
            return i
        i += 1 if b & 0x80 else (2 if b & 0x40 else 4)
        i = _skip_value(d, b & 0x3F, i, end)


def parse_created(d, datalen):
    """Locate the created-trick list. Returns (header_offset, [{'start','end','name'}...])."""
    d = bytes(d)
    m = re.search(re.escape(b'\x0c' + struct.pack('<I', qbkey('tricks'))) + rb'\x0a(..)', d[:datalen], re.S)
    if not m:
        raise SaveError('This save has no created-trick list.')
    count = struct.unpack('<H', m.group(1))[0]
    items, i = [], m.end()
    for _ in range(count):
        s = i
        i = _skip_struct(d, i, datalen)
        nm = re.search(rb'\x83\x2b([\x20-\x7e]*)\x00', d[s:i])
        items.append({'start': s, 'end': i, 'name': nm.group(1).decode('latin1') if nm else ''})
    return m.start(), items


def created_trick_blob(path, index):
    """Raw bytes of one created trick, for copying into another save."""
    d = open(path, 'rb').read()
    _, _, _, datalen = read_header(d)
    items = parse_created(d, datalen)[1]
    if not 0 <= index < len(items):
        raise SaveError('Created trick #%d does not exist in %s.' % (index, os.path.basename(path)))
    it = items[index]
    return d[it['start']:it['end']], it['name']


def encode_mapping_entry(slot, value):
    idx = KEY8_INDEX.get(slot.lower())
    if idx is None:
        raise SaveError('Unknown slot %s' % slot)
    if 'trick' in value:
        return bytes([0x80 | 0x0D, idx]) + struct.pack('<I', key_from(value['trick']))
    n = int(value['created'])
    if not 0 <= n < 256:
        raise SaveError('Created trick number out of range.')
    return bytes([0x80 | 0x10, idx, n])


def build_mapping(entries, changes):
    """changes: slot -> {'trick': id} | {'created': n} | None (remove -> game default)."""
    want = {k.lower(): (k, v) for k, v in changes.items()}
    out = bytearray([0x8A, KEY_TRICK_MAPPING])
    for e in entries:
        k = e['key'].lower()
        if k and k in want:
            slot, v = want.pop(k)
            if v is not None:
                out += encode_mapping_entry(slot, v)
        else:
            out += e['raw']
    for slot, v in want.values():
        if v is not None:
            out += encode_mapping_entry(slot, v)
    out.append(0)
    return bytes(out)

# ------------------------------------------------------------- specials ---

def parse_entries(d, off):
    entries = []
    i = off + 3
    for _ in range(12):
        k1, v1 = d[i + 1], struct.unpack('<I', d[i + 2:i + 6])[0]
        k2, v2 = d[i + 7], struct.unpack('<I', d[i + 8:i + 12])[0]
        kv = {k1: v1, k2: v2}
        if set(kv) != {KEY_SLOT, KEY_TRICK}:
            raise SaveError('Unexpected specials entry at 0x%x' % i)
        entries.append({'slot': name_or_hex(kv[KEY_SLOT], SLOT_BY_KEY),
                        'trick': name_or_hex(kv[KEY_TRICK], TRICK_BY_KEY),
                        'order': [k1, k2]})
        i += ENTRY
    return entries


def load_save(path):
    d = open(path, 'rb').read()
    _, _, sumlen, datalen = read_header(d)
    blocks = [m.start() for m in BLOCK_RE.finditer(d[:datalen])]
    if not blocks:
        raise SaveError('No special-trick lists were found in this file.')
    off = blocks[-1]  # the save's own skater is the last one stored in the file
    sk = {'offset': off, 'label': summary_name(d, sumlen), 'custom': True, 'slots': parse_entries(d, off),
          'mapping': None, 'mapping_error': None, 'includes': []}
    try:
        _, _, entries = find_mapping(d, off)
        sk['mapping'], sk['includes'] = mapping_view(entries)
    except SaveError as e:
        sk['mapping_error'] = str(e)
    return [sk]


def load_created_tricks(path):
    d = open(path, 'rb').read()
    _, _, _, datalen = read_header(d)
    return created_trick_names(d, datalen)


def file_stamp(path):
    st = os.stat(path)
    return (st.st_mtime_ns, st.st_size)


def write_specials(path, offset, slots, backup_dir=None):
    return write_skater(path, offset, specials=slots, backup_dir=backup_dir)


def _specials_block(d, offset, slots):
    if len(slots) != 12:
        raise SaveError('Need exactly 12 slots.')
    old = parse_entries(d, offset)

    used, block = {}, bytearray()
    for idx, s in enumerate(slots):
        sk, tk = key_from(s.get('slot')), key_from(s.get('trick'))
        if (sk == UNASSIGNED_KEY) != (tk == UNASSIGNED_KEY):
            raise SaveError('Slot %d needs both a trick and a combo (or neither).' % (idx + 1))
        if sk != UNASSIGNED_KEY:
            if sk in used:
                raise SaveError('Slots %d and %d use the same combo.' % (used[sk] + 1, idx + 1))
            used[sk] = idx
        vals = {KEY_SLOT: sk, KEY_TRICK: tk}
        for k in old[idx]['order']:
            block += bytes([0x8D, k]) + struct.pack('<I', vals[k])
        block += b'\x00'
    return block


def _splice(d, datalen, filelen, start, end, new):
    """Replace d[start:end] with new inside the data area, keeping the file length. Returns (d, datalen)."""
    pad = bytes(d[datalen:filelen])
    newlen = datalen - (end - start) + len(new)
    if newlen > filelen:
        raise SaveError('Not enough free space in the save for this change.')
    fill = pad[-1:] if pad else b'i'
    d = bytearray(bytes(d[:start]) + new + bytes(d[end:datalen]) + fill * (filelen - newlen))
    d[12:16] = struct.pack('<I', newlen)
    return d, newlen


def write_skater(path, offset, specials=None, mapping=None, created_imports=None, backup_dir=None):
    """Write one skater's specials (12 slot dicts), standard mapping changes
    ({slot: {'trick': id} | {'created': n} | None}) and created tricks copied from another save
    ({index: raw_bytes}, replacing that created-trick slot). Returns the backup path."""
    d = bytearray(open(path, 'rb').read())
    filelen = len(d)
    _, h1, sumlen, datalen = read_header(d)
    if offset not in {m.start() for m in BLOCK_RE.finditer(bytes(d[:datalen]))}:
        raise SaveError('The file changed since it was opened. Press Refresh and try again.')

    if specials is not None:
        block = _specials_block(d, offset, specials)
        d[offset + 3:offset + 3 + len(block)] = block

    if mapping:
        start, end, entries = find_mapping(d, offset)
        new = build_mapping(entries, mapping)
        d, datalen = _splice(d, datalen, filelen, start, end, new)
        if start < offset:  # the mapping sits before the specials list, which moved with it
            offset += len(new) - (end - start)

    if created_imports:
        # replace from the last slot to the first so earlier offsets stay valid
        for idx in sorted(created_imports, reverse=True):
            items = parse_created(d, datalen)[1]
            if not 0 < idx < len(items):
                raise SaveError('Created-trick slot #%d does not exist in this save.' % idx)
            blob = created_imports[idx]
            _skip_struct(blob, 0, len(blob))  # must be one complete created trick
            d, datalen = _splice(d, datalen, filelen, items[idx]['start'], items[idx]['end'], blob)
        parse_created(d, datalen)  # whole list must still read cleanly

    backup_dir = backup_dir or os.path.join(os.path.dirname(path), 'TrickEditorBackups')
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = os.path.join(backup_dir, '%s.%s.bak' % (os.path.basename(path), stamp))
    shutil.copy2(path, backup)

    d[0:4] = bytes(4)
    d[0:4] = struct.pack('<I', crc(bytes(d[:datalen])))
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(d)
    check = open(tmp, 'rb').read()
    try:
        read_header(check)
        if crc(check[20:20 + sumlen]) != h1:
            raise SaveError('Verification failed.')
    except SaveError:
        os.remove(tmp)
        raise SaveError('Verification failed; the file was left unchanged.')
    os.replace(tmp, path)
    return backup


def game_running():
    if os.name != 'nt':
        return False
    try:
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq THUGPro.exe', '/NH'],
                             capture_output=True, text=True, timeout=5,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout
        return 'thugpro.exe' in out.lower()
    except Exception:
        return False


def in_game_save_dir(path):
    norm = lambda p: os.path.normcase(os.path.abspath(p)).rstrip('\\/')
    return norm(os.path.dirname(path)) in (norm(get_save_dir()), norm(DEFAULT_SAVE_DIR))
