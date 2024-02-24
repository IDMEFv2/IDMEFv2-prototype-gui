# Copyright (C) 2016-2021 CS GROUP - France. All Rights Reserved.
# Author: Abdel ELMILI <abdel.elmili@c-s.fr>
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

import datetime
import prelude

from prewikka import crontab, hookmanager, renderer, utils, version
from prewikka.dataprovider import DataProviderBase, Criterion, CriterionOperator, ParserError, PathValue, InvalidPathError


class _IDMEFPath(prelude.IDMEFPath):
    def __init__(self, path):
        try:
            prelude.IDMEFPath.__init__(self, path)
        except RuntimeError as e:
            raise InvalidPathError(path, details=e)


class _IDMEFCriterion(prelude.IDMEFCriteria):
    def __init__(self, criteria):
        try:
            prelude.IDMEFCriteria.__init__(self, criteria)
        except RuntimeError as e:
            raise ParserError(details=e)


class _IDMEFProvider(DataProviderBase):
    plugin_version = version.__version__
    plugin_author = version.__author__
    plugin_license = version.__license__
    plugin_copyright = version.__copyright__

    TYPE_OPERATOR_MAPPING = {
        text_type: ("=", "=*", "!=", "!=*", "~", "~*", "!~", "!~*", "<>", "<>*", "!<>", "!<>*"),
        bytes: ("=", "!=", "<>", "!<>", "<", ">", "<=", ">="),
        None: ("=", "!=", "<", ">", "<=", ">=")
    }

    def __init__(self):
        DataProviderBase.__init__(self, "create_time")

    def get_path_type(self, path):
        _typemap = {
            prelude.IDMEFValue.TYPE_DATA: bytes,
            prelude.IDMEFValue.TYPE_STRING: text_type,
            prelude.IDMEFValue.TYPE_TIME: datetime.datetime,
            prelude.IDMEFValue.TYPE_FLOAT: float,
            prelude.IDMEFValue.TYPE_DOUBLE: float,
            prelude.IDMEFValue.TYPE_ENUM: text_type,
            prelude.IDMEFValue.TYPE_INT8: int,
            prelude.IDMEFValue.TYPE_UINT8: int,
            prelude.IDMEFValue.TYPE_INT16: int,
            prelude.IDMEFValue.TYPE_UINT16: int,
            prelude.IDMEFValue.TYPE_INT32: int,
            prelude.IDMEFValue.TYPE_UINT32: int,
            prelude.IDMEFValue.TYPE_INT64: int,
            prelude.IDMEFValue.TYPE_UINT64: int,
            prelude.IDMEFValue.TYPE_CLASS: object,
        }

        return _typemap[prelude.IDMEFClass(path).getValueType()]

    def _get_paths(self, rootcl):
        for node in rootcl:
            if node.getValueType() == prelude.IDMEFValue.TYPE_CLASS:
                for subnode in self._get_paths(node):
                    yield subnode
            else:
                yield node.getPath()

    @staticmethod
    def _value_adjust(operator, value):
        if not operator.is_substring:
            return value

        value = text_type(value)

        has_wildcard = utils.find_unescaped_characters(value, ["*"])
        if has_wildcard:
            return value

        return "*%s*" % value

    @staticmethod
    def _path_adjust(path):
        """
        Automatically add indexes to IDMEF listed fields
        FIXME: to be removed when libpreludedb supports != for listed fields
        """
        fields = []
        for elem in path.replace("(*)", "").split("."):
            p = ".".join(fields + [elem])

            if elem == "analyzer":
                fields.append("%s(-1)" % elem)
            elif _IDMEFPath(p).isAmbiguous():
                fields.append("%s(0)" % elem)
            else:
                fields.append(elem)

        return ".".join(fields)

    def compile_criterion(self, criterion):
        if criterion.right:
            criterion.right = self._value_adjust(criterion.operator, criterion.right)

        elif criterion.operator == CriterionOperator.EQUAL:
            criterion = Criterion(criterion.left, "==", None)
            if _IDMEFPath(criterion.left).getValueType() == prelude.IDMEFValue.TYPE_STRING:
                criterion |= Criterion(criterion.left, "==", "''")

        if criterion.operator.negated and _IDMEFPath(criterion.left).isAmbiguous():
            criterion.left = self._path_adjust(criterion.left)

        return DataProviderBase.compile_criterion(self, criterion)

    def compile_criteria(self, criteria):
        if criteria:
            return _IDMEFCriterion(criteria.to_string())

    def _get_path_values(self, path):
        klass = prelude.IDMEFClass(path)

        if path == "alert.assessment.impact.severity":
            return [
                PathValue("high", label=N_("High"), color=renderer.RED_STD),
                PathValue("medium", label=N_("Medium"), color=renderer.ORANGE_STD),
                PathValue("low", label=N_("Low"), color=renderer.GREEN_STD),
                PathValue("info", label=N_("Informational"), color=renderer.BLUE_STD),
            ]
        elif klass.getValueType() == prelude.IDMEFValue.TYPE_ENUM:
            return [PathValue(v) for v in klass.getEnumValues()]
        else:
            return None


