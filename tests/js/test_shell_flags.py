# coding=utf-8
# pylint: disable=invalid-name
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Test the shell_flags.py file."""

from __future__ import absolute_import, unicode_literals

import logging
import os
import sys

import funfuzz

if sys.version_info.major == 2:
    from functools32 import lru_cache  # pylint: disable=import-error
else:
    from functools import lru_cache  # pylint: disable=no-name-in-module

funfuzz_log = logging.getLogger("funfuzz_test")
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("flake8").setLevel(logging.WARNING)


@lru_cache(maxsize=None)
def get_current_shell_path():
    """Retrieve the path to the currently built shell.

    Returns:
        str: Path to the compiled shell.
    """
    assert os.path.isdir(os.path.join(os.path.expanduser("~"), "trees", "mozilla-central"))
    # Remember to update the expected binary filename
    build_opts = ("--enable-debug --disable-optimize --enable-more-deterministic "
                  "--build-with-valgrind --enable-oom-breakpoint")
    # Change the repository location by uncommenting this line and specifying the right one
    # "-R ~/trees/mozilla-central/")
    build_opts_processed = funfuzz.js.build_options.parseShellOptions(build_opts)
    hg_hash_of_default = funfuzz.util.hg_helpers.getRepoHashAndId(build_opts_processed.repoDir)[0]

    return os.path.join(os.path.expanduser("~"), "shell-cache",
                        "js-dbg-optDisabled-64-dm-vg-oombp-linux-" + hg_hash_of_default,
                        "js-dbg-optDisabled-64-dm-vg-oombp-linux-" + hg_hash_of_default)


def mock_chance(i):
    """Overwrite the chance function to return True or False depending on a specific condition.

    Args:
        i (float): Intended probability between 0 < i < 1

    Returns:
        bool: True if i > 0, False otherwise.
    """
    return True if i > 0 else False


def test_add_random_arch_flags(monkeypatch):
    """Test that we are able to obtain add shell runtime flags related to architecture.

    Args:
        monkeypatch (class): monkeypatch fixture.
    """
    monkeypatch.setattr(funfuzz.js.shell_flags, "chance", mock_chance)

    all_flags = funfuzz.js.shell_flags.add_random_arch_flags(get_current_shell_path(), [])
    assert "--enable-avx" in all_flags
    assert "--no-sse3" in all_flags
    if funfuzz.js.inspect_shell.queryBuildConfiguration(get_current_shell_path(), "arm-simulator"):
        assert "--arm-sim-icache-checks" in all_flags


def test_add_random_ion_flags(monkeypatch):
    """Test that we are able to obtain add shell runtime flags related to IonMonkey.

    Args:
        monkeypatch (class): monkeypatch fixture.
    """
    monkeypatch.setattr(funfuzz.js.shell_flags, "chance", mock_chance)

    all_flags = funfuzz.js.shell_flags.add_random_ion_flags(get_current_shell_path(), [])
    assert "--cache-ir-stubs=on" in all_flags
    assert "--ion-aa=flow-sensitive" in all_flags
    assert "--ion-pgo=on" in all_flags
    assert "--ion-sincos=on" in all_flags
    assert "--ion-instruction-reordering=on" in all_flags
    assert "--ion-shared-stubs=on" in all_flags
    assert "--ion-regalloc=testbed" in all_flags
    assert "--non-writable-jitcode" in all_flags
    assert '--execute="setJitCompilerOption(\\"ion.forceinlineCaches\\",1)"' in all_flags
    assert "--ion-extra-checks" in all_flags
    # assert "--ion-sink=on" in all_flags
    assert "--ion-loop-unrolling=on" in all_flags
    assert "--ion-scalar-replacement=on" in all_flags
    assert "--ion-check-range-analysis" in all_flags
    # assert "--ion-regalloc=stupid" in all_flags
    assert "--ion-range-analysis=on" in all_flags
    assert "--ion-edgecase-analysis=on" in all_flags
    assert "--ion-limit-script-size=on" in all_flags
    assert "--ion-osr=on" in all_flags
    assert "--ion-inlining=on" in all_flags
    assert "--ion-eager" in all_flags
    assert "--ion-gvn=on" in all_flags
    assert "--ion-licm=on" in all_flags


def test_add_random_wasm_flags(monkeypatch):
    """Test that we are able to obtain add shell runtime flags related to WebAssembly (wasm).

    Args:
        monkeypatch (class): monkeypatch fixture.
    """
    monkeypatch.setattr(funfuzz.js.shell_flags, "chance", mock_chance)

    all_flags = funfuzz.js.shell_flags.add_random_wasm_flags(get_current_shell_path(), [])
    assert "--no-wasm-baseline" in all_flags
    assert "--no-wasm-ion" in all_flags
    assert "--test-wasm-await-tier2" in all_flags


def test_basic_flag_sets():
    """Test that we are able to obtain a basic set of shell runtime flags for fuzzing."""
    important_flag_set = ["--fuzzing-safe", "--no-threads", "--ion-eager"]  # Important flag set combination
    assert important_flag_set in funfuzz.js.shell_flags.basic_flag_sets(get_current_shell_path())


def test_chance(monkeypatch):
    """Test that the chance function works as intended.

    Args:
        monkeypatch (class): monkeypatch fixture.
    """
    monkeypatch.setattr(funfuzz.js.shell_flags, "chance", mock_chance)
    assert funfuzz.js.shell_flags.chance(0.6)
    assert funfuzz.js.shell_flags.chance(0.1)
    assert not funfuzz.js.shell_flags.chance(0)
    assert not funfuzz.js.shell_flags.chance(-0.2)


def test_random_flag_set(monkeypatch):
    """Test runtime flags related to SpiderMonkey.

    Args:
        monkeypatch (class): monkeypatch fixture.
    """
    monkeypatch.setattr(funfuzz.js.shell_flags, "chance", mock_chance)

    all_flags = funfuzz.js.shell_flags.random_flag_set(get_current_shell_path())
    assert "--fuzzing-safe" in all_flags
    assert "--nursery-strings=on" in all_flags
    assert "--no-array-proto-values" in all_flags
    assert "--spectre-mitigations=on" in all_flags
    assert "--ion-offthread-compile=on" in all_flags
    # assert "--enable-streams" in all_flags
    assert "--no-unboxed-objects" in all_flags
    assert "--no-cgc" in all_flags
    assert "--gc-zeal=4,999" in all_flags
    assert "--no-incremental-gc" in all_flags
    assert "--no-threads" in all_flags
    assert "--no-native-regexp" in all_flags
    assert "--no-ggc" in all_flags
    assert "--no-baseline" in all_flags
    assert "--no-asmjs" in all_flags
    assert "--dump-bytecode" in all_flags


def test_shell_supports_flag():
    """Test that the shell does support flags as intended."""
    assert funfuzz.js.shell_flags.shell_supports_flag(get_current_shell_path(), "--fuzzing-safe")
