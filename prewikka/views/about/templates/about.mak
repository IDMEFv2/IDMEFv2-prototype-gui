<div class="container">
  <div class="widget" role="dialog" aria-labelledby="dialogLabel" aria-hidden="true">
    <link rel="stylesheet" type="text/css" href="about/css/about.css" />

    <div class="modal-header">
      <button type="button" class="close" data-dismiss="modal">&times;</button>
      <h5 class="modal-title">${ _("Safe4SOC prototype") }</h5>
    </div>

    <div class="modal-body about">
      <div class="software">
        <div class="col-sm-4">
          <img src="prewikka/images/S4SOC-logo.png"/>
        </div>
        <div class="col-sm-8">
          ${ _("This piece of software is the Safe4SOC project's prototype for an IDMEFv2 implementation. Please do not use it in a production environment.") }
          <br><br>
          ${ _("More information:") }
          <ul>
            <li><a href="https://www.idmefv2.org">www.idmefv2.org</a></li>
            <li><a href="https://github.com/IDMEFv2">github.com/IDMEFv2</a></li>
          </ul>
        </div>
      </div>
    </div>

    <div class="modal-footer">
      <button class="btn btn-default widget-only" aria-hidden="true" data-dismiss="modal">${ _('Close') }</button>
    </div>
  </div>
</div>
