# Copyright (c) 2024, Cuatrocubos Soluciones and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FirmaDigital(Document):
  def validate(self):
    user_id = frappe.get_value("Employee", self.employee, ["user_id"])
    self.user = user_id