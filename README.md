## ANSI escape codes color highlighting for SublimeText 3

From time to time, you end up with a file in your editor that has ANSI escape codes in plain text which makes it really hard to read the content. Something that has been added to make your life easier, stands in your way and it's really annoying. 

This plugin solves this annoying problem. Not by just removing the ANSI escape codes but by bringing back the color highlighting to those files.

![Sublime ANSI Screenshot](https://s3.amazonaws.com/f.cl.ly/items/0e3a0V1A3y392W0R3z20/sublime_ansi.gif)

## Installation

You can install via [Sublime Package Control](http://wbond.net/sublime_packages/package_control)  
Or you can clone this repo into your SublimeText Packages directory and rename it to `ANSI`

## Usage

When you see garbage in your editor change the syntax to `ANSI` and you're good!

### Using this plugin as a dependency for your build output
If you're writing a plugin that builds something using a shell command and shows the results in an output panel, use this plugin! Do not remove ANSI codes, just set the syntax file of your output to `Packages/ANSIescape/ANSI.tmLanguage` and ANSI will take care of color highlighting your terminal output. 

### Customizing ANSI colors
All the colors used to highlight ANSI escape code can be customized through 
[`ansi.sublime-settings`](ansi.sublime-settings).
Create a file named `ansi.sublime-settings` in your user directory, copy the content of default settings and change them to your heart's content.

### Caveats: 
- ANSI views are read-only. But you can switch back to plain text to edit them if you want. 
- Does not render ANSI bold as bold, although we support it. You can assign a unique foreground color to bold items to distinguish them from the rest of the content.
- Does not support dim, underscore, blink, reverse and hidden text attributes, which is fine since they are not supported by many terminals as well and their usage are pretty rare. 

### License
Copyright 2014-2015 [Allen Bargi](https://twitter.com/aziz). Licensed under the MIT License

