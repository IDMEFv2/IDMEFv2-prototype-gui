<%
    def get_panel_class(priority):
        return {
            "low": "panel-success",
            "medium": "panel-warning",
            "high": "panel-danger"
        }.get(priority, "panel-default")
%>

<div class="container">
  <div class="widget ui-front" role="dialog" aria-labelledby="dialogLabel" aria-hidden="true" data-backdrop="false" data-draggable="true" data-widget-options="modal-lg">

    <div class="modal-header">
      <button type="button" class="close" data-dismiss="modal" aria-hidden="true">&times;</button>
      <h5 class="modal-title" id="dialogLabel">${_("Summary")}</h5>
    </div>

    <div class="modal-body">
      <div class="panel panel-theme">
        <div class="panel-heading">
          <h3 class="panel-title">${ _("Alert") }</h3>
        </div>
        <div class="panel-body">
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("Create time") }</th>
              <th>${ _("Start time") }</th>
              <th>${ _("End time") }</th>
            </tr>
            <tr>
              <td>${ alert.get('create_time') }</td>
              <td>${ alert.get('start_time') }</td>
              <td>${ alert.get('end_time') }</td>
            </tr>
          </table>
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("Category") }</th>
              <th>${ _("Description") }</th>
              <th>${ _("Note") }</th>
            </tr>
            <tr>
              <td>${ ", ".join(alert.get('category', []) + alert.get('ext_category', [])) }</td>
              <td>${ alert.get('description') }</td>
              <td>${ alert.get('note') }</td>
            </tr>
          </table>
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("Entity") }</th>
              <th>${ _("Priority") }</th>
              <th>${ _("Status") }</th>
              <th>${ _("References") }</th>
            </tr>
            <tr>
              <td>${ alert.get('entity') }</td>
              <td>${ alert.get('priority') }</td>
              <td>${ alert.get('status') }</td>
              <td>${ ", ".join(alert.get('reference', [])) }</td>
            </tr>
          </table>
        </div>
      </div>
      <div class="panel panel-theme">
        <div class="panel-heading">
          <h3 class="panel-title">${ _("Analyzer") }</h3>
        </div>
        <div class="panel-body">
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("Category") }</th>
              <th>${ _("Data") }</th>
              <th>${ _("Geolocation") }</th>
              <th>${ _("Hostname") }</th>
              <th>${ _("IP") }</th>
            </tr>
            <tr>
              <td>${ ", ".join(alert.get('analyzer').get('category', []) + alert.get('analyzer').get('ext_category', [])) }</td>
              <td>${ ", ".join(alert.get('analyzer').get('data', []) + alert.get('analyzer').get('ext_data', [])) }</td>
              <td>${ alert.get('analyzer').get('geolocation') }</td>
              <td>${ alert.get('analyzer').get('hostname') }</td>
              <td>${ alert.get('analyzer').get('ip') }</td>
            </tr>
          </table>
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("Location") }</th>
              <th>${ _("Model") }</th>
              <th>${ _("Method") }</th>
            </tr>
            <tr>
              <td>${ alert.get('analyzer').get('location') }</td>
              <td>${ alert.get('analyzer').get('model') }</td>
              <td>${ ", ".join(alert.get('analyzer').get('method', []) + alert.get('analyzer').get('ext_method', [])) }</td>
            </tr>
          </table>
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("Name") }</th>
              <th>${ _("Type") }</th>
              <th>${ _("UN Location") }</th>
            </tr>
            <tr>
              <td>${ alert.get('analyzer').get('name') }</td>
              <td>${ alert.get('analyzer').get('type') }</td>
              <td>${ alert.get('analyzer').get('un_location') }</td>
            </tr>
          </table>
        </div>
      </div>
      % if alert.get('sensor'):
      <div class="panel panel-theme">
        <div class="panel-heading">
          <h3 class="panel-title">${ _("Sensor") }</h3>
        </div>
        <div class="panel-body">
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("Name") }</th>
              <th>${ _("Model") }</th>
              <th>${ _("Hostname") }</th>
              <th>${ _("IP") }</th>
              <th>${ _("Location") }</th>
            </tr>
            <tr>
              <td>${ alert.get('sensor')[0].get('name') }</td>
              <td>${ alert.get('sensor')[0].get('model') }</td>
              <td>${ alert.get('sensor')[0].get('hostname') }</td>
              <td>${ alert.get('sensor')[0].get('ip') }</td>
              <td>${ alert.get('sensor')[0].get('location') }</td>
            </tr>
          </table>
        </div>
      </div>
      % endif
      % if alert.get('source'):
      <div class="panel panel-theme">
        <div class="panel-heading">
          <h3 class="panel-title">${ _("Source") }</h3>
        </div>
        <div class="panel-body">
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("Hostname") }</th>
              <th>${ _("IP") }</th>
              <th>${ _("Location") }</th>
            </tr>
            <tr>
              <td>${ alert.get('source')[0].get('hostname') }</td>
              <td>${ alert.get('source')[0].get('ip') }</td>
              <td>${ alert.get('source')[0].get('location') }</td>
            </tr>
          </table>
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("Service") }</th>
              <th>${ _("Port") }</th>
              <th>${ _("Email") }</th>
              <th>${ _("User") }</th>
            </tr>
            <tr>
              <td>${ alert.get('source')[0].get('service') }</td>
              <td>${ ", ".join([str(x) for x in alert.get('source')[0].get('port', [])]) }</td>
              <td>${ alert.get('source')[0].get('email') }</td>
              <td>${ alert.get('source')[0].get('user') }</td>
            </tr>
          </table>
        </div>
      </div>
      % endif
      % if alert.get('target'):
      <div class="panel panel-theme">
        <div class="panel-heading">
          <h3 class="panel-title">${ _("Target") }</h3>
        </div>
        <div class="panel-body">
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("Hostname") }</th>
              <th>${ _("IP") }</th>
              <th>${ _("Location") }</th>
            </tr>
            <tr>
              <td>${ alert.get('target')[0].get('hostname') }</td>
              <td>${ alert.get('target')[0].get('ip') }</td>
              <td>${ alert.get('target')[0].get('location') }</td>
            </tr>
          </table>
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("Service") }</th>
              <th>${ _("Port") }</th>
              <th>${ _("Email") }</th>
              <th>${ _("User") }</th>
            </tr>
            <tr>
              <td>${ alert.get('target')[0].get('service') }</td>
              <td>${ ", ".join([str(x) for x in alert.get('target')[0].get('port', [])]) }</td>
              <td>${ alert.get('target')[0].get('email') }</td>
              <td>${ alert.get('target')[0].get('user') }</td>
            </tr>
          </table>
        </div>
      </div>
      % endif
      % if alert.get('vector'):
      <div class="panel panel-theme">
        <div class="panel-heading">
          <h3 class="panel-title">${ _("Vector") }</h3>
        </div>
        <div class="panel-body">
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("Name") }</th>
              <th>${ _("Size") }</th>
              <th>${ _("Location") }</th>
            </tr>
            <tr>
              <td>${ alert.get('vector')[0].get('name') }</td>
              <td>${ alert.get('vector')[0].get('size') }</td>
              <td>${ alert.get('vector')[0].get('location') }</td>
            </tr>
          </table>
        </div>
      </div>
      % endif
      % if alert.get('attachment'):
      <div class="panel panel-theme">
        <div class="panel-heading">
          <h3 class="panel-title">${ _("Attachment") }</h3>
        </div>
        <div class="panel-body">
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("File name") }</th>
              <th>${ _("Hash") }</th>
              <th>${ _("Size") }</th>
              <th>${ _("Content type") }</th>
            </tr>
            <tr>
              <td>${ alert.get('attachment')[0].get('file_name') }</td>
              <td>${ alert.get('attachment')[0].get('hash') }</td>
              <td>${ alert.get('attachment')[0].get('size') }</td>
              <td>${ alert.get('attachment')[0].get('content_type') }</td>
            </tr>
          </table>
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("Content") }</th>
            </tr>
            <tr>
              <td>${ alert.get('attachment')[0].get('content') }</td>
            </tr>
          </table>
        </div>
      </div>
      % endif
    </div>

    <div class="modal-footer">
      <button class="btn btn-default widget-only" aria-hidden="true" data-dismiss="modal">${ _('Close') }</button>
    </div>

  </div>
</div>
