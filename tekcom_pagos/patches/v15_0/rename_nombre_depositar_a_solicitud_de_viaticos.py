import frappe
from frappe.model.document import Document
from frappe.model.utils.rename_field import rename_field

def execute():
  frappe.reload_doc('Viaticos','doctype','Solicitud de Viaticos')
  try:
    rename_field("Solicitud de Viaticos", "nombre_depositar_a", "custom_nombre_depositar_a")
    
  except Exception as e:
    if e.args[0] != 1054:
      raise
    
  if not frappe.db.has_column("nombre_depositar_a"):
    return