# Copyright (C) 2018-2021 CS GROUP - France. All Rights Reserved.
#
# This file is part of the Prewikka program.
#
# SPDX-License-Identifier: BSD-2-Clause
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIEDi
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Configuration file for pytest.
"""

import sys

import pytest

from tests.fixtures import initialization_fixtures, prewikka_fixtures  # noqa


_PYTHON = sys.version_info
_PYTEST_SKIP_MESSAGE = 'Test skipped due to %s: %s (system) != %s (test requirement)'


def _check_py_markers(markers):
    """
    Check markers for python ("py" in name).

    :param list markers: list of all markers on a test.
    """
    py_markers = [marker for marker in markers if 'py' in marker]

    if not py_markers:
        return

    py_major_marker = 'py%d_only' % _PYTHON.major
    py_major_minor_marker = 'py%d%d_only' % (_PYTHON.major, _PYTHON.minor)
    if py_major_marker not in py_markers and py_major_minor_marker not in py_markers:
        # formatting skip message
        python_test_version = py_markers[0].split('_')[0][2:]
        if len(python_test_version) == 1:  # 2 or 3 (not 2.7, 3.0, 3.1...)
            python_sys_version = '%d' % _PYTHON.major
        else:
            python_sys_version = '%d.%d' % (_PYTHON.major, _PYTHON.minor)
        pytest_message = _PYTEST_SKIP_MESSAGE % ('python version', python_sys_version, python_test_version)
        pytest.skip(pytest_message)


def _check_sql_markers(markers):
    """
    Check markers for SQL engines ("sql" in name).

    :param list markers: list of all markers on a test.
    """
    db_type = env.config.database.type
    sql_markers = [marker for marker in markers if 'sql' in marker]

    if not sql_markers:
        return

    sql_marker = '%s_only' % db_type
    if sql_marker not in sql_markers:
        pytest.skip(_PYTEST_SKIP_MESSAGE % ('sql engine', db_type, sql_markers[0].split('_')[0]))


def pytest_runtest_setup(item):
    """
    Pytest hook run before each test to skip specified tests.

    - Python version is checked and all tests with "@pytest.mark.py<x>_only" and "@pytest.mark.py<x><y>_only" they
    do not match with current Python version are skipped.
    - SQL engine is checked based on prewikka configuration file using during tests.

    Supported markers:
        - py<x>_only            where <x> is major version of Python (ex: py2_only)
        - py<x><y>_only         where <x> is major version of Python and <y> minor version (ex: py36_only)
        - mysql_only            MySQL/MariaDB only
        - pgsql_only            PostgreSQL only
        - sqlite_only           SQLte3 only

    Multiple markers are supported for Python markers. They are NOT exclusive. Example:

        @pytest.mark.mysql_only
        @pytest.mark.py26_only
        @pytest.mark.py27_only
        def test_foo():
            pass

    This test will run only with python 2.6 or 2.7 and with MySQL engine.
    """
    if isinstance(item, item.Function):
        # get all markers with "_only" in name
        markers = [marker for marker in item.keywords.keys() if '_only' in marker]
        if markers:
            _check_py_markers(markers)
            _check_sql_markers(markers)
