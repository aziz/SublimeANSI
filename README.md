## ANSI escape codes color highlighting for ST3

From time to time, you end up with a file in your editor that has ANSI escape codes in plain text which makes it really hard to read the content. Something that has been added to make your life easier, stands in your way and it's really annoying. 

This plugin solves this annoying problem. Not by just removing the ANSI escape codes but by bringing back the color highlighting to those files.

![Sublime ANSI Screenshot](https://s3.amazonaws.com/f.cl.ly/items/0e3a0V1A3y392W0R3z20/sublime_ansi.gif)

## Installation

You can install via [Sublime Package Control](http://wbond.net/sublime_packages/package_control)  
Or you can clone this repository into your SublimeText Packages directory and rename it to `ANSIescape`

## Usage

When you see garbage in your editor change the syntax to `ANSI` and you're good!

The plugin works by detecting the syntax change event and marking ANSI color chars regions with the appropriate scopes matching the style defined in a tmTheme file.

### Using this plugin as a dependency for your plugin/build output panel
If you're writing a plugin that builds something using a shell command and shows the results in an output panel, use this plugin! Do not remove ANSI codes, just set the syntax file of your output to `Packages/ANSIescape/ANSI.sublime-syntax` and ANSI will take care of color highlighting your terminal output.

Likewise, if you would like to display ANSI colors in your existing [build-command](http://sublime-text-unofficial-documentation.readthedocs.org/en/latest/reference/build_systems/basics.html) output, you would only need to set `ansi_color_build` as the target and `Packages/ANSIescape/ANSI.sublime-syntax` as the syntax; for example:

```javascript
// someproject.sublime-project
{
    "build_systems":
    [
        {
            /* your existing build command arguments */
            "name": "Run",
            "working_dir": "${project_path}/src",
            "env": {"PYTHONPATH": ".../venv/python2.7/site-packages"},
            "cmd": ["nosetests", "--rednose"],

            /*  add target and syntax */
            "target": "ansi_color_build",
            "syntax": "Packages/ANSIescape/ANSI.sublime-syntax"
        }
    ]
}
```

If you use a custom build script and sub-programms don't output color, it could be that they assume the output has no colors. On Linux some applications can be forced to use colors by setting the environment variable `CLICOLOR_FORCE=1`. It is not recommended to set it permanently since it could cause issues if color is not supported and applications still output color. But in a SublimeANSI build you can use it for the usage in a Makefile build script, e.g.: 

```javascript
// someproject.sublime-project
{
    "build_systems":
    [
        {
            /* your existing build command arguments */
            "name": "Build",
            "working_dir": "${project_path}",
            "env": {"CLICOLOR_FORCE": "1"},
            "cmd": ["sh", "build.sh"],

            /*  add target and syntax */
            "target": "ansi_color_build",
            "syntax": "Packages/ANSIescape/ANSI.sublime-syntax"
            
             "variants":
            [
                {
                    "name": "Clean",
                    "cmd": ["sh", "build.sh", "clean"]
                }
            ]
        }
    ]
}
```


#### Killing the build process

If you want to kill build process during execution, use this command in sublime console (``ctrl+` ``):

```shell
window.run_command("ansi_color_build", args={"kill": True})
```

You can also add key binding eg.:

```javascript
// Preferences > Key Binding - User
[
    { "keys": ["ctrl+alt+c"], "command": "ansi_color_build", "args": {"kill": true} },
    // other key-bindings 
]
```

#### Formatting ANSI codes during build process

In order to format ANSI codes during building process change 'ANSI_process_trigger' in [`ansi.sublime-settings`](ansi.sublime-settings).

### Customizing ANSI colors
All the colors used to highlight ANSI escape code can be customized through 
[`ansi.sublime-settings`](ansi.sublime-settings).
Create a file named `ansi.sublime-settings` in your user directory, copy the content of default settings and change them to your heart's content.

### Caveats: 
- ANSI views are read-only. But you can switch back to plain text to edit them if you want. 
- Does not render ANSI bold as bold, although we support it. You can assign a unique foreground color to bold items to distinguish them from the rest of the content.
- Does not support dim, underscore, blink, reverse and hidden text attributes, which is fine since they are not supported by many terminals as well and their usage are pretty rare. 

### Known Issues

#### Not able to paste copied build message into a new buffer view

Just making the new view non-empty so the syntax won't be auto set.
For example, type a new line before you paste.

### License
Copyright 2014-2016 [Allen Bargi](https://twitter.com/aziz). Licensed under the MIT License

