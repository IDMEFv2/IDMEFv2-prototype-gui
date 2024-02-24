# Copyright (C) 2016-2021 CS GROUP - France. All Rights Reserved.
# Author: Yoann Vandoorselaere <yoannv@gmail.com>
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

import collections
import io
import glob
import os
import re

from prewikka import error, siteconfig


_sentinel = object()


class ConfigError(error.PrewikkaUserError):
    def __init__(self, message):
        error.PrewikkaUserError.__init__(self, N_("Configuration error"), message)


class ConfigParseError(ConfigError):
    def __init__(self, filename, lineno, line):
        ConfigError.__init__(self, N_("Parse error in \"%(txt)s\" at %(file)s line %(line)d",
                                      {'txt': line.rstrip(), 'file': filename, 'line': lineno}))


class ConfigValueError(ConfigError):
    def __init__(self, value, key):
        ConfigError.__init__(self, N_("Invalid value '%(value)s' for parameter '%(name)s'",
                                      {'value': value, 'name': key}))


class ConfigMissingError(ConfigError, AttributeError):
    def __init__(self, key):
        ConfigError.__init__(self, N_("Missing value for parameter '%(name)s'",
                                      {'name': key}))


class ConfigSection(collections.Mapping):
    def __init__(self, name):
        object.__setattr__(self, "_instance_name", name)
        object.__setattr__(self, "_od", collections.OrderedDict())

    def __repr__(self):
        return "ConfigSection<%s,%s>" % (self._instance_name, self._od.items())

    def __len__(self):
        return self._od.__len__()

    def __setitem__(self, key, value):
        return self._od.__setitem__(key, value)

    def __getitem__(self, key):
        return self._od.__getitem__(key)

    def __setattr__(self, key, value):
        self._od[key] = value

    def __getattr__(self, key):
        ret = self._od.get(key, None)
        if ret is None:
            raise ConfigMissingError(key)

        return ret

    def __contains__(self, key):
        return self._od.__contains__(key)

    def __iter__(self):
        return self._od.__iter__()

    def get_instance_name(self):
        return self._instance_name

    def get(self, name, default=None):
        return self._od.get(name, default)

    def get_int(self, name, default=0):
        assert isinstance(default, int)

        value = self.get(name)
        if value is None:
            return default

        try:
            return int(value)
        except (TypeError, ValueError):
            raise ConfigValueError(value, name)

    def get_float(self, name, default=0.):
        assert isinstance(default, float)

        value = self.get(name)
        if value is None:
            return default

        try:
            return float(value)
        except (TypeError, ValueError):
            raise ConfigValueError(value, name)

    def get_bool(self, name, default=False):
        assert isinstance(default, bool)

        value = self.get(name, _sentinel)
        if value is _sentinel:
            return default

        if value is None or value.lower() in ['true', 'yes']:
            return True
        elif value.lower() in ['false', 'no']:
            return False

        raise ConfigValueError(value, name)

    def get_size(self, name, default=0):
        assert isinstance(default, int)

        value = self.get(name)
        if value is None:
            return default

        match = re.match(r'(\d+(?:\.\d+)?)([kKMGT]?)B', value)
        if not match:
            raise ConfigValueError(value, name)

        prefixes = ["", "K", "M", "G", "T"]

        return int(float(match.group(1)) * 1024 ** prefixes.index(match.group(2).upper()))

    def keys(self):
        return self._od.keys()

    def items(self):
        return self._od.items()

    def values(self):
        return self._od.values()

    def setdefault(self, key, default):
        return self._od.setdefault(key, default)


class SectionRoot(list):
    def __contains__(self, key):
        return self and self[0].__contains__(key)

    def __getitem__(self, key):
        if isinstance(key, int):
            return list.__getitem__(self, key)
        else:
            return self[0][key]

    def __getattr__(self, attr):
        if not self:
            self.append(ConfigSection(""))

        return getattr(self[0], attr)

    def get_instance_by_name(self, name):
        for section in self:
            if section.get_instance_name() == name:
                return section

        return None


class MyConfigParser(object):
    """
    A config parser class ala ConfigParser.ConfigParser (only read operations
    are (will be) supported).
    ConfigParser.ConfigParser did not feed all our needs:
    - we need the '= value' part of option to be optional
    - we need to support special characters (like ':') in option name (for urls)
    - we need to keep the right order of options in sections (this is done via
      the OrderedDict class that subclass dict)
    """

    EMPTY_LINE_REGEXP = re.compile(r"^\s*(\#.*)?$")
    SECTION_REGEXP = re.compile(r"^\s*\[\s*(?P<name>[^\s]+)\s*(?P<instance>.+)?]\s*$")
    OPTION_REGEXP = re.compile(r"^\s*(?P<name>[^:=]+)([:=]\s*(?P<value>.+))?$")

    def __init__(self):
        self._sections = collections.OrderedDict()

    def _create_section(self, name, instance):
        if instance:
            instance = instance.strip()

        if name not in self._sections:
            self._sections[name] = SectionRoot()

        for section in self._sections[name]:
            if section.get_instance_name() == instance:
                return section

        self._sections[name].append(ConfigSection(instance))
        return self._sections[name][-1]

    def read_string(self, string):
        """Read and parse a string."""
        self._read(string.splitlines())

    def read(self, filename):
        """Read and parse a filename."""
        with io.open(filename, 'r', encoding="utf8") as f:
            self._read(f.readlines(), filename)

    def _read(self, iterable, filename=None):
        cursection = None

        for lineno, line in enumerate(iterable):
            result = self.EMPTY_LINE_REGEXP.match(line)
            if result:
                continue

            result = self.SECTION_REGEXP.match(line)
            if result:
                cursection = self._create_section(*result.group("name", "instance"))
                continue

            result = self.OPTION_REGEXP.match(line)
            if not result:
                raise ConfigParseError(filename, lineno + 1, line)

            if cursection is None:
                continue

            name, value = result.group("name").strip(), result.group("value")
            cursection[name] = value.strip() if value else None

    def get(self, name, default):
        return self._sections.get(name, default)

    def __getattr__(self, key):
        return self._sections.setdefault(key, SectionRoot())

    def __len__(self):
        return len(self._sections)


class Config(MyConfigParser):
    def __init__(self, filename=None):
        MyConfigParser.__init__(self)

        conf_filename = filename or siteconfig.conf_dir + "/prewikka.conf"
        self.read(conf_filename)

        self.basedir = os.path.dirname(conf_filename)
        for fpattern in self.include.keys():
            if not os.path.isabs(fpattern):
                fpattern = os.path.join(self.basedir, fpattern)

            # Files are loaded in alphabetical order
            for fname in sorted(glob.glob(fpattern)):
                self.read(fname)
