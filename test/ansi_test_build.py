#!/usr/bin/env python

import sys
import time


def print_file_lines(ansi_file):
    with open(ansi_file) as file:
        for line in file:
            time.sleep(0.25)
            print(line)

if __name__ == '__main__':

    if len(sys.argv) > 1:
        ansi_file = sys.argv[1]
    else:
        ansi_file = "ansi_test_file.txt"

    print('=========================')
    print(' ANSI TEST BUILD STARTED ')
    print('=========================')

    print_file_lines(ansi_file)

    print('\n==========================')
    print(' ANSI TEST BUILD COMPLETE ')
    print('==========================')
