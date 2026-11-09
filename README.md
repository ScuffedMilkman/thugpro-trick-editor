# THUG Pro Trick Editor

A Windows desktop app for editing the tricks of a custom skater in a THUG Pro save
file (`.SKA`), without clicking through the in-game menus.

## Download and run

1. Download `THUG.Pro.Trick.Editor.exe` from the
   [latest release](https://github.com/ScuffedMilkman/thugpro-trick-editor/releases/latest).
2. Close THUG Pro, then double-click the .exe. It opens a skater from your save folder.

## Features

- **Special Tricks**: all 12 slots. Pick the type (grind, manual, air, lip), the trick, and the
  combo (two arrows plus a button). Problems such as two slots on the same combo are shown above
  the slot with a red outline, and Save stays off until they're fixed.
- **Grab / Flip / Lip Tricks**: the standard button mapping, including double-tap slots and the
  save's created tricks (★). Lip slots you haven't changed show the default from the lip set.
- **Overwrite**: replaces every trick on the skater with the tricks from another `.SKA`. If the
  other save uses created tricks this one doesn't have, they're copied over too; the confirmation
  warns that this may overwrite created tricks and lists exactly which ones.
- The same trick on more than one slot gets a blue outline, so duplicates stand out.
- Buttons are shown PlayStation-style and matched to the PC keypad: △ KP8, □ KP4, ○ KP6.
- **Refresh** rescans the file, and the app reloads automatically when the file changes on disk
  (for example after the game saves) as long as you have no unsaved edits.
- **Revert** throws away unsaved edits. Changed slots and tabs are marked until you save.

## Saving and safety

- Changes are only written when you press **Save to file**, and only to the file shown under
  *Currently editing*.
- Before every save the previous file is copied into a `TrickEditorBackups` folder next to it.
- The app recomputes the save's checksums and verifies the new file before replacing the old one.
- It won't save into the game's save folder while THUG Pro is running, because the game would
  overwrite the changes.

## Save folder

THUG Pro keeps skater saves in `%LOCALAPPDATA%\THUG Pro\Save`. If yours are somewhere else,
click the **?** button next to **Open .SKA…** and choose **Change…**. The choice is stored in
`%APPDATA%\THUG Pro Trick Editor\settings.json`; **Use default** puts it back.


## Building from source

Requires Python 3.10+ (standard library only).

```
python app.py [file.SKA]      run from source
build.bat                     build the single-file .exe (needs: pip install pyinstaller)
```

| File | What it is |
|---|---|
| `app.py` | The desktop window (tkinter). |
| `thugsave.py` | Reads and writes the save format: checksums, specials, trick mapping, created tricks. |
| `catalog.json` | Trick names and types plus the save-format key table, taken from the game's scripts. |
| `icon.ico` | App icon. |
| `build.bat` | PyInstaller build script. |

## License

[MIT](LICENSE)

## Disclaimer

This is an unofficial fan tool. It is not affiliated with or endorsed by the THUG Pro team,
Activision or Neversoft. Use it at your own risk and keep backups of your saves.
