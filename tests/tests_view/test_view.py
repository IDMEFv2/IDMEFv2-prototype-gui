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
Tests for `prewikka.view`.
"""

import pytest
from werkzeug.routing import Map

from prewikka.view import InvalidParameterError, InvalidParameterValueError, MissingParameterError, \
    InvalidMethodError, InvalidViewError, ListConverter, ParameterDesc, Parameters, View


def test_invalid_parameter_error():
    """
    Test `prewikka.view.InvalidParameterError` error.
    """
    error = InvalidParameterError('test')

    with pytest.raises(InvalidParameterError):
        raise error


def test_invalid_parameter_val_err():
    """
    Test `prewikka.view.InvalidParameterValueError` error.
    """
    error = InvalidParameterValueError('test', 'value')

    with pytest.raises(InvalidParameterValueError):
        raise error


def test_missing_parameter_error():
    """
    Test `prewikka.view.MissingParameterError` error.
    """
    error = MissingParameterError('test')

    with pytest.raises(MissingParameterError):
        raise error


def test_invalid_method_error():
    """
    Test `prewikka.view.InvalidMethodError` error.
    """
    error = InvalidMethodError('test')

    with pytest.raises(InvalidMethodError):
        raise error


def test_invalid_view_error():
    """
    Test `prewikka.view.InvalidViewError` error.
    """
    error = InvalidViewError('test')

    with pytest.raises(InvalidViewError):
        raise error


def test_list_converter():
    """
    Test `prewikka.view.ListConverter` class.
    """
    list_converter = ListConverter(Map())

    assert list_converter.to_python('a,b,c') == ['a', 'b', 'c']
    assert list_converter.to_python('abc') == ['abc']
    assert list_converter.to_url('a,b,c') == 'a,%2C,b,%2C,c'
    assert list_converter.to_url('abc') == 'a,b,c'


def test_parameter_desc():
    """
    Test `prewikka.view.ParameterDesc` class.
    """
    parameter_desc_1 = ParameterDesc('param1', str)
    parameter_desc_2 = ParameterDesc('param2', list)
    parameter_desc_3 = ParameterDesc('param3', str, mandatory=True)
    parameter_desc_4 = ParameterDesc('param4', str, default='4')
    parameter_desc_5 = ParameterDesc('param5', str, save=True)
    parameter_desc_6 = ParameterDesc('param6', str, general=True)
    parameter_desc_7 = ParameterDesc(None, None)

    # has_default()
    assert not parameter_desc_1.has_default()
    assert parameter_desc_4.has_default()

    # parse()
    assert parameter_desc_1.parse('param1') == 'param1'
    assert parameter_desc_2.parse('param2') == ['param2']
    assert parameter_desc_1.parse(['param1']) == '[\'param1\']'
    assert parameter_desc_2.parse(['param2']) == ['param2']
    assert parameter_desc_3.parse('param3') == 'param3'
    assert parameter_desc_4.parse('param4') == 'param4'
    assert parameter_desc_5.parse('param5') == 'param5'
    assert parameter_desc_6.parse('param6') == 'param6'

    with pytest.raises(InvalidParameterValueError):
        parameter_desc_7.parse('param999')


def test_parameters():
    """
    Test `prewikka.view.Parameters` class.
    """
    v = View()
    v.view_endpoint = "myview.render"
    params = {'foo': 'bar'}
    parameters = Parameters(v, **params)
    parameters2 = Parameters(v, **params)
    parameters3 = Parameters(v)

    # optional()
    parameters.optional('optional', str)
    parameters.optional('default', str, default='default')
    parameters.optional('foo', str, 'bar', save=True)

    # normalize()
    parameters.normalize()
    parameters2.normalize()
    parameters3.normalize()

    parameters2.allow_extra_parameters = False

    with pytest.raises(InvalidParameterError):
        parameters2.normalize()

    parameters2.allow_extra_parameters = True


def test_parameters_mandatory():
    """
    Test `prewikka.view.Parameters` class.

    Mandatory parameters.
    """
    v = View()
    v.view_endpoint = "myview.render"
    params = {'foo': 'bar'}

    # no mandatory parameters
    parameters = Parameters(v, **params)
    parameters.normalize()

    # "foo" as mandatory parameter (str)
    parameters = Parameters(v, **params)
    parameters.mandatory('foo', str)
    parameters.normalize()

    # "foo" as mandatory parameter (int)
    with pytest.raises(InvalidParameterValueError):
        parameters = Parameters(v, **params)
        parameters.mandatory('foo', int)
        parameters.normalize()

    # "bar" as mandatory parameter
    with pytest.raises(MissingParameterError):
        parameters = Parameters(v, **params)
        parameters.mandatory('bar', str)
        parameters.normalize()
