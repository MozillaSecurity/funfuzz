# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Allows inspection of the SpiderMonkey shell to ensure that it is compiled as intended with specified configurations.
"""

from __future__ import absolute_import, print_function  # isort:skip

import os
import platform

from lithium.interestingness.utils import env_with_path
from shellescape import quote

from ..util import subprocesses as sps

RUN_NSPR_LIB = ""
RUN_PLDS_LIB = ""
RUN_PLC_LIB = ""

if platform.system() == "Windows":
    # Update if the following changes:
    # https://dxr.mozilla.org/mozilla-central/search?q=%3C%2FOutputFile%3E+.dll+path%3Aintl%2Ficu%2Fsource%2F&case=true
    RUN_ICUUC_LIB_EXCL_EXT = "icuuc"
    # Debug builds seem to have their debug "d" notation *before* the ICU version.
    # Check https://dxr.mozilla.org/mozilla-central/search?q=%40BINPATH%40%2Ficudt&case=true&redirect=true
    RUN_ICUUCD_LIB_EXCL_EXT = "icuucd"
    RUN_ICUIN_LIB_EXCL_EXT = "icuin"
    RUN_ICUIND_LIB_EXCL_EXT = "icuind"
    RUN_ICUIO_LIB_EXCL_EXT = "icuio"
    RUN_ICUIOD_LIB_EXCL_EXT = "icuiod"
    RUN_ICUDT_LIB_EXCL_EXT = "icudt"
    RUN_ICUDTD_LIB_EXCL_EXT = "icudtd"
    RUN_ICUTEST_LIB_EXCL_EXT = "icutest"
    RUN_ICUTESTD_LIB_EXCL_EXT = "icutestd"
    RUN_ICUTU_LIB_EXCL_EXT = "icutu"
    RUN_ICUTUD_LIB_EXCL_EXT = "icutud"

    RUN_MOZGLUE_LIB = "mozglue.dll"
    RUN_NSPR_LIB = "nspr4.dll"
    RUN_PLDS_LIB = "plds4.dll"
    RUN_PLC_LIB = "plc4.dll"
    RUN_TESTPLUG_LIB = "testplug.dll"
elif platform.system() == "Darwin":
    RUN_MOZGLUE_LIB = "libmozglue.dylib"
elif platform.system() == "Linux":
    RUN_MOZGLUE_LIB = "libmozglue.so"

# These include running the js shell (mozglue) and should be in dist/bin.
# At least Windows required the ICU libraries.
ALL_RUN_LIBS = [RUN_MOZGLUE_LIB, RUN_NSPR_LIB, RUN_PLDS_LIB, RUN_PLC_LIB]
if platform.system() == "Windows":
    ALL_RUN_LIBS.append(RUN_TESTPLUG_LIB)
    WIN_ICU_VERS = []
    # Needs to be updated when the earliest known working revision changes. Currently:
    # m-c 369571 Fx56, 1st w/ successful MSVC 2017 builds, see bug 1356493
    WIN_ICU_VERS.append(59)  # prior version
    WIN_ICU_VERS.append(60)  # m-c 391988 Fx59, 1st w/ ICU 60.1, see bug 1405993
    for icu_ver in WIN_ICU_VERS:
        ALL_RUN_LIBS.append(RUN_ICUUC_LIB_EXCL_EXT + str(icu_ver) + ".dll")
        ALL_RUN_LIBS.append(RUN_ICUUCD_LIB_EXCL_EXT + str(icu_ver) + ".dll")
        ALL_RUN_LIBS.append(RUN_ICUIN_LIB_EXCL_EXT + str(icu_ver) + ".dll")
        ALL_RUN_LIBS.append(RUN_ICUIND_LIB_EXCL_EXT + str(icu_ver) + ".dll")
        ALL_RUN_LIBS.append(RUN_ICUIO_LIB_EXCL_EXT + str(icu_ver) + ".dll")
        ALL_RUN_LIBS.append(RUN_ICUIOD_LIB_EXCL_EXT + str(icu_ver) + ".dll")
        ALL_RUN_LIBS.append(RUN_ICUDT_LIB_EXCL_EXT + str(icu_ver) + ".dll")
        ALL_RUN_LIBS.append(RUN_ICUDTD_LIB_EXCL_EXT + str(icu_ver) + ".dll")
        ALL_RUN_LIBS.append(RUN_ICUTEST_LIB_EXCL_EXT + str(icu_ver) + ".dll")
        ALL_RUN_LIBS.append(RUN_ICUTESTD_LIB_EXCL_EXT + str(icu_ver) + ".dll")
        ALL_RUN_LIBS.append(RUN_ICUTU_LIB_EXCL_EXT + str(icu_ver) + ".dll")
        ALL_RUN_LIBS.append(RUN_ICUTUD_LIB_EXCL_EXT + str(icu_ver) + ".dll")


def archOfBinary(binary):  # pylint: disable=inconsistent-return-statements,invalid-name,missing-param-doc
    # pylint: disable=missing-raises-doc,missing-return-doc,missing-return-type-doc,missing-type-doc
    """Test if a binary is 32-bit or 64-bit."""
    # We can possibly use the python-magic-bin PyPI library in the future
    unsplit_file_type = sps.captureStdout(["file", binary])[0]
    filetype = unsplit_file_type.decode("utf-8", errors="replace").split(":", 1)[1]
    if platform.system() == "Windows":
        assert "MS Windows" in filetype
        return "32" if "Intel 80386 32-bit" in filetype else "64"
    else:
        if "32-bit" in filetype or "i386" in filetype:
            assert "64-bit" not in filetype
            return "32"
        if "64-bit" in filetype:
            assert "32-bit" not in filetype
            return "64"


def constructVgCmdList(errorCode=77):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Construct default parameters needed to run valgrind with."""
    valgrind_cmds = []
    valgrind_cmds.append("valgrind")
    if platform.system() == "Darwin":
        valgrind_cmds.append("--dsymutil=yes")
    valgrind_cmds.append("--error-exitcode=" + str(errorCode))
    # See bug 913876 comment 18:
    valgrind_cmds.append("--vex-iropt-register-updates=allregs-at-mem-access")
    valgrind_cmds.append("--gen-suppressions=all")
    valgrind_cmds.append("--leak-check=full")
    valgrind_cmds.append("--errors-for-leak-kinds=definite")
    valgrind_cmds.append("--show-leak-kinds=definite")
    valgrind_cmds.append("--show-possibly-lost=no")
    valgrind_cmds.append("--num-callers=50")
    return valgrind_cmds


