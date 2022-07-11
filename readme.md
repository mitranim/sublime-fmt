## Overview

Sublime Text plugin for auto-formatting arbitrary code by calling arbitrary executables. Works for `gofmt`, `rustfmt`, any similar tool that's an executable and uses standard input/output.

Features:

* Format on demand. Optionally auto-format on save.
* Configure executables and other settings per _scope_ (syntax type: `source.go`, `source.rust` and so on).
* Preserve cursor and scroll position when formatting.
* Show errors in an output panel (configurable).
* Format either an entire file, or only selection.
  * Selection formatting works for embedded syntaxes, such as JS inside HTML.

Limitations:

* Invokes a subprocess every time. Good enough for formatters written in compiled languages, such as `gofmt` and `rustfmt`. If a given formatter is written in JS and takes a second to start up, this tool might not be suitable.

Based on https://github.com/mitranim/sublime-gofmt and fully replaces it. Also replaces [RustFmt](https://github.com/mitranim/sublime-rust-fmt) and countless others.

## Why

Why this exists?

Package Control has special-case formatter plugins for different languages, and the monstrous Formatter with too many batteries included. This makes it hard to add formatters: someone has to make and publish a new plugin every time, or fork a repo and make a PR, etc.

Many formatters just call a subprocess and use stdio. One plugin can handle them all, while letting the _user_ specify any new formatter for any new syntax! This works for `gofmt`, `rustfmt`, `clang-format`, and endless others.

## Installation

### Package Control

1. Get [Package Control](https://packagecontrol.io).
2. Open the command palette: ⇪⌘P or ⇪^P.
3. `Package Control: Install Package`.
4. `Fmt`.

### Manual

Clone the repo and symlink it to your Sublime packages directory. Example for MacOS:

```sh
git clone https://github.com/mitranim/sublime-fmt.git
cd sublime-fmt
ln -sf "$(pwd)" "$HOME/Library/Application Support/Sublime Text 3/Packages/Fmt"
```

To find the packages directory on your system, use Sublime Text menu → Preferences → Browse Packages.

## Usage

The plugin has _no default formatters_. You must specify them in the plugin settings. Example for Go:

```json
{
  "rules": [
    {
      "selector": "source.go",
      "cmd": ["goimports"],
      "format_on_save": true,
      "merge_type": "diff",
    },
  ],
}
```

To understand Sublime scopes and selector matching, read this short official doc: https://www.sublimetext.com/docs/selectors.html.

**How to get scope name**. Option 1: menu → Tools → Developer → Show Scope Name. Option 2: run the command `Fmt: Format Buffer`, and if not configured for the current scope, it will tell you!

To format on demand, run the `Fmt: Format Buffer` command from the command palette. See below how to configure hotkeys.

To auto-format on save, set `"format_on_save": true` in the settings. Can be global or per rule.

## Settings

See [`Fmt.sublime-settings`](Fmt.sublime-settings) for all available settings. To override them, open:

```
menu → Preferences → Package Settings → Fmt → Settings
```

The plugin looks for settings in the following places, with the following priority:

  * `"Fmt"` dict in general Sublime settings, project-specific or global.
  * `Fmt.sublime-settings`, user-created or default.

For overrides, open project or global settings and make a `"Fmt"` entry:

```json
{
  "Fmt": {
    "rules": [
      {
        "selector": "source.some_lang",
        "cmd": ["some_lang_fmt", "--some_arg"],
      },
    ],
  },
}
```

A rule may contain _any_ of the root-level settings, such as `format_on_save`. This allows fine-tuning.

## Commands

In Sublime's command palette:

* `Fmt: Format Buffer`
* `Fmt: Format Selection`

## Hotkeys

Hotkeys? More like _notkeys_!

To avoid potential conflicts, this plugin does not come with hotkeys. To hotkey
the format commands, add something like this to your `.sublime-keymap`:

```sublime-keymap
{"keys": ["primary+k", "primary+j"], "command": "fmt_format_buffer"},
{"keys": ["primary+k", "primary+k"], "command": "fmt_format_selection"},
```

Depending on your OS, "primary" is either Cmd or Ctrl.

## Changelog

**2020-12-28**. Support env variable substitution. Format-on-save is no longer enabled by default.

**2020-11-26**. Support variable substitution in `cmd`.

**2020-11-25**. Use scope selectors instead of exactly matching the scope name.

**2020-10-25**. Support subprocess timeout, always kill the subprocess.

**2020-10-23**. Support several ways of printing errors. By default, errors are shown in a transient output panel at the bottom.

## License

https://unlicense.org
