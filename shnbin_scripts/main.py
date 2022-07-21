#!/usr/bin/env python
# Style based on: http://google-styleguide.googlecode.com/svn/trunk/pyguide.html
# Exception: 100 characters width.

"""The entry module for shnbin project pex."""

import argparse
import logging
import os
import sys


def main():
    argv = sys.argv[1:2]
    parser = argparse.ArgumentParser()
    subcommands = {
        'install': 'install.py',
        'uninstall': 'uninstall.py',
        'configure': 'configure.py',
        'unconfigure': 'unconfigure.py',
        'start': 'start.py',
        'stop': 'stop.py',
        'monitor': 'monitor.py'
    }
    parser.add_argument(dest='subcommand', choices=subcommands.keys(), help='what to call')
    parsed, unknown = parser.parse_known_args(argv)
    scriptpath = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        subcommands[parsed.subcommand],
    )
    if os.path.exists(scriptpath):
        argv = sys.argv[2:]
        pexenv = os.environ.copy()
        pexenv['PYTHONPATH'] = '%s:%s' % (pexenv['PYTHONPATH'], ':'.join(sys.path))
        cmd = [sys.executable, scriptpath] + argv
        logging.info('> %s', ' '.join(cmd))
        os.execve(cmd[0], cmd, pexenv)


if __name__ == '__main__':
    main()