def shellSupports(shellPath, args):  # pylint: disable=invalid-name,missing-param-doc,missing-raises-doc
    # pylint: disable=missing-return-doc,missing-return-type-doc,missing-type-doc
    """Return True if the shell likes the args.

    You can add support for a function, e.g. ["-e", "foo()"], or a flag, e.g. ["-j", "-e", "42"].
    """
    return_code = testBinary(shellPath, args, False)[1]
    if return_code == 0:
        return True
    elif 1 <= return_code <= 3:
        # Exit codes 1 through 3 are all plausible "non-support":
        #   * "Usage error" is 1 in new js shell, 2 in old js shell, 2 in xpcshell.
        #   * "Script threw an error" is 3 in most shells, but 1 in some versions (see bug 751425).
        # Since we want autobisectjs to support all shell versions, allow all these exit codes.
        return False
    else:
        raise Exception("Unexpected exit code in shellSupports " + str(return_code))


def testBinary(shellPath, args, useValgrind):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Test the given shell with the given args."""
    test_cmd = (constructVgCmdList() if useValgrind else []) + [shellPath] + args
    sps.vdump("The testing command is: " + " ".join(quote(x) for x in test_cmd))
    out, return_code = sps.captureStdout(test_cmd, combineStderr=True, ignoreStderr=True,
                                         ignoreExitCode=True, env=env_with_path(
                                             os.path.dirname(os.path.abspath(shellPath))))
    sps.vdump("The exit code is: " + str(return_code))
    return out, return_code


def testJsShellOrXpcshell(s):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Test if a binary is a js shell or xpcshell."""
    return "xpcshell" if shellSupports(s, ["-e", "Components"]) else "jsShell"


def queryBuildConfiguration(s, parameter):  # pylint: disable=invalid-name,missing-param-doc,missing-return-doc
    # pylint: disable=missing-return-type-doc,missing-type-doc
    """Test if a binary is compiled with specified parameters, in getBuildConfiguration()."""
    ans = testBinary(s, ["-e", 'print(getBuildConfiguration()["' + parameter + '"])'],
                     False)[0]
    return ans.decode("utf-8", errors="replace").find("true") != -1


def verifyBinary(sh):  # pylint: disable=invalid-name,missing-param-doc,missing-type-doc
    """Verify that the binary is compiled as intended."""
    binary = sh.getShellCacheFullPath()

    assert archOfBinary(binary) == ("32" if sh.build_opts.enable32 else "64")

    # Testing for debug or opt builds are different because there can be hybrid debug-opt builds.
    assert queryBuildConfiguration(binary, "debug") == sh.build_opts.enableDbg

    assert queryBuildConfiguration(binary, "more-deterministic") == sh.build_opts.enableMoreDeterministic
    assert queryBuildConfiguration(binary, "asan") == sh.build_opts.buildWithAsan
    assert (queryBuildConfiguration(binary, "arm-simulator") and
            sh.build_opts.enable32) == sh.build_opts.enableSimulatorArm32
    assert (queryBuildConfiguration(binary, "arm-simulator") and not
            sh.build_opts.enable32) == sh.build_opts.enableSimulatorArm64
    # Note that we should test whether a shell has profiling turned on or not.
    # m-c rev 324836:800a887c705e turned profiling on by default, so once this is beyond the
    # earliest known working revision, we can probably test it here.
