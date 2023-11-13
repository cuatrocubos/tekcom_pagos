# Copyright (c) 2023, Cuatrocubos Soluciones and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ComprobantedeSolicituddePago(Document):
	@property
	def cost_center(self):
		if (self.reference_doctype and self.reference_name):
			cc = frappe.db.get_value(self.reference_doctype, self.reference_name, "cost_center")
			return cc
		else:
			return ""