Fmt installed!

## Setup

Fmt has NO DEFAULT FORMATTERS. You must specify them in the plugin settings:

    menu → Preferences → Package Settings → Fmt → Settings

Example for Go:

    {
      "scopes": {
        "source.go": {
          "cmd": ["goimports"],
        },
      },
    }

If you're not familiar with Sublime's concept of "scope", think of it roughly as "syntax type".

HOW TO GET SCOPE NAME:

Option 1: menu → Tools → Developer → Show Scope Name.

Option 2: run the command `Fmt: Format Buffer`, and if not configured for the current scope, it will tell you!
