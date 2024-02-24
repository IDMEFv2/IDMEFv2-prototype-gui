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
Tests for `prewikka.config`.
"""

import os

import pytest

from prewikka import config
from tests.utils.vars import TEST_DATA_DIR

_TEST_CONFIG_FILE = os.path.join(TEST_DATA_DIR, 'prewikka_tests.conf')


@pytest.fixture(scope='function')
def config_fixtures(request):
    """
    Load custom configuration file, for tests only.
    """
    env.config_bak = env.config
    env.config = config.Config(_TEST_CONFIG_FILE)

    def tear_down():
        """
        Tear Down.
        """
        env.config = env.config_bak
        env.config_bak = None

    request.addfinalizer(tear_down)


def test_config_parser():
    """
    Test `prewikka.config.Config` class parsing.
    """
    conf = config.Config(_TEST_CONFIG_FILE)

    # basic tests
    assert 'heartbeat_count' in conf.general
    assert 'heartbeat_count' in str(conf.general)
    assert 'heartbeat_count' in conf.general.__repr__()
    assert int(conf.general.get('heartbeat_count')) == 42
    assert len(conf.general.values()) == 16
    assert conf.get('general', None) == conf.general
    assert not conf.read_string('a\nb\nc')
    assert len(conf)

    # unknown file
    with pytest.raises(IOError):
        config.Config('foobar.txt')


def test_config_parser_invalid():
    """
    Test `prewikka.config.Config` class.

    With invalid configuration file.
    """
    path = os.path.join(TEST_DATA_DIR, 'prewikka_invalid.conf')
    with pytest.raises(config.ConfigParseError):
        config.Config(path)


def test_config_parser_regexp():
    """
    Test `prewikka.config.Config.REGEXP_*` regexp.
    """
    # EMPTY_LINE_REGEXP
    assert config.Config.EMPTY_LINE_REGEXP.match('')
    assert not config.Config.EMPTY_LINE_REGEXP.match('[section]')
    assert not config.Config.EMPTY_LINE_REGEXP.match('foo')

    # SECTION_REGEXP
    assert not config.Config.SECTION_REGEXP.match('')
    assert config.Config.SECTION_REGEXP.match('[section]')
    assert config.Config.SECTION_REGEXP.match('[section x]')
    assert not config.Config.SECTION_REGEXP.match('foo')

    # OPTION_REGEXP
    assert config.Config.OPTION_REGEXP.match('foo')
    assert config.Config.OPTION_REGEXP.match('foo: bar')
    assert config.Config.OPTION_REGEXP.match('foo : bar')
    assert config.Config.OPTION_REGEXP.match('foo:bar')
    assert config.Config.OPTION_REGEXP.match('foo=bar')
    assert config.Config.OPTION_REGEXP.match('foo= bar')
    assert config.Config.OPTION_REGEXP.match('foo = bar')


def test_config_parser_section():
    """
    Test `prewikka.config.ConfigSection` class.
    """
    section = config.ConfigSection('test_section')

    # add element
    section['foo'] = 'bar'
    assert section.foo == 'bar'

    # add element with setattr()
    setattr(section, 'bar', 'foo')
    assert section.bar == 'foo'

    # len
    assert len(section) == 2

    # get element
    assert section['foo'] == 'bar'
    with pytest.raises(KeyError):
        assert section['error']

    # get element with getattr()
    assert getattr(section, 'bar', 'foo')
    with pytest.raises(AttributeError):
        assert getattr(section, 'error')

    # loop
    for elt in section:
        assert elt

    # values
    assert list(section.values()) == ['bar', 'foo']


def test_config_values(config_fixtures):
    """
    Test configuration file.
    """
    # [general]
    assert int(env.config.general.get('heartbeat_count')) == 42
    assert int(env.config.general.get('heartbeat_error_margin')) == 4
    assert env.config.general.get('external_link_new_window') == 'yes'
    assert env.config.general.get('enable_details') == 'no'
    assert env.config.general.get('enable_error_traceback') == 'yes'
    assert env.config.general.get('host_details_url') == 'http://www.prelude-siem.com/host_details.php'
    assert env.config.general.get('port_details_url') == 'http://www.prelude-siem.com/port_details.php'
    assert env.config.general.get('reference_details_url') == 'http://www.prelude-siem.com/reference_details.php'
    assert int(env.config.general.get('max_aggregated_source')) == 12
    assert int(env.config.general.get('max_aggregated_target')) == 12
    assert int(env.config.general.get('max_aggregated_classification')) == 12
    assert int(env.config.general.get('dns_max_delay')) == 0
    assert env.config.general.get('default_locale') == 'en_GB'
    assert env.config.general.get('default_theme') == 'cs'
    assert env.config.general.get('encoding') == 'UTF-8'
    assert env.config.general.get('reverse_path') == 'http://example.com/proxied/prewikka/'

    # [interface]
    assert env.config.interface.get('software') == 'Prelude Test'
    assert env.config.interface.get('browser_title') == 'Prelude Test'

    # [url host]
    assert env.config.url.get('label') == 'http://url?host=$host'

    # [idmef_database]
    assert env.config.idmef_database.get('type') == 'pgsql'
    assert env.config.idmef_database.get('host') == 'localhost'
    assert env.config.idmef_database.get('user') == 'prelude'
    assert env.config.idmef_database.get('pass') == 'prelude'
    assert env.config.idmef_database.get('name') == 'prelude_test'

    # [database]
    assert env.config.database.get('type') == 'pgsql'
    assert env.config.database.get('host') == 'localhost'
    assert env.config.database.get('user') == 'prelude'
    assert env.config.database.get('pass') == 'prelude'
    assert env.config.database.get('name') == 'prewikka_test'

    # [log stderr]
    assert env.config.log.get('level') == 'info'


def test_config_subfile(config_fixtures):
    """
    Test to load a sub config file.
    """
    # ensure that new value is not default value
    heartbeat_value = int(env.config.general.get('heartbeat_count')) + 10

    # create 'conf.d/' and write temp file
    file_directory = os.path.join(os.path.dirname(_TEST_CONFIG_FILE), 'conf.d')
    file_name = os.path.join(file_directory, 'tests_sub.conf')
    file_content = '[general]\nheartbeat_count: %d' % heartbeat_value
    if not os.path.exists(file_directory):
        os.makedirs(file_directory)

    with open(file_name, 'w+') as conf_file:
        conf_file.write(file_content)

    conf = config.Config(_TEST_CONFIG_FILE)

    assert int(conf.general.get('heartbeat_count')) == heartbeat_value

    # clean
    os.remove(file_name)
    os.rmdir(file_directory)


def test_config_parse_error():
    """
    Test `prewikka.config.ConfigParseError` error.
    """
    with pytest.raises(config.ConfigParseError) as e_info:
        raise config.ConfigParseError('file_name.txt', 418, 'I\'m a teapot')

    assert 'file_name.txt' in str(e_info)
    assert '418' in str(e_info)
    assert 'I\'m a teapot' in str(e_info)

    # error no must be int
    with pytest.raises(TypeError):
        raise config.ConfigParseError('file_name.txt', '418', 'I\'m a teapot')
