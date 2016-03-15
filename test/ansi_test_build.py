#!/usr/bin/env python

import sys, time

print '========================='
print ' ANSI TEST BUILD STARTED '
print '========================='

with open(sys.argv[1]) as file:
	for line in file:
		time.sleep(0.25)
		print line

print '=========================='
print ' ANSI TEST BUILD COMPLETE '
print '=========================='