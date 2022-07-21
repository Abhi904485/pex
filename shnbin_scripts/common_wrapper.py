#!/usr/bin/env python
# Style based on: http://google-styleguide.googlecode.com/svn/trunk/pyguide.html
# Exception: 100 characters width.

"""common functions to the wrapper."""
import copy
import os
import subprocess
import sys
import logging
from contextlib import contextmanager


try:
    STRING_TYPE = basestring
except NameError:
    STRING_TYPE = str


@contextmanager
def chdir(new_path):
    """Contextmanage to change directory then return to the previous directory."""
    old_path = os.getcwd()
    os.chdir(new_path)
    try:
        yield
    finally:
        os.chdir(old_path)


def run_shnbin_script(cmd, env=None):
    """Call the given command.
    """
    logging.info('> %s', cmd if isinstance(cmd, STRING_TYPE) else ' '.join(cmd))
    if env is None:
        os.execv(cmd[0], cmd)
    else:
        os.execve(cmd[0], cmd, env)


def get_shnbin_path():
    return os.path.dirname(os.path.abspath(__file__))


def get_current_path():
    return os.path.dirname(get_shnbin_path())


def get_pex_path():
    pexfilename = ''
    if os.path.exists(os.path.join(get_shnbin_path(), 'pexfilename')):
        with open(os.path.join(get_shnbin_path(), 'pexfilename')) as pexfilenamefh:
            pexfilename = pexfilenamefh.read().strip()
    if pexfilename == '':
        setup_path = os.path.join(get_shnbin_path(), 'setup.py')
        pexfilename = subprocess.check_output(['python', setup_path, '--name']).strip()
    return os.path.join(get_shnbin_path(), '%s.pex' % pexfilename)


def get_pex_root_dir():
    return os.path.join(get_current_path(), '.pex')


def get_python_env():
    """Returns env to set PEX_ROOT, sets PYTHONPATH, and sets up the PATH so that "python" corresponds with sys.executable"""

    bin_path = os.path.join(get_pex_root_dir(), "bin")
    if not os.path.exists(bin_path):
        os.makedirs(bin_path)
    python_path = os.path.join(bin_path, "python")
    if not os.path.exists(python_path):
        os.symlink(sys.executable, python_path)
    python_env = copy.deepcopy(os.environ)
    if not python_env.get("PATH", "").startswith(bin_path):
        python_env["PATH"] = os.pathsep.join(
            [bin_path] + python_env.get("PATH", "").split(os.pathsep)
        )

    python_env['PEX_ROOT'] = get_pex_root_dir()
    python_env['PYTHONPATH'] = get_shnbin_path()
    return python_env


def prepare_shnbin():
    # Temporarily needed while development, since dependency is set in glu_model.json and a change
    # there will affect all deployment.
    # Remove those dependencies that are already implemented by pypi packaging and included in
    # requirements.txt.
    for filename in [
        'shnbin_common',
        'eureka_common',
        'eureka_sidecar',
        'tembo_client',
        'client_common',
        'common_crate_new',
        'common_torque_new',
        'shn_common_crate',
        'shn_common_torque',
    ]:
        filepath = os.path.join(get_shnbin_path(), filename)
        subprocess.check_call('rm -f %s*.py*' % filepath, shell=True)
