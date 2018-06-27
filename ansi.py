# -*- coding: utf-8 -*-

from collections import namedtuple
from functools import partial
import bisect
import Default
import inspect
import os
import threading
import re
import sublime
import sublime_plugin

DEBUG = False

AnsiDefinition = namedtuple("AnsiDefinition", "scope regex")
regex_obj_cache = {}


def debug(view, msg):
    if not DEBUG:
        return

    info = inspect.getframeinfo(inspect.stack()[1][0])
    filepath = os.path.abspath(info.filename)
    if view.name():
        name = view.name()
    elif view.file_name():
        name = os.path.basename(view.file_name())
    else:
        name = "not named"
    msg = re.sub(r'\n', "\n\t", msg)

    print("File: \"{path}\", line {lineno}, window: {window_id}, view: {view_id}, file: {name}\n\t{msg}".format_map({
        'lineno': info.lineno,
        'msg': msg,
        'name': name,
        'path': filepath,
        'view_id': view.id(),
        'window_id': view.window().id(),
    }))


def get_regex_obj(regex_string):
    """
    @brief Get the regular expression object.

    @param regex_string the regular expression string

    @return The regular expression object.
    """

    if regex_string not in regex_obj_cache:
        regex_obj_cache[regex_string] = re.compile(regex_string)

    return regex_obj_cache[regex_string]


def fast_view_find_all(view, regex_string):
    """
    @brief A faster implementation of View.find_all().

    @param view         the View object
    @param regex_string the regular expression string

    @return sublime.Region[]
    """

    regex_obj = get_regex_obj(regex_string)
    content = view.substr(sublime.Region(0, view.size()))

    iterator = regex_obj.finditer(content)

    if iterator is None:
        return []

    return [sublime.Region(*(m.span())) for m in iterator]


def ansi_definitions(content=None):

    settings = sublime.load_settings("ansi.sublime-settings")

    if content is None:
        bgs = settings.get('ANSI_BG', [])
        fgs = settings.get('ANSI_FG', [])
    else:
        # collect colors from file content and make them a string
        color_str = "{0}{1}{0}".format(
            '\x1b',
            '\x1b'.join(set(
                # find all possible colors
                re.findall(r'\[[0-9;]*m', content)
            ))
        )

        # filter out unnecessary colors in user settings
        bgs = [v for v in settings.get('ANSI_BG', []) if get_regex_obj(v['code']).search(color_str) is not None]
        fgs = [v for v in settings.get('ANSI_FG', []) if get_regex_obj(v['code']).search(color_str) is not None]

    for bg in bgs:
        for fg in fgs:
            regex = r'(?:{0}{1}|{1}{0})[^\x1b]*'.format(fg['code'], bg['code'])
            scope = "{0}{1}".format(fg['scope'], bg['scope'])
            yield AnsiDefinition(scope, regex)


class AnsiRegion(object):

    def __init__(self, scope):
        super(AnsiRegion, self).__init__()
        self.scope = scope
        self.regions = []

    def add(self, a, b):
        self.regions.append([a, b])

    def cut_area(self, a, b):
        begin, end = min(a, b), max(a, b)
        for n, (a, b) in enumerate(self.regions):
            a = self.subtract_region(a, begin, end)
            b = self.subtract_region(b, begin, end)
            self.regions[n] = (a, b)

    def shift(self, val):
        for n, (a, b) in enumerate(self.regions):
            self.regions[n] = (a + val, b + val)

    def jsonable(self):
        return {self.scope: self.regions}

    @staticmethod
    def subtract_region(p, begin, end):
        if p < begin:
            return p
        elif p < end:
            return begin
        else:
            return p - (end - begin)


