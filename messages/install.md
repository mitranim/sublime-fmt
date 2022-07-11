## Fmt Setup

(More in the readme: https://github.com/mitranim/sublime-fmt)

Fmt has NO DEFAULT FORMATTERS. You must specify them in the plugin settings:

    menu → Preferences → Package Settings → Fmt → Settings

Example for Go:

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

To understand Sublime scopes and selector matching, read this short official doc: https://www.sublimetext.com/docs/selectors.html.

HOW TO GET SCOPE NAME:

Option 1: menu → Tools → Developer → Show Scope Name.

Option 2: run the command `Fmt: Format Buffer`, and if not configured for the current scope, it will tell you!
