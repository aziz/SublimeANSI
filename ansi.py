# -*- coding: utf-8 -*-

import sublime
import sublime_plugin
import os
import Default
import re
from collections import namedtuple

AnsiDefinition = namedtuple("AnsiDefinition", "scope regex")

DEBUG = False


def ansi_definitions(content):

    # collect colors from file content and make them a string
    color_str = "{0}{1}{0}".format(
        '\x1b',
        '\x1b'.join(set(re.findall(
            r'(\[[\d;]*m)',  # find all possible colors
            content
        )))
    )

    settings = sublime.load_settings("ansi.sublime-settings")
    # filter out unnecessary colors in user settings
    bgs = [v for v in settings.get("ANSI_BG", []) if re.search(v['code'], color_str) is not None]
    fgs = [v for v in settings.get("ANSI_FG", []) if re.search(v['code'], color_str) is not None]

    for bg in bgs:
        for fg in fgs:
            regex = r'(?:(?:{0}{1})|(?:{1}{0}))[^\x1b]*'.format(fg['code'], bg['code'])
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
        begin = min(a, b)
        end = max(a, b)
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

    def run(self, edit, regions=None):
        view = self.view
        if view.settings().get("ansi_enabled"):
            return

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

        if regions is None:
            self._colorize_ansi_codes(edit)
        else:
            self._colorize_regions(regions)

        view.set_read_only(True)

    def _colorize_regions(self, regions):
        view = self.view
        for scope, regions_points in regions.items():
            regions = []
            for a, b in regions_points:
                regions.append(sublime.Region(a, b))
            sum_regions = view.get_regions(scope) + regions
            view.add_regions(scope, sum_regions, scope, '', sublime.DRAW_NO_OUTLINE)

    def _colorize_ansi_codes(self, edit):
        view = self.view
        # removing unsupported ansi escape codes before going forward: 2m 4m 5m 7m 8m
        ansi_unsupported_codes = view.find_all(r'(\x1b\[(0;)?(2|4|5|7|8)m)')
        ansi_unsupported_codes.reverse()
        for r in ansi_unsupported_codes:
            view.replace(edit, r, "\x1b[1m")

        content = view.substr(sublime.Region(0, view.size()))
        for ansi in ansi_definitions(content):
            ansi_regions = view.find_all(ansi.regex)
            if DEBUG and ansi_regions:
                print("scope: {}\nregex: {}\nregions: {}\n----------\n".format(ansi.scope, ansi.regex, ansi_regions))
            if ansi_regions:
                sum_regions = view.get_regions(ansi.scope) + ansi_regions
                view.add_regions(ansi.scope, sum_regions, ansi.scope, '', sublime.DRAW_NO_OUTLINE)

        # removing the rest of ansi escape codes
        ansi_codes = view.find_all(r'(\x1b\[[\d;]*m){1,}')
        ansi_codes.reverse()
        for r in ansi_codes:
            view.erase(edit, r)


class UndoAnsiCommand(sublime_plugin.WindowCommand):

    def run(self):
        view = self.window.active_view()

        # if the syntax has not already been changed from ansi this means the command has
        # been run via the sublime console therefore the syntax must be changed manually
        if view.settings().get("syntax") == "Packages/ANSIescape/ANSI.tmLanguage":
            view.settings().set("syntax", "Packages/Text/Plain text.tmLanguage")

        view.settings().erase("ansi_enabled")
        view.settings().erase("color_scheme")
        view.settings().erase("draw_white_space")

        view.set_read_only(False)
        settings = sublime.load_settings("ansi.sublime-settings")
        for bg in settings.get("ANSI_BG", []):
            for fg in settings.get("ANSI_FG", []):
                ansi_scope = "{0}{1}".format(fg['scope'], bg['scope'])
                view.erase_regions(ansi_scope)
        view.run_command("undo")

        # restore the view's original scratch and read only settings
        view.set_scratch(view.settings().get("ansi_scratch", False))
        view.settings().erase("ansi_scratch")
        view.set_read_only(view.settings().get("ansi_read_only", False))
        view.settings().erase("ansi_read_only")