class AnsiCommand(sublime_plugin.TextCommand):

    def run(self, edit, regions=None, clear_before=False):
        view = self.view
        if view.settings().get("ansi_in_progres", False):
            debug(view, "oops ... the ansi command is already in progress")
            return
        view.settings().set("ansi_in_progres", True)

        # if the syntax has not already been changed to ansi this means the command has
        # been run via the sublime console therefore the syntax must be changed manually
        if view.settings().get("syntax") != "Packages/ANSIescape/ANSI.tmLanguage":
            view.settings().set("syntax", "Packages/ANSIescape/ANSI.tmLanguage")

        view.settings().set("ansi_enabled", True)
        view.settings().set("color_scheme", "Packages/User/ANSIescape/ansi.tmTheme")
        view.settings().set("draw_white_space", "none")

        # save the view's original scratch and read only settings
        if not view.settings().has("ansi_scratch"):
            view.settings().set("ansi_scratch", view.is_scratch())
        view.set_scratch(True)
        if not view.settings().has("ansi_read_only"):
            view.settings().set("ansi_read_only", view.is_read_only())
        view.set_read_only(False)

        if clear_before:
            self._remove_ansi_regions()

        if regions is None:
            self._colorize_ansi_codes(edit)
        else:
            self._colorize_regions(regions)

        view.settings().set("ansi_in_progres", False)
        view.settings().set("ansi_size", view.size())
        view.set_read_only(True)

    def _colorize_regions(self, regions):
        view = self.view
        for scope, regions_points in regions.items():
            regions = []
            for a, b in regions_points:
                regions.append(sublime.Region(a, b))
            sum_regions = view.get_regions(scope) + regions
            view.add_regions(scope, sum_regions, scope, '', sublime.DRAW_NO_OUTLINE | sublime.PERSISTENT)

    def _colorize_ansi_codes(self, edit):
        view = self.view

        # removing unsupported ansi escape codes before going forward: 2m 4m 5m 7m 8m
        ansi_unsupported_codes = fast_view_find_all(view, r'\x1b\[(0;)?[24578]m')
        for r in reversed(ansi_unsupported_codes):
            view.replace(edit, r, '\x1b[1m')

        # collect ansi regions
        ansi_regions = {
            # scope: regions,
        }
        content = view.substr(sublime.Region(0, view.size()))
        for ansi in ansi_definitions(content):
            regions = fast_view_find_all(view, ansi.regex)
            if regions:
                debug(view, "scope: {}\nregex: {}\nregions: {}\n----------\n".format(ansi.scope, ansi.regex, ansi_regions))
                ansi_regions[ansi.scope] = regions

        # removing ansi escaped codes
        ansi_codes = fast_view_find_all(view, r'\x1b\[[0-9;]*m')
        for r in reversed(ansi_codes):
            view.erase(edit, r)

        # build offset correction tables
        correction_tables = {
            'points': [0],
            'offsets': [0],
        }
        for r in ansi_codes:
            correction_tables['points'].append(r.end())
            correction_tables['offsets'].append(r.size() + correction_tables['offsets'][-1])

        # apply offset correction to ansi regions
        for scope, regions in ansi_regions.items():
            for r in regions:
                r.a -= correction_tables['offsets'][bisect.bisect(correction_tables['points'], r.a) - 1]
                r.b -= correction_tables['offsets'][bisect.bisect(correction_tables['points'], r.b) - 1]
            # render corrected ansi regions
            sum_regions = view.get_regions(scope) + regions
            view.add_regions(scope, sum_regions, scope, '', sublime.DRAW_NO_OUTLINE | sublime.PERSISTENT)

    def _remove_ansi_regions(self):
        view = self.view
        for ansi in ansi_definitions():
            view.erase_regions(ansi.scope)


class UndoAnsiCommand(sublime_plugin.WindowCommand):

    def run(self):
        view = self.window.active_view()
        # if ansi is in progress or don't have ansi_in_progress setting
        # don't run the command
        if view.settings().get("ansi_in_progres", True):
            debug(view, "oops ... the ansi command is already executing")
            return
        view.settings().set("ansi_in_progres", True)

        # if the syntax has not already been changed from ansi this means the command has
        # been run via the sublime console therefore the syntax must be changed manually
        if view.settings().get("syntax") == "Packages/ANSIescape/ANSI.tmLanguage":
            view.settings().set("syntax", "Packages/Text/Plain text.tmLanguage")

        view.settings().erase("ansi_enabled")
        view.settings().erase("color_scheme")
        view.settings().erase("draw_white_space")

        view.set_read_only(False)
        view.run_command("undo")
        for ansi in ansi_definitions():
            view.erase_regions(ansi.scope)

        # restore the view's original scratch and read only settings
        view.set_scratch(view.settings().get("ansi_scratch", False))
        view.settings().erase("ansi_scratch")
        view.set_read_only(view.settings().get("ansi_read_only", False))
        view.settings().erase("ansi_read_only")
        view.settings().erase("ansi_in_progres")
        view.settings().erase("ansi_size")


