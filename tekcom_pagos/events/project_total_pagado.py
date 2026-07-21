import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import flt

PAID_STATUSES = ("Pagado", "Contabilizado", "Entregado a Contabilidad")

def calculate_total_pagado_solicitud_de_pago(project: str | None = None):
	if not project:
		return 0.0
	SDP = frappe.qb.DocType("Solicitud de Pago")
	result = (
		frappe.qb.from_(SDP)
		.select(Sum(SDP.monto_solicitado_base))
		.where(
			(SDP.project == project)
			& (SDP.workflow_status.isin(PAID_STATUSES))
		)
		.run()
	)
	return flt(result[0][0]) if result and result[0][0] is not None else 0.0