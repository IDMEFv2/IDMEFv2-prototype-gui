# Copyright (C) 2014-2021 CS GROUP - France. All Rights Reserved.
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

import uuid

from prewikka import error, localization, pluginmanager, resource
from prewikka.utils import cache

RED_STD = "E78D90"
ORANGE_STD = "F5B365"
YELLOW_STD = "D4C608"
GREEN_STD = "B1E55D"
BLUE_STD = "93B9DD"
GRAY_STD = "5C5C5C"

COLORS = (BLUE_STD, GREEN_STD, YELLOW_STD, ORANGE_STD, RED_STD,
          "C6A0CF", "5256D3", "A7DE65", "F2A97B", "F6818A", "B087C6", "66DC92")


class RendererException(Exception):
    pass


class RendererNoDataException(RendererException):
    def __str__(self):
        return _("No data to display.")


class RendererItem(object):
    __slots__ = ["values", "series", "links", "_tuple"]

    def __init__(self, values=0, series=None, links=None):
        self._tuple = values, series, links

        self.values = values
        self.series = series
        self.links = links

    def __getitem__(self, i):
        return self._tuple[i]


class RendererUtils(object):
    _nexist_color = (_("n/a"), GRAY_STD)

    def __init__(self, options):
        self._color_map_idx = 0
        self._color_map = options.get("names_and_colors")

    def get_label(self, series):
        if self._color_map and len(series) == 1:
            return _(self._color_map.get(series[0], self._nexist_color)[0])

        return ", ".join(localization.format_value(s) for s in series)

    @cache.request_memoize("renderer_color")
    def get_color(self, series, onecolor=False):
        if self._color_map and len(series) == 1:
            color = self._color_map.get(series[0], self._nexist_color)[1]
            if color:
                return color

        color = COLORS[self._color_map_idx % len(COLORS)]

        if not onecolor:
            self._color_map_idx += 1

        return color


class RendererBackend(pluginmanager.PluginBase):
    pass


class RendererPluginManager(pluginmanager.PluginManager):
    _default_backends = {}

    def __init__(self, autoupdate=False):
        self._backends = pluginmanager.PluginManager("prewikka.renderer.backend", autoupdate=autoupdate)
        pluginmanager.PluginManager.__init__(self, "prewikka.renderer.type", autoupdate=autoupdate)

        for typ, backend in env.config.renderer_defaults.items():
            self._default_backends[typ] = backend

        self._renderer = {}

    def _init_callback(self, plugin):
        self._renderer.setdefault(plugin.renderer_backend, {})[plugin.renderer_type] = plugin

        if plugin.renderer_type not in self._default_backends:
            self._default_backends[plugin.renderer_type] = plugin.renderer_backend

    def get_types(self):
        return self._default_backends.keys()

    def has_backend(self, wanted_backend, wanted_type=None):
        if wanted_backend not in self._renderer:
            return False

        if wanted_type is None:
            return True

        return set(wanted_type).issubset(self._renderer[wanted_backend])

    def get_backends(self, wanted_type):
        for backend, typedict in self._renderer.items():
            if wanted_type in typedict:
                yield backend

    def get_backends_instances(self, wanted_type):
        for backend in self.get_backends(wanted_type):
            yield self._renderer[backend][wanted_type]

    def get_default_backend(self, wanted_type):
        return self._default_backends.get(wanted_type)

    def _setup_renderer(self, type, renderer):
        renderer = renderer or self.get_default_backend(type)

        if renderer is None:
            raise error.PrewikkaUserError(N_("Renderer error"),
                                          N_("No backend supporting render type '%s'", type))

        if renderer not in self._renderer:
            raise error.PrewikkaUserError(N_("Renderer error"),
                                          N_("No backend named '%s'", renderer))

        if type not in self._renderer[renderer]:
            raise error.PrewikkaUserError(N_("Renderer error"),
                                          N_("Backend '%(backend)s' does not support render type '%(type)s'",
                                             {'backend': renderer, 'type': type}))

        return renderer

    def update(self, type, data, renderer=None, **kwargs):
        renderer = self._setup_renderer(type, renderer)
        return self._renderer[renderer][type].update(data, **kwargs)

    def render(self, type, data, renderer=None, **kwargs):
        renderer = self._setup_renderer(type, renderer)

        classname = kwargs["class"] = "-".join((renderer, type))
        cssid = kwargs["cssid"] = "-".join((classname, text_type(uuid.uuid4())))

        try:
            data = self._renderer[renderer][type].render(data, **kwargs)
            htmls = resource.HTMLSource('<div id="%s" class="renderer-elem %s">%s</div>'
                                        % (cssid, classname, data.get("html", "")))

            return {"html": htmls, "script": resource.HTMLSource(data.get("script", ""))}
        except RendererException as e:
            htmls = resource.HTMLSource('<div id="%s" class="renderer-elem renderer-elem-error %s"><div class="text-center-vh">%s</div></div>'
                                        % (cssid, classname, text_type(e)))

            return {"html": htmls, "script": None}
