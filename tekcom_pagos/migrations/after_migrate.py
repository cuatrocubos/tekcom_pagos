import frappe
from frappe.query_builder.functions import IfNull

from tekcom_pagos.events.purchase_order_events import (
  get_configuracion_pagos,
  update_workflow_details
)

def execute():
  update_purchase_order_workflow_details()

def update_purchase_order_workflow_details():
  frappe.reload_doc('buying', 'doctype', 'purchase_order')
  frappe.reload_doc('Solicitudes de Pagos', 'doctype', 'Configuracion de Solicitudes de Pago')
  
  purchase_orders = frappe.db.get_all("Purchase Order")
  
  for purchase_order in purchase_orders:
    # purchase_order_doc = frappe.get_doc('Purchase Order', purchase_order.name)

    solicitante_details = frappe.get_all('Comment', filters={'comment_type': 'Workflow','content':'Solicitado','reference_doctype':'Purchase Order','reference_name':purchase_order.name}, fields=['creation','comment_email'], order_by='creation desc')
    
    configuracion_pagos = get_configuracion_pagos(purchase_order)
    
    if purchase_order.custom_aprobador == None:
      frappe.db.set_value('Purchase Order', purchase_order.name, 'custom_aprobador', configuracion_pagos["aprobador_predeterminado"], update_modified=False)
    if purchase_order.custom_encargado_compras == None:
      frappe.db.set_value('Purchase Order', purchase_order.name, 'custom_encargado_compras', configuracion_pagos["encargado_compras"], update_modified=False)
    
    if len(solicitante_details) > 0:
      solicitante = solicitante_details[0]
      solicitante_email = solicitante.comment_email
      fecha_solicitud = solicitante.creation
      
      if purchase_order.custom_solicitado_por == None:
        frappe.db.set_value('Purchase Order', purchase_order.name, 'custom_solicitado_por', solicitante_email, update_modified=False)
        frappe.db.set_value('Purchase Order', purchase_order.name, 'custom_fecha_hora_solicitud', fecha_solicitud, update_modified=False)
      
      aprobador_details = frappe.get_all('Comment', filters={'comment_type': 'Workflow','content':'Aprobado','reference_doctype':'Purchase Order','reference_name':purchase_order.name}, fields=['creation','comment_email'], order_by='creation desc')
      
      if len(aprobador_details) > 0:
        aprobacion = aprobador_details[0]
        aprobador_email = aprobacion.comment_email
        fecha_aprobacion = aprobacion.creation
      
        frappe.db.set_value('Purchase Order', purchase_order.name, 'custom_aprobado_por', aprobador_email, update_modified=False)
        frappe.db.set_value('Purchase Order', purchase_order.name, 'custom_fecha_hora_aprobacion', fecha_aprobacion, update_modified=False)
    
      # if (purchase_order.workflow_status == 'Rejected'):
      #   pass