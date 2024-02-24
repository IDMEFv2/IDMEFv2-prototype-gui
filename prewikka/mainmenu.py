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

import calendar
import collections
import datetime

from dateutil.relativedelta import relativedelta
from prewikka import hookmanager, localization, resource, template, utils
from prewikka.dataprovider import Criterion

_SENTINEL = object()
_MAINMENU_TEMPLATE = template.PrewikkaTemplate(__name__, "templates/mainmenu.mak")
_MAINMENU_PARAMETERS = ["timeline_value", "timeline_unit", "timeline_end", "timeline_start", "timeline_mode", "timeline_offset", "auto_apply_value"]


def _register_parameters(view_parameters):
    view_parameters.optional("timeline_mode", text_type, default="relative", save=True, general=True)
    view_parameters.optional("timeline_value", int, default=1, save=True, general=True)
    view_parameters.optional("timeline_unit", text_type, default="month", save=True, general=True)
    view_parameters.optional("timeline_offset", int, default=0, save=True, general=True)
    view_parameters.optional("timeline_end", int, save=True, general=True)
    view_parameters.optional("timeline_start", int, save=True, general=True)
    view_parameters.optional("auto_apply_value", int, default=0, save=True, general=True)

    view_parameters.MAINMENU_PARAMETERS = _MAINMENU_PARAMETERS[:]
    for i in hookmanager.trigger("HOOK_MAINMENU_PARAMETERS_REGISTER", view_parameters):
        view_parameters.MAINMENU_PARAMETERS.extend(i)


class TimeUnit(object):
    _unit = ("year", "month", "day", "hour", "minute", "second", "millisecond", "microsecond")
    _dbunit = {"year": "year", "month": "month", "day": "mday", "hour": "hour", "minute": "min", "second": "sec", "millisecond": "msec", "microsecond": "usec"}

    @property
    def dbunit(self):
        return self._dbunit[text_type(self)]

    def __init__(self, unit):
        if isinstance(unit, int):
            assert 0 <= unit < len(self._unit)
            self._idx = unit
        else:
            assert unit in self._unit
            self._idx = self._unit.index(unit)

    def __add__(self, x):
        return TimeUnit(self._idx + x)

    def __sub__(self, x):
        return TimeUnit(self._idx - x)

    def __lt__(self, x):
        if isinstance(x, TimeUnit):
            return int(self) > int(x)
        else:
            return int(self) < x

    def __gt__(self, x):
        if isinstance(x, TimeUnit):
            return int(self) < int(x)
        else:
            return int(self) > x

    def __ge__(self, x):
        if isinstance(x, TimeUnit):
            return int(self) <= int(x)
        else:
            return int(self) >= x

    def __le__(self, x):
        if isinstance(x, TimeUnit):
            return int(self) >= int(x)
        else:
            return int(self) <= x

    def __eq__(self, x):
        return int(self) == int(x)

    def __int__(self):
        return self._idx

    def __str__(self):
        return self._unit[self._idx]


class MainMenuStep(object):
    def __init__(self, unit, value):
        d = {
            "year": (relativedelta(years=value), "%Y", "year"),
            "month": (relativedelta(months=value), _(localization.DATE_YM_FMT), "month"),
            "day": (relativedelta(days=value), _(localization.DATE_YMD_FMT), "mday"),
            "hour": (relativedelta(hours=value), _(localization.DATE_YMDH_FMT), "hour"),
            "minute": (relativedelta(minutes=value), _(localization.TIME_HM_FMT), "min"),
            "second": (relativedelta(seconds=value), _(localization.TIME_HMS_FMT), "sec"),
            "millisecond": (relativedelta(microseconds=value * 1000), _("%S.%.6f"), "msec"),
            "microsecond": (relativedelta(microseconds=value), _("%S.%.3f"), "usec")
        }

        self.unit = text_type(unit)
        self.timedelta, self.unit_format, self.dbunit = d[self.unit]