class IDMEFAlertProvider(_IDMEFProvider):
    plugin_name = "IDMEF Alert provider"
    plugin_description = N_("Provides an API to fetch IDMEF alerts")
    dataprovider_label = N_("Alerts")

    def get_paths(self):
        return self._get_paths(prelude.IDMEFClass("alert"))

    def get_common_paths(self, index=False):
        return [
            (N_("Classification"), "alert.classification.text"),
            (N_("Source IP"), "alert.source(0).node.address(0).address" if index else "alert.source.node.address.address"),
            (N_("Source port"), "alert.source(0).service.port" if index else "alert.source.service.port"),
            (N_("Target IP"), "alert.target(0).node.address(0).address" if index else "alert.target.node.address.address"),
            (N_("Target port"), "alert.target(0).service.port" if index else "alert.target.service.port"),
            (N_("Analyzer name"), "alert.analyzer(-1).name" if index else "alert.analyzer.name")
        ]

    @crontab.schedule("alert", N_("Alert deletion"), "0 0 * * *", enabled=False)
    def _alert_cron(self, job):
        config = env.config.cron.get_instance_by_name("alert")
        if config is None:
            return

        criteria = Criterion()
        age = int(config.get("age", 0))
        now = utils.timeutil.utcnow()
        for severity in (None, "info", "low", "medium", "high"):
            days = int(config.get(severity, age))
            if days < 1:
                continue

            criteria |= (Criterion("alert.assessment.impact.severity", "==", severity) &
                         Criterion("alert.create_time", "<", now - datetime.timedelta(days=days)))

        if not criteria:
            return

        if not list(hookmanager.trigger("HOOK_CRON_DELETE", criteria, "alert")):
            env.dataprovider.delete(criteria, type="alert")


class IDMEFHeartbeatProvider(_IDMEFProvider):
    plugin_name = "IDMEF Heartbeat provider"
    plugin_description = N_("Provides an API to fetch IDMEF heartbeats")
    dataprovider_label = N_("Heartbeats")

    def get_paths(self):
        return self._get_paths(prelude.IDMEFClass("heartbeat"))

    @crontab.schedule("heartbeat", N_("Heartbeat deletion"), "0 0 * * *", enabled=False)
    def _heartbeat_cron(self, job):
        config = env.config.cron.get_instance_by_name("heartbeat")
        if config is None:
            return

        days = int(config.get("age", 0))
        if days < 1:
            return

        criteria = Criterion("heartbeat.create_time", "<", utils.timeutil.utcnow() - datetime.timedelta(days=days))

        if not list(hookmanager.trigger("HOOK_CRON_DELETE", criteria, "heartbeat")):
            env.dataprovider.delete(criteria, type="heartbeat")
