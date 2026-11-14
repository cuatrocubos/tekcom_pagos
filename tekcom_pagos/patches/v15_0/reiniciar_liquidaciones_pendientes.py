import frappe

from tekcom_pagos.viaticos.doctype.liquidacion_de_viaticos.liquidacion_de_viaticos import get_devuelto_en_planilla


def execute():
	"""Liquidaciones waiting in En Revisión Contable (after cerrar_viaticos_2025 only the recent ones) are posted by
	Contabilizar now: drop the draft Journal Entries the previous flow prepared for them, and put their Employee
	Advance back to the state Contabilizar starts from (nothing claimed, returned = payroll returns linked to it).
	The previous flow and hrms left claimed/returned amounts on these advances that no submitted entry backs."""
	for liquidacion, solicitud in frappe.get_all(
		"Liquidacion de Viaticos",
		filters={"docstatus": 0, "workflow_status": "En Revisión Contable"},
		fields=["name", "solicitud_de_viaticos"],
		as_list=True,
	):
		for je in frappe.get_all(
			"Journal Entry",
			filters={"docstatus": 0, "title": ["like", f"%Liquidación de viáticos {liquidacion} contra anticipo%"]},
			pluck="name",
		):
			frappe.delete_doc("Journal Entry", je, ignore_permissions=True)

		employee_advance = solicitud and frappe.db.get_value(
			"Employee Advance", {"solicitud_de_viaticos": solicitud, "docstatus": 1}, "name"
		)
		if not employee_advance:
			continue
		frappe.db.set_value(
			"Employee Advance",
			employee_advance,
			{"claimed_amount": 0, "return_amount": get_devuelto_en_planilla(employee_advance)},
			update_modified=False,
		)
		doc = frappe.get_doc("Employee Advance", employee_advance)
		doc.set_status()
		doc.db_set("status", doc.status, update_modified=False)
