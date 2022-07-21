#!/usr/bin/env python
# Style based on: http://google-styleguide.googlecode.com/svn/trunk/pyguide.html
# Exception: 100 characters width.

"""Python script to start agentless service"""

import sys

import shnbin_common
import logging
import common


def start():
    logging.info("Start Eureka Sidecar")
    common.get_eureka_sidecar_helper().start_sidecar()


def main(argv):
    """main"""
    return start()


if __name__ == '__main__':
    shnbin_common.force_line_buffer()
    sys.exit(main(sys.argv))
