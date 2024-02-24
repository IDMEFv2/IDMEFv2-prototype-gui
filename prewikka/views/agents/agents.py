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

import pkg_resources

from prewikka import hookmanager, localization, mainmenu, resource, template, utils, view, response
from prewikka.dataprovider import Criterion
from prewikka.utils.viewhelpers import GridParameters


class Agents(view.View):
    plugin_htdocs = (("agents", pkg_resources.resource_filename(__name__, 'htdocs')),)

    @hookmanager.register("HOOK_RISKOVERVIEW_DATA", _order=0)
    def _set_agents_summary(self):
        results = env.dataprovider.query(["max(heartbeat.create_time)", "heartbeat.analyzer(-1).analyzerid/group_by"])
        if not results:
            return

        c = Criterion()
        for create_time, analyzerid in results:
            c |= Criterion("heartbeat.create_time", "==", create_time) & Criterion("heartbeat.analyzer(-1).analyzerid", "==", analyzerid)

        agents = {
            "up": utils.AttrObj(count=0, title=_("Online"), label="label-success", status=["online"]),
            "down": utils.AttrObj(count=0, title=_("Offline"), label="label-danger", status=["offline", "missing", "unknown"])
        }
        heartbeat_error_margin = env.config.general.get_int("heartbeat_error_margin", 3)

        for heartbeat in env.dataprovider.get(c):
            heartbeat = heartbeat["heartbeat"]
            analyzer = heartbeat["analyzer"][-1]
            analyzer.status = utils.get_analyzer_status_from_latest_heartbeat(heartbeat, heartbeat_error_margin)[0]

            for key, values in agents.items():
                if analyzer.status in values.status:
                    values.count += 1

        parameters = env.request.menu_parameters
        val = agents["down"] if agents["down"].count else agents["up"]
        data = resource.HTMLNode("a", localization.format_number(val.count), title=val.title, _class="label " + val.label, href=url_for("Agents.agents", status=val.status, **parameters))

        return utils.AttrObj(
            name="agents",
            title=resource.HTMLNode("a", _("Agents"), href=url_for("Agents.agents", **parameters)),
            data=[data]
        )

    def __init__(self):
        env.dataprovider.check_datatype("heartbeat")

        view.View.__init__(self)
        self._heartbeat_count = env.config.general.get_int("heartbeat_count", 30)
        self._heartbeat_error_margin = env.config.general.get_int("heartbeat_error_margin", 3)

    def _get_analyzer(self, analyzerid):
        res = env.dataprovider.get(Criterion("heartbeat.analyzer(-1).analyzerid", "=", analyzerid), limit=1)
        heartbeat = res[0]["heartbeat"]
        analyzer = heartbeat["analyzer"][-1]

        return analyzer, heartbeat

    def _get_analyzers(self, reqstatus):
        # Do not take the control menu into account.
        # The expected behavior is yet to be determined.
        results = env.dataprovider.query(["max(heartbeat.create_time)", "heartbeat.analyzer(-1).analyzerid/group_by"])
        if not results:
            return

        c = Criterion()
        for create_time, analyzerid in results:
            c |= Criterion("heartbeat.create_time", "==", create_time) & Criterion("heartbeat.analyzer(-1).analyzerid", "==", analyzerid)

        ids = set()
        for heartbeat in env.dataprovider.get(c):
            heartbeat = heartbeat["heartbeat"]
            analyzerid = heartbeat["analyzer(-1).analyzerid"]

            if analyzerid in ids:
                continue

            ids.add(analyzerid)

            status, status_text = utils.get_analyzer_status_from_latest_heartbeat(
                heartbeat, self._heartbeat_error_margin
            )

            if reqstatus and status not in reqstatus:
                continue

            delta = heartbeat.get("create_time") - utils.timeutil.now()

            heartbeat_listing = url_for("HeartbeatDataSearch.forensic", criteria=Criterion("heartbeat.analyzer(-1).analyzerid", "==", analyzerid), _default=None)
            alert_listing = url_for("AlertDataSearch.forensic", criteria=Criterion("alert.analyzer.analyzerid", "==", analyzerid), _default=None)
            heartbeat_analyze = url_for(".analyze", analyzerid=analyzerid)

            analyzer = heartbeat["analyzer(-1)"]
            node_name = analyzer["node.name"] or _("Node name n/a")
            osversion = analyzer["osversion"] or _("OS version n/a")
            ostype = analyzer["ostype"] or _("OS type n/a")

            yield {
                "id": analyzerid,
                "label": "%s - %s %s" % (node_name, ostype, osversion),
                "location": analyzer["node.location"] or _("Node location n/a"),
                "node": node_name,
                "name": analyzer["name"],
                "model": analyzer["model"],
                "class": analyzer["class"],
                "version": analyzer["version"],
                "latest_heartbeat": localization.format_timedelta(delta, add_direction=True),
                "status": status,
                "status_text": status_text,
                "links": [
                    resource.HTMLNode("a", _("Alert listing"), href=alert_listing),
                    resource.HTMLNode("a", _("Heartbeat listing"), href=heartbeat_listing),
                    resource.HTMLNode("a", _("Heartbeat analysis"), href=heartbeat_analyze)
                ]
            }

    @view.route("/agents/agents", methods=["GET", "POST"], permissions=[N_("IDMEF_VIEW")], help="#agents",
                menu=(N_("Monitoring"), N_("Agents")), parameters=GridParameters("agents"), datatype="heartbeat")
    def agents(self):

        analyzer_data = list(self._get_analyzers(env.request.parameters.getlist("status")))
        list(hookmanager.trigger("HOOK_AGENTS_EXTRA_CONTENT", analyzer_data))
        extra_columns = filter(None, hookmanager.trigger("HOOK_AGENTS_EXTRA_COLUMN"))

        return view.ViewResponse(template.PrewikkaTemplate(__name__, "templates/agents.mak").render(data=analyzer_data, extra_columns=extra_columns), menu=mainmenu.HTMLMainMenu())

    @view.route("/agents/delete", methods=["POST"], permissions=[N_("IDMEF_ALTER")])
    def delete(self):
        for i in env.request.parameters.getlist("types"):
            if i not in ("alert", "heartbeat"):
                continue

            c = Criterion()

            for analyzerid in env.request.parameters.getlist("id"):
                c |= Criterion("%s.analyzer.analyzerid" % i, "=", analyzerid)

            env.dataprovider.delete(c)

        return response.PrewikkaRedirectResponse(url_for(".agents"))

    @view.route("/agents/analyze/<analyzerid>", permissions=[N_("IDMEF_VIEW")], help="#heartbeatanalyze")
    def analyze(self, analyzerid):
        analyzer, heartbeat = self._get_analyzer(analyzerid)
        delta = heartbeat["create_time"] - utils.timeutil.now()
        analyzer.last_heartbeat_time = localization.format_timedelta(delta, add_direction=True)

        analyzer.status = None
        analyzer.events = []

        res = env.dataprovider.get(Criterion("heartbeat.analyzer(-1).analyzerid", "=", analyzerid), limit=self._heartbeat_count)

        prev = None
        total_interval = 0

        # Iterate from oldest heartbeat to newest
        for obj in reversed(res):
            cur = HeartbeatObject(obj["heartbeat"])

            if not (prev and cur.status and cur.interval):
                prev = cur
                continue

            total_interval += cur.interval

            event = None
            if cur.status == "starting":
                if prev.status == "exiting":
                    event = utils.AttrObj(time=cur.time_str, value=_("Normal sensor start"), type="start")
                else:
                    event = utils.AttrObj(time=cur.time_str, value=_("Unexpected sensor restart"), type="unexpected_restart")

            elif cur.status == "running":
                delta = cur.time - prev.time
                if abs(delta.total_seconds() - cur.interval) > self._heartbeat_error_margin:
                    delta = localization.format_timedelta(delta, granularity="second")
                    event = utils.AttrObj(time=cur.time_str, value=_("Unexpected heartbeat interval: %(delta)s") % {'delta': delta}, type="abnormal_heartbeat_interval")

            elif cur.status == "exiting":
                event = utils.AttrObj(time=cur.time_str, value=_("Normal sensor stop"), type="normal_stop")

            if event:
                analyzer.events.append(event)

            prev = cur

        if prev:
            analyzer.status, analyzer.status_meaning = \
                utils.get_analyzer_status_from_latest_heartbeat(obj["heartbeat"], self._heartbeat_error_margin)
            if analyzer.status == "missing":
                delta = utils.timeutil.now() - prev.time
                analyzer.events.append(utils.AttrObj(time=prev.time_str, value=_("Sensor is down since %s") % localization.format_timedelta(delta), type="down"))

        if not analyzer.status:
            analyzer.status, analyzer.status_meaning = "unknown", _("Unknown")

        if not analyzer.events:
            delta = localization.format_timedelta(total_interval / self._heartbeat_count)
            analyzer.events.append(utils.AttrObj(
                time="",
                value=_("No anomaly in the last %(count)d heartbeats (one heartbeat every %(delta)s average)") % {'count': self._heartbeat_count, 'delta': delta},
                type="no_anomaly"
            ))

        return template.PrewikkaTemplate(__name__, "templates/heartbeatanalyze.mak").render(analyzer=analyzer)


class HeartbeatObject(object):
    def __init__(self, heartbeat):
        self.status = heartbeat.get("additional_data('Analyzer status').data")[0]
        self.interval = heartbeat["heartbeat_interval"]
        self.time = heartbeat["create_time"]
        self.time_str = localization.format_datetime(self.time)
