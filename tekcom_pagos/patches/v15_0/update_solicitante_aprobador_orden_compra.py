import frappe
from frappe.query_builder.functions import IfNull

from tekcom_pagos.events.purchase_order_events import (
  get_configuracion_pagos,
  update_workflow_details
)

def execute():
  purchase_orders = frappe.db.get_all("Purchase_order")
  
  for purchase_order in purchase_orders:
    # purchase_order_doc = frappe.get_doc('Purchase Order', purchase_order.name)
    
    solicitante_details = frappe.get_all('Comment', filters={'comment_type': 'Workflow','content':'Solicitado','reference_doctype':'Purchase Order','reference_name':purchase_order.name}, fields=['creation','comment_email'], order_by='creation desc')
    
    aprobador_details = frappe.get_all('Comment', filters={'comment_type': 'Workflow','content':'Aprobado','reference_doctype':'Purchase Order','reference_name':purchase_order.name}, fields=['creation','comment_email'], order_by='creation desc')
    
    configuracion_pagos = get_configuracion_pagos(purchase_order)
    
    if purchase_order.custom_aprobador == None:
      frappe.db.set_value('Purchase Order', purchase_order.name, 'custom_aprobador', configuracion_pagos.aprobador_predeterminado)
    if purchase_order.custom_encargado_compras == None:
      frappe.db.set_value('Purchase Order', purchase_order.name, 'custom_encargado_compras', configuracion_pagos.encargado_compras)
    
    if len(solicitante_details) > 0:
      solicitante = solicitante_details[0]
      solicitante = solicitante.comment_email
      fecha_solicitud = solicitante.creation
      
      if purchase_order.custom_solicitado_por == None:
        frappe.db.set_value('Purchase Order', purchase_order.name, 'custom_solicitado_por', solicitante)
        frappe.db.set_value('Purchase Order', purchase_order.name, 'custom_fecha_hora_solicitud', fecha_solicitud)
        
      if purchase_order.docstatus == 1 and len(aprobador_details) > 0:
        aprobacion = aprobador_details[0]
        aprobador = aprobacion.comment_email
        fecha_aprobacion = aprobacion.creation
      
        frappe.db.set_value('Purchase Order', purchase_order.name, 'custom_aprobado_por', aprobador)
        frappe.db.set_value('Purchase Order', purchase_order.name, 'custom_fecha_hora_solicitud', fecha_aprobacion)
    
      # if (purchase_order.workflow_status == 'Rejected'):
      #   pass
      