class AnsiEventListener(sublime_plugin.EventListener):

    def on_new_async(self, view):
        self.process_view_open(view)

    def on_load_async(self, view):
        self.process_view_open(view)

    def on_pre_close(self, view):
        self.process_view_close(view)

    def process_view_open(self, view):
        self._del_event_listeners(view)
        self._add_event_listeners(view)
        if view.settings().get("syntax") == "Packages/ANSIescape/ANSI.tmLanguage":
            view.run_command("ansi")

    def process_view_close(self, view):
        self._del_event_listeners(view)
        #if view.settings().get("syntax") == "Packages/ANSIescape/ANSI.tmLanguage":
        #    view.window().run_command("undo_ansi") ** this needs to be tested **

    def detect_left_ansi(self, view):
        sublime.set_timeout_async(partial(self.check_left_ansi, view), 50)

    def check_left_ansi(self, view):
        if not self._is_view_valid(view):
            self._del_event_listeners(view)
            return
        if view.settings().get("syntax") != "Packages/ANSIescape/ANSI.tmLanguage":
            return
        if view.settings().get("ansi_in_progres", False):
            debug(view, "ansi in progres")
            sublime.set_timeout_async(partial(self.check_left_ansi, view), 50)
            return
        if view.settings().get("ansi_size", view.size()) != view.size():
            debug(view, "ANSI view size changed. Running ansi command")
            view.run_command("ansi", args={"clear_before": True})
        debug(view, "ANSI cmd done and no codes left")

    def detect_syntax_change(self, view):
        if not self._is_view_valid(view):
            self._del_event_listeners(view)
            return
        if view.settings().get("ansi_in_progres", False):
            return
        if view.settings().get("syntax") == "Packages/ANSIescape/ANSI.tmLanguage":
            if not view.settings().has("ansi_enabled"):
                debug(view, "Syntax change detected (running ansi command).")
                view.run_command("ansi", args={"clear_before": True})
        else:
            if view.settings().has("ansi_enabled"):
                debug(view, "Syntax change detected (running undo command).")
                view.window().run_command("undo_ansi")

    def _is_view_valid(self, view):
        if view.window() is None:
            return False
        if view.window() not in sublime.windows():
            return False
        if view not in view.window().views():
            return False
        return True

    def _add_event_listeners(self, view):
        view.settings().add_on_change("CHECK_FOR_ANSI_SYNTAX", lambda: self.detect_syntax_change(view))
        view.settings().add_on_change("CHECK_FOR_LEFT_ANSI", lambda: self.detect_left_ansi(view))
        debug(view, "ANSIescape event listeners assigned to view.")

    def _del_event_listeners(self, view):
        view.settings().clear_on_change("CHECK_FOR_ANSI_SYNTAX")
        view.settings().clear_on_change("CHECK_FOR_LEFT_ANSI")
        debug(view, "ANSIescape event listener removed from view.")


class AnsiColorBuildCommand(Default.exec.ExecCommand):

    process_trigger = "on_finish"
    data_lock = threading.Lock()

    @classmethod
    def update_build_settings(self, settings):
        val = settings.get("ANSI_process_trigger", "on_finish")
        if val in ["on_finish", "on_data"]:
            self.process_trigger = val
        else:
            self.process_trigger = None
            sublime.error_message("ANSIescape settings warning:\n\nThe setting ANSI_process_trigger has been set to an invalid value; must be one of 'on_finish' or 'on_data'.")

    @classmethod
    def clear_build_settings(self, settings):
        self.process_trigger = None

    def on_data_process(self, proc, data):
        # note that ST 3169 is the same with 3170
        needDataCodec = True if int(sublime.version()) < 3169 else False

        view = self.output_view
        if not view.settings().get("syntax") == "Packages/ANSIescape/ANSI.tmLanguage":
            super(AnsiColorBuildCommand, self).on_data(proc, data)
            return

        str_data = data

        if needDataCodec:
            str_data = str_data.decode(self.encoding)

        # replace unsupported ansi escape codes before going forward: 2m 4m 5m 7m 8m
        unsupported_pattern = r'\x1b\[(0;)?[24578]m'
        str_data = re.sub(unsupported_pattern, "\x1b[1m", str_data)

        # find all regions
        ansi_regions = []
        for ansi in ansi_definitions(str_data):
            if re.search(ansi.regex, str_data):
                reg = re.finditer(ansi.regex, str_data)
                new_region = AnsiRegion(ansi.scope)
                for m in reg:
                    new_region.add(*m.span())
                ansi_regions.append(new_region)

        # remove codes
        remove_pattern = r'(\x1b\[[0-9;]*m)+'
        ansi_codes = re.finditer(remove_pattern, str_data)
        ansi_codes = list(ansi_codes)
        ansi_codes.reverse()
        for c in ansi_codes:
            to_remove = c.span()
            for r in ansi_regions:
                r.cut_area(*to_remove)
        out_data = re.sub(remove_pattern, "", str_data)

        # create json serialable region representation
        json_ansi_regions = {}
        shift_val = view.size()
        for region in ansi_regions:
            region.shift(shift_val)
            json_ansi_regions.update(region.jsonable())

        if needDataCodec:
            out_data = out_data.encode(self.encoding)

        # send on_data without ansi codes
        super(AnsiColorBuildCommand, self).on_data(proc, out_data)

        # send ansi command
        view.run_command('ansi', args={"regions": json_ansi_regions})

    def on_data(self, proc, data):
        with self.data_lock:
            if self.process_trigger == "on_data":
                self.on_data_process(proc, data)
            else:
                super(AnsiColorBuildCommand, self).on_data(proc, data)

    def on_finished(self, proc):
        with self.data_lock:
            super(AnsiColorBuildCommand, self).on_finished(proc)
            if self.process_trigger == "on_finish":
                view = self.output_view
                if view.settings().get("syntax") == "Packages/ANSIescape/ANSI.tmLanguage":
                    view.run_command("ansi", args={"clear_before": True})


