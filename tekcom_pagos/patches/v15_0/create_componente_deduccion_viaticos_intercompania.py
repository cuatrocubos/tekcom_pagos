import frappe

COMPONENTE = "DEDUCCION VIATICOS INTERCOMPAÑIA"


def execute():
	"""Deduction for a liquidacion balance when the employee is in another company's payroll than the advance's.
	Its account is the viáticos clearing account 20010111 of each company (also used by REEMBOLSO VIATICOS):
	Contabilizar debits it against the payable to the advance's company and payroll credits it back."""
	frappe.reload_doc("Tekcom Pagos", "doctype", "configuraciones_de_pagos_y_viaticos")

	if not frappe.db.exists("Salary Component", COMPONENTE):
		componente = frappe.get_doc({
			"doctype": "Salary Component",
			"salary_component": COMPONENTE,
			"salary_component_abbr": "D-VIAT-IC",
			"type": "Deduction",
			"description": "Deducción del saldo de una liquidación de viáticos cuyo anticipo es de otra compañía",
			"exempted_from_income_tax": 1,
			"remove_if_zero_valued": 1,
			"depends_on_payment_days": 0,
		})
		for company, account in frappe.get_all(
			"Account", filters={"account_number": "20010111", "is_group": 0}, fields=["company", "name"], as_list=True
		):
			componente.append("accounts", {"company": company, "account": account})
		componente.insert(ignore_permissions=True)

	frappe.db.set_single_value(
		"Configuraciones de Pagos y Viaticos", "componente_deduccion_viaticos_intercompania", COMPONENTE, update_modified=False
	)
