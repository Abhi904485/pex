#!/usr/bin/env python
# Style based on: http://google-styleguide.googlecode.com/svn/trunk/pyguide.html
# Exception: 100 characters width.

"""when shn_bin/install.py does not exist, this install is still needed to prepare shnbin"""

import common_wrapper


def install():
    """install wrapper"""
    common_wrapper.prepare_shnbin()


def main():
    """main"""
    install()


if __name__ == '__main__':
    main()
