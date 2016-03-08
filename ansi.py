# -*- coding: utf-8 -*-

import sublime
import sublime_plugin
import os
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

        # removing unsupported ansi escape codes before going forward: 2m 4m 5m 7m 8m
        ansi_unsupported_codes = v.find_all(r'(\x1b\[(0;)?(2|4|5|7|8)m)')
        ansi_unsupported_codes.reverse()
        for r in ansi_unsupported_codes:
            v.replace(edit, r, "\x1b[1m")

        settings = sublime.load_settings("ansi.sublime-settings")
        for bg in settings.get("ANSI_BG", []):
            for fg in settings.get("ANSI_FG", []):
                regex = r'({0}{1}(?!\x1b))(.+?)(?=\x1b)|({1}{0}(?!\x1b))(.+?)(?=\x1b)'.format(fg['code'], bg['code'])
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
        v.set_scratch(True)


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

    def on_load_async(self, view):
        view.settings().add_on_change("CHECK_FOR_ANSI_SYNTAX", lambda: self.syntax_change(view))
        if view.settings().get("syntax") == "Packages/ANSIescape/ANSI.tmLanguage":
            view.run_command("ansi")

    def syntax_change(self, view):
        if view.settings().get("syntax") == "Packages/ANSIescape/ANSI.tmLanguage":
            view.run_command("ansi")
        elif view.settings().get("ansi_enabled"):
            view.window().run_command("undo_ansi")


class AnsiColorBuildCommand(Default.exec.ExecCommand):

    def process_ansi(self):
        view = self.output_view
        if view.settings().get("syntax") == "Packages/ANSIescape/ANSI.tmLanguage":
            view.settings().set("ansi_enabled", False)
            self.output_view.set_read_only(False)
            view.run_command('ansi')

    def on_data(self, proc, data):
        super(AnsiColorBuildCommand, self).on_data(proc, data)
        settings = sublime.load_settings("ansi.sublime-settings")
        if settings.get("process_on_data", False):
            self.process_ansi()

    def on_finished(self, proc):
        super(AnsiColorBuildCommand, self).on_finished(proc)
        settings = sublime.load_settings("ansi.sublime-settings")
        if settings.get("process_on_finish", True):
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
    settings.add_on_change("ANSI_COLORS_CHANGE", lambda: generate_color_scheme(cs_file))


def plugin_unloaded():
    settings = sublime.load_settings("ansi.sublime-settings")
    settings.clear_on_change("ANSI_COLORS_CHANGE")
