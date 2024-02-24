# -*- coding: utf-8 -*-
# Copyright (C) 2016-2021 CS GROUP - France. All Rights Reserved.
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

import cgi
import glob
import io
import sys
import yaml

try:
    import pydot
    WITH_PYDOT = True
except ImportError:
    WITH_PYDOT = False

_LINK_TAG = 'IDMEF_NAV_LINK_TAG'


class Schema(dict):
    def __init__(self, folder):
        self.folder = folder

    def image_load(self):
        self.data_load()

        for struct in self._data_load():
            with io.open("%s/graph/%s.svg" % (self.folder, struct["name"]), 'r', encoding="utf8") as stream:
                self[struct["name"]]["svg"] = stream.read()

    def data_load(self):
        for struct in self._data_load():
            self[struct["name"]] = struct

    def _data_load(self):
        for f in glob.glob("%s/yaml/*.yml" % self.folder):
            with io.open(f, 'r', encoding='utf-8') as stream:
                yield yaml.safe_load(stream)

    @staticmethod
    def quote_val(val):
        return '"%s"' % val

    def graphviz(self, idmef_class, direction='LR', link_format=None, format='svg'):
        dot = pydot.Dot(graph_name=self.quote_val(idmef_class), format=format, bgcolor='transparent')
        dot.set_graph_defaults(rankdir=direction)
        dot.set_node_defaults(shape='plaintext')

        self.add_node(dot, idmef_class, link_format)

        return dot

    def gen_all(self, direction='LR', link_format=None):
        for name in self:
            self.graphviz(name, direction, link_format, 'svg').write("%s/graph/%s.svg" % (self.folder, name), format='svg')

    def add_node(self, dot, node_name, link_format=None, nodes=None):
        if node_name not in self:
            return

        if not nodes:
            nodes = {}

        nodes[node_name] = True

        color = self[node_name].get("color", "#FFFFFF")
        link = link_format % node_name if link_format else "#"

        label = """<
        <table BORDER="0" CELLBORDER="1" CELLSPACING="0">
        <tr>
            <td BGCOLOR="{color}" HREF="{link}" TITLE="{title}">{name}</td>
        </tr>
        """.format(
            color=self.darken_color(color),
            link=link,
            title=cgi.escape(self[node_name].get("description"), quote=True),
            name=node_name
        )

        for key, value in self[node_name].get("childs", {}).items():
            if key not in self:
                continue

            if key not in nodes:
                self.add_node(dot, key, link_format, nodes)

            args = {'dir': 'back',
                    'arrowtail': 'invempty'}
            if value.get("multiplicity"):
                args['label'] = value.get("multiplicity")

            dot.add_edge(pydot.Edge(self.quote_val(node_name), self.quote_val(key), **args))

        for key, value in self[node_name].get("aggregates", {}).items():
            if key in self:
                if key not in nodes:
                    self.add_node(dot, key, link_format, nodes)

                args = {'dir': 'forward'}
                if value.get("multiplicity"):
                    args['label'] = value.get("multiplicity")

                dot.add_edge(pydot.Edge(self.quote_val(node_name), self.quote_val(key), **args))
                continue

            label += self.graph_attr(key, value, color, link)

        for key, value in self[node_name].get("attributes", {}).items():
            label += self.graph_attr(key, value, color, link)

        label += "</table>>"
        dot.add_node(pydot.Node(self.quote_val(node_name), label=label))

    @staticmethod
    def darken_color(hex_color, amount=0.6):
        hex_color = hex_color.replace('#', '')
        rgb = []
        rgb.append(int(hex_color[0:2], 16) * amount)
        rgb.append(int(hex_color[2:4], 16) * amount)
        rgb.append(int(hex_color[4:6], 16) * amount)

        return "#" + ''.join(["{0:02x}".format(int(c)) for c in rgb])

    @staticmethod
    def graph_attr(name, value, color, link):
        return """<tr><td BGCOLOR="{color}" HREF="{link}" TITLE="{title}" >[{type}] {name} ({mult})</td></tr>""".format(
            color=color,
            link=link,
            title=cgi.escape(value.get("description"), quote=True),
            name=name,
            mult=value.get("multiplicity"),
            type=value.get("type"),
        )


if __name__ == "__main__":
    if not WITH_PYDOT:
        print('You need pydot to update graphs.')
        sys.exit(1)

    schema = Schema('htdocs')
    schema.data_load()
    schema.gen_all(link_format="%s?idmef_class=%%s" % _LINK_TAG)
