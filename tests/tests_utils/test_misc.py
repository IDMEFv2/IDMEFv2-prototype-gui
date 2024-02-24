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
Tests for `prewikka.utils.misc`.
"""

import io
import pytest

from prewikka.dataprovider import Criterion
from prewikka.utils import misc, json
from tests.tests_views.utils import create_heartbeat, delete_heartbeat


@misc.deprecated
def fake_deprecated_function():
    """
    Fake function used in tests.
    :return: 42
    """
    return 42


def test_attr_obj():
    """
    Test `prewikka.utils.misc.AttrObj()`.
    """
    attr1 = misc.AttrObj()
    attr2 = misc.AttrObj(foo=12, bar=list())

    assert attr1
    assert attr2

    assert json.dumps(attr1) == '{}'
    assert json.dumps(attr2) == '{"foo": 12, "bar": []}'

    assert not attr1 == attr2


def test_get_analyzer_status():
    """
    Test `prewikka.utils.misc.get_analyzer_status_from_latest_heartbeat()`.
    """
    heartbeat_id = 'NqnYbirynpr'
    idmef_db = env.dataprovider._backends["alert"]._db
    criteria = Criterion('heartbeat.messageid', '=', heartbeat_id)

    heartbeats = [
        (create_heartbeat(heartbeat_id, status='exiting'), 'offline'),
        (create_heartbeat(heartbeat_id, heartbeat_interval=None), 'unknown'),
        (create_heartbeat(heartbeat_id, heartbeat_date='1991-08-25 20:57:08'), 'missing'),
        (create_heartbeat(heartbeat_id), 'online')
    ]

    for idmef, expected_status in heartbeats:
        idmef_db.insert(idmef)
        heartbeat = env.dataprovider.get(criteria)[0]['heartbeat']
        status = misc.get_analyzer_status_from_latest_heartbeat(heartbeat, 0)

        assert status[0] == expected_status

        delete_heartbeat(heartbeat_id)


def test_protocol_number_to_name():
    """
    Test `prewikka.utils.misc.protocol_number_to_name()`.
    """
    assert misc.protocol_number_to_name(42) == 'sdrp'
    assert misc.protocol_number_to_name(80) == 'iso-ip'
    assert misc.protocol_number_to_name(139) == 'hip'
    assert not misc.protocol_number_to_name(300)


def test_find_unescaped_characters():
    """
    Test `prewikka.utils.misc.find_unescaped_characters()`.
    """
    assert misc.find_unescaped_characters('foo', 'o')
    assert not misc.find_unescaped_characters('foo', 'a')
    assert not misc.find_unescaped_characters('foo\\bar', 'b')
    assert misc.find_unescaped_characters('foo\\\\bar', 'b')


def test_split_unescaped_characters():
    """
    Test `prewikka.utils.misc.split_unescaped_characters()`.
    """
    res = misc.split_unescaped_characters('foo', '')
    assert list(res) == ['foo']

    res = misc.split_unescaped_characters('foo bar', ' ')
    assert list(res) == ['foo', 'bar']

    res = misc.split_unescaped_characters('foobar', 'oa')
    assert list(res) == ['f', '', 'b', 'r']

    res = misc.split_unescaped_characters('foo\\;bar', ';')
    assert list(res) == ['foo\\;bar']

    res = misc.split_unescaped_characters('foo\\\\;bar', ';')
    assert list(res) == ['foo\\\\', 'bar']


def test_soundex():
    """
    Test `prewikka.utils.misc.soundex()`.
    """
    assert misc.soundex('Prewikka') == 'P62'
    assert misc.soundex('Prelude') == 'P643'
    assert misc.soundex('foobar') == 'F16'


def test_hexdump():
    """
    Test `prewikka.utils.misc.hexdump()`.
    """
    assert misc.hexdump(b'Prewikka') == '0000:    50 72 65 77 69 6b 6b 61                            Prewikka\n'
    assert misc.hexdump(b'Prelude') == '0000:    50 72 65 6c 75 64 65                               Prelude\n'
    assert misc.hexdump(b'foobar') == '0000:    66 6f 6f 62 61 72                                  foobar\n'


def test_deprecated():
    """
    Test `prewikka.utils.misc.deprecated()`.
    """
    # just call the function
    assert fake_deprecated_function() == 42


def test_path_sort_key():
    """
    Test `prewikka.utils.misc.path_sort_key()`.
    """
    paths = ["foo.bar", "foo.baz", "foo.bar(10).baz", "foo.bar(2).baz"]
    assert sorted(paths, key=misc.path_sort_key) == ["foo.bar", "foo.bar(2).baz", "foo.bar(10).baz", "foo.baz"]


def test_get_file_size():
    """
    Test `prewikka.utils.misc.get_file_size()`.
    """
    fileobj = io.StringIO()
    fileobj.write("foobar")
    assert misc.get_file_size(fileobj) == 6


def test_caching_iterator():
    """
    Test `prewikka.utils.misc.CachingIterator()`.
    """
    iterator1 = misc.CachingIterator(['foo', 'bar', 42])
    iterator2 = misc.CachingIterator(['foo', 'bar', 42], 3)

    # len()
    assert len(iterator1) == 3
    assert len(iterator2) == 3

    # preprocess_value()
    assert iterator1.preprocess_value(12) == 12
    assert not iterator2.preprocess_value(None)

    # __iter__
    assert list(iterator1)
    assert list(iterator1)  # second time use cache

    # __getitems__
    assert iterator1[0] == 'foo'
    assert iterator1[0:1] == ['foo']
    assert iterator1[0:2] == ['foo', 'bar']
    assert iterator1[1] == 'bar'
    assert iterator1[2] == 42

    with pytest.raises(IndexError):
        assert iterator1[3]

    assert iterator2[0] == 'foo'
    assert iterator2[1] == 'bar'
    assert iterator2[0:1] == ['foo']
    assert iterator2[0:2] == ['foo', 'bar']
    assert iterator2[2] == 42

    with pytest.raises(IndexError):
        assert iterator2[3]
