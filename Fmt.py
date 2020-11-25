import sublime
import sublime_plugin
import subprocess as sub
import os
import sys
from . import difflib

PLUGIN_NAME = 'Fmt'
SETTINGS_KEY = PLUGIN_NAME + '.sublime-settings'
IS_WINDOWS = os.name == 'nt'
PANEL_OUTPUT_NAME = 'output.' + PLUGIN_NAME

class fmt_listener(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        if is_enabled(view) and get_setting(view, 'format_on_save'):
            view.run_command('fmt_format_buffer')

class fmt_format_buffer(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        content = view.substr(sublime.Region(0, view.size()))

        hide_panel(view.window())

        try:
            output = format(
                view=view,
                input=content,
                encoding=view_encoding(view),
            )
        except Exception as err:
            report(view, err)
            return

        merge_type = get_setting(view, 'merge_type')

        if merge_type == 'diff':
            merge_into_view(view, edit, output)

        elif merge_type == 'replace':
            position = view.viewport_position()
            view.replace(edit, sublime.Region(0, view.size()), output)
            # Works only on the main thread, hence lambda and timer.
            restore = lambda: view.set_viewport_position(position, animate=False)
            sublime.set_timeout(restore, 0)

        else:
            report(view, 'unknown value of setting "merge_type": {}'.format(merge_type))
            return

class fmt_panel_replace_content(sublime_plugin.TextCommand):
    def run(self, edit, text):
        view = self.view
        view.erase(edit, sublime.Region(0, view.size()))
        view.insert(edit, 0, text)

def format(view, input, encoding):
    cmd = get_setting(view, 'cmd')

    if not cmd:
        raise Exception('missing setting "cmd" for scope "{}"'.format(view_scope(view)))

    if not isinstance(cmd, list):
        raise Exception('expected setting "cmd" to be a list, found {}'.format(cmd))

    timeout = get_setting(view, 'timeout')

    proc = sub.Popen(
        args=cmd,
        stdin=sub.PIPE,
        stdout=sub.PIPE,
        stderr=sub.PIPE,
        startupinfo=process_startup_info(),
        universal_newlines=False,
        cwd=guess_cwd(view),
    )

    try:
        (stdout, stderr) = proc.communicate(input=bytes(input, encoding=encoding), timeout=timeout)
    finally:
        try:
            proc.kill()
        except:
            pass

    stdout = stdout.decode(encoding)
    stderr = stderr.decode(encoding)

    if proc.returncode != 0:
        err = sub.CalledProcessError(proc.returncode, cmd)
        msg = str(err)
        if len(stderr) > 0:
            msg += ':\n' + stderr
        elif len(stdout) > 0:
            msg += ':\n' + stdout
        raise Exception(msg)

    if len(stderr) > 0:
        raise Exception(stderr)

    return stdout

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
                report(view, "mismatch between diff's source and current content")
                return
            merged_len += patch_len
        elif op_type == difflib.Ops.INSERT:
            view.insert(edit, merged_len, patch)
            merged_len += patch_len
        elif op_type == difflib.Ops.DELETE:
            if subview(merged_len, merged_len+patch_len) != patch:
                report(view, "mismatch between diff's source and current content")
                return
            view.erase(edit, sublime.Region(merged_len, merged_len+patch_len))

def report(view, err):
    window = view.window()
    style = get_setting(view, 'error_style')

    if style == None:
        return

    if style == 'console':
        if isinstance(err, Exception):
            raise err
        msg = '[{}] {}'.format(PLUGIN_NAME, err)
        print(msg)
        return

    if style == 'panel':
        msg = '[{}] {}'.format(PLUGIN_NAME, err)
        ensure_panel(window).run_command('fmt_panel_replace_content', {'text': msg})
        show_panel(window)
        return

    if style == 'popup':
        msg = '[{}] {}'.format(PLUGIN_NAME, err)
        sublime.error_message(msg)
        return

    sublime.error_message('[{}] unknown value of setting "error_style": {}'.format(PLUGIN_NAME, style))

# Copied from other plugins, haven't personally tested on Windows.
def process_startup_info():
    if not IS_WINDOWS:
        return None
    startupinfo = sub.STARTUPINFO()
    startupinfo.dwFlags |= sub.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = sub.SW_HIDE
    return startupinfo

def guess_cwd(view):
    window = view.window()
    mode = get_setting(view, 'cwd_mode')

    if mode.startswith(':'):
        return mode[1:]

    if mode == 'none':
        return None

    if mode == 'project_root':
        if len(window.folders()):
            return window.folders()[0]
        return None

    if mode == 'auto':
        if view.file_name():
            return os.path.dirname(view.file_name())
        elif len(window.folders()):
            return window.folders()[0]

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
    overrides = view.settings().get(PLUGIN_NAME)

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

def is_enabled(view):
    return bool(get_setting(view, 'cmd'))

def view_encoding(view):
    encoding = view.encoding()
    return 'UTF-8' if encoding == 'Undefined' else encoding

def create_panel(window):
    return window.create_output_panel(PLUGIN_NAME)

def find_panel(window):
    return window.find_output_panel(PANEL_OUTPUT_NAME)

def ensure_panel(window):
    return find_panel(window) or create_panel(window)

def hide_panel(window):
    if window.active_panel() == PANEL_OUTPUT_NAME:
        window.run_command('hide_panel', {'panel': PANEL_OUTPUT_NAME})

def show_panel(window):
    window.run_command('show_panel', {'panel': PANEL_OUTPUT_NAME})
