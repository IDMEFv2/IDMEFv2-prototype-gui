# Copyright (C) 2017-2021 CS GROUP - France. All Rights Reserved.
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
import croniter
import datetime
import gevent

from prewikka.compat.gevent import fix_ssl
from prewikka.utils import timeutil
from prewikka import database, error, hookmanager, log, registrar, usergroup, utils


fix_ssl()

logger = log.get_logger(__name__)


DEFAULT_SCHEDULE = collections.OrderedDict((("0 * * * *", N_("Hourly")),
                                            ("0 0 * * *", N_("Daily")),
                                            ("0 0 * * 1", N_("Weekly")),
                                            ("0 0 1 * *", N_("Monthly")),
                                            ("0 0 1 1 *", N_("Yearly")),
                                            ("custom", N_("Custom")),
                                            ("disabled", N_("Disabled"))))

_SCHEDULE_PARAMS = dict((("0 * * * *", "hour"),
                         ("0 0 * * *", "day"),
                         ("0 0 * * 1", "week"),
                         ("0 0 1 * *", "month"),
                         ("0 0 1 1 *", "year")))


class CronJob(object):
    def __hash__(self):
        return self.id

    def __eq__(self, other):
        return self.id == other.id

    def __init__(self, id, name, schedule, func, base, runcnt, ext_type=None, ext_id=None, user=None, error=None, enabled=True, status=None):
        self.id = id
        self.name = name
        self.user = user
        self.callback = func
        self.error = error
        self.ext_type = ext_type
        self.ext_id = ext_id
        self.enabled = enabled
        self.status = status
        self.base = base
        self.runcnt = runcnt
        self._greenlet = None

        self.set_schedule(schedule)

    def set_schedule(self, schedule):
        self.schedule = schedule

        # Interpret the cronjob configuration as local time
        self._cron = croniter.croniter(schedule, datetime.datetime.now(utils.timeutil.tzlocal()))

        # If the job was not executed at the previous scheduled time,
        # make sure to schedule it back
        self._cron.get_next()
        if self.base and self._cron.get_prev(datetime.datetime).replace(microsecond=0) <= self.base:  # replace() needed for croniter < 0.3.8
            self._cron.get_next()

        self.next_schedule = self._cron.get_current(datetime.datetime)

    def update(self, job):
        # Update the current job data (following a modified schedule or a plugin reinitialization)
        self.callback = job.callback
        self.status = job.status
        self.error = job.error
        if job.schedule != self.schedule:
            self.set_schedule(job.schedule)

    def _run(self):
        self.status = "running"
        env.db.query("UPDATE Prewikka_Crontab SET status=%s WHERE id=%d", self.status, self.id)

        # setup the environment
        env.request.init(None)
        env.request.user = self.user

        if self.user:
            self.user.set_locale()

        err = None
        try:
            if self.callback:
                self.callback(self)
            else:
                raise self.error
        except Exception as e:
            logger.exception("[%d/%s]: cronjob failed: %s", self.id, self.name, e)
            err = utils.json.dumps(error.PrewikkaError(e, N_("Scheduled job execution failed")))

        self._finalize(err)

    def _cancel(self):
        if self._greenlet:
            gevent.kill(self._greenlet)

        self._finalize()

    def _finalize(self, err=None):
        self.runcnt += 1
        self.status = None
        self.base = timeutil.utcnow()
        self.next_schedule = self._cron.get_next(datetime.datetime)
        env.db.query("UPDATE Prewikka_Crontab SET base=%s, status=%s, runcnt=runcnt+1, error=%s WHERE id=%d",
                     self.base, self.status, err, self.id)

    def run(self, now):
        if self.status == "cancelled":
            self._cancel()
            return
        elif now < self.next_schedule or self.status == "running":
            return

        env.log.info("[%d/%s]: RUNNING JOB schedule=%s callback=%s" % (self.id, self.name, self.schedule, self.callback))
        self._greenlet = gevent.spawn(self._run)


