## Overview

Sublime Text plugin for auto-formatting arbitrary code by calling arbitrary executables. Works for `gofmt`, `rustfmt`, any similar tool that's an executable and uses standard input/output.

Features:

* Auto-format on save or on demand (configurable).
* Configure executables and other settings per _scope_ (syntax type: `source.go`, `source.rust` and so on).
* Preserve cursor and scroll position when formatting.
* Show errors in an output panel (configurable).

This is based on https://github.com/mitranim/sublime-gofmt and fully replaces it. It can also replace https://github.com/mitranim/sublime-rust-fmt, but you'll have to specify a few CLI args yourself.

## Installation

This plugin is not on Package Control and requires manual installation.

Clone the repo and symlink it to your Sublime packages directory. Example for MacOS:

```sh
git clone https://github.com/mitranim/sublime-fmt.git
cd sublime-fmt
ln -sf "$(pwd)" "$HOME/Library/Application Support/Sublime Text 3/Packages/"
```

To find the packages directory on your system, use Sublime Text menu → Preferences → Browse Packages.

## Usage

The plugin has _no default formatters_. You must specify them yourself. Example for Go:

```sublime-settings
{
  "scopes": {
    "source.go": {
      "cmd": ["goimports"],
    },
  },
}
```

By default, this will autoformat on save (configurable). You can format manually with the `fmt: Format Buffer` command in the command palette.

**How to get the scope name**. Option 1: menu → Tools → Developer → Show Scope Name. Option 2: run the `fmt_format_buffer` command, and if not configured for the current scope, it will tell you!

## Settings

See [`fmt.sublime-settings`](fmt.sublime-settings) for all available settings. To override them, open:

```
Preferences → Package Settings → fmt → Settings
```

The plugin looks for settings in the following places, with the following priority:

  * `"fmt"` dict in general Sublime settings, project-specific or global.
  * `fmt.sublime-settings`, user-created or default.

For overrides, open project or global settings and make a `"fmt"` entry:

```sublime-settings
{
  "fmt": {
    "format_on_save": false,
    "scopes": {
      "source.some_lang": {
        "cmd": ["some_lang_fmt", "--some_arg"],
      },
    },
  },
}
```

## Commands

In Sublime's command palette:

* `fmt: Format Buffer`

## Hotkeys

Hotkeys? More like _notkeys_!

To avoid potential conflicts, this plugin does not come with hotkeys. To hotkey
the format command, add something like this to your `.sublime-keymap`:

```sublime-keymap
{"keys": ["ctrl+super+k"], "command": "fmt_format_buffer"}
```

## Changelog

**2020-10-23**. Now supports several ways of printing errors. By default, errors are shown in a transient output panel at the bottom.

## License

https://unlicense.org
