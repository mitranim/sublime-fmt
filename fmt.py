import sublime
import sublime_plugin
import subprocess as sub
import os
import sys
from . import difflib

SETTINGS_KEY = 'fmt.sublime-settings'
SETTING_OVERRIDE_KEY = 'fmt'
IS_WINDOWS = os.name == 'nt'

# Copied from other plugins, haven't personally tested on Windows.
def process_startup_info():
    if not IS_WINDOWS:
        return None
    startupinfo = sub.STARTUPINFO()
    startupinfo.dwFlags |= sub.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = sub.SW_HIDE
    return startupinfo

def guess_cwd(view):
    mode = get_setting(view, 'cwd_mode')

    if mode.startswith(':'):
        return mode[1:]

    if mode == 'none':
        return None

    if mode == 'project_root':
        if len(view.window().folders()):
            return view.window().folders()[0]
        return None

    if mode == 'auto':
        if view.file_name():
            return os.path.dirname(view.file_name())
        elif len(view.window().folders()):
            return view.window().folders()[0]

def get_in(val, *path):
    for key in path:
        if (
            isinstance(val, dict) and key in val
        ) or (
            (isinstance(val, list) or isinstance(val, tuple)) and
            (isinstance(key, int) and len(val) > key)
        ):
            val = val[key]
        else:
            return (None, False)
    return (val, True)

def view_scope(view):
    scopes = view.scope_name(0)
    return scopes[0:scopes.find(' ')]

def get_setting(view, key):
    scope = view_scope(view)
    overrides = view.settings().get(SETTING_OVERRIDE_KEY)

    (val, found) = get_in(overrides, 'scopes', scope, key)
    if found:
        return val

    (val, found) = get_in(overrides, key)
    if found:
        return val

    settings = sublime.load_settings(SETTINGS_KEY)

    (val, found) = get_in(settings.get('scopes'), scope, key)
    if found:
        return val

    return settings.get(key)

def get_cmd(view):
    return get_setting(view, 'cmd')

def is_enabled(view):
    return bool(get_cmd(view))

def merge_into_view(view, edit, new_src):
    def subview(start, end):
        return view.substr(sublime.Region(start, end))
    diffs = difflib.myers_diffs(subview(0, view.size()), new_src)
    difflib.cleanup_efficiency(diffs)
    merged_len = 0
    for (op_type, patch) in diffs:
        patch_len = len(patch)
        if op_type == difflib.Ops.EQUAL:
            if subview(merged_len, merged_len+patch_len) != patch:
                raise Exception("[sublime-fmt] mismatch between diff's source and current content")
            merged_len += patch_len
        elif op_type == difflib.Ops.INSERT:
            view.insert(edit, merged_len, patch)
            merged_len += patch_len
        elif op_type == difflib.Ops.DELETE:
            if subview(merged_len, merged_len+patch_len) != patch:
                raise Exception("[sublime-fmt] mismatch between diff's source and current content")
            view.erase(edit, sublime.Region(merged_len, merged_len+patch_len))

def run_format(view, input, encoding):
    cmd = get_cmd(view)
    if not isinstance(cmd, list):
        raise Exception("[sublime-fmt] expected cmd to be a list, found {}".format(cmd))

    proc = sub.Popen(
        args=cmd,
        stdin=sub.PIPE,
        stdout=sub.PIPE,
        stderr=sub.PIPE,
        startupinfo=process_startup_info(),
        universal_newlines=False,
        cwd=guess_cwd(view),
    )

    (stdout, stderr) = proc.communicate(input=bytes(input, encoding=encoding))
    (stdout, stderr) = (stdout.decode(encoding), stderr.decode(encoding))

    if proc.returncode != 0:
        err = sub.CalledProcessError(proc.returncode, cmd)

        if get_setting(view, 'error_messages'):
            msg = str(err)
            if len(stderr) > 0:
                msg += ':\n' + stderr
            elif len(stdout) > 0:
                msg += ':\n' + stdout
            msg += '\nNote: to disable error popups, set the fmt setting "error_messages" to false.'
            sublime.error_message(msg)

        raise err

    if len(stderr) > 0:
        print('[sublime-fmt]:', stderr, file=sys.stderr)

    return stdout

def view_encoding(view):
    encoding = view.encoding()
    return 'UTF-8' if encoding == 'Undefined' else encoding

class fmt_format_buffer(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        content = view.substr(sublime.Region(0, view.size()))

        stdout = run_format(
            view=view,
            input=content,
            encoding=view_encoding(view),
        )

        merge_type = get_setting(view, 'merge_type')

        if merge_type == 'diff':
            # `gofmt` forces tabs. If the file currently uses spaces, diffing
            # and formatting will fail. Forcing tabs avoid this.
            view.settings().set('translate_tabs_to_spaces', False)
            merge_into_view(view, edit, stdout)

        elif merge_type == 'replace':
            position = view.viewport_position()
            view.replace(edit, sublime.Region(0, view.size()), stdout)
            # Works only on main thread, hence lambda and timer.
            restore = lambda: view.set_viewport_position(position, animate=False)
            sublime.set_timeout(restore, 0)

        else:
            raise Exception('[sublime-fmt] unknown merge_type setting: {}'.format(merge_type))

class fmt_listener(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        if is_enabled(view) and get_setting(view, 'format_on_save'):
            view.run_command('fmt_format_buffer')
