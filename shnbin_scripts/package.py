#!/usr/bin/env python3.5
"""Usage:
    package.py

"""
# START boilerplate imports
import os
import sys
import urllib.request

# END boilerplate imports


def parse_requirements(infile):
    return set(
        line
        for line in (
            # Remove comments and extra whitespace
            line.split("#")[0].strip().strip("\\").strip()
            for line in iter(infile.readline, "")
        )
        # Remove empty lines and lines with cmdline options
        if line and not line.startswith("-")
    )


def get_requirements(filename):
    with open(filename) as infile:
        return parse_requirements(infile)


DEV_REQUIREMENTS = get_requirements("dev_requirements.txt")

PYPI_HOST = "artifactory.corp.int.shn.io"
PYPI_URL = "http://%s/api/pypi/pypi" % (PYPI_HOST,)
PIP_OPTIONS = [
    "--index-url",
    "%s/simple" % (PYPI_URL,),
    "--trusted-host",
    "artifactory.corp.int.shn.io",
]

# START boilerplate
try:
    import pkg_resources

    pkg_resources.require(DEV_REQUIREMENTS)

# We're expecting ImportError or pkg_resources.ResolutionError but since pkg_resources might not be importable,
# we're just catching Exception.
except Exception:
    GET_PIP_URL = "https://artifactory.corp.int.shn.io/shn-support-tools/v2/get-pip.py"
    if __name__ != "__main__":
        raise
    try:
        import magicreq

        magicreq.magic(
            DEV_REQUIREMENTS,
            pip_options=" ".join(PIP_OPTIONS),
            pypi_url=PYPI_URL,
            get_pip_url=GET_PIP_URL,
        )
    except ImportError:
        url = (
            "http://artifactory.corp.int.shn.io/shn-support-tools/magicreq_bootstrap.py"
        )
        bootstrap_script = os.path.join(os.getcwd(), ".magicreq_bootstrap.py")
        with open(bootstrap_script, "wb") as outfile:
            outfile.write(urllib.request.urlopen(url).read())
        cmd = [
            sys.executable,
            bootstrap_script,
            "PIP_OPTIONS:%s" % (" ".join(PIP_OPTIONS),),
            "PYPI_URL:%s" % (PYPI_URL,),
            "GET_PIP_URL:%s" % (GET_PIP_URL,),
        ] + sys.argv
        print("sys argv:%s" % sys.argv)
        print("sys executable:%s, cmd:%s" % (sys.executable, cmd))
        os.execv(sys.executable, cmd)
# END boilerplate


import glob  # noqa

# import io
import logging  # noqa
import os  # noqa
import shutil  # noqa

# import subprocess
import sys  # noqa

import tomlkit  # noqa

import shnbin_common  # noqa


LOG = logging.getLogger(__name__)


POETRY = os.path.join(os.getcwd(), "_venv", "bin", "poetry")
NOSETESTS = os.path.join(os.getcwd(), "_venv", "bin", "nosetests-3.5")
PEX = os.path.join(os.getcwd(), "_venv", "bin", "pex")
# We need to set the specific python version we want as we're still running trusty where the default python3 is 3.4
SHEBANG_CMD = "/usr/bin/env python3.5"
SHEBANG = "#!%s" % (SHEBANG_CMD,)


def build_wheels(requirements, shnbin_package_name):
    LOG.info("Copying shnbin_scripts/main.py")
    os.mkdir(shnbin_package_name)
    shutil.copy(
        "shnbin_scripts/main.py", os.path.join(shnbin_package_name, "main.py"),
    )
    os.system("cp -r shn_bin/* %s" % (shnbin_package_name,))

    LOG.info("Building shnbin wheel")
    shnbin_common.logged_call([POETRY, "build", "-vvv"])


def cleanup(env):
    LOG.info("Cleanup")
    if os.path.exists(env["PEX_ROOT"]):
        shnbin_common.logged_call(["rm", "-rf", env["PEX_ROOT"]])
    shnbin_common.logged_call(["rm", "-r", "build"])


def build_shnbin_pex(
    env, PEX, shnbin_requirements, shnbin_package_name, SHEBANG_CMD, PYPI_URL
):
    LOG.info("Building shnbin pex")
    shnbin_common.logged_call(
        [PEX]
        + glob.glob("dist/*.whl")
        + list(shnbin_requirements)
        + [
            "-o",
            "%s.pex" % (shnbin_package_name,),
            "-e",
            "%s.main" % (shnbin_package_name,),
            "--python-shebang",
            SHEBANG_CMD,
            "--disable-cache",
            "-v",
            "-f",
            "../wheels",
            "--no-pypi",
            "--index",
            "%s/simple" % (PYPI_URL,),
        ],
        env=env,
    )
    shnbin_common.logged_call(["./%s.pex" % (shnbin_package_name,), "--help"])

    LOG.info("Building run_daemonize pex")
    shnbin_common.logged_call(
        [PEX]
        + [
            "-v",
            "-o",
            "run_daemonize.pex",
            "-e",
            "reversefold.util.daemonize:main",
            "--disable-cache",
            "--index",
            "%s/simple" % (PYPI_URL,),
            "reversefold.util>=1.15.6,<3.0.0",
            "watchdog<0.10.0",
        ],
        env=env,
    )

    LOG.info("Building ianitor pex")
    shnbin_common.logged_call(
        [PEX]
        + [
            "-v",
            "-o",
            "ianitor.pex",
            "-e",
            "ianitor.script:main",
            "--disable-cache",
            "--index",
            "%s/simple" % (PYPI_URL,),
            "ianitor",
        ],
        env=env,
    )


