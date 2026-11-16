import frappe

from tekcom_pagos.solicitudes_de_pagos.doctype.solicitud_de_pago.solicitud_de_pago import (
	get_fecha_contabilizacion_solicitud_pago,
)


def execute():
	frappe.reload_doc("Solicitudes de Pagos", "doctype", "solicitud_de_pago")

	# solicitudes already paid: the date of their payment
	for query in (
		"""UPDATE `tabSolicitud de Pago` sp
		JOIN (SELECT solicitud_de_pago, MIN(posting_date) posting_date FROM `tabPayment Entry`
			WHERE docstatus = 1 AND IFNULL(solicitud_de_pago, '') != '' GROUP BY solicitud_de_pago) pe
			ON pe.solicitud_de_pago = sp.name
		SET sp.posting_date = pe.posting_date
		WHERE sp.posting_date IS NULL""",
		"""UPDATE `tabSolicitud de Pago` sp
		JOIN `tabEmployee Advance` ea ON ea.solicitud_de_pago = sp.name AND ea.docstatus = 1
		SET sp.posting_date = ea.posting_date
		WHERE sp.posting_date IS NULL""",
		"""UPDATE `tabSolicitud de Pago` sp
		JOIN (SELECT bill_no, MIN(posting_date) posting_date FROM `tabJournal Entry`
			WHERE docstatus < 2 AND IFNULL(bill_no, '') != '' GROUP BY bill_no) je
			ON je.bill_no = sp.name
		SET sp.posting_date = je.posting_date
		WHERE sp.posting_date IS NULL""",
	):
		frappe.db.sql(query)

	# paid but not posted yet: what validate would set (docs may be submitted, so no doc.save())
	pendientes = frappe.get_all(
		"Solicitud de Pago",
		filters={"posting_date": ["is", "not set"], "reference_date": ["is", "set"], "docstatus": ["<", 2]},
		fields=["name", "reference_date", "company", "party_type", "party"],
	)
	for solicitud in pendientes:
		gastos_varios = frappe.db.get_value(
			"Comprobante de Solicitud de Pago", {"parent": solicitud.name, "parenttype": "Solicitud de Pago", "idx": 1}, "reference_doctype"
		) == "Gastos Varios"
		posting_date = get_fecha_contabilizacion_solicitud_pago(
			solicitud.reference_date, solicitud.company, solicitud.party_type, solicitud.party, gastos_varios
		)
		frappe.db.set_value("Solicitud de Pago", solicitud.name, "posting_date", posting_date, update_modified=False)
