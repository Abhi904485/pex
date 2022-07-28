#!/usr/bin/env python
import os

import shnbin_common


def install():
    with shnbin_common.chdir(shnbin_common.get_app_current_path()):
        if not os.path.exists("../current"):
            if os.path.exists("current"):
                os.remove("current")
            # Symlink the "runtime" directory to "current" so that it is the same as other components
            os.symlink(".", "current")


def main():
    install()


if __name__ == "__main__":
    shnbin_common.force_line_buffer()
    main()