CS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>name</key><string>Ansi</string>
<key>settings</key><array><dict><key>settings</key><dict>
<key>background</key><string>%s</string>
<key>caret</key><string>%s</string>
<key>foreground</key><string>%s</string>
<key>gutter</key><string>%s</string>
<key>gutterForeground</key><string>%s</string>
<key>invisibles</key><string>%s</string>
<key>lineHighlight</key><string>%s</string>
<key>selection</key><string>%s</string>
</dict></dict>
%s</array></dict></plist>
"""

ANSI_SCOPE = "<dict><key>scope</key><string>{0}{1}</string><key>settings</key><dict><key>background</key><string>{2}</string><key>foreground</key><string>{3}</string>{4}</dict></dict>\n"


def generate_color_scheme(cs_file, settings):
    print("Regenerating ANSI color scheme...")
    cs_scopes = ""
    for bg in settings.get("ANSI_BG", []):
        for fg in settings.get("ANSI_FG", []):
            if (bg.get('font_style') and bg['font_style'] == 'bold') or (fg.get('font_style') and fg['font_style'] == 'bold'):
                font_style = "<key>fontStyle</key><string>bold</string>"
            else:
                font_style = ''
            cs_scopes += ANSI_SCOPE.format(fg['scope'], bg['scope'], bg['color'], fg['color'], font_style)
    g = settings.get("GENERAL")
    vals = [g['background'], g['caret'], g['foreground'], g['gutter'], g['gutterForeground'], g['invisibles'], g['lineHighlight'], g['selection'], cs_scopes]
    theme = CS_TEMPLATE % tuple(vals)
    with open(cs_file, 'w') as color_scheme:
        color_scheme.write(theme)


def plugin_loaded():
    # load pluggin settings
    settings = sublime.load_settings("ansi.sublime-settings")
    # create ansi color scheme directory
    ansi_cs_dir = os.path.join(sublime.packages_path(), "User", "ANSIescape")
    if not os.path.exists(ansi_cs_dir):
        os.makedirs(ansi_cs_dir)
    # create ansi color scheme file
    cs_file = os.path.join(ansi_cs_dir, "ansi.tmTheme")
    if not os.path.isfile(cs_file):
        generate_color_scheme(cs_file, settings)
    # update the settings for the plugin
    AnsiColorBuildCommand.update_build_settings(settings)
    settings.add_on_change("ANSI_COLORS_CHANGE", lambda: generate_color_scheme(cs_file, settings))
    settings.add_on_change("ANSI_TRIGGER_CHANGE", lambda: AnsiColorBuildCommand.update_build_settings(settings))
    # update the setting for each view
    for window in sublime.windows():
        for view in window.views():
            AnsiEventListener().process_view_open(view)


def plugin_unloaded():
    # update the settings for the plugin
    settings = sublime.load_settings("ansi.sublime-settings")
    AnsiColorBuildCommand.clear_build_settings(settings)
    settings.clear_on_change("ANSI_COLORS_CHANGE")
    settings.clear_on_change("ANSI_TRIGGER_CHANGE")
    # update the setting for each view
    for window in sublime.windows():
        for view in window.views():
            AnsiEventListener().process_view_close(view)
