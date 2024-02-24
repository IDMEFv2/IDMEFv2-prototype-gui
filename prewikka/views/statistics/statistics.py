# Copyright (C) 2015-2021 CS GROUP - France. All Rights Reserved.
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

from prewikka import error, hookmanager, localization, mainmenu, resource, statistics, template, view
from prewikka.statistics import Query
from prewikka.utils import json


class Widget(dict):
    def __init__(self, param, id_=None, raw=True, set_id=True):
        dict.__init__(self, json.loads(param))
        self._ignored = ["id", "realheight", "realwidth"]

        if set_id and id_ is not None:
            self["id"] = id_

        if not all(hookmanager.trigger("HOOK_WIDGET_INIT", self)):
            return

        if "query" not in self:
            self["query"] = self._normalize_query()

        if not raw:
            limit = self["query"][0].get("limit", env.request.parameters["limit"])
            self["title"] = _(self["title"]).replace("{limit}", text_type(limit) if limit > 0 else "")  # we don't use .format() to avoid potential errors
            if "description" in self:
                self["description"] = _(self["description"])

    def _normalize_query(self):
        # Compatibility with the old API
        query = {}
        for k in Query.KEYS:
            if k not in self:
                continue

            if k == "path" and not isinstance(self[k], list):
                query[k] = [self[k]]
            else:
                query[k] = self[k]

        return [query]

    def to_db(self):
        return json.dumps({k: v for k, v in self.items() if k not in self._ignored and v is not None})

    @staticmethod
    def get_categories():
        return collections.OrderedDict(hookmanager.trigger("HOOK_WIDGET_CATEGORIES"))


def chart_class(cls):
    GenericStats._EXTRA_CHART_CLASSES[cls.__name__] = cls
    return cls


class StatsParameters(view.Parameters):
    def register(self):
        self.optional("limit", int, default=env.config.general.get_int('stats_charts_limit', 5))
        self.optional("offset", int, default=0)


class GenericStats(view.View):
    view_parameters = StatsParameters
    widget_template = template.PrewikkaTemplate(__name__, "templates/widget.mak")

    _CHART_CLASSES = {
        "chronology": statistics.ChronologyChart,
        "diagram": statistics.DiagramChart,
    }

    _EXTRA_CHART_CLASSES = {}

    def __init__(self):
        view.View.__init__(self)
        hookmanager.register("HOOK_LOAD_HEAD_CONTENT",
                             [resource.CSSLink("statistics/css/gridstack.min.css")])

    def setup(self, dataset):
        dataset["limit"] = env.request.parameters.get("limit")

    @classmethod
    def get_chart_classes(cls):
        ret = cls._CHART_CLASSES.copy()
        for name, class_ in hookmanager.trigger("HOOK_CHART_CLASSES"):
            ret[name] = class_

        return ret

    def _get_graph_data(self, chart, category):
        # we don't use .format() to avoid potential errors
        title = _(chart.title).replace("{limit}", text_type(chart.query[0].limit) if chart.query[0].limit > 0 else "")
        chart.options.setdefault("renderer", chart.options.get("renderer", env.request.parameters.get("%s_renderer" % chart.chart_type, None)))
        return {
            "title": title,
            "description": _(chart.options["description"]) if chart.options.get("description") else None,
            "rendering": chart.render(),
            "data": chart.data
        }

    def get_graph_data(self, category, rtype, title, query, **kwargs):
        color_paths = query[-1].paths  # for subquery
        if len(color_paths) == 1:
            info = env.dataprovider.get_path_info(color_paths[0])
            if info.value_accept:
                kwargs.setdefault("names_and_colors", {v.value: (v.label, v.color) for v in info.value_accept})

        class_ = kwargs.get("class")
        if class_:
            class_ = self._EXTRA_CHART_CLASSES.get(class_)
        else:
            class_ = self.get_chart_classes().get(category)

        if not class_:
            raise error.PrewikkaUserError(N_("Statistics error"), N_("Could not find chart class: %s", kwargs.get("class") or category))

        return self._get_graph_data(class_(rtype, title, query, **kwargs), category)

    def get_graphs(self, graphlist, **kwargs):
        keys = ["title", "category", "type", "query"]

        for graph in graphlist:
            extra = kwargs.copy()
            extra.update((i, graph.get(i)) for i in set(graph.keys()) - set(keys))
            queries = [statistics.Query(**q) for q in graph["query"]] if graph.get("query") else [statistics.Query(**graph)]
            yield self.get_graph_data(graph.get("category"), graph.get("type"), graph.get("title"), queries, **extra)


class StaticStats(GenericStats):
    view_template = template.PrewikkaTemplate(__name__, "templates/statistics.mak")

    _DEFAULT_ATTRIBUTES = {}
    _mainmenu_options = {}

    def __init__(self):
        GenericStats.__init__(self)
        self.chart_infos = self._PREDEFINED_GRAPHS

    def get_chart_infos(self, endpoint=None):
        return self.chart_infos

    def setup(self, dataset):
        GenericStats.setup(self, dataset)

        if "load" in env.request.parameters:
            return self._load_widget()

        charts = []
        for chart in self.chart_infos:
            widget = self._set_default_attributes(chart)
            if "description" in widget:
                widget["description"] = _(widget["description"])
            charts.append(widget)

        dataset["options"] = {
            "charts": charts,
            "widget_html": self.widget_template.render(),
        }

    def _load_widget(self):
        widget = Widget(env.request.parameters["widget"])

        categories = Widget.get_categories()
        if categories:
            if widget["category"] not in categories:
                raise error.PrewikkaUserError(N_("Invalid widget"), N_("The widget category does not exist"))

            data = categories[widget["category"]].prepare_render(widget)
            if data:
                return data

        data = self._get_graph(widget)

        if widget.get("period") and widget["category"] != "chronology":
            dictperiod = dict(('timeline_' + k, v) for k, v in widget["period"].items())
            period = mainmenu.TimePeriod(dictperiod)

            data["period_display"] = {
                "start": localization.format_datetime(period.start),
                "end": localization.format_datetime(period.end)
            }

        if widget.get("filter"):
            data["filter"] = widget.get("filter")

        return data

    def _get_graph(self, widget, **options):
        widget["width"] = int(widget["realwidth"])
        widget["height"] = int(widget["realheight"])

        for graph in self.get_graphs([widget], **options):
            ret = {"title": graph["title"]}
            ret.update(graph["rendering"])
            return ret

    def _set_default_attributes(self, chart):
        widget = {}
        widget.update(self._DEFAULT_ATTRIBUTES.get("global", {}))
        widget.update(self._DEFAULT_ATTRIBUTES.get(chart.get("category", widget.get("category")), {}))
        widget.update(chart)
        return widget

    def draw(self):
        dataset = self.view_template.dataset()
        data = self.setup(dataset)
        if data:
            return data

        return view.ViewResponse(dataset.render(), menu=mainmenu.HTMLMainMenu(**self._mainmenu_options))
