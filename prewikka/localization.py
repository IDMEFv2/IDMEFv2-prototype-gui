# coding=UTF-8
# Copyright (C) 2007-2021 CS GROUP - France. All Rights Reserved.
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

import builtins
import collections
import datetime
import gettext
from threading import Lock, local

import babel.core
# Babel functions
import babel.dates
import babel.numbers
import pkg_resources
import prelude
from prewikka import log, utils

try:
    # Needs babel >= 1.0
    from babel.dates import format_timedelta as _format_timedelta
except ImportError:
    from prewikka.compat.babelcompat import format_timedelta as _format_timedelta


logger = log.get_logger(__name__)


class TranslationProxy(object):
    def __init__(self):
        self._data = local()
        self._catalogs = {}
        self._catalogs_lock = Lock()

        self._domains_lock = Lock()
        self._domains = collections.OrderedDict([("prewikka", pkg_resources.resource_filename(__name__, "locale"))])

    def add_domain(self, domain, locale_dir):
        with self._domains_lock:
            self._domains[domain] = locale_dir

    def _get_catalog(self, domain, lang):
        with self._catalogs_lock:
            if domain not in self._catalogs:
                self._catalogs[domain] = {}

            if lang not in self._catalogs[domain]:
                logger.info("loading '%s' translation for domain '%s'", lang, domain)
                self._catalogs[domain][lang] = gettext.translation(domain, self._domains[domain], languages=[lang])

            return self._catalogs[domain][lang]

    def get_charset(self):
        try:
            return self._data.catalog.charset()
        except Exception:
            return env.config.general.encoding

    def get_locale(self):
        try:
            return self._data.lang
        except Exception:
            return env.config.general.default_locale

    def set_locale(self, lang):
        first = None
        for domain, locale_dir in self._domains.items():
            t = self._get_catalog(domain, lang)
            if not first:
                first = t
            else:
                first._catalog.update(t._catalog)

        self._data.lang = lang
        self._data.catalog = first

    def gettext(self, s):
        return self._data.catalog.gettext(s) if hasattr(self._data, "catalog") else s

    def ngettext(self, singular, plural, num):
        if not hasattr(self._data, "catalog"):
            return singular if num <= 1 else plural

        return self._data.catalog.ngettext(singular, plural, num)


translation = TranslationProxy()


class _DeferredGettext(text_type):
    def __new__(cls, text, arguments=None):
        message = text % arguments if arguments else text
        o = text_type.__new__(cls, message)
        o.origin = text
        o._arguments = arguments
        return o

    def translate(self):
        s = translation.gettext(self.origin)
        return s % self._arguments if self._arguments else s


def _translate(s):
    if isinstance(s, _DeferredGettext):
        return s.translate()
    else:
        return translation.gettext(s)


builtins._ = _translate
builtins.N_ = _DeferredGettext
builtins.ngettext = translation.ngettext

DATE_YM_FMT = N_("%m/%Y")
DATE_YMD_FMT = N_("%m/%d/%Y")
DATE_YMDH_FMT = N_("%m/%d/%Y %Hh")
DATE_YMDHM_FMT = N_("%m/%d/%Y %H:%M")
DATE_YMDHMS_FMT = N_("%m/%d/%Y %H:%M:%S")

TIME_HM_FMT = N_("%H:%M")
TIME_HMS_FMT = N_("%H:%M:%S")


_LANGUAGES = {
    "de_DE": "Deutsch",
    "es_ES": "Español",
    "en_GB": "English",
    "fr_FR": "Français",
    "it_IT": "Italiano",
    "pl_PL": "Polski",
    "pt_BR": "Português (Brasileiro)",
    "ru_RU": "Русский"
}


def set_locale(lang):
    if not lang:
        lang = env.config.general.default_locale

    translation.set_locale("%s.%s" % (lang, env.config.general.encoding))


def get_languages():
    return _LANGUAGES


def get_current_charset():
    return translation.get_charset()


