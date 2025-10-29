
# Shelves Plugin for MusicBrainz Picard

## Description

The **Shelves** plugin adds virtual shelf management to MusicBrainz Picard, allowing you to organize your music files by top-level folders (shelves) in your music library.

Think of your music library as a physical library with different shelves - one for your standard collection, one for incoming/unprocessed music, one for Christmas music, etc.

## Features

- ✅ **Automatic shelf detection** from file paths during scanning
- ✅ **Smart detection** prevents artist/album names from being mistaken as shelves
- ✅ **Manual shelf assignment** via context menu
- ✅ **Shelf management** in plugin settings (add, remove, scan)
- ✅ **Undo functionality** to restore previous shelf assignments
- ✅ **Workflow support** (e.g., auto-staging from "Incoming" to "Standard")
- ✅ **File naming script integration** for organized storage

## Installation

1. Copy the `shelves` folder to your Picard plugins directory:
   - **Linux:** `~/.config/MusicBrainz/Picard/plugins/`
   - **Windows:** `%APPDATA%\MusicBrainz\Picard\plugins\`
   - **macOS:** `~/.config/MusicBrainz/Picard/plugins/`

2. Restart Picard

3. Enable the plugin in: **Options → Plugins → Shelves**

## Usage

### Directory Structure

The plugin expects your music library to be organized like this:

    ~/Music/
    ├── Standard/
    │   ├── Artist Name/
    │   │   └── Album Name/
    │   │       └── track.mp3
    ├── Incoming/
    ├── Christmas/
    ├── Soundtrack/
    └── ...

Each top-level folder under your music directory is considered a "shelf".

### Automatic Detection

When you scan files in Picard, the plugin automatically:
1. Detects the shelf name from the file path
2. Sets the `shelf` tag in the file metadata
3. Adds the shelf to the list of known shelves

### Smart Shelf Detection

The plugin includes intelligent detection to prevent confusion:

- **Default and known shelves** are always recognized correctly
- **Suspicious folder names** are automatically identified and treated as misplaced files:
  - Names containing " - " (typical for "Artist - Album" format)
  - Very long names (> 30 characters)
  - Names with many words (> 3 words)
  - Names containing album indicators (Vol., Disc, CD, Part)

**Example:**
- If you accidentally place files in `~/Music/Wardruna - Runaljod - Yggdrasil/`, the plugin recognizes this as an artist/album name (not a shelf)
- The shelf tag is automatically set to "Standard" instead
- Files will be organized properly when saved: `~/Music/Standard/Wardruna/Runaljod - Yggdrasil/`

**Note:** If you *really* want to use such a name as a shelf, simply add it manually in the plugin settings. Once added, it will be recognized as a valid shelf.

### Manual Assignment

**Right-click** on albums or tracks in Picard and select:
- **"Set shelf name..."** - Assign or change the shelf
- **"Undo set shelf name"** - Restore the previous shelf value

### Plugin Settings

Open **Options → Plugins → Shelves** to:
- View all known shelves
- Add new shelves manually
- Remove shelves from the list
- **Scan Music Directory** - Automatically detect all shelves from your music folder

## File Naming Script

To organize files by shelf when saving, use this file naming script in **Options → File Naming**:

    $set(_basefolder,$if(%shelf%,%shelf%))

    $noop(*** Workflow ***)
    $noop(*** Stage Incoming ⇢ Standard ***)
    $set(_basefolder,$if($eq(%_basefolder%,"Incoming"),"Standard", %_basefolder%))

    $noop(*** add path separator if necessary ***)
    $set(_basefolder,$if($not($eq(%_basefolder%,)),%_basefolder%/))

    %_basefolder%
    $if2(%albumartist%,%artist%)/
    $if(%albumartist%,%album%/,)
    $if($gt(%totaldiscs%,1),%discnumber%-,)
    $if($and(%albumartist%,%tracknumber%),$num(%tracknumber%,2) ,)
    $if(%_multiartist%,%artist% - ,)
    %title%

### Workflow Examples

#### Example 1: Incoming → Standard

This script implements an "Incoming → Standard" workflow:

1. **Scan** music files from `~/Music/Incoming/Artist/Album/`
2. Plugin sets `shelf` tag to "Incoming"
3. Do your tagging/editing in Picard
4. **Save** the files
5. Files are automatically moved to `~/Music/Standard/Artist/Album/`

#### Example 2: Manual Shelf Change

If you want to keep files in a specific shelf (e.g., "Christmas"):

1. **Scan** files from any location
2. **Right-click** the album → **"Set shelf name..."** → Select "Christmas"
3. **Save** the files
4. Files are moved to `~/Music/Christmas/Artist/Album/`

#### Example 3: Moving Between Shelves Outside Picard

If you manually move files outside of Picard:

1. Move `~/Music/Standard/Artist/Album/` to `~/Music/Soundtrack/Artist/Album/` (outside Picard)
2. **Scan** the files in Picard
3. Plugin automatically detects shelf as "Soundtrack"
4. When you **Save**, files remain in `~/Music/Soundtrack/Artist/Album/`

#### Example 4: Accidentally Misplaced Files

If you accidentally place files directly under Music:

1. Files are in: `~/Music/Artist - Album/tracks/`
2. **Scan** in Picard
3. Plugin detects suspicious name, sets shelf to "Standard" (with warning in log)
4. **Save** moves files to: `~/Music/Standard/Artist/Album/`

## Tag Information

- **Tag name:** `shelf`
- **Backup tag:** `shelfbackup` (used for undo, not saved to files)
- **Default shelves:** Standard, Incoming

## Troubleshooting

### My folder name is detected as "Standard" instead of the actual folder name

This is intentional! The plugin detected that your folder name looks like an artist/album name rather than a shelf name. Check the log for details about why it was considered suspicious.

**Solutions:**
1. **Recommended:** Let the plugin move your files to the correct location (`Standard/Artist/Album/`)
2. **Alternative:** If this folder name really should be a shelf, add it manually in the plugin settings

### How can I see which shelf was detected?

1. Select a file/album in Picard
2. Look at the metadata panel on the right
3. Find the `shelf` tag

You can also check Picard's log (Help → View Error/Debug Log) for detailed information about shelf detection.

## Requirements

- MusicBrainz Picard 2.0 or higher
- PyQt5

## License

GPL-2.0

## Author

nrth3rnlb

## Version

1.0.0