class AnsiEventListener(sublime_plugin.EventListener):

    def on_new_async(self, view):
        self.assign_event_listener(view)

    def on_load_async(self, view):
        self.assign_event_listener(view)

    def assign_event_listener(self, view):
        view.settings().clear_on_change("CHECK_FOR_ansi_syntax")
        view.settings().add_on_change("CHECK_FOR_ANSI_SYNTAX", lambda: self.detect_syntax_change(view))
        if view.settings().get("syntax") == "Packages/ANSIescape/ANSI.tmLanguage":
            view.run_command("ansi")

    def detect_syntax_change(self, view):
        if view.settings().get("syntax") == "Packages/ANSIescape/ANSI.tmLanguage":
            view.run_command("ansi")
        elif view.settings().get("ansi_enabled"):
            view.window().run_command("undo_ansi")


class AnsiColorBuildCommand(Default.exec.ExecCommand):

    process_trigger = "on_finish"

    @classmethod
    def update_build_settings(cls):
        print("updating ANSI build settings...")
        settings = sublime.load_settings("ansi.sublime-settings")
        val = settings.get("ANSI_process_trigger", "on_finish")
        if val in ["on_finish", "on_data"]:
            cls.process_trigger = val
        else:
            print("ANSIescape settings warning: not valid ANSI_process_trigger value. Valid values: 'on_finish' or 'on_data")

    def on_data_process(self, proc, data):
        view = self.output_view
        if not view.settings().get("syntax") == "Packages/ANSIescape/ANSI.tmLanguage":
            super(AnsiColorBuildCommand, self).on_data(proc, data)
            return

        str_data = data.decode(self.encoding)

        # replace unsupported ansi escape codes before going forward: 2m 4m 5m 7m 8m
        unsupported_pattern = r'(\x1b\[(0;)?(2|4|5|7|8)m)'
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
        remove_pattern = r'(\x1b\[[\d;]*m){1,}'
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

        # send on_data without ansi codes
        super(AnsiColorBuildCommand, self).on_data(proc, out_data.encode(self.encoding))

        # send ansi command
        view.settings().set("ansi_enabled", False)
        view.run_command('ansi', args={"regions": json_ansi_regions})

    def on_data(self, proc, data):
        if self.process_trigger == "on_data":
            self.on_data_process(proc, data)
        else:
            super(AnsiColorBuildCommand, self).on_data(proc, data)

    def on_finished(self, proc):
        super(AnsiColorBuildCommand, self).on_finished(proc)
        if self.process_trigger == "on_finish":
            view = self.output_view
            if view.settings().get("syntax") == "Packages/ANSIescape/ANSI.tmLanguage":
                view.settings().set("ansi_enabled", False)
                view.run_command('ansi')


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


def generate_color_scheme(cs_file):
    print("Regenerating ANSI color scheme...")
    cs_scopes = ""
    settings = sublime.load_settings("ansi.sublime-settings")
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
    ansi_cs_dir = os.path.join(sublime.packages_path(), "User", "ANSIescape")
    if not os.path.exists(ansi_cs_dir):
        os.makedirs(ansi_cs_dir)
    cs_file = os.path.join(ansi_cs_dir, "ansi.tmTheme")
    if not os.path.isfile(cs_file):
        generate_color_scheme(cs_file)
    settings = sublime.load_settings("ansi.sublime-settings")
    AnsiColorBuildCommand.update_build_settings()
    settings.add_on_change("ANSI_COLORS_CHANGE", lambda: generate_color_scheme(cs_file))
    settings.add_on_change("ANSI_SETTINGS_CHANGE", lambda: AnsiColorBuildCommand.update_build_settings())
    for window in sublime.windows():
        for view in window.views():
            AnsiEventListener().assign_event_listener(view)


def plugin_unloaded():
    settings = sublime.load_settings("ansi.sublime-settings")
    settings.clear_on_change("ANSI_COLORS_CHANGE")
    settings.clear_on_change("ANSI_SETTINGS_CHANGE")
