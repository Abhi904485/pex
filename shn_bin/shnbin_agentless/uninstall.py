#!/usr/bin/env python
import logging
import shutil

import shnbin_common

import common


LOG = logging.getLogger(__name__)


def uninstall():
    if not common.is_salt_managed():
        LOG.info("Removing %s", shnbin_common.get_app_path())
        shutil.rmtree(shnbin_common.get_app_path())
    else:
        LOG.info("Uninstall is a noop for salt-managed %s", common.get_appname())


def main():
    uninstall()


if __name__ == "__main__":
    shnbin_common.force_line_buffer()
    main()
