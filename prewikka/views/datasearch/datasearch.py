# -*- coding: utf-8 -*-
# Copyright (C) 2015-2021 CS GROUP - France. All Rights Reserved.
# Author: Sélim Menouar <selim.menouar@c-s.fr>
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

""" DataSearch view """

import collections
import csv
import datetime
import functools
import itertools
import operator
import pkg_resources
import re

from prewikka.utils import json
from prewikka import error, history, hookmanager, mainmenu, resource, response, template, utils, view
from prewikka.dataprovider import Criterion, ResultObject
from prewikka.dataprovider.pathparser import PathParser
from prewikka.dataprovider.parsers import criteria, lucene
from prewikka.localization import format_datetime, format_timedelta
from prewikka.renderer import RendererItem
from prewikka.statistics import ChronologyChart, DiagramChart, Query


COLUMN_PROPERTIES = functools.partial(utils.AttrObj, hidden=False, align="center", cellattr="default_cellattr")

_DEFAULT_CHART_TYPES = {"chronology": "timebar", "diagram": "bar"}
_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"
_TEMPORAL_VALUES = [N_("minute"), N_("hour"), N_("day"), N_("month"), N_("year")]
_MAX_RECURSION_DEPTH = 100


class MaximumDepthExceeded(Exception):
    pass


class DataSearchParameters(view.Parameters):
    def register(self):
        self.optional("limit", int, default=30, save=True)
        self.optional("chart_type", text_type, save=True)
        self.optional("timeline", int, default=1, save=True)
        self.optional("query_mode", text_type, save=True)
        self.optional("editable", int, save=True)
        self.optional("condensed", int, save=True)
        self.optional("expert", int, save=True)
        self.optional("jqgrid_params_datasearch_table", json.loads, default={}, persist=True)


class HighLighter(object):
    """ Create an HTML representation of a phrase """
    _word_separators = [' ', '[', ']', '=', '(', ')', '"', "'", '<', '>', '\r', '\n', '\t']
    _term_separators = ['-', '/', '\\', ',', '.', ':', '?', '@', '_']

    def __init__(self, phrase):
        self.value = self.get_clean_value(phrase)
        parsed_phrase = [self.word_prepare(word) for word in self.split_phrase(phrase)]
        self.html = resource.HTMLNode("span", *parsed_phrase, _class="selectable")

    @classmethod
    def get_separators(cls):
        return {
            "word": cls._word_separators,
            "term": cls._term_separators
        }

    @staticmethod
    def get_clean_value(value):
        return value

    @classmethod
    def split_phrase(cls, phrase):
        return [phrase]

    @classmethod
    def word_prepare(cls, word):
        return resource.HTMLNode("span", word)


class Formatter(object):
    highlighter = HighLighter
    ignore_fields = frozenset()

    _converters = {
        datetime.datetime: lambda f, r, o: resource.HTMLNode("span", format_datetime(o), **{"data-field": f.field, "data-value": o})
    }

    def __init__(self, data_type):
        self._enrich_data_cb = [elem[1] for elem in sorted(hookmanager.trigger("HOOK_DATASEARCH_FORMATTER_ENRICH_CALLBACK"))]
        self.type = data_type

    def _format_nonstring(self, field, value):
        if isinstance(value, list):
            value = ", ".join(value)

        return resource.HTMLNode("span", resource.HTMLNode("span", value), _class="selectable", **{"data-field": field})

    def format_value(self, field, value):
        if not isinstance(value, text_type):
            return self._format_nonstring(field, value)

        hl = self.highlighter(value or "n/a")
        node, value = hl.html, hl.value
        node.attrs["data-field"] = field

        for i in self._enrich_data_cb:
            node = i(node, value, self.type)

        return node

    def format(self, finfo, root, obj):
        if finfo.type in self._converters:
            return self._converters[finfo.type](finfo, root, obj)

        if finfo.field in self.ignore_fields:
            return obj

        return self.format_value(finfo.field, obj)