class TimePeriod(object):
    def __init__(self, parameters):
        self._parameters = parameters
        self._setup_timeline_range()

    def _get_unit(self):
        delta = self.end - self.start
        totsec = delta.seconds + (delta.days * 24 * 60 * 60)

        if self._timeunit != "unlimited" and self._timevalue > 1:
            unit = TimeUnit(self._timeunit)
            if int(unit) > 0:
                unit = unit - 1

        elif totsec > 365 * 24 * 60 * 60:
            unit = TimeUnit("year")

        elif totsec > 30 * 24 * 60 * 60:
            unit = TimeUnit("month")  # step = month

        elif totsec > 24 * 60 * 60:
            unit = TimeUnit("day")  # step = days

        elif totsec > 60 * 60:
            unit = TimeUnit("hour")  # step = hours

        elif totsec > 60:
            unit = TimeUnit("minute")  # step = minutes

        else:
            unit = TimeUnit("second")

        return unit

    def _get_nearest_unit(self, stepno):
        delta = self.end - self.start
        totsec = delta.seconds + (delta.days * 24 * 60 * 60)

        if totsec < 60:
            return TimeUnit("minute")

        gtable = {
            365 * 24 * 60 * 60: "year",
            31 * 24 * 60 * 60: "month",
            24 * 60 * 60: "day",
            60 * 60: "hour",
            60: "minute"
        }

        nearest = min(gtable, key=lambda x: abs((totsec / x) - stepno))

        return TimeUnit(gtable[nearest])

    def _setup_timeline_range(self):
        self.start = self.end = None
        mode = self._parameters["timeline_mode"]

        if mode == "custom":
            # datetime specified through the mainmenu are precise to the second, we thus increase
            # end time by 999999 microseconds to account for us/ms.
            if "timeline_start" in self._parameters:
                self.start = env.request.user.timezone.localize(datetime.datetime.utcfromtimestamp(self._parameters["timeline_start"]))

            if "timeline_end" in self._parameters:
                self.end = env.request.user.timezone.localize(datetime.datetime.utcfromtimestamp(self._parameters["timeline_end"])) + datetime.timedelta(microseconds=999999)
            else:
                self.end = datetime.datetime.now(env.request.user.timezone).replace(microsecond=999999)

        else:
            tunit = self._parameters["timeline_unit"]
            if tunit == "unlimited":
                tunit = "year"

            delta = relativedelta(**{tunit + "s": self._parameters["timeline_value"]})

            self.start = self.end = datetime.datetime.now(env.request.user.timezone).replace(microsecond=0)
            if mode == "relative":  # relative
                self.start = self.end - delta
                self.end = self.end.replace(microsecond=999999)
            else:  # absolute
                self.end = utils.timeutil.truncate(self.end, tunit) + relativedelta(**{tunit + "s": self._parameters["timeline_offset"] + 1})
                if self._parameters["timeline_unit"] == "unlimited":
                    self.start = datetime.datetime.fromtimestamp(0).replace(tzinfo=env.request.user.timezone)
                else:
                    self.start = self.end - delta

                self.end -= relativedelta(microseconds=1)

    @staticmethod
    def mktime_param(dt, precision=None):
        tpl = list(dt.timetuple())

        if precision is not None:
            assert(precision > 0)
            for i in range(precision, len(tpl)):
                # month/day must at least be 1
                tpl[i] = 1 if i <= 2 else 0

        return int(calendar.timegm(tpl))

    def get_criteria(self):
        criteria = Criterion()

        if self.start:
            start = self.start.astimezone(utils.timeutil.timezone("UTC"))
            criteria += Criterion("{backend}.{end_time_field}", ">=", start)

        if self.end:
            end = self.end.astimezone(utils.timeutil.timezone("UTC"))
            criteria += Criterion("{backend}.{start_time_field}", "<=", end)

        return criteria

    def get_step(self, stepno=None):
        if stepno:
            x = self._get_nearest_unit(stepno)
        else:
            x = self._get_unit()

        return MainMenuStep(x, 1)

    def get_parameters(self):
        return dict(((key, value) for key, value in self._parameters.items() if key in env.request.menu_parameters.MAINMENU_PARAMETERS))


