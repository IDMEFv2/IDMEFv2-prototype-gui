import pkg_resources
from datetime import datetime
import requests
import json
from prewikka import database, template, view, error, mainmenu, response
from prewikka.dataprovider import Criterion
import base64

class InputPluginDatabase(database.DatabaseHelper):
    def get_files(self, fileid = None):
        q = "SELECT id, list_name, list_content FROM Prewikka_inputplugin"
        if fileid is not None:
            q = q + " WHERE id = %s"
            rows = self.query(q, fileid)
        else:
            rows = self.query(q)
        return list(rows)

    def add_file(self, a , b):
        env.log.warning(b)
        try:
            js = json.loads(b)
        except:
            raise error.PrewikkaUserError(N_("Wrong file format 1"), N_("Wrong file format"))
        env.log.warning(js)
        env.log.warning(type(js))
        env.log.warning(isinstance(js, list))
        env.log.warning(isinstance(js, object))
        if isinstance(js, list):
            if "Version" in js[0] and js[0]["Version"].startswith('2.'):
                data = js
            else:
                raise error.PrewikkaUserError(N_("Wrong file format 2"), N_("Wrong file format"))
        elif isinstance(js, object):
            if "Version" in js and js["Version"].startswith('2.'):
                data = [js]
            else:
                raise error.PrewikkaUserError(N_("Wrong file format 3"), N_("Wrong file format"))
        else:
            raise error.PrewikkaUserError(N_("Wrong file format 4"), N_("Wrong file format"))

        self.query("INSERT INTO Prewikka_inputplugin (list_name, list_content) VALUES (%s, %s)",a, json.dumps(data))

    def delete_file(self, file_id):
        self.query("DELETE FROM Prewikka_inputplugin WHERE id = %s", file_id)

class InputPluginView(view.View):
    plugin_htdocs = (("inputplugin", pkg_resources.resource_filename(__name__, 'htdocs')),)
    _db = InputPluginDatabase()

    def __init__(self):
        view.View.__init__(self)

    def insert_idmefv2(self, idmefv2):
        url = "http://logstash:4690"
        resp = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(idmefv2))

    @view.route("/inputplugin", methods=["GET"], permissions=[N_("IDMEF_VIEW")], menu=(N_("Alerts"), N_("Inject IDMEFv2")))
    def inputplugin(self):
        dset = template.PrewikkaTemplate(__name__, "templates/inputplugin.mak").dataset()
        dset["idmefv2files"] = self._db.get_files()
        return dset.render()

    @view.route("/inputplugin/add_file", methods=["POST"], permissions=[N_("IDMEF_VIEW")])
    def inputplugin_add_file(self):
        self._db.add_file(env.request.parameters["file"].filename, env.request.parameters["file"].value)
        return response.PrewikkaResponse({"type": "reload", "target": "view"})

    @view.route("/inputplugin/delete_file", methods=["POST"], permissions=[N_("IDMEF_VIEW")])
    def inputplugin_delete_file(self):
        self._db.delete_file(env.request.parameters["selfile"])
        return response.PrewikkaResponse({"type": "reload", "target": "view"})

    @view.route("/inputplugin/run_file", methods=["POST"], permissions=[N_("IDMEF_VIEW")])
    def inputplugin_run_file(self):
        data = self._db.get_files(env.request.parameters["selfile"])
        ctime = True if env.request.parameters.get("create_time") else False
        for js in json.loads(data[0][2]):
            if ctime:
                js["CreateTime"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            self.insert_idmefv2(js)
        return response.PrewikkaResponse({"type": "reload", "target": "view"})
