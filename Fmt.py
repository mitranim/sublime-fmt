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
            try:
                merge_into_view(view, edit, output)
            except difflib.TooManyDiffsException:
                replace_view(view, edit, output)
            return

        if merge_type == 'replace':
            replace_view(view, edit, output)
            return

        report(view, 'unknown value of setting "merge_type": {}'.format(merge_type))

class fmt_panel_replace_content(sublime_plugin.TextCommand):
    def run(self, edit, text):
        view = self.view
        view.erase(edit, sublime.Region(0, view.size()))
        view.insert(edit, 0, text)

def format(view, input, encoding):
    cmd = get_setting(view, 'cmd')

    if not cmd:
        raise Exception('unable to find setting "cmd" for scope "{}"'.format(view_scope(view)))

    if not isinstance(cmd, list) or not every(cmd, is_string):
        raise Exception('expected setting "cmd" to be a list of strings, found {}'.format(cmd))

    # Support "$variable" substitutions.
    variables = extract_variables(view)
    cmd = [sublime.expand_variables(arg, variables) for arg in cmd]

    proc = sub.Popen(
        args=cmd,
        stdin=sub.PIPE,
        stdout=sub.PIPE,
        stderr=sub.PIPE,
        startupinfo=process_startup_info(),
        universal_newlines=False,
        cwd=guess_cwd(view),
    )

    timeout = get_setting(view, 'timeout')

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

def merge_into_view(view, edit, content):
    def subview(start, end):
        return view.substr(sublime.Region(start, end))

    diffs = difflib.myers_diffs(subview(0, view.size()), content)
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

def replace_view(view, edit, content):
    position = view.viewport_position()
    view.replace(edit, sublime.Region(0, view.size()), content)
    # Works only on the main thread, hence lambda and timer.
    restore = lambda: view.set_viewport_position(position, animate=False)
    sublime.set_timeout(restore, 0)

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
        val, ok = get(val, key)
        if not ok:
            return (None, False)
    return (val, True)

def get(val, key):
    if (
        isinstance(val, dict) and key in val
    ) or (
        (isinstance(val, list) or isinstance(val, tuple)) and
        (isinstance(key, int) and len(val) > key)
    ):
        return (val[key], True)
    return (None, False)

def view_scope(view):
    scopes = view.scope_name(0)
    return scopes[0:scopes.find(' ')]

def get_setting(view, key):
    scope = view_scope(view)
    overrides = view.settings().get(PLUGIN_NAME)

    rule = rule_for_scope(get(overrides, 'rules')[0], scope)
    (val, found) = get(rule, key)
    if found:
        return val

    (val, found) = get_in(overrides, key)
    if found:
        return val

    settings = sublime.load_settings(SETTINGS_KEY)

    rule = rule_for_scope(settings.get('rules'), scope)
    (val, found) = get(rule, key)
    if found:
        return val

    return settings.get(key)

def rule_for_scope(rules, scope):
    if not rules:
        return None
    rule = max(rules, key = lambda rule: rule_score(rule, scope))
    # Note: `max` doesn't ensure this condition.
    if rule_score(rule, scope) > 0:
        return rule
    return None

def rule_score(rule, scope):
    if 'selector' not in rule:
        raise Exception('missing "selector" in rule {}'.format(rule))
    return sublime.score_selector(scope, rule['selector'])

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

def every(iter, fun):
    if iter:
        for val in iter:
            if not fun(val):
                return False
    return True

def is_string(val):
    return isinstance(val, str)

def extract_variables(view):
    settings = view.settings()
    tab_size = settings.get('tab_size') or 0
    indent = ' ' * tab_size if settings.get('translate_tabs_to_spaces') else '\t'

    vars = view.window().extract_variables()
    vars['tab_size'] = str(tab_size)
    vars['indent'] = indent

    return vars