class _MainMenu(TimePeriod):
    def __init__(self, criteria_type=_SENTINEL, parameters=None, **kwargs):
        if criteria_type is not _SENTINEL:
            self._criteria_type = criteria_type
        else:
            self._criteria_type = env.request.view.view_datatype

        self._parameters = parameters or env.request.menu_parameters
        self.dataset = _MAINMENU_TEMPLATE.dataset(inline=True, period=True, refresh=True, period_optional=False, label_width=2, input_size="sm", update=False)
        self.dataset.update(kwargs)

        self.dataset["timeline"] = utils.AttrObj()
        self.dataset["timeline"].quick = collections.OrderedDict((
            ((1, "day", True, 0), _("Today")),
            ((1, "day", True, -1), _("Yesterday")),
            ((1, "week", True, 0), _("This week")),
            ((1, "week", True, -1), _("Last week")),
            ((1, "month", True, 0), _("This month")),
            ((1, "month", True, -1), _("Last month")),
            ((1, "hour", False, 0), ngettext("%d hour", "%d hours", 1) % 1),
            ((2, "hour", False, 0), ngettext("%d hour", "%d hours", 2) % 2),
            ((1, "day", False, 0), ngettext("%d day", "%d days", 1) % 1),
            ((2, "day", False, 0), ngettext("%d day", "%d days", 2) % 2),
            ((1, "week", False, 0), ngettext("%d week", "%d weeks", 1) % 1),
            ((1, "month", False, 0), ngettext("%d month", "%d months", 1) % 1),
            ((3, "month", False, 0), ngettext("%d month", "%d months", 3) % 3),
            ((1, "year", False, 0), ngettext("%d year", "%d years", 1) % 1)
        ))

        self.dataset["timeline"].refresh = collections.OrderedDict((
            (30, ngettext("%d second", "%d seconds", 30) % 30),
            (60, ngettext("%d minute", "%d minutes", 1) % 1),
            (60 * 5, ngettext("%d minute", "%d minutes", 5) % 5),
            (60 * 10, ngettext("%d minute", "%d minutes", 10) % 10)
        ))

        self._render()

    def _set_timeline(self, start, end):
        if not start and not end:
            return

        self.dataset["timeline"].start = start.replace(tzinfo=None, microsecond=0).isoformat()
        self.dataset["timeline"].end = end.replace(tzinfo=None, microsecond=0).isoformat()

    def _render(self):
        mode = self.dataset["timeline"].mode = self._parameters["timeline_mode"]
        self.dataset["auto_apply_value"] = self._parameters["auto_apply_value"]
        self.dataset["timeline"].value = self._parameters["timeline_value"]
        self.dataset["timeline"].unit = self._parameters["timeline_unit"]
        self.dataset["timeline"].offset = self._parameters["timeline_offset"]
        self.dataset["timeline"].time_format = localization.get_calendar_format()
        self.dataset["timeline"].refresh_selected = self.dataset["timeline"].refresh.get(self._parameters["auto_apply_value"], _("Inactive"))

        if mode == "custom":
            self.dataset["timeline"].quick_selected = _("Custom")
        else:
            wanted = (self._parameters["timeline_value"], self._parameters["timeline_unit"], mode == "absolute", self._parameters["timeline_offset"])
            self.dataset["timeline"].quick_selected = self.dataset["timeline"].quick.get(wanted, _("None"))

        self._setup_timeline_range()
        self._set_timeline(self.start, self.end)

        self.dataset["mainmenu_url"] = url_for("BaseView.mainmenu", datatype=self._criteria_type)

        if "menu_extra" not in self.dataset:
            self.dataset["menu_extra"] = filter(None, hookmanager.trigger("HOOK_MAINMENU_EXTRA_CONTENT", self._criteria_type, parameters=self._parameters, **self.dataset))

    def render(self):
        return resource.HTMLSource(self.dataset.render())


def HTMLMainMenu(**kwargs):
    return resource.HTMLSource(_MainMenu(**kwargs).dataset.render())
