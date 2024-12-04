import frappe
from frappe.model.document import Document

def execute():
  frappe.reload_doc('Viaticos','doctype','Solicitud de Viaticos')
  solicitud_de_viaticos = frappe.qb.DocType("Solicitud de Viaticos")

  frappe.qb.update(solicitud_de_viaticos).set(solicitud_de_viaticos.currency,"HNL").where(solicitud_de_viaticos.currency.is_null()).run()
  