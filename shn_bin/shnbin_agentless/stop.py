#!/usr/bin/env python
# Style based on: http://google-styleguide.googlecode.com/svn/trunk/pyguide.html
# Exception: 100 characters width.

"""Python script to stop Agentless service"""

import sys
import logging
import shnbin_common

import common


def stop():
    logging.info("Stopping Eureka Sidecar")
    common.get_eureka_sidecar_helper().stop_sidecar()


def main(argv):
    """main"""
    return stop()


if __name__ == '__main__':
    shnbin_common.force_line_buffer()
    sys.exit(main(sys.argv))