class QueryParser(object):
    path_prefix = "{backend}."

    def __init__(self, query, parent, groupby=[], orderby=[], offset=0, limit=50):
        self.type = parent.type
        self.query = query
        self.offset = offset
        self.limit = limit
        self.groupby = []
        self._sort_order = ["%s.%s/order_%s" % (self.type, field, order) for field, order in orderby]
        self._time_group = None
        self._paths = collections.OrderedDict()
        self._result = None
        self._parent = parent
        self._date_selection_index = None

        self.criteria = self.get_criteria(query)
        self.all_criteria = self.criteria + env.request.menu.get_criteria()

        if groupby:
            self._prepare_groupby_query(groupby, orderby)
        else:
            self._paths.update((field, '%s%s' % (self.path_prefix, field)) for field in self._parent.all_fields)
            self._handle_order(orderby)

        if self.query:
            # Make sure to use printable characters in the search bar
            self.query = "".join(chr(x) for x in bytearray(self.query.encode("unicode-escape")))

    def _prepare_groupby_query(self, groupby, orderby):
        self._paths["_aggregation"] = "count(1)"

        groupby = set(groupby)
        ogroup = list(groupby - set(_TEMPORAL_VALUES))
        tgroup = list(groupby & set(_TEMPORAL_VALUES))
        self.groupby = ogroup + tgroup

        for field in ogroup:
            if field not in self._parent.path_translate:
                self._paths[field] = '%s%s/group_by' % (self.path_prefix, field)
            else:
                for i in self._parent.path_translate[field][0]:
                    self._paths[field] = '%s/group_by' % i

        self._handle_order(orderby)

        if not tgroup:
            return

        if len(tgroup) > 1:
            raise error.PrewikkaUserError(N_("Time group error"), N_("Only one time unit can be specified in a groupby query"))

        self._time_group = tgroup[0]
        self._date_selection_index = len(self._paths)
        self._paths.update(("_time_unit_%d" % i, path) for i, path in enumerate(self._time_selection(self._time_group)))

    def _handle_order(self, orderby):
        for field, order in orderby:
            path = self._paths.pop(field, "%s%s" % (self.path_prefix, field))
            separator = "," if "/" in path else "/"
            self._paths[field] = "%s%sorder_%s" % (path, separator, order)

    def get_result(self):
        if self._result:
            return self._result

        if self.groupby:
            res = self._groupby_query()
        else:
            res = self._query()

        if self._date_selection_index:
            res = ResultDatetimeIterator(res, self._date_selection_index)

        self._result = res
        return res

    @classmethod
    def _lucene_escape(cls, value):
        if re.search(r'[/\s+\-!(){}[\]^"~*?\:\\]|&&|\|\|', value):
            return '"%s"' % re.sub(r'(["\\])', r'\\\1', value)

        return value

    @classmethod
    def format_criterion(cls, path, value, mode):
        if mode == "lucene":
            if isinstance(value, (int, float, datetime.datetime)):
                return "%s:%s" % (path, value)

            if not value:
                return "-%s:[* TO *]" % path

            return "%s.exact:%s" % (path, cls._lucene_escape(value))

        return text_type(Criterion(path, "==", value))

    def get_groupby_link(self, groups, values, step, cview):
        url_param = env.request.menu.get_parameters()
        query_mode = env.request.parameters.get("query_mode", self._parent.criterion_config_default)

        query = []
        if self.query:
            query.append(self.query)

        for group, value in zip(groups, values):
            if group not in _TEMPORAL_VALUES:
                query.append(self.format_criterion(group, value, query_mode))
            else:
                precision = mainmenu.TimeUnit(step.unit) + 1
                url_param["timeline_mode"] = "custom"
                url_param["timeline_start"] = mainmenu.TimePeriod.mktime_param(value, precision)
                url_param["timeline_end"] = mainmenu.TimePeriod.mktime_param((value + step.timedelta), precision) - 1

        url_param.update({
            "limit": env.request.parameters["limit"]
        })

        query_str = (" %s " % self._parent.criterion_config[query_mode]["operators"]["AND"][0]).replace("  ", " ").join(query)
        return url_for(cview, query=query_str, query_mode=query_mode, **url_param)

    def get_step(self):
        if self._time_group:
            step = mainmenu.MainMenuStep(self._time_group, 1)
        else:
            step = env.request.menu.get_step(100)

        return step

    def diagram(self, cview, step=None, **kwargs):
        if not self.groupby:
            return None

        if step is None:
            step = self.get_step()

        chart_type = env.request.parameters.get("chart_type", _DEFAULT_CHART_TYPES["diagram"])

        try:
            return env.renderer.render(chart_type, [list(self._diagram_data(cview, step))], **kwargs)
        except error.PrewikkaUserError:
            return {"html": None, "script": None}

    def chronology(self, **kwargs):
        paths = ["{backend}.%s" % path for path in self.groupby]
        query = Query(path=paths, aggregate="count(1)", criteria=self.criteria, limit=self.limit, offset=self.offset, datatype=self._parent.type)
        label = _(env.dataprovider.get_label(self._parent.type))

        linkview = env.viewmanager.get_view(endpoint=".forensic")
        linkparams = {"query": env.request.parameters.get("query"), "query_mode": env.request.parameters.get("query_mode", self._parent.criterion_config_default)}

        return ChronologyChart(env.request.parameters.get("chart_type", _DEFAULT_CHART_TYPES["chronology"]),
                               label, [query], linkview=linkview, linkparams=linkparams, **kwargs).render()

    def _fix_operator(self, left, op):
        if op in env.dataprovider.get_path_info(left).operators:
            return op

        return "=" if op[0] != "!" else "!="

    def _criterion_compile(self, left, op, right):
        if left not in self._parent.path_translate:
            left = "%s.%s" % (self.type, left)
            return Criterion(left, self._fix_operator(left, op), right)

        paths, valuefunc = self._parent.path_translate[left]
        if valuefunc:
            right = valuefunc(right)

        # Translation (for source [A, B]):
        # source : (A != None || B != None)
        # !source : !(A != None || B != None) => !(A || B)
        # source != test: (A != test && B != test)
        # source == test: (A == test || B == test)

        if op[0] == "!" and right is not None:
            f = operator.and_
        else:
            f = operator.or_

        return functools.reduce(lambda x, y: f(x, y), (Criterion(i, self._fix_operator(i, op), right) for i in paths))

    def get_index(self, field):
        if field in _TEMPORAL_VALUES:
            return self._date_selection_index

        return list(self._paths).index(field)

    def get_paths(self):
        return list(self._paths.values())

    def get_criteria(self, query):
        if not query:
            return Criterion()

        qmode = env.request.parameters.get("query_mode", self._parent.criterion_config_default)
        if qmode == "criterion":
            return criteria.parse(query, transformer=criteria.CriteriaTransformer(compile=self._criterion_compile))

        elif qmode == "lucene":
            if self._parent.criterion_config_default != "lucene":
                tr = lucene.CriteriaTransformer(compile=self._criterion_compile, default_paths=self._parent.lucene_search_fields)
                return lucene.parse(query, transformer=tr)
            else:
                return Criterion("{backend}._raw_query", "==", query)

    def _time_selection(self, time_unit):
        selection = []
        for unit in range(int(mainmenu.TimeUnit(time_unit) + 1)):
            selection += ["timezone({backend}.{time_field}, '%s'):%s/order_asc,group_by" % (env.request.user.timezone, mainmenu.TimeUnit(unit).dbunit)]

        return selection

    def _diagram_data(self, cview, step):
        """Generator for the diagram chart"""
        for result in self.get_result():
            count = result[0]
            labels = result[1:]

            link = self.get_groupby_link(self.groupby, labels, step, cview=cview)

            if self._date_selection_index:
                labels[-1] = labels[-1].strftime(step.unit_format)

            yield RendererItem(count, tuple(labels), link)

    def _query(self):
        return env.dataprovider.query(self.get_paths(), self.all_criteria, limit=self.limit, offset=self.offset, type=self.type)

    def _groupby_query(self):
        return self._query()


