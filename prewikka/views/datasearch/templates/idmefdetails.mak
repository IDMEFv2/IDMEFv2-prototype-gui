<%
    def get_panel_class(severity):
        return {
            "low": "panel-success",
            "medium": "panel-warning",
            "high": "panel-danger"
        }.get(severity, "panel-default")
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
              <th>${ _("Cease time") }</th>
            </tr>
            <tr>
              <td>${ alert.get('create_time') }</td>
              <td>${ alert.get('start_time') }</td>
              <td>${ alert.get('cease_time') }</td>
            </tr>
          </table>
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("Category") }</th>
              <th>${ _("Description") }</th>
              <th>${ _("Note") }</th>
            </tr>
            <tr>
              <td>${ ", ".join(alert.get('category', [])) }</td>
              <td>${ alert.get('description') }</td>
              <td>${ alert.get('note') }</td>
            </tr>
          </table>
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("Entity") }</th>
              <th>${ _("Severity") }</th>
              <th>${ _("Status") }</th>
              <th>${ _("References") }</th>
            </tr>
            <tr>
              <td>${ alert.get('entity') }</td>
              <td>${ alert.get('severity') }</td>
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
              <th>${ _("Name") }</th>
              <th>${ _("Model") }</th>
              <th>${ _("Hostname") }</th>
              <th>${ _("IP") }</th>
              <th>${ _("Location") }</th>
            </tr>
            <tr>
              <td>${ alert.get('analyzer.name') }</td>
              <td>${ alert.get('analyzer.model') }</td>
              <td>${ alert.get('analyzer.hostname') }</td>
              <td>${ alert.get('analyzer.ip') }</td>
              <td>${ alert.get('analyzer.location') }</td>
            </tr>
          </table>
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("Category") }</th>
              <th>${ _("Data") }</th>
              <th>${ _("Method") }</th>
            </tr>
            <tr>
              <td>${ ", ".join(alert.get('analyzer.category', [])) }</td>
              <td>${ ", ".join(alert.get('analyzer.data', [])) }</td>
              <td>${ ", ".join(alert.get('analyzer.method', [])) }</td>
            </tr>
          </table>
        </div>
      </div>
      % if alert.get('sensor.name'):
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
              <td>${ alert.get('sensor.name') }</td>
              <td>${ alert.get('sensor.model') }</td>
              <td>${ alert.get('sensor.hostname') }</td>
              <td>${ alert.get('sensor.ip') }</td>
              <td>${ alert.get('sensor.location') }</td>
            </tr>
          </table>
        </div>
      </div>
      % endif
      % if alert.get('source.ip'):
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
              <td>${ alert.get('source.hostname') }</td>
              <td>${ alert.get('source.ip') }</td>
              <td>${ alert.get('source.location') }</td>
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
              <td>${ alert.get('source.service') }</td>
              <td>${ ", ".join(alert.get('source.port', [])) }</td>
              <td>${ alert.get('source.email') }</td>
              <td>${ alert.get('source.user') }</td>
            </tr>
          </table>
        </div>
      </div>
      % endif
      % if alert.get('target.ip'):
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
              <td>${ alert.get('target.hostname') }</td>
              <td>${ alert.get('target.ip') }</td>
              <td>${ alert.get('target.location') }</td>
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
              <td>${ alert.get('target.service') }</td>
              <td>${ ", ".join(alert.get('target.port', [])) }</td>
              <td>${ alert.get('target.email') }</td>
              <td>${ alert.get('target.user') }</td>
            </tr>
          </table>
        </div>
      </div>
      % endif
      % if alert.get('vector.name'):
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
              <td>${ alert.get('vector.name') }</td>
              <td>${ alert.get('vector.size') }</td>
              <td>${ alert.get('vector.location') }</td>
            </tr>
          </table>
        </div>
      </div>
      % endif
      % if alert.get('attachment.file_name'):
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
              <td>${ alert.get('attachment.file_name') }</td>
              <td>${ alert.get('attachment.hash') }</td>
              <td>${ alert.get('attachment.size') }</td>
              <td>${ alert.get('attachment.content_type') }</td>
            </tr>
          </table>
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("Content") }</th>
            </tr>
            <tr>
              <td>${ alert.get('attachment.content') }</td>
            </tr>
          </table>
        </div>
      </div>
      % endif
      % if alert.get('observable.name'):
      <div class="panel panel-theme">
        <div class="panel-heading">
          <h3 class="panel-title">${ _("Observable") }</h3>
        </div>
        <div class="panel-body">
          <table class="table table-striped table-bordered">
            <tr>
              <th>${ _("Name") }</th>
              <th>${ _("Reference") }</th>
              <th>${ _("Content") }</th>
            </tr>
            <tr>
              <td>${ alert.get('observable.name') }</td>
              <td>${ alert.get('observable.reference') }</td>
              <td>${ alert.get('observable.content') }</td>
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
