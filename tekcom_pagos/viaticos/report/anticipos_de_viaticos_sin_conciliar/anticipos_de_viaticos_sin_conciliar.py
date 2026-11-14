# Copyright (c) 2026, Cuatrocubos Soluciones and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

CERRADOS = ("Claimed", "Returned", "Partly Claimed and Returned", "Cancelled", "Draft")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Employee Advance"), "fieldname": "employee_advance", "fieldtype": "Link", "options": "Employee Advance", "width": 160},
		{"label": _("Estado"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Fecha"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 90},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
		{"label": _("Solicitud de Viáticos"), "fieldname": "solicitud_de_viaticos", "fieldtype": "Link", "options": "Solicitud de Viaticos", "width": 180},
		{"label": _("Pagado"), "fieldname": "paid_amount", "fieldtype": "Currency", "options": "currency", "width": 110},
		{"label": _("Liquidado"), "fieldname": "claimed_amount", "fieldtype": "Currency", "options": "currency", "width": 110},
		{"label": _("Devuelto"), "fieldname": "return_amount", "fieldtype": "Currency", "options": "currency", "width": 110},
		{"label": _("Pendiente"), "fieldname": "pendiente", "fieldtype": "Currency", "options": "currency", "width": 110},
		{"label": _("Liquidación"), "fieldname": "liquidacion", "fieldtype": "Link", "options": "Liquidacion de Viaticos", "width": 180},
		{"label": _("Estado Liquidación"), "fieldname": "estado_liquidacion", "fieldtype": "Data", "width": 140},
		{"label": _("Diferencia Liquidación"), "fieldname": "total_reembolso", "fieldtype": "Currency", "options": "currency", "width": 120},
		{"label": _("Fecha Liquidación"), "fieldname": "fecha_liquidacion", "fieldtype": "Date", "width": 100},
		{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "hidden": 1},
	]


def get_data(filters):
	Advance = frappe.qb.DocType("Employee Advance")
	Liquidacion = frappe.qb.DocType("Liquidacion de Viaticos")

	query = (
		frappe.qb.from_(Advance)
		.left_join(Liquidacion)
		.on((Liquidacion.solicitud_de_viaticos == Advance.solicitud_de_viaticos) & (Liquidacion.docstatus < 2))
		.select(
			Advance.name.as_("employee_advance"),
			Advance.status,
			Advance.posting_date,
			Advance.employee,
			Advance.employee_name,
			Advance.company,
			Advance.currency,
			Advance.solicitud_de_viaticos,
			Advance.paid_amount,
			Advance.claimed_amount,
			Advance.return_amount,
			Liquidacion.name.as_("liquidacion"),
			Liquidacion.workflow_status.as_("estado_liquidacion"),
			Liquidacion.total_reembolso,
			Liquidacion.fecha_liquidacion,
		)
		.where(Advance.docstatus == 1)
		.where(Advance.solicitud_de_viaticos.isnotnull())
		.where(Advance.status.notin(CERRADOS))
		.orderby(Advance.posting_date)
	)

	if filters.company:
		query = query.where(Advance.company == filters.company)
	if filters.employee:
		query = query.where(Advance.employee == filters.employee)
	if filters.from_date:
		query = query.where(Advance.posting_date >= filters.from_date)
	if filters.to_date:
		query = query.where(Advance.posting_date <= filters.to_date)
	if filters.solo_liquidadas:
		query = query.where(Liquidacion.docstatus == 1)

	data = query.run(as_dict=True)
	for row in data:
		row.pendiente = flt(row.paid_amount) - flt(row.claimed_amount) - flt(row.return_amount)

	return data
