import logging
import sys
import os

from shnbin_common import force_line_buffer
from shnbin_common import get_product
import common


def configure():
    product = get_product()
    logging.info('Configuring %s', product)
    sidecar = common.get_eureka_sidecar_helper()
    if not os.path.exists(sidecar.configs_path):
        os.makedirs(sidecar.configs_path)
    sidecar.configure_sidecar()
    logging.info('Configured %s', product)


if __name__ == '__main__':
    force_line_buffer()
    sys.exit(configure())
