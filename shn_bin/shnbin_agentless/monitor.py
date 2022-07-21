#!/usr/bin/env python
# Style based on: http://google-styleguide.googlecode.com/svn/trunk/pyguide.html
# Exception: 100 characters width.

"""Python script to monitor Agentless service and register with Eureka."""

import sys


def monitor():
    return 'runnning'


def main(argv):
    """main"""
    print(monitor())
    return monitor()


if __name__ == '__main__':
    sys.exit(main(sys.argv))
