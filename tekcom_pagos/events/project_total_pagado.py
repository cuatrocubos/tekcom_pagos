import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import flt

PAID_STATUSES = ("Pagado", "Contabilizado", "Entregado a Contabilidad")
PAID_VIATICOS_STATUSES = (
	"Pagado",
	"Recibido en Contabilidad",
	"Entregado a Contabilidad",
	"Contabilizado",
)

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


def calculate_total_pagado_solicitudes_viaticos(project: str | None = None):
	if not project:
		return 0.0

	SV = frappe.qb.DocType("Solicitud de Viaticos")
	LV = frappe.qb.DocType("Liquidacion de Viaticos")
	rows = (
		frappe.qb.from_(SV)
		.left_join(LV)
		.on(LV.solicitud_de_viaticos == SV.name)
		.select(SV.name, SV.total_anticipo_solicitado_base, Sum(LV.total_ejecutado))
		.where((SV.project == project) & (SV.workflow_status.isin(PAID_VIATICOS_STATUSES)))
		.groupby(SV.name, SV.total_anticipo_solicitado_base)
		.run()
	)

	return flt(
		sum(
			flt(liquidated_amount)
			if liquidated_amount is not None
			else flt(requested_amount)
			for _, requested_amount, liquidated_amount in rows
		)
	)
