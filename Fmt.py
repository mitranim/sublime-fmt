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
        try:
            fmt_region(view, edit, view_region(view))
        except Exception as err:
            report(view, err)

class fmt_format_selection(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view

        for region in view.sel():
            try:
                fmt_region(view, edit, region)
            except Exception as err:
                report(view, err)
                break

class fmt_panel_replace_content(sublime_plugin.TextCommand):
    def run(self, edit, text):
        view = self.view
        view.replace(edit, view_region(view), text)
        view.sel().clear()

# TODO: any other exception type should be printed with the stack. Only error
# messages generated by Fmt, as `ErrMsg`, should have the stack suppressed
# (which is the default behavior of `str.format`).
class ErrMsg(Exception):
    pass

def fmt_region(view, edit, region):
    if region.empty():
        return

    hide_panel(view.window())

    scope = view.scope_name(region.begin())
    fmted = fmt(view, view.substr(region), view_encoding(view), scope)
    merge_type = get_setting(view, 'merge_type', scope)

    if merge_type == 'diff':
        try:
            merge_into_view(view, edit, fmted, region)
        except difflib.TooManyDiffsException:
            replace_view(view, edit, fmted, region)
        return

    if merge_type == 'replace':
        replace_view(view, edit, fmted, region)
        return

    report(view, 'unknown value of setting "merge_type": {}'.format(merge_type))

def fmt(view, input, encoding, scope):
    cmd = get_setting(view, 'cmd', scope)

    if not cmd:
        raise ErrMsg('unable to find setting "cmd" for scope "{}"'.format(scope))

    if not isinstance(cmd, list) or not every(cmd, is_string):
        raise ErrMsg('expected setting "cmd" to be a list of strings, found {}'.format(cmd))

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
        env=get_env(view, scope),
    )

    timeout = get_setting(view, 'timeout', scope)

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
        msg = str(sub.CalledProcessError(proc.returncode, cmd))
        if len(stderr) > 0:
            msg += ':\n' + stderr
        elif len(stdout) > 0:
            msg += ':\n' + stdout
        raise ErrMsg(msg)

    if len(stdout) == 0 and len(stderr) > 0:
        raise ErrMsg(stderr)

    return stdout

def merge_into_view(view, edit, content, region):
    def subview(start, end):
        return view.substr(sublime.Region(start, end))

    diffs = difflib.myers_diffs(subview(0, view.size()), content)
    difflib.cleanup_efficiency(diffs)
    offset = region.begin()

    for (op_type, patch) in diffs:
        patch_len = len(patch)
        if op_type == difflib.Ops.EQUAL:
            if subview(offset, offset+patch_len) != patch:
                report(view, "mismatch between diff's source and current content")
                return
            offset += patch_len
        elif op_type == difflib.Ops.INSERT:
            view.insert(edit, offset, patch)
            offset += patch_len
        elif op_type == difflib.Ops.DELETE:
            if subview(offset, offset+patch_len) != patch:
                report(view, "mismatch between diff's source and current content")
                return
            view.erase(edit, sublime.Region(offset, offset+patch_len))

def replace_view(view, edit, content, region):
    position = view.viewport_position()
    view.replace(edit, region, content)
    # Works only on the main thread, hence lambda and timer.
    restore = lambda: view.set_viewport_position(position, animate=False)
    sublime.set_timeout(restore, 0)

def report(view, msg):
    window = view.window()
    style = get_setting(view, 'error_style')

    if style == '':
        return

    if style is None:
        style = 'panel'

    if style == 'console':
        if isinstance(msg, Exception):
            raise msg
        msg = '[{}] {}'.format(PLUGIN_NAME, msg)
        print(msg)
        return

    if style == 'panel':
        msg = '[{}] {}'.format(PLUGIN_NAME, msg)
        ensure_panel(window).run_command('fmt_panel_replace_content', {'text': msg.replace('\r\n', '\n')})
        show_panel(window)
        return

    if style == 'popup':
        msg = '[{}] {}'.format(PLUGIN_NAME, msg)
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
    mode = get_setting(view, 'cwd_mode') or ''

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
        if len(window.folders()):
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

def get_setting(view, key, scope = None):
    if scope is None:
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
        raise ErrMsg('missing "selector" in rule {}'.format(rule))
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
    vars.update(os.environ)

    return vars

def view_region(view):
    return sublime.Region(0, view.size())

def get_env(view, scope):
    val = get_setting(view, 'env', scope)
    if val is None:
        return None
    env = os.environ.copy()
    env.update(val)
    return env
