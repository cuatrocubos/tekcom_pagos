import frappe
from frappe.model.document import Document

def before_validate_event(doc, method=None):
  user = frappe.session.user
  update_workflow_details(doc, user)

@frappe.whitelist()
def get_configuracion_pagos(doc):
  configuracion_pagos = frappe.get_doc('Configuracion de Solicitudes de Pago')
  configuracion_centro_costos = configuracion_pagos.cost_center_predeterminados
  
  aprobador_predeterminado = configuracion_pagos.aprobador_predeterminado
  encargado_compras = configuracion_pagos.encargado_compras
  if len(configuracion_centro_costos) > 0:
    cc_predeterminado = next((ele for ele in configuracion_centro_costos if ele.cost_center == doc.cost_center), None)

    if cc_predeterminado != None:
      if cc_predeterminado.aprobador_predeterminado != None:
        aprobador_predeterminado = cc_predeterminado.aprobador_predeterminado
        
  return {
    "aprobador_predeterminado": aprobador_predeterminado,
    "encargado_compras": encargado_compras
  }

def update_workflow_details(doc, user=None):
  old_doc = Document.get_doc_before_save(doc)
  
  configuracion_pagos = get_configuracion_pagos(doc)
  
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
        