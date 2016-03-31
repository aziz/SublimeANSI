# -*- coding: utf-8 -*-

import sublime
import sublime_plugin
import os
import re
import Default

DEBUG = False


class AnsiCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        v = self.view
        if v.settings().get("ansi_enabled"):
            return
        v.settings().set("ansi_enabled", True)
        v.settings().set("color_scheme", "Packages/User/ANSIescape/ansi.tmTheme")
        v.settings().set("draw_white_space", "none")

        if not v.settings().has("ansi_scratch"):
            v.settings().set("ansi_scratch", v.is_scratch())
        v.set_scratch(True)

        if not v.settings().has("ansi_read_only"):
            v.settings().set("ansi_read_only", v.is_read_only())
        v.set_read_only(False)

        # removing unsupported ansi escape codes before going forward: 2m 4m 5m 7m 8m
        ansi_unsupported_codes = v.find_all(r'(\x1b\[(0;)?(2|4|5|7|8)m)')
        ansi_unsupported_codes.reverse()
        for r in ansi_unsupported_codes:
            v.replace(edit, r, "\x1b[1m")

        # collect colors from file content and make them a string
        color_str = '\x1b' + '\x1b'.join({
            v for v in
            re.findall(
                r'(\[[\d;]*m)', # find all possible colors
                v.substr(sublime.Region(0, v.size())) # file content
            )
        }) + '\x1b'

        settings = sublime.load_settings("ansi.sublime-settings")
        # filter out unnecessary colors in user settings
        bgs = [v for v in settings.get("ANSI_BG", []) if re.search(v['code'], color_str) is not None]
        fgs = [v for v in settings.get("ANSI_FG", []) if re.search(v['code'], color_str) is not None]

        for bg in bgs:
            for fg in fgs:
                regex = r'(?:(?:{0}{1})|(?:{1}{0}))[^\x1b]*'.format(fg['code'], bg['code'])
                ansi_scope = "{0}{1}".format(fg['scope'], bg['scope'])
                ansi_regions = v.find_all(regex)
                if DEBUG and ansi_regions:
                    print("scope: {}\nregex: {}\n regions: {}\n----------\n".format(ansi_scope, regex, ansi_regions))
                if ansi_regions:
                    sum_regions = v.get_regions(ansi_scope) + ansi_regions
                    v.add_regions(ansi_scope, sum_regions, ansi_scope, '', sublime.DRAW_NO_OUTLINE)

        # removing the rest of  ansi escape codes
        ansi_codes = v.find_all(r'(\x1b\[[\d;]*m){1,}')
        ansi_codes.reverse()
        for r in ansi_codes:
            v.erase(edit, r)
        v.set_read_only(True)


class UndoAnsiCommand(sublime_plugin.WindowCommand):

    def run(self):
        view = self.window.active_view()
        view.settings().erase("ansi_enabled")
        view.settings().erase("color_scheme")
        view.settings().erase("draw_white_space")
        view.set_read_only(False)
        settings = sublime.load_settings("ansi.sublime-settings")
        for bg in settings.get("ANSI_BG", []):
            for fg in settings.get("ANSI_FG", []):
                ansi_scope = "{0}{1}".format(fg['scope'], bg['scope'])
                view.erase_regions(ansi_scope)
        self.window.run_command("undo")
        view.set_scratch(view.settings().get("ansi_scratch", False))
        view.settings().erase("ansi_scratch")
        view.set_read_only(view.settings().get("ansi_read_only", False))
        view.settings().erase("ansi_read_only")

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

    process_on_data = False
    process_on_finish = True

    @classmethod
    def update_build_settings(cls):
        print("updating ANSI build settings...")
        settings = sublime.load_settings("ansi.sublime-settings")
        val = settings.get("ANSI_process_trigger", "on_finish")
        if val == "on_finish":
            cls.process_on_data = False
            cls.process_on_finish = True
        elif val == "on_data":
            cls.process_on_data = True
            cls.process_on_finish = False

    def process_ansi(self):
        view = self.output_view
        if view.settings().get("syntax") == "Packages/ANSIescape/ANSI.tmLanguage":
            view.settings().set("ansi_enabled", False)
            view.run_command('ansi')

    def on_data(self, proc, data):
        super(AnsiColorBuildCommand, self).on_data(proc, data)
        if self.process_on_data:
            self.process_ansi()

    def on_finished(self, proc):
        super(AnsiColorBuildCommand, self).on_finished(proc)
        if self.process_on_finish:
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
