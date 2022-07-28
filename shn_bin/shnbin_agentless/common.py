#!/usr/bin/env python
# Style based on: http://google-styleguide.googlecode.com/svn/trunk/pyguide.html
# Exception: 100 characters width.

"""Common functions to manage Agentless sidecar"""
import os

import shnbin_common
from shnbin_common import get_app_current_path
from shnbin_common import get_setting
from shnbin_common import get_hosts
from shnbin_eureka_common import eureka_common


class Error(Exception):
    """Base Error class."""
    pass


def get_config_path():
    return os.path.join(get_app_current_path(), 'config')


def get_eureka_sidecar_helper():
    """No actual service is listening on this port 5000, purpose is to just to discover ip address of this node"""
    return eureka_common.EurekaSidecarHelper(
        shnbin_common.get_product(), 5000, 
        shnbin_common.get_app_current_path(), 
        shnbin_common.get_templates_path(),
        shnbin_common.get_logs_path(),
        metadata={}
    )   


def get_eureka_url():
    """Returns comma separated string of eureka urls"""
    port = get_setting('http_port')
    return ','.join('http://%s:%s/eureka/v2/' % (host, port)
                    for host in get_hosts('eureka'))


def get_appname():
    return "agentless"


def get_app_path():
    return os.path.join("/shn/apps", get_appname())


def is_salt_managed():
    return os.path.realpath(shnbin_common.get_app_current_path()).startswith(
        get_app_path()
    )
