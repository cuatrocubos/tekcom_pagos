import frappe
from frappe.model.document import Document

from tekcom_pagos.tekcom_pagos.doctype.configuraciones_de_pagos_y_viaticos.configuraciones_de_pagos_y_viaticos import (
  get_configuraciones_cuentas, get_configuraciones_de_pagos
)

def before_validate_event(doc, method=None):
  user = frappe.session.user
  update_workflow_details(doc, user)

def update_workflow_details(doc, user=None):
  old_doc = Document.get_doc_before_save(doc)
  
  configuracion_pagos = get_configuraciones_de_pagos(doc.company, doc.cost_center)
  
  if doc.workflow_status == 'Draft':
    doc.custom_aprobador = configuracion_pagos["aprobador_predeterminado"]
    
  if doc.custom_aprobador == None or doc.custom_aprobador == '':
    doc.custom_aprobador = configuracion_pagos["aprobador_predeterminado"]

  if old_doc != None:
    if old_doc.workflow_status != doc.workflow_status:
      if (doc.workflow_status) == 'Solicitado' and doc.custom_fecha_hora_solicitud == None:
        # set fecha hora revision
        doc.custom_fecha_hora_solicitud = frappe.utils.now_datetime()
        if doc.custom_solicitado_por == None or doc.custom_solicitado_por == '':
          doc.custom_solicitado_por = frappe.session.user
      if (doc.workflow_status) == 'Approved' and doc.custom_fecha_hora_aprobacion == None:
        # set fecha hora aprobacion
        doc.custom_fecha_hora_aprobacion = frappe.utils.now_datetime()
        if doc.custom_aprobado_por == None or doc.custom_aprobado_por == '':
          doc.custom_aprobado_por = user
      if (doc.workflow_status == 'Rejected'):
        doc.custom_aprobador = ''
        doc.custom_aprobado_por = ''
        doc.custom_solicitado_por = ''
        doc.custom_fecha_hora_solicitud = ''
        doc.custom_fecha_hora_aprobacion = ''
        