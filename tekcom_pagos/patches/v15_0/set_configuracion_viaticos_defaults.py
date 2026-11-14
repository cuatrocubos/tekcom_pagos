import frappe


def execute():
	frappe.reload_doc("Tekcom Pagos", "doctype", "configuraciones_de_pagos_y_viaticos")

	values = {"limite_solicitudes_sin_liquidar": 3}
	for fieldname, component in (
		("componente_deduccion_viaticos", "DEDUCCION VIATICOS"),
		("componente_reembolso_viaticos", "REEMBOLSO VIATICOS"),
	):
		if frappe.db.exists("Salary Component", component):
			values[fieldname] = component

	for fieldname, value in values.items():
		frappe.db.set_single_value("Configuraciones de Pagos y Viaticos", fieldname, value, update_modified=False)
