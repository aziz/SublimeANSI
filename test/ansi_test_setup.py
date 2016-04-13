#!/usr/bin/env python

import os
import re
import sys

help_text = '''
This scripts adds the ANSIescape mock build to the list of available
build systems within Sublime Text. The purpose of this mock build is
to provide an easy way of testing changes to the ANSIescape package.

Usage: ansi_test_setup.py [options]

Options:
 -h --help    Print help and exit.
 -c --create  Add the ANSIescape mock build to Sublime Text.
 -r --remove  Remove the ANSIescape mock build from Sublime Text.
'''

bld_cfg_settings = '''
{
	"cmd": ["python", "-u", "ansi_test_build.py", "ansi_test_file.txt"],
	"working_dir": "$packages/ANSIescape/test",
	"target": "ansi_color_build",
	"syntax": "Packages/ANSIescape/ANSI.tmLanguage"
}
'''

bld_cfg_file = 'ansi.sublime-build'


def help():
    print(help_text)


def create():
    with open(bld_cfg_file, 'w') as file:
        file.write(bld_cfg_settings)
    print('Added ANSIescape test build to Sublime Text.')


def remove():
    if os.path.isfile(bld_cfg_file):
        os.remove(bld_cfg_file)
    print('Removed ANSIescape test build from Sublime Text.')

opt = help

if len(sys.argv) > 1:
    if re.match(r'^-(?:-)?h(?:e(?:l(?:p)?)?)?$', sys.argv[1]):
        opt = help
    if re.match(r'^-(?:-)?c(?:r(?:e(?:a(?:t(?:e)?)?)?)?)?$', sys.argv[1]):
        opt = create
    if re.match(r'^-(?:-)?r(?:e(?:m(?:o(?:v(?:e)?)?)?)?)?$', sys.argv[1]):
        opt = remove

opt()
