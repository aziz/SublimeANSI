# -*- coding: utf-8 -*-

import sublime
import sublime_plugin
import os
import Default
import re
from collections import namedtuple

AnsiPoint = namedtuple("AnsiPoint", "scope regex")

DEBUG = False


def ansi_point_generator():
    settings = sublime.load_settings("ansi.sublime-settings")
    for bg in settings.get("ANSI_BG", []):
        for fg in settings.get("ANSI_FG", []):
            regex = r'({0}{1}(?!\x1b))(.+?)(?=\x1b)|({1}{0}(?!\x1b))(.+?)(?=\x1b)'.format(fg['code'], bg['code'])
            scope = "{0}{1}".format(fg['scope'], bg['scope'])
            yield AnsiPoint(scope, regex)


def subtract_region(p, begin, end):
    if p < begin:
        return p
    elif p < end:
        return begin
    else:
        return p - (end - begin)


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
            a = subtract_region(a, begin, end)
            b = subtract_region(b, begin, end)
            self.regions[n] = (a, b)

    def shift(self, val):
        for n, (a, b) in enumerate(self.regions):
            self.regions[n] = (a + val, b + val)

    def jsonable(self):
        return {self.scope: self.regions}


class AnsiCommand(sublime_plugin.TextCommand):

    def run(self, edit, regions=None):
        v = self.view
        if v.settings().get("ansi_enabled"):
            return
        v.settings().set("ansi_enabled", True)
        v.settings().set("color_scheme", "Packages/User/ANSIescape/ansi.tmTheme")
        v.settings().set("draw_white_space", "none")

        if regions is None:
            self.colorize_existing_data(edit)
        else:
            for scope, regions_points in regions.items():
                regions = []
                for a, b in regions_points:
                    regions.append(sublime.Region(a, b))
                sum_regions = v.get_regions(scope) + regions
                v.add_regions(scope, sum_regions, scope, '', sublime.DRAW_NO_OUTLINE)

        v.set_read_only(True)

    def colorize_existing_data(self, edit):
        v = self.view
        # removing unsupported ansi escape codes before going forward: 2m 4m 5m 7m 8m
        ansi_unsupported_codes = v.find_all(r'(\x1b\[(0;)?(2|4|5|7|8)m)')
        ansi_unsupported_codes.reverse()
        for r in ansi_unsupported_codes:
            v.replace(edit, r, "\x1b[1m")

        for ansi in ansi_point_generator():
            ansi_regions = v.find_all(ansi.regex)
            if DEBUG and ansi_regions:
                print("scope: {}\nregex: {}\nregions: {}\n----------\n".format(ansi.scope, ansi.regex, ansi_regions))
            if ansi_regions:
                sum_regions = v.get_regions(ansi.scope) + ansi_regions
                v.add_regions(ansi.scope, sum_regions, ansi.scope, '', sublime.DRAW_NO_OUTLINE)

        # removing the rest of  ansi escape codes
        ansi_codes = v.find_all(r'(\x1b\[[\d;]*m){1,}')
        ansi_codes.reverse()
        v.set_scratch(True)
        v.set_read_only(False)
        for r in ansi_codes:
            v.erase(edit, r)


class UndoAnsiCommand(sublime_plugin.WindowCommand):

    def run(self):
        view = self.window.active_view()
        view.settings().erase("ansi_enabled")
        view.settings().erase("color_scheme")
        view.settings().erase("draw_white_space")
        view.set_read_only(False)
        view.set_scratch(False)
        settings = sublime.load_settings("ansi.sublime-settings")
        for bg in settings.get("ANSI_BG", []):
            for fg in settings.get("ANSI_FG", []):
                ansi_scope = "{0}{1}".format(fg['scope'], bg['scope'])
                view.erase_regions(ansi_scope)
        self.window.run_command("undo")


class AnsiEventListener(sublime_plugin.EventListener):

    def on_new_async(self, view):
        self.assign_event_listner(view)

    def on_load_async(self, view):
        self.assign_event_listner(view)

    def assign_event_listner(self, view):
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
        if val in ["on_finish", "on_data", "pre_data"]:
            cls.process_trigger = val
        else:
            print("ANSIescape settings warning: not valid ANSI_process_trigger value")

    def pre_data_process(self, proc, data):
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
        for ansi in ansi_point_generator():
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

        # create json serialable region repressentation
        json_ansi_regions = {}
        shift_val = view.size()
        for region in ansi_regions:
            region.shift(shift_val)
            json_ansi_regions.update(region.jsonable())

        # send on_data witout ansi codes
        super(AnsiColorBuildCommand, self).on_data(proc, out_data.encode(self.encoding))

        # send ansi command
        view.settings().set("ansi_enabled", False)
        self.output_view.set_read_only(False)
        view.run_command('ansi', args={"regions": json_ansi_regions})

    def process_ansi(self):
        view = self.output_view
        if view.settings().get("syntax") == "Packages/ANSIescape/ANSI.tmLanguage":
            view.settings().set("ansi_enabled", False)
            view.run_command('ansi')

    def on_data(self, proc, data):
        if self.process_trigger == "pre_data":
            self.pre_data_process(proc, data)
        else:
            super(AnsiColorBuildCommand, self).on_data(proc, data)
            if self.process_trigger == "on_data":
                self.process_ansi()

    def on_finished(self, proc):
        super(AnsiColorBuildCommand, self).on_finished(proc)
        if self.process_trigger == "on_finish":
            self.process_ansi()


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
            AnsiEventListener().assign_event_listner(view)


def plugin_unloaded():
    settings = sublime.load_settings("ansi.sublime-settings")
    settings.clear_on_change("ANSI_COLORS_CHANGE")
    settings.clear_on_change("ANSI_SETTINGS_CHANGE")
