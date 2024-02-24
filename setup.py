#!/usr/bin/env python

# Copyright (C) 2005-2021 CS GROUP - France. All Rights Reserved.
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

from glob import glob
import io
import os
import stat
import subprocess
import sys
import tempfile

from setuptools import Command, setup, find_packages
from setuptools.command.test import test as TestCommand
from distutils.dist import Distribution
from distutils.command.install import install
from distutils.dep_util import newer
from distutils.command.build import build as _build


LIBPRELUDE_REQUIRED_VERSION = "5.2.0"
LIBPRELUDEDB_REQUIRED_VERSION = "5.2.0"


def init_siteconfig(conf_prefix, data_prefix, path=""):
    """
    Initialize configuration file (prewikka/siteconfig.py).

    :param str conf_prefix: configuration path
    :param str data_prefix: data path
    """
    configuration = (
        ('tmp_dir', os.path.join(tempfile.gettempdir(), 'prewikka')),
        ('conf_dir', os.path.abspath(conf_prefix)),
        ('data_dir', os.path.abspath(data_prefix)),
        ('libprelude_required_version', LIBPRELUDE_REQUIRED_VERSION),
        ('libpreludedb_required_version', LIBPRELUDEDB_REQUIRED_VERSION),
    )

    with open(os.path.join(path, 'prewikka', 'siteconfig.py'), 'w') as config_file:
        for option, value in configuration:
            config_file.write("%s = '%s'\n" % (option, value))


class MyDistribution(Distribution):
    def __init__(self, attrs):
        try:
            os.remove("prewikka/siteconfig.py")
        except Exception:
            pass

        self.conf_files = {}
        self.closed_source = os.path.exists("PKG-INFO")
        Distribution.__init__(self, attrs)


class my_install(install):
    def finalize_options(self):
        # if no prefix is given, configuration should go to /etc or in {prefix}/etc otherwise
        if self.prefix:
            self.conf_prefix = self.prefix + "/etc/prewikka"
            self.data_prefix = self.prefix + "/var/lib/prewikka"
        else:
            self.conf_prefix = "/etc/prewikka"
            self.data_prefix = "/var/lib/prewikka"

        install.finalize_options(self)

    def get_outputs(self):
        tmp = [self.conf_prefix + "/prewikka.conf"] + install.get_outputs(self)
        return tmp

    def install_conf(self):
        self.mkpath((self.root or "") + self.conf_prefix + "/conf.d")
        for dest_dir, patterns in self.distribution.conf_files.items():
            for pattern in patterns:
                for f in glob(pattern):
                    dest = (self.root or "") + self.conf_prefix + "/" + dest_dir + "/" + os.path.basename(f)
                    if os.path.exists(dest):
                        dest += "-dist"
                    self.copy_file(f, dest)

    def create_datadir(self):
        self.mkpath((self.root or "") + self.data_prefix)

    def install_wsgi(self):
        share_dir = os.path.join(self.install_data, 'share', 'prewikka')
        if not os.path.exists(share_dir):
            os.makedirs(share_dir)

        ofile, copied = self.copy_file('scripts/prewikka.wsgi', share_dir)

    def run(self):
        os.umask(0o22)
        self.install_conf()
        self.install_wsgi()
        self.create_datadir()

        install.run(self)
        init_siteconfig(self.conf_prefix, self.data_prefix, path=self.install_lib)

        os.chmod((self.root or "") + self.conf_prefix, 0o755)

        if not self.dry_run:
            for filename in self.get_outputs():
                if filename.find(".conf") != -1:
                    continue
                mode = os.stat(filename)[stat.ST_MODE]
                mode |= 0o44
                if mode & 0o100:
                    mode |= 0o11
                os.chmod(filename, mode)


class build(_build):
    sub_commands = [('compile_catalog', None), ('build_custom', None)] + _build.sub_commands


