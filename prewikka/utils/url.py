# Copyright (C) 2004-2021 CS GROUP - France. All Rights Reserved.
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

import base64
import errno
import os.path
import random

from prewikka import siteconfig

from urllib.parse import quote, quote_plus, urlparse, urlsplit, urlunsplit, urlencode as _urlencode  # noqa: imported but unused


class mkdownload(object):
    DOWNLOAD_DIRECTORY = os.path.join(siteconfig.data_dir, "download")

    """
        Create a file to be downloaded

        :param str filename: Name of the file as downloaded by the user
        :param str mode: Mode for opening the file (default is 'wb+')
        :param bool user: User who can download the file (default to current user, False or a specific user can be provided).
        :param bool inline: Whether to display the downloaded file inline
    """
    def __init__(self, filename, mode="wb+", user=True, inline=False):
        self.name = filename
        self._id = random.randint(0, 9999999)
        self._dlname = base64.urlsafe_b64encode(filename.encode("utf8")).decode("utf8")
        filename = self.get_filename(self._id, self._dlname, user)

        try:
            os.makedirs(os.path.dirname(filename), mode=0o700)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise

        self.fd = open(filename, mode)

        self._user = user
        self._inline = inline

    @property
    def href(self):
        user = self._get_user(self._user)
        return "%sdownload%s/%d/%s%s" % (env.request.web.get_baseurl(), "/" + user if user else "", self._id, self._dlname, "/inline" if self._inline else "")

    @classmethod
    def get_filename(cls, id, filename, user=True):
        user = cls._get_user(user)
        if user:
            user = base64.urlsafe_b64encode(user.encode("utf8")).decode("utf8")

        return os.path.join(cls.DOWNLOAD_DIRECTORY, user or "", "%d-%s" % (id, filename))

    @staticmethod
    def _get_user(user):
        if user is True:
            return env.request.user.name

        # handle string and User object
        return getattr(user, "name", user or "")

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.fd.close()

    def __getattr__(self, attr):
        return getattr(self.fd, attr)

    def __json__(self):
        return {"type": "download", "href": self.href}


def iri2uri(iri, encoding="utf8"):
    # Character list compiled from RFC 3986, section 2.2
    safe = b":/?#[]@!$&'()*+,;="
    scheme, authority, path, query, frag = urlsplit(iri)

    tpl = authority.split(":", 1)
    if len(tpl) == 1:
        authority = authority.encode('idna')
    else:
        authority = tpl[0].encode('idna') + ":%s" % tpl[1]

    return urlunsplit((scheme, text_type(authority, encoding),
                       quote(path.encode(encoding), safe),
                       quote(query.encode(encoding), safe),
                       quote(frag.encode(encoding), safe)))


def urlencode(parameters, doseq=False):
    return _urlencode(parameters, doseq)
