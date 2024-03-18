# Copyright (c) 2024, Cuatrocubos Soluciones and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ConfiguraciondeViaticos(Document):
	pass

@frappe.whitelist()
def get_users_by_role(role):
  usuarios = []
  usuarios = frappe.get_all(
    "Has Role", filters={"role": ['like', role], "parenttype": "User"}, fields=["parent"]
  )
  return usuarios
