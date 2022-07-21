#!/usr/bin/env python
# Style based on: http://google-styleguide.googlecode.com/svn/trunk/pyguide.html
# Exception: 100 characters width.

"""wrapper for shn_bin/configure.py."""

import sys
import common_wrapper


def configure():
    """Configure wrapper"""
    argv = sys.argv[1:]
    common_wrapper.run_shnbin_script(
        [common_wrapper.get_pex_path(), 'configure'] + argv,
        env=common_wrapper.get_python_env()
    )


def main():
    """main"""
    configure()


if __name__ == '__main__':
    main()