class DataSearch(view.View):
    view_parameters = DataSearchParameters
    plugin_htdocs = (("datasearch", pkg_resources.resource_filename(__name__, 'htdocs')),)
    type = None
    section = None

    formatter = Formatter
    query_parser = QueryParser
    groupby_default = []
    sort_path_default = "timestamp"
    criterion_config = {}
    criterion_config_default = "lucene"
    path_translate = {}
    default_columns = {}
    lucene_search_fields = []
    expert_enabled = False
    _extra_resources = []

    criterion_config["lucene"] = {
        "format": '{operator}{path}:{value}',
        "operators": {
            "equal": "",
            "notequal": "-",
            "substr": "",
            "notsubstr": "-",
            "AND": ["", "AND"],
            "OR": ["OR"]
        }
    }
    criterion_config["criterion"] = {
        "format": '{path} {operator} {value}',
        "operators": {
            "equal": "=",
            "notequal": "!=",
            "substr": "<>",
            "notsubstr": "!<>",
            "AND": ["&&"],
            "OR": ["||"]
        }
    }

    def __init__(self):
        env.dataprovider.check_datatype(self.type)

        self._formatter = self.formatter(self.type)

        self.all_fields = []
        self._main_fields = list(self.default_columns.keys())
        self.fields_info = collections.OrderedDict()
        self.columns_properties = collections.OrderedDict()

        self._prepare_fields()
        view.View.__init__(self)

        hookmanager.register("HOOK_LOAD_HEAD_CONTENT", [resource.CSSLink("datasearch/css/datasearch.css")])

        section = self.section or env.dataprovider.get_label(self.type)
        tabs = self.tabs or (N_("Forensic"), N_("Dashboard"))

        view.route("/%s/forensic/ajax_timeline" % self.name, self.ajax_timeline)
        view.route("/%s/forensic/ajax_table" % self.name, self.ajax_table)
        view.route("/%s/forensic/ajax_details" % self.name, self.ajax_details, methods=["POST"])
        view.route("/%s/forensic/ajax_infos" % self.name, self.ajax_infos)
        view.route("/%s/forensic/ajax_groupby" % self.name, self.ajax_groupby)
        view.route("/%s/forensic/csv_download" % self.name, self.csv_download, methods=["POST"])
        view.route("/%s/forensic" % self.name, self.forensic, menu=(section, tabs[0]), keywords=["listing", "inheritable"],
                   datatype=self.type, priority=1, help="#%sforensic" % self.type, methods=["POST", "GET"])
        view.route("/%s/dashboard" % self.name, self.dashboard, menu=(section, tabs[1]),
                   datatype=self.type, help="#%sdashboard" % self.type, methods=["POST", "GET"])

    def _get_fields(self):
        return env.dataprovider.get_paths(self.type)

    def _get_column_property(self, field, pi):
        pass

    def _default_order(self, value):
        try:
            return self._main_fields.index(value)
        except ValueError:
            return 100

    def _prepare_fields(self):
        for field in sorted(self._get_fields(), key=self._default_order):
            field = field.split(".", 1)[1]

            self.all_fields.append(field)
            self.fields_info[field] = pi = env.dataprovider.get_path_info("%s.%s" % (self.type, field))

            pi.filterable = pi.type is not datetime.datetime
            pi.groupable = pi.type is not object

            cprop = self._get_column_property(field, pi)
            if cprop:
                self.columns_properties[field] = cprop

    def _set_common(self, dataset):
        view.View.render(self)

        dataset["backend"] = self.type
        dataset["limit"] = env.request.parameters["limit"]

        dataset["columns_properties"] = columns = collections.OrderedDict()
        right_columns = []
        for prop, finfo, func in filter(None, self._trigger_datasearch_hook("EXTRA_COLUMN")):
            if prop.position == "left":
                columns[prop.label] = COLUMN_PROPERTIES(**prop)
            else:
                right_columns.append(prop)

        columns.update(self.columns_properties)
        for prop in right_columns:
            columns[prop.label] = COLUMN_PROPERTIES(**prop)

        dataset["separators"] = self._formatter.highlighter.get_separators()
        dataset["criterion_config"] = self.criterion_config
        dataset["criterion_config_default"] = env.request.parameters.get("query_mode", self.criterion_config_default)

        query = env.request.parameters.get("query")
        if query:
            history.save(env.request.user, "%s_form_search" % self.type, query)

        dataset["history"] = history.create(env.request.user, "%s_form_search" % self.type)

    def _criteria_to_urlparams(self, criteria):
        # Link creation from other pages (e.g. statistics)
        return {
            "query": criteria.to_string(noroot=True),  # remove the prefixed type
            "query_mode": "criterion"
        }

    def _trigger_datasearch_hook(self, name, *args):
        return itertools.chain(hookmanager.trigger("HOOK_DATASEARCH_%s" % name, *args), hookmanager.trigger("HOOK_DATASEARCH_%s_%s" % (self.type.upper(), name), *args))

    def get_forensic_actions(self):
        return [resource.HTMLNode("button", _("CSV export"), formaction=url_for(".csv_download"), type="submit", form="datasearch_export_form",
                                  _class="btn btn-default needone", _sortkey="download", _icon="fa-file-excel-o")]

    def dashboard(self, groupby=[]):
        return self.forensic(groupby, is_dashboard=True)

    def _get_dataset(self):
        return template.PrewikkaTemplate(__name__, "templates/forensic.mak").dataset()

    def forensic(self, groupby=[], is_dashboard=False):
        groupby = env.request.parameters.getlist("groupby") or groupby
        query = env.request.parameters.get("query")
        mode = env.request.parameters.get("query_mode", self.criterion_config_default)

        if groupby and not(is_dashboard):
            raise error.RedirectionError(url_for(".dashboard", query=query, groupby=groupby, query_mode=mode), 302)

        if not groupby and is_dashboard:
            groupby = self.groupby_default

        dataset = self._get_dataset()
        self._set_common(dataset)

        dataset["available_types"] = filter(lambda x: list(env.renderer.get_backends(x)) and x != "table", DiagramChart.TYPES if groupby else ChronologyChart.TYPES)
        dataset["chart_type"] = env.request.parameters.get("chart_type", _DEFAULT_CHART_TYPES["diagram" if groupby else "chronology"])
        dataset["groupby_tempo"] = _TEMPORAL_VALUES
        dataset["fields_info"] = self.fields_info
        dataset["actions"] = itertools.chain(self.get_forensic_actions(), self._trigger_datasearch_hook("ACTION"))
        dataset["search"] = self.query_parser(query,
                                              groupby=groupby,
                                              limit=env.request.parameters["limit"],
                                              parent=self)
        dataset["extra_resources"] = self._extra_resources
        dataset["common_paths"] = {path.split(".", 1)[-1]: _(label) for label, path in env.dataprovider.get_common_paths(self.type, index=True)}
        dataset["expert_enabled"] = self.expert_enabled

        return view.ViewResponse(dataset)

    def _prepare(self, page=1, limit=-1):
        query = env.request.parameters.get("query")
        if query:
            history.save(env.request.user, "%s_form_search" % self.type, query)

        groupby = env.request.parameters.get("groupby")
        orderby = []

        # @HACK free-jqGrid messes the parameters badly when sorting on multiple columns simultaneously
        sort_settings = "%s %s" % (env.request.parameters.get("sort_index", ""), env.request.parameters.get("sort_order", ""))
        for sort_setting in sort_settings.split(','):
            try:
                field, order = sort_setting.split()
            except ValueError:
                pass
            else:
                if order not in ("asc", "desc"):
                    pass
                elif field in self.path_translate:
                    orderby.append((self.path_translate[field][0][0].split(".", 1)[-1], order))
                elif field == "_aggregation" or PathParser.unindex_path(field) in self.all_fields:
                    orderby.append((field, order))

        if not orderby:
            orderby.append(("_aggregation" if groupby else self.sort_path_default, "desc"))

        return self.query_parser(query, groupby=groupby, orderby=orderby,
                                 offset=(page - 1) * limit, limit=limit, parent=self)

    def csv_download(self):
        grid = utils.json.loads(env.request.parameters["datasearch_grid"], object_pairs_hook=collections.OrderedDict)
        with utils.mkdownload("table.csv") as dl:
            w = csv.writer(dl)

            if grid:
                w.writerow(grid[0].keys())

            for row in grid:
                w.writerow(map(lambda x: x.encode("utf8"), row.values()))

        return dl

    def ajax_timeline(self):
        query = self.query_parser(env.request.parameters.get("query"), parent=self)
        data = query.chronology(height=200)

        return response.PrewikkaResponse(resource.HTMLSource("""
            %s
            <script type="text/javascript">%s</script>
            """ % (data["html"], data["script"] or "")))

    def _get_default_cells(self, obj, search):
        r = {}

        for fname, cprop in self.columns_properties.items():
            finfo = self.fields_info[fname]
            index = getattr(finfo, "column_index", search.get_index(fname))
            r[fname] = self._formatter.format(finfo, obj, obj[index])

        return r

    def ajax_table(self):
        search = self._prepare(int(env.request.parameters.get("page", 1)), int(env.request.parameters.get("rows", 30)))
        results = search.get_result()
        resrows = []

        extradata = list(self._trigger_datasearch_hook("EXTRA_DATA", results))
        extracol = list(filter(None, self._trigger_datasearch_hook("EXTRA_COLUMN")))

        for i, obj in enumerate(results):
            cells = self._get_default_cells(obj, search)
            for prop, finfo, func in extracol:
                if isinstance(obj, ResultObject):
                    ret = func(obj, extradata)
                else:
                    ret = func({env.dataprovider.format_path(f.split("/")[0], type=self.type): v for f, v in zip(search.get_paths(), obj)}, extradata)

                if finfo:
                    cells[prop.name] = self._formatter.format(finfo, obj, ret)
                else:
                    cells[prop.name] = ret

            resrows.append({"_rowId": text_type(i), "cell": cells})

        return utils.viewhelpers.GridAjaxResponse(resrows, results.total, criteria=search.all_criteria).add_html_content(mainmenu.HTMLMainMenu(update=True))

    def ajax_details(self):
        tmpl = template.PrewikkaTemplate(__name__, "templates/details.mak")
        return response.PrewikkaResponse(tmpl.dataset(fields_info=self.fields_info,
                                                      fields_value=env.request.parameters))

    def _get_common_infos(self):
        tmpl = template.PrewikkaTemplate(__name__, "templates/infos.mak")
        query = self.query_parser(env.request.parameters["query"],
                                  groupby=[env.request.parameters["field"]],
                                  limit=5,
                                  parent=self)

        occurrences = [(value, count) for count, value in query.get_result()]
        return tmpl.dataset(selected_field=env.request.parameters["field"], selected_occur=occurrences).render()

    def _get_extra_infos(self):
        return []

    def ajax_infos(self):
        infos = collections.OrderedDict()
        infos["general"] = utils.AttrObj(label=_("General"), info=self._get_common_infos())

        extra_infos = filter(None, hookmanager.trigger("HOOK_DATASEARCH_INFO", env.request.parameters))
        for category, data in itertools.chain(extra_infos, self._get_extra_infos()):
            infos[category] = data

        return response.PrewikkaResponse({"infos": infos})

    def ajax_groupby(self):
        limit = int(env.request.parameters["limit"])
        page = int(env.request.parameters.get("page", 1))

        search = self._prepare(page, limit)
        step = search.get_step()
        results = search.get_result()
        resrows = []

        # We need to reorder results according to what is expected
        permutation = [search.get_index(f) for f in ["_aggregation"] + search.groupby]

        for i, result in enumerate(results):
            values = [result[permutation[idx]] for idx in range(len(result))]

            cells = {}
            for idx, group in enumerate(search.groupby):
                label = values[idx + 1]
                if isinstance(label, datetime.datetime):
                    label = label.strftime(step.unit_format)
                elif isinstance(label, datetime.timedelta):
                    label = format_timedelta(label)

                link = search.get_groupby_link([group], [values[idx + 1]], step, cview='.forensic')
                cells[group] = resource.HTMLNode("a", label, href=link)

            link = search.get_groupby_link(search.groupby, values[1:], step, cview='.forensic')
            cells["_aggregation"] = resource.HTMLNode("a", values[0], href=link)
            resrows.append({"id": text_type(i), "cell": cells})

        total = (page if len(resrows) < limit else page + 1) * limit
        return utils.viewhelpers.GridAjaxResponse(resrows, total).add_html_content(mainmenu.HTMLMainMenu(update=True))


class ResultDatetimeIterator(object):
    def __init__(self, results, date_selection_index):
        self._results = results
        self._date_selection_index = date_selection_index

    def __getattr__(self, x):
        return self.__dict__.get(x, getattr(self._results, x))

    def __iter__(self):
        for i in self._results:

            tval = [int(x) for x in i[self._date_selection_index:]]
            tval += [1] * (3 - min(3, len(tval)))  # Minimum length for datetime.

            tval = datetime.datetime(*tval).replace(tzinfo=env.request.user.timezone)

            yield i[:self._date_selection_index] + [tval]
