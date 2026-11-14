import frappe

from tekcom_pagos.viaticos.doctype.solicitud_de_viaticos.solicitud_de_viaticos import (
	get_fecha_contabilizacion_solicitud,
)


def execute():
	frappe.reload_doc("Viaticos", "doctype", "solicitud_de_viaticos")

	# solicitudes with an advance already posted: the advance's date
	frappe.db.sql(
		"""
		UPDATE `tabSolicitud de Viaticos` sv
		JOIN `tabEmployee Advance` ea ON ea.solicitud_de_viaticos = sv.name AND ea.docstatus = 1
		SET sv.posting_date = ea.posting_date
		WHERE sv.posting_date IS NULL
		"""
	)

	# paid but not posted yet: what validate would set (docs may be submitted, so no doc.save())
	pendientes = frappe.get_all(
		"Solicitud de Viaticos",
		filters={"posting_date": ["is", "not set"], "reference_date": ["is", "set"], "docstatus": ["<", 2]},
		fields=["name", "reference_date", "company", "depositar_a"],
	)
	for solicitud in pendientes:
		posting_date = get_fecha_contabilizacion_solicitud(
			solicitud.reference_date, solicitud.company, solicitud.depositar_a
		)
		frappe.db.set_value(
			"Solicitud de Viaticos", solicitud.name, "posting_date", posting_date, update_modified=False
		)