class Crontab(object):
    _REFRESH = datetime.timedelta(minutes=1)

    def _reinit(self):
        self._plugin_callback = {}
        self._formatters = {}

    def __init__(self):
        self._reinit()
        self._joblist = set()
        hookmanager.register("HOOK_PLUGINS_RELOAD", self._reinit)

    def _make_job(self, res):
        id, name, userid, schedule, ext_type, ext_id, base, runcnt, enabled, status, error_s = res

        func = self._plugin_callback.get(ext_type)
        if not func:
            err = error.PrewikkaUserError(N_("Invalid job extension"), N_("Scheduled job with invalid extension type '%s'", ext_type))
        elif error_s:
            err = utils.json.loads(error_s)
        else:
            err = None

        if ext_id:
            ext_id = int(ext_id)

        if base:
            base = env.db.parse_datetime(base)

        user = None
        if userid:
            user = usergroup.User(userid=userid)

        return CronJob(int(id), name, schedule, func, base, int(runcnt), ext_type=ext_type, ext_id=ext_id,
                       user=user, error=err, enabled=bool(int(enabled)), status=status)

    @database.use_lock("Prewikka_Crontab")
    def _init_system_job(self, ext_type, name, schedule, enabled, method):
        self._plugin_callback[ext_type] = method

        res = env.db.query("SELECT 1 FROM Prewikka_Crontab WHERE ext_type=%s AND userid IS NULL", ext_type)
        if not res:
            self.add(name, schedule, ext_type=ext_type, enabled=enabled)

    def _update_joblist(self):
        # Update jobs instead of re-creating them because some of them may be currently running
        mainlist = set(self.list(enabled=True))

        # Suppress jobs that were removed from the main list
        self._joblist -= self._joblist.difference(mainlist)

        # Add jobs that were added to the main list
        self._joblist |= mainlist.difference(self._joblist)

        # Take schedule changes into account
        for job in self._joblist:
            for j in mainlist:
                if j == job:
                    job.update(j)
                    break

        return self._joblist

    def _run_jobs(self):
        first = now = timeutil.utcnow()

        for job in self._update_joblist():
            job.run(now)
            now = timeutil.utcnow()

        return (self._REFRESH - (now - first)).total_seconds()

    def run(self, core):
        env.db.query("UPDATE Prewikka_Crontab SET status = NULL WHERE status = 'running'")

        while True:
            next = self._run_jobs()
            if next > 0:
                gevent.sleep(next)

            core.reload_plugin_if_needed()

    def list(self, **kwargs):
        qs = env.db.kwargs2query(kwargs, prefix=" WHERE ")
        for res in env.db.query("SELECT id, name, userid, schedule, ext_type, ext_id, base, runcnt, enabled, status, error "
                                "FROM Prewikka_Crontab%s" % qs):
            yield self._make_job(res)

    def get(self, id):
        res = env.db.query("SELECT id, name, userid, schedule, ext_type, ext_id, base, runcnt, enabled, status, error "
                           "FROM Prewikka_Crontab WHERE id=%d", id)
        if not res:
            raise error.PrewikkaError(N_('Invalid CronJob'), N_('CronJob with id=%d cannot be found in database', id))

        return self._make_job(res[0])

    def delete(self, **kwargs):
        user = kwargs.pop("user", None)
        if user:
            kwargs["userid"] = getattr(user, "id", user)  # Can be None / NotNone

        qs = env.db.kwargs2query(kwargs, " WHERE ")
        env.db.query("DELETE FROM Prewikka_Crontab%s" % qs)

    def update(self, id, **kwargs):
        accept = {
            "user": lambda x: ("userid", getattr(x, "id", None))
        }

        cols = []
        data = []
        for field, value in kwargs.items():
            dec = accept.get(field)
            if dec:
                field, value = dec(value)

            if id:
                data.append("%s = %s" % (field, env.db.escape(value)))
            else:
                cols.append(field)
                data.append(value)

        if not id:
            env.db.query("INSERT INTO Prewikka_Crontab (%s) VALUES %%s" % (", ".join(cols + ["base"])), data + [timeutil.utcnow()])
            return env.db.get_last_insert_ident()
        else:
            env.db.query("UPDATE Prewikka_Crontab SET %s WHERE id IN %%s" % (", ".join(data)), env.db._mklist(id))
            return id

        # FIXME: there is an issue with upsert() when using PostgreSQL CTE (serial problem + cast problem)
        # id = int(env.db.upsert("Prewikka_Crontab", cols, [data], pkey=("id",), returning=["id"])[0])
        # return id

    def add(self, name, schedule, user=None, ext_type=None, ext_id=None, enabled=True):
        return self.update(None, name=name, schedule=schedule, user=user, ext_type=ext_type, ext_id=ext_id, enabled=enabled)

    def update_from_parameters(self, id, delete_disabled=False, **kwargs):
        schedule = env.request.parameters.get("quick-schedule")
        if schedule != "disabled":
            kwargs["schedule"] = schedule
            try:
                croniter.croniter(schedule)
            except Exception:
                raise error.PrewikkaUserError(N_("Invalid schedule"), N_("The specified job schedule is invalid"))

        elif delete_disabled:
            return crontab.delete(id=id, **kwargs)

        crontab.update(id, enabled=int(schedule != "disabled"), **kwargs)

    def schedule(self, ext_type, name, schedule, _regfunc=None, enabled=True):
        if _regfunc:
            self._init_system_job(ext_type, name, schedule, enabled, _regfunc)
        else:
            return registrar.DelayedRegistrar.make_decorator("crontab", self.schedule, ext_type, name, schedule, enabled=enabled)

    def setup(self, ext_type, _regfunc=None, formatter=None):
        if _regfunc:
            assert not(ext_type in self._plugin_callback)
            self._plugin_callback[ext_type] = _regfunc
            self._formatters[ext_type] = formatter
        else:
            return registrar.DelayedRegistrar.make_decorator("crontab", self.setup, ext_type, formatter=formatter)

    def format(self, ext_type, name):
        formatter = self._formatters.get(ext_type)
        return N_(formatter, name) if formatter else name


def format_schedule(x):
    val = DEFAULT_SCHEDULE.get(x)
    if val:
        return _(val)
    else:
        return _("Custom (%s)") % x


def schedule_to_menuparams(x):
    params = {}

    val = _SCHEDULE_PARAMS.get(x)
    if val:
        params["timeline_mode"] = "relative"
        params["timeline_value"] = 1
        params["timeline_unit"] = val
    else:
        now = timeutil.now()
        params["timeline_mode"] = "custom"
        params["timeline_start"] = timeutil.get_timestamp_from_datetime(croniter.croniter(x, now).get_prev(datetime.datetime))
        params["timeline_end"] = timeutil.get_timestamp_from_datetime(now)

    return params


crontab = Crontab()

list = crontab.list
run = crontab.run
get = crontab.get
add = crontab.add
update = crontab.update
delete = crontab.delete
schedule = crontab.schedule
setup = crontab.setup
format = crontab.format
update_from_parameters = crontab.update_from_parameters
