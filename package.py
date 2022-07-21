#!/usr/bin/env python3.9
import os
import sys


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


PYPI_HOST = "artifactory.corp.int.shn.io"
PYPI_URL = f"https://{PYPI_HOST}/api/pypi/pypi"
PIP_OPTIONS = [
    "--index-url",
    f"{PYPI_URL}/simple",
    "--trusted-host",
    "artifactory.corp.int.shn.io",
]


import glob  # noqa

# import io
import logging  # noqa
import os  # noqa
import shutil  # noqa

# import subprocess
import sys  # noqa

import docopt  # noqa
import tomlkit  # noqa

import shnbin_common  # noqa


LOG = logging.getLogger(__name__)


POETRY = shutil.which("poetry")
# We need to set the specific python version we want as we're still running trusty where the default python3 is 3.4
SHEBANG_CMD = "/usr/bin/env python3.9"
SHEBANG = f"#!{SHEBANG_CMD}"


def main():
    # # TODO: This is a hack needed because poetry 1.0.0b depends on clikit 0.3 which has a compatibility problem with Python 3.5.2, which is the version on Ubuntu 16.04
    # shnbin_common.logged_call(
    #     "find . -name application_config.py | xargs -IFILE sed -i.bak 's/from typing import ContextManager/# from typing import ContextManager/g' FILE",
    #     shell=True,
    # )
    # # TODO: This one is an issue with poetry itself which purports to be fixed in master but has not been release yet.
    # shnbin_common.logged_call(
    #     "find . -name helpers.py | xargs -IFILE sed -i.bak 's/from typing import NoReturn/# from typing import NoReturn/g' FILE",
    #     shell=True,
    # )

    with open("pyproject.toml", "r") as f:
        project = tomlkit.parse(f.read())

    package_name = project["tool"]["poetry"]["name"]
    entrypoint = f"{package_name}.main"
    env = dict(os.environ.items())
    env["PEX_ROOT"] = os.path.join(os.path.dirname(__file__), ".pex")
    # NOTE: Working around a known issue with setuptools 50(+)? See https://github.com/pypa/setuptools/issues/2353
    env["SETUPTOOLS_USE_DISTUTILS"] = "stdlib"
    if os.path.exists(env["PEX_ROOT"]):
        shnbin_common.logged_call(["rm", "-rf", env["PEX_ROOT"]])
    if os.path.exists("dist"):
        shnbin_common.logged_call(["rm", "-r", "dist"])

    # LOG.info("Setting up poetry")
    # shnbin_common.logged_call(["poetry", "install"])

    # LOG.info("Getting requirements")
    # proc = subprocess.Popen(
    #     "poetry export -f requirements.txt --without-hashes",
    #     shell=True,
    #     stdout=subprocess.PIPE,
    #     stderr=subprocess.PIPE,
    #     stdin=subprocess.PIPE,
    # )
    # (stdout, stderr) = proc.communicate()
    # requirements = parse_requirements(io.StringIO(stdout.decode("utf-8")))

    # LOG.info("Getting dev requirements")
    # proc = subprocess.Popen(
    #     "poetry export --dev -f requirements.txt --without-hashes",
    #     shell=True,
    #     stdout=subprocess.PIPE,
    #     stderr=subprocess.PIPE,
    #     stdin=subprocess.PIPE,
    # )
    # (stdout, stderr) = proc.communicate()
    # dev_requirements = parse_requirements(io.StringIO(stdout.decode("utf-8")))

    requirements = get_requirements("requirements.txt")
    # dev_requirements = get_requirements("dev_requirements.txt")

    shnbin_package_name = f"shnbin_{package_name}"

    shnbin_path = "shn_bin"

    # with shnbin_common.chdir(build_shnbin_path):
    with shnbin_common.chdir(shnbin_path):
        # LOG.info("Setting up poetry for shnbin")
        # shnbin_common.logged_call(["poetry", "install"])

        # LOG.info("Getting shnbin requirements")
        # proc = subprocess.Popen(
        #     "poetry export -f requirements.txt --without-hashes",
        #     shell=True,
        #     stdout=subprocess.PIPE,
        #     stderr=subprocess.PIPE,
        #     stdin=subprocess.PIPE,
        # )
        # (stdout, stderr) = proc.communicate()
        # shnbin_requirements = parse_requirements(io.StringIO(stdout.decode("utf-8")))
        shnbin_requirements = get_requirements("requirements.txt")
        # shnbin_dev_requirements = get_requirements("dev_requirements.txt")

    LOG.info("Copying shnbin_scripts/main.py")
    shutil.copy(
        "shnbin_scripts/main.py",
        os.path.join(shnbin_path, shnbin_package_name, "main.py"),
    )

    LOG.info("Building agentless wheel")
    shnbin_common.logged_call([POETRY, "build", "-vvv"])
    LOG.info("Building agentless pex")
    shnbin_common.logged_call(
        [POETRY, "run", "pex"]
        + glob.glob("dist/*.whl")
        + list(requirements)
        + [
            "-o",
            f"{package_name}.pex",
            "-m",
            entrypoint,
            "--python-shebang",
            SHEBANG_CMD,
            "--disable-cache",
            "-v",
            # "-f",
            # "wheels",
            # "--no-index",
            "--no-pypi",
            "--index",
            f"{PYPI_URL}/simple",
        ],
        env=env,
    )
    LOG.info(f"Testing {package_name}.pex")
    shnbin_common.logged_call(["./%s.pex" % (package_name,), "--help"], env=env)

    with shnbin_common.chdir(shnbin_path):
        LOG.info("Building shnbin wheel")
        # shnbin_common.logged_call(["poetry", "install"])
        # shnbin_common.logged_call(["poetry", "build", "-vvv"])
        shnbin_common.logged_call([POETRY, "build", "-vvv"])

        LOG.info("Building shnbin pex")
        shnbin_common.logged_call(
            [POETRY, "run", "pex"]
            + glob.glob("dist/*.whl")
            + list(shnbin_requirements)
            + [
                "-o",
                f"../{shnbin_package_name}.pex",
                "-e",
                f"{shnbin_package_name}.main",
                "--python-shebang",
                SHEBANG_CMD,
                "--disable-cache",
                "-v",
                # "-f",
                # "../wheels",
                # "--no-index",
                "--no-pypi",
                "--index",
                f"{PYPI_URL}/simple",
            ],
            env=env,
        )

    shnbin_common.logged_call([f"./{shnbin_package_name}.pex", "--help"])

    shnbin_common.logged_call(
        [
            POETRY,
            "run",
            "pex",
            "reversefold.util",
            "--python-shebang",
            SHEBANG_CMD,
            "-o",
            "daemonize.pex",
            "-e",
            "reversefold.util.daemonize:main",
            "--disable-cache",
            "-v",
            # "-f",
            # "wheels",
            # "--no-index",
            "--no-pypi",
            "--index",
            f"{PYPI_URL}/simple",
        ],
        env=env,
    )
    LOG.info("Testing daemonize.pex")
    shnbin_common.logged_call(["./daemonize.pex", "--help"], env=env)

    shnbin_common.logged_call(
        [
            POETRY,
            "run",
            "pex",
            "ianitor",
            "--python-shebang",
            SHEBANG_CMD,
            "-o",
            "ianitor.pex",
            "-e",
            "ianitor.script:main",
            "--disable-cache",
            "-v",
            # "-f",
            # "wheels",
            # "--no-index",
            "--no-pypi",
            "--index",
            f"{PYPI_URL}/simple",
        ],
        env=env,
    )
    LOG.info("Testing ianitor.pex")
    shnbin_common.logged_call(["./ianitor.pex", "--help"], env=env)

    shnbin_common.logged_call(
        [
            POETRY,
            "run",
            "pex",
            "shnbin-eureka-common",
            "--python-shebang",
            SHEBANG_CMD,
            "-o",
            "eureka_sidecar.pex",
            "-e",
            "shnbin_eureka_common.eureka_sidecar:main",
            "--disable-cache",
            "-v",
            # "-f",
            # "wheels",
            # "--no-index",
            "--no-pypi",
            "--index",
            f"{PYPI_URL}/simple",
        ],
        env=env,
    )
    LOG.info("Testing eureka_sidecar.pex")
    shnbin_common.logged_call(["./eureka_sidecar.pex", "--help"], env=env)

    if os.path.exists("build"):
        shnbin_common.logged_call(["rm", "-r", "build"])
    shnbin_common.logged_call(["mkdir", "build"])
    with shnbin_common.chdir("build"):
        shnbin_common.logged_call(["mv"] + glob.glob("../*.pex") + ["."])

        LOG.info("Copying shnbin wrappers")
        shnbin_common.logged_call(["mkdir", "shn_bin"])
        shnbin_common.logged_call(["mv", shnbin_package_name + ".pex", "shn_bin"])
        for action in [
            "configure",
            "install",
            "monitor",
            "start",
            "stop",
            "unconfigure",
            "uninstall",
        ]:
            action_py = os.path.join("shn_bin", f"{action}.py")
            if os.path.exists(
                os.path.join("../shn_bin", shnbin_package_name, f"{action}.py")
            ):
                shnbin_common.logged_call(
                    ["cp", os.path.join("../shnbin_scripts", f"{action}.py"), action_py]
                )
            elif os.path.exists(
                os.path.join("../shnbin_scripts", shnbin_package_name, f"{action}_without.py")
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

        LOG.info("Building tarball")
        shnbin_common.logged_call(["tar", "zcvf", f"../{package_name}.tgz", "."])

    LOG.info("Cleanup")
    if os.path.exists(env["PEX_ROOT"]):
        shnbin_common.logged_call(["rm", "-rf", env["PEX_ROOT"]])
    shnbin_common.logged_call(["rm", "-r", "build"])


if __name__ == "__main__":
    shnbin_common.force_line_buffer()
    main()
