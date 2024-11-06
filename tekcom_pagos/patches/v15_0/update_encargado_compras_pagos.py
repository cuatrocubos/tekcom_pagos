import frappe
from frappe.model.document import Document

def execute():
  frappe.reload_doc('Solicitudes de Pagos','doctype','Configuracion de Solicitudes de Pago')
  frappe.db.set_single_value('Configuracion de Solicitudes de Pago','encargado_compras','sarrazola@tekcomca.com',update_modified=False)