# Copyright (C) 2004-2021 CS GROUP - France. All Rights Reserved.
# Author: Yoann Vandoorselaere <yoannv@gmail.com>
# Author: Nicolas Delon <nicolas.delon@prelude-ids.com>
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

import pkg_resources

from prewikka import cli, database, error, hookmanager, resource, response, template, view
from prewikka.dataprovider import CriterionOperator
from prewikka.dataprovider.parsers.criteria import parse
from prewikka.utils import AttrObj, json
from prewikka.utils.viewhelpers import GridParameters


class Filter(object):
    def __init__(self, id_, name, category, description, criteria):
        self.id_ = id_
        self.name = name
        self.category = category
        self.description = description
        self.criteria = criteria

    def flatten_criteria(self):
        ret = {}
        for typ, criterion in self.criteria.items():
            crit = criterion.flatten()
            if not crit.operator.is_boolean:
                crit = AttrObj(operator=CriterionOperator.AND, operands=[crit])

            ret[typ] = crit

        return ret


class FilterDatabase(database.DatabaseHelper):
    def get_filters(self, user, ftype=None):
        rows = self.query("SELECT id, name, category, description, value FROM Prewikka_Filter "
                          "WHERE userid = %s ORDER BY name", user.id)

        rows = next(hookmanager.trigger("HOOK_FILTER_LISTING", rows), rows)

        for id_, name, category, description, value in rows:
            criteria = json.loads(value)
            if not ftype or ftype in criteria:
                yield Filter(id_, name, category, description, criteria)

    def get_filter(self, user, name=None, id_=None):
        query = "SELECT id, name, category, description, value FROM Prewikka_Filter WHERE userid = %(user)s"
        if name:
            query += " AND name = %(name)s"
        if id_:
            query += " AND id = %(id)s"

        rows = self.query(query, user=user.id, name=name, id=id_)
        if not rows:
            return None

        id_, name, category, description, value = rows[0]
        return Filter(id_, name, category, description, json.loads(value))

    def upsert_filter(self, user, filter_):
        values = (user.id, filter_.id_, filter_.name, filter_.category, filter_.description, json.dumps(filter_.criteria))
        self.upsert("Prewikka_Filter", ("userid", "id", "name", "category", "description", "value"), [values], pkey=("id",))

    def delete_filter(self, user, name=None, id_=None):
        query = "SELECT id, name FROM Prewikka_Filter WHERE userid = %(user)s"
        if name:
            query += " AND name = %(name)s"
        if id_:
            query += " AND id = %(id)s"

        rows = self.query(query, user=user.id, name=name, id=id_)
        if rows:
            self.query("DELETE FROM Prewikka_Filter WHERE id IN %s", (row[0] for row in rows))

        return rows

    def get_categories(self, user):
        query = "SELECT category FROM Prewikka_Filter WHERE userid = %(user)s AND category IS NOT NULL GROUP BY category ORDER BY category"
        return [row[0] for row in self.query(query, user=user.id)]


class FilterView(view.View):
    plugin_htdocs = (("filter", pkg_resources.resource_filename(__name__, 'htdocs')),)
    _filter_menu_tmpl = template.PrewikkaTemplate(__name__, "templates/menu.mak")

    def __init__(self):
        view.View.__init__(self)
        self._db = FilterDatabase()

    def _get_types(self):
        for typ in sorted(env.dataprovider.get_types(public=True)):
            yield typ, _(env.dataprovider.get_label(typ))

    @view.route("/settings/filters", menu=(N_("Preferences"), N_("Filters")), help="#filters", parameters=GridParameters("filters"))
    def listing(self):
        dataset = {}
        data = []

        for fltr in self._db.get_filters(env.request.user):
            elem = {
                "id": fltr.id_,
                "name": resource.HTMLNode(
                    "a", fltr.name,
                    href=url_for(".edit", name=fltr.name),
                    title=_("Filter %s") % fltr.name
                ),
                "category": fltr.category,
                "description": fltr.description
            }
            for typ in fltr.criteria:
                elem[typ] = True

            data.append(elem)

        dataset["data"] = data
        dataset["columns"] = self._get_types()

        return template.PrewikkaTemplate(__name__, "templates/filterlisting.mak").render(**dataset)

    def _filter_delete(self, user, name=None, id_=None):
        for fid, fname in self._db.delete_filter(user, name, id_):
            list(hookmanager.trigger("HOOK_FILTER_DELETE", user, fname, fid))

    @hookmanager.register("HOOK_MAINMENU_PARAMETERS_REGISTER")
    def _filter_parameters_register(self, view):
        view.optional("filter", text_type, save=True)
        return ["filter"]

    @hookmanager.register("HOOK_DATAPROVIDER_CRITERIA_PREPARE")
    def _filter_get_criteria(self, ctype):
        if not env.request.has_menu:
            return

        fname = env.request.menu_parameters.get("filter")
        if not fname:
            return

        return self._filter_get_criteria_by_name(fname, ctype)

    @hookmanager.register("HOOK_FILTER_GET_CRITERIA")
    def _filter_get_criteria_by_name(self, fname, ctype, user=None):
        f = self._db.get_filter(user or env.request.user, fname)
        if not f:
            return

        return f.criteria.get(ctype)

    @hookmanager.register("HOOK_MAINMENU_EXTRA_CONTENT")
    def _filter_html_menu(self, ctype, parameters, **kwargs):
        filters = list(self._db.get_filters(env.request.user, ctype))

        current_filter = parameters.get("filter")
        if current_filter not in [x.name for x in filters]:
            current_filter = None

        filter_categories = {}
        for fltr in filters:
            filter_categories.setdefault(fltr.category, []).append(fltr)

        dset = self._filter_menu_tmpl.dataset(
            current_filter=current_filter,
            filter_categories=filter_categories,
            **kwargs
        )

        return resource.HTMLSource(dset.render())

    @hookmanager.register("HOOK_CHART_PREPARE")
    def _chart_prepare(self, query, options):
        filter_name = options.get("filter")
        if not filter_name:
            return

        c = self._filter_get_criteria_by_name(filter_name, query.datatype, options.get("owner"))
        if not c:
            raise error.PrewikkaUserError(N_("Filter error"), N_("Filter '%s' does not exist", filter_name))

        query.criteria &= c

    @view.route("/settings/filters/new", help="#filteredition")
    @view.route("/settings/filters/<path:name>/edit", help="#filteredition")
    def edit(self, name=None):
        id_ = env.request.parameters.get("duplicate", type=int)

        dataset = {
            "fltr": AttrObj(id_=None, name=None, category=None, description=None, criteria={}),
            "categories": self._db.get_categories(env.request.user),
            "types": list(self._get_types())
        }

        if name or id_:
            dataset["fltr"] = self._db.get_filter(env.request.user, name, id_)
            if not dataset["fltr"]:
                raise error.PrewikkaUserError(N_("Filter error"), N_("Filter '%s' does not exist", name or id_))

            dataset["fltr"].criteria = dataset["fltr"].flatten_criteria()

        if "duplicate" in env.request.parameters:
            dataset["fltr"].name = None

        return template.PrewikkaTemplate(__name__, "templates/filteredition.mak").render(**dataset)

    @view.route("/settings/filters/delete", methods=["POST"])
    def delete(self):
        for id_ in env.request.parameters.getlist("id", type=int):
            self._filter_delete(env.request.user, id_=id_)

    @view.route("/settings/filters/save", methods=["POST"])
    @view.route("/settings/filters/<path:name>/save", methods=["POST"])
    def save(self, name=None):
        new_name = env.request.parameters.get("filter_name")
        category = env.request.parameters.get("filter_category")
        description = env.request.parameters.get("filter_description")

        criteria = dict(zip(
            env.request.parameters.getlist("filter_types"),
            (json.loads(c) for c in env.request.parameters.getlist("filter_criteria"))
        ))

        self._save(name, new_name, category, description, criteria)
        return response.PrewikkaResponse({"type": "reload", "target": "#main_menu_ng", "options": {"filter": new_name}})

    @cli.register("create", "filter", help=N_("""create filter <name> <data>: create a filter
     data is a JSON-encoded object with the following keys:
     * category: an optional category for the filter
     * description: an optional description for the filter
     * criteria: an object containing the filter criterion for each datatype"""))
    def save_filter(self, name, data):
        criteria = {typ: parse(crit) for typ, crit in data["criteria"].items()}
        self._save(None, name, data.get("category"), data.get("description"), criteria)

    def _save(self, name, new_name, category, description, criteria):
        if not new_name:
            raise error.PrewikkaUserError(N_("Could not save filter"), N_("No name for this filter was provided"))
        elif new_name.startswith("/"):
            raise error.PrewikkaUserError(N_("Could not save filter"), N_("The filter name cannot start with a slash"))

        filter_ = self._db.get_filter(env.request.user, name) if name else None
        filter_id = filter_.id_ if filter_ else None

        # Ensure the filter name is not already used by this user
        if new_name != name and self._db.get_filter(env.request.user, new_name):
            raise error.PrewikkaUserError(N_("Could not save filter"), N_("The filter name is already used by another filter"))

        # Do not erase filter components if the dataprovider failed to load
        if filter_:
            new_criteria = filter_.criteria
            new_criteria.update(criteria)
            criteria = new_criteria

        criteria = dict((k, v) for k, v in criteria.items() if v is not None)
        self._db.upsert_filter(env.request.user, Filter(filter_id, new_name, category, description, criteria))