class build_custom(Command):
    @staticmethod
    def _need_compile(template, outfile):
        if os.path.exists(outfile) and not any(newer(tmpl, outfile) for tmpl in template):
            return False

        directory = os.path.dirname(outfile)
        if not os.path.exists(directory):
            print("creating %s" % directory)
            os.makedirs(directory)

        print("compiling %s -> %s" % (template, outfile))
        return True

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        style = os.path.join("prewikka", "htdocs", "css", "style.less")

        for less in glob("themes/*.less"):
            css = os.path.join("prewikka", "htdocs", "css", "themes", "%s.css" % os.path.basename(less[:-5]))
            if self._need_compile([less, style], css):
                io.open(css, "wb").write(subprocess.check_output(["lesscpy", "-I", less, style]))


class PrewikkaTest(TestCommand):
    """
    Custom command for Prewikka test suite with pytest.

    Based on
    https://docs.pytest.org/en/2.7.3/goodpractises.html#integration-with-setuptools-test-commands
    """
    user_options = [
        ('pytest-args=', 'a', 'Arguments to pass to pytest')
    ]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = []

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        init_siteconfig('conf', 'tests/downloads')

        import pytest  # import here, cause outside the eggs aren't loaded

        if not isinstance(self.pytest_args, list):
            self.pytest_args = self.pytest_args.split()

        errno = pytest.main(self.pytest_args + ['tests'])
        sys.exit(errno)


class PrewikkaCoverage(Command):
    """
    Coverage command.
    """
    user_options = [
        ('run-args=', None, 'Arguments to pass to coverage during run'),
        ('report-args=', None, 'Arguments to pass to coverage for report')
    ]
    description = 'Run tests with coverage.'

    def initialize_options(self):
        self.run_args = []
        self.report_args = []

    def finalize_options(self):
        pass

    def run(self):
        subprocess.call(['coverage', 'run', 'setup.py', 'test'] + self.run_args)
        subprocess.call(['coverage', 'report'] + self.report_args)


