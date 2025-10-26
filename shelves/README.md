# Picard Plugin: Shelves

This plugin adds virtual shelf management to MusicBrainz Picard, allowing music files to be organized by top-level folders.

The plugin assumes that there should be a folder level below the target folder, whose individual folders follow the metaphor of a shelf, and provides support for implementation.

```
~/Music/
├── Standard
├── Special
├── Christmas
├── GoodFeeling
└── Incoming
```

- The top level `~/Music/` is the path to the music library
- The second level with `Default`, `Incoming`, etc. contains the virtual shelves in this library
- In principle, every directory directly below the library directory `~/Music/` represents a shelf

The plugin takes into account that end users make decisions and, for example, move albums to other “shelves” using file managers or other actions.

## Features

- Automatically detects shelf name from file path
- Adds shelf tag `shelves_shelf` to metadata
- Context menu to change or restore shelf name
- Configuration dialog to manage shelf names and preview rename script

## Installation

1. Copy the `shelves` folder into your Picard plugin directory.
2. Enable the plugin in Picard under `Options > Plugins`.

## Rename Script Fragment

This fragment serves to ensure that the paths are configured correctly. The last line is an example of further processing of `_basefolder`.

```picard
$set(_basefolder,
  $if($or($not(%shelves_shelf%),$eq(%shelves_shelf%,)),
    $replace($rreplace($dirname,".*/<library_path>/([^/]+).*","$1"),"Incoming","Standard"),
    %shelves_shelf%
  )
)
$join(<library_path>,%_basefolder%/<Artist>/<Album>/<Title>)
```

Replace `<library_path>` with your actual music folder path. The structure after the shelf is freely configurable.

## Tags Used

- `shelves_shelf`: current shelf name
- `shelves_shelf_backup`: previous shelf name (not saved)