def format_date(date=None, tzinfo=None, **kwargs):
    if isinstance(date, (float, int)):
        date = datetime.datetime.utcfromtimestamp(date).replace(tzinfo=utils.timeutil.tzutc())

    # Babel format_date() miss tzinfo convertion
    if date:
        date = date.astimezone(tzinfo or env.request.user.timezone)

    return babel.dates.format_date(date, locale=translation.get_locale(), **kwargs)


def format_time(dt=None, tzinfo=None, **kwargs):
    if isinstance(dt, (float, int, prelude.IDMEFTime)):
        dt = datetime.datetime.fromtimestamp(dt, utils.timeutil.tzutc())

    if not tzinfo:
        tzinfo = env.request.user.timezone

    return babel.dates.format_time(dt, tzinfo=tzinfo, locale=translation.get_locale(), **kwargs)


def format_datetime(dt=None, tzinfo=None, **kwargs):
    if isinstance(dt, (float, int, prelude.IDMEFTime)):
        dt = datetime.datetime.fromtimestamp(dt, utils.timeutil.tzutc())

    if not tzinfo:
        tzinfo = env.request.user.timezone

    return babel.dates.format_datetime(datetime=dt, tzinfo=tzinfo, locale=translation.get_locale(), **kwargs)


def format_timedelta(*args, **kwargs):
    return _format_timedelta(*args, locale=translation.get_locale(), **kwargs)


def _abbreviate_number(number, binary=False):
    thousand = 1024 if binary else 1000

    for unit in ['', 'K', 'M', 'G', 'T', 'P']:
        if abs(number) < thousand or unit == 'P':
            format_ = None if isinstance(number, int) else "@@@"  # three significant digits
            return "%s%s" % (format_number(number, format=format_), unit)

        number /= thousand


def format_number(number, short=False, binary=False, **kwargs):
    if short:
        return _abbreviate_number(number, binary)

    return babel.numbers.format_decimal(number, locale=translation.get_locale(), **kwargs)


def format_value(value):
    if value is None:
        return _("n/a")

    elif isinstance(value, (int, float)):
        return format_number(value)

    elif isinstance(value, datetime.datetime):
        return format_datetime(value)

    elif isinstance(value, datetime.timedelta):
        # format_timedelta does not provide this granularity (days/hours/minutes)
        hours, minutes = divmod(value.seconds / 60, 60)
        return _("%(days)dd %(hours)dh %(minutes)d'") % {
            "days": value.days,
            "hours": hours,
            "minutes": minutes
        }

    else:
        return text_type(value) or _("n/a")


def get_period_names(*args, **kwargs):
    return babel.dates.get_period_names(*args, locale=translation.get_locale(), **kwargs)


def get_day_names(*args, **kwargs):
    return babel.dates.get_day_names(*args, locale=translation.get_locale(), **kwargs)


def get_month_names(*args, **kwargs):
    return babel.dates.get_month_names(*args, locale=translation.get_locale(), **kwargs)


def get_quarter_names(*args, **kwargs):
    return babel.dates.get_quarter_names(*args, locale=translation.get_locale(), **kwargs)


def get_era_names(*args, **kwargs):
    return babel.dates.get_era_names(*args, locale=translation.get_locale(), **kwargs)


def get_calendar_format():
    """ Return a date format for use by jquery's datetime picker """

    calendar_format = babel.dates.get_date_format(
        'short',
        translation.get_locale()).pattern

    # babel uses 'MM' for month, and jquery uses 'mm'
    # 4-digits year: "yyyy" in Babel, "yy" in jQuery.
    # 2-digits year: "yy" in Babel, "y" in jQuery.
    return calendar_format.replace("yy", "y").replace("MM", "mm")


def get_timezones():
    return sorted(zone for zone in list(babel.core.get_global('zone_territories').keys()) + ["UTC"] if not zone.startswith('Etc/'))


def get_system_timezone():
    try:
        # Needs babel >= 1.0
        return babel.dates.LOCALTZ.zone
    except Exception:
        return "UTC"


def get_first_week_day():
    """
    Get the first day of the week based on locale.

    :return: first day of week, from 0 (monday) to 6 (sunday)
    :rtype: int
    """
    return babel.Locale.parse(translation.get_locale()).first_week_day