def run_tests(NOSETESTS):
    LOG.info("Running tests")
    NOSEOPTS = [
        "-v",
        "--with-xunit",
        "--cover-erase",
        "--with-coverage",
        "--cover-erase",
        "--cover-branches",
        "--cover-xml",
        "--cover-html",
        "--cover-package=shn_bin",
    ]
    shnbin_common.logged_call([NOSETESTS] + NOSEOPTS + ["shn_bin"])


def build_tarball(env, shnbin_package_name, SHEBANG):
    if os.path.exists("build"):
        shnbin_common.logged_call(["rm", "-r", "build"])
    shnbin_common.logged_call(["mkdir", "build"])
    with shnbin_common.chdir("build"):
        shnbin_common.logged_call(["mv"] + glob.glob("../*.pex") + ["."])

        LOG.info("Copying shnbin wrappers")
        shnbin_common.logged_call(["mkdir", "shn_bin"])
        shnbin_common.logged_call(["mv", shnbin_package_name + ".pex", "shn_bin"])
        for auxiliary_pex in ["run_daemonize.pex", "ianitor.pex"]:
            if os.path.exists(auxiliary_pex):
                shnbin_common.logged_call(["mv", auxiliary_pex, "shn_bin"])
        for action in [
            "configure",
            "install",
            "monitor",
            "start",
            "stop",
            "unconfigure",
            "uninstall",
        ]:
            action_py = os.path.join("shn_bin", "%s.py" % (action,))
            if os.path.exists(os.path.join("../shn_bin", "%s.py" % (action,))):
                shnbin_common.logged_call(
                    [
                        "cp",
                        os.path.join("../shnbin_scripts", "%s.py" % (action,)),
                        action_py,
                    ]
                )
            elif os.path.exists(
                os.path.join("../shnbin_scripts", "%s_without.py" % (action,))
            ):
                shnbin_common.logged_call(
                    ["cp", "../shnbin_scripts/%s_without.py" % (action,), action_py]
                )
            if os.path.exists(action_py):
                with open(action_py, "rb") as f:
                    first_2 = f.read(2)
                    if first_2 == b"#!":
                        while f.read(1) != b"\n":
                            continue
                        first_2 = b""
                    action_py_contents = first_2 + f.read()
                with open(action_py, "wb") as f:
                    f.write(SHEBANG.encode("utf-8"))
                    f.write(b"\n")
                    f.write(action_py_contents)

        shnbin_common.logged_call(
            ["cp", "../shnbin_scripts/common_wrapper.py", "shn_bin"]
        )
        with open("shn_bin/pexfilename", "w") as f:
            f.write(shnbin_package_name)
        shnbin_common.logged_call(["chmod", "+x"] + glob.glob("shn_bin/*.py"))

        os.system("cp -r ../shn_bin/templates shn_bin")
        os.system("cp -r ../conf .")
        LOG.info("Building tarball")
        folders_to_be_archived = ["shn_bin", "conf"]
        list1 = [folder for folder in folders_to_be_archived if os.path.lexists(folder)]
        shnbin_common.logged_call(
            [
                "tar",
                "zcvf",
                "../%s-%s.tgz"
                % (shnbin_package_name.replace("_", "-"), env["BUILD_NUMBER"],),
            ]
            + list1
        )


def collect_shnbin_requirements():
    shnbin_requirements = get_requirements("requirements.txt")
    return shnbin_requirements


def setup_env():
    with open("pyproject.toml", "r") as f:
        project = tomlkit.parse(f.read())

    shnbin_package_name = project["tool"]["poetry"]["name"]
    env = dict(os.environ.items())
    env["PEX_ROOT"] = os.path.join(os.path.dirname(__file__), ".pex")
    env["SETUPTOOLS_USE_DISTUTILS"] = "stdlib"
    return [env, shnbin_package_name]


def cleanup_before_build(env):
    if os.path.exists(env["PEX_ROOT"]):
        shnbin_common.logged_call(["rm", "-rf", env["PEX_ROOT"]])
    if os.path.exists("dist"):
        shnbin_common.logged_call(["rm", "-r", "dist"])


def main():
    env, shnbin_package_name = setup_env()  # setup environment
    cleanup_before_build(env)  # cleanup required folders and files before the build
    shnbin_requirements = collect_shnbin_requirements()  # collecting requirements
    build_wheels(shnbin_requirements, shnbin_package_name)  # building wheels
    build_shnbin_pex(
        env, PEX, shnbin_requirements, shnbin_package_name, SHEBANG_CMD, PYPI_URL
    )  # building shnbin pex
    run_tests(NOSETESTS)  # running tests
    build_tarball(env, shnbin_package_name, SHEBANG)  # building tarball
    cleanup(env)


if __name__ == "__main__":
    shnbin_common.force_line_buffer()
    main()