setup(
    name="prewikka",
    version="5.2.0",
    maintainer="Prelude Team",
    maintainer_email="support.prelude@csgroup.eu",
    url="https://www.prelude-siem.com",
    packages=find_packages(exclude=[
        'tests',
        'tests.*'
    ]),
    setup_requires=[
        'Babel'
    ],
    entry_points={
        'prewikka.renderer.backend': [
            'ChartJS = prewikka.renderer.chartjs:ChartJSPlugin',
        ],
        'prewikka.renderer.type': [
            'ChartJSBar = prewikka.renderer.chartjs.bar:ChartJSBarPlugin',
            'ChartJSDoughnut = prewikka.renderer.chartjs.pie:ChartJSDoughnutPlugin',
            'ChartJSPie = prewikka.renderer.chartjs.pie:ChartJSPiePlugin',
            'ChartJSTimebar = prewikka.renderer.chartjs.timeline:ChartJSTimebarPlugin',
            'ChartJSTimeline = prewikka.renderer.chartjs.timeline:ChartJSTimelinePlugin',
        ],
        'prewikka.dataprovider.backend': [
            'ElasticsearchIDMEFv2 = prewikka.dataprovider.plugins.idmefv2.elasticsearch:ElasticsearchIDMEFv2Plugin',
            'ElasticsearchLog = prewikka.dataprovider.plugins.log.elasticsearch:ElasticsearchLogPlugin',
            'IDMEFAlert = prewikka.dataprovider.plugins.idmef:IDMEFAlertPlugin',
            'IDMEFHeartbeat = prewikka.dataprovider.plugins.idmef:IDMEFHeartbeatPlugin',
        ],
        'prewikka.dataprovider.type': [
            'alert = prewikka.dataprovider.idmef:IDMEFAlertProvider',
            'heartbeat = prewikka.dataprovider.idmef:IDMEFHeartbeatProvider',
            'IDMEFv2 = prewikka.dataprovider.idmefv2:IDMEFv2API',
            'log = prewikka.dataprovider.log:LogAPI',
        ],
        'prewikka.plugins': [
        ],
        'prewikka.auth': [
            'DBAuth = prewikka.auth.dbauth:DBAuth',
        ],
        'prewikka.session': [
            'Anonymous = prewikka.session.anonymous:AnonymousSession',
            'LoginForm = prewikka.session.loginform:LoginFormSession',
        ],
        'prewikka.views': [
            'About = prewikka.views.about:About',
            'AboutPlugin = prewikka.views.aboutplugin:AboutPlugin',
            'AgentPlugin = prewikka.views.agents:AgentPlugin',
            'AlertDataSearch = prewikka.views.datasearch.alert:AlertDataSearch',
            'AlertStats = prewikka.views.statistics.alertstats:AlertStats',
            'CrontabView = prewikka.views.crontab:CrontabView',
            'Custom = prewikka.views.custom:Custom',
            'FilterPlugin = prewikka.plugins.filter:FilterPlugin',
            'HeartbeatDataSearch = prewikka.views.datasearch.heartbeat:HeartbeatDataSearch',
            'IDMEFnav = prewikka.views.idmefnav:IDMEFNav',
            'LogDataSearch = prewikka.views.datasearch.log:LogDataSearch',
            'MessageSummary = prewikka.views.messagesummary:MessageSummary',
            'RiskOverview = prewikka.views.riskoverview:RiskOverview',
            'Statistics = prewikka.views.statistics:Statistics',
            'UserManagement = prewikka.views.usermanagement:UserManagement',
        ],
        'prewikka.updatedb': [
            'prewikka = prewikka.sql',
            'prewikka.auth.dbauth = prewikka.auth.dbauth.sql',
            'prewikka.plugins.filter = prewikka.plugins.filter.sql'
        ]
    },
    package_data={
        '': [
            "htdocs/css/*.*",
            "htdocs/css/themes/*.css",
            "htdocs/css/images/*.*",
            "htdocs/fonts/*.*",
            "htdocs/images/*.*",
            "htdocs/js/*.js",
            "htdocs/js/locales/*.js",
            "htdocs/js/locales/*/*.js",
            "htdocs/js/*.map",
            "htdocs/js/locales/*.map",
            "locale/*/LC_MESSAGES/*.mo",
            "sql/*.py",
            "templates/*.mak"
        ],
        'prewikka.auth.dbauth': ["sql/*.py"],
        'prewikka.renderer.chartjs': ["htdocs/js/*.js"],
        'prewikka.session.loginform': ["htdocs/css/*.css"],
        'prewikka.views.about': ["htdocs/css/*.css", "htdocs/images/*.png"],
        'prewikka.views.aboutplugin': ["htdocs/css/*.css"],
        "prewikka.views.idmefnav": ["htdocs/yaml/*.yml", "htdocs/graph/*"],
        'prewikka.views.riskoverview': ["htdocs/js/*.js"],
        'prewikka.views.statistics': ["htdocs/js/*.js", "htdocs/css/*.css"],
        'prewikka.views.usermanagement': ["htdocs/js/*.js", "htdocs/css/*.css"],
    },
    scripts=[
        "scripts/prewikka-cli",
        "scripts/prewikka-crontab",
        "scripts/prewikka-httpd"
    ],
    conf_files={
        "": ["conf/prewikka.conf", "conf/menu.yml"],
        "conf.d": ["conf/plugins/*.conf"]
    },
    cmdclass={
        'build': build,
        'build_custom': build_custom,
        'coverage': PrewikkaCoverage,
        'install': my_install,
        'test': PrewikkaTest,
    },
    tests_require=[
        'pytest'
    ],
    distclass=MyDistribution,
    message_extractors={
        'scripts': [
            ('prewikka-cli', 'python', None),
            ('prewikka-httpd', 'python', None),
            ('prewikka-crontab', 'python', None)
        ],
        'prewikka': [
            ('**.py', 'python', None),
            ('**/templates/*.mak', 'mako', None)
        ]
    }
)
