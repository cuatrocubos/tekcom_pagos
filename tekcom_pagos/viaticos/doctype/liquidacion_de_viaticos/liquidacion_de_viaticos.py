# Copyright (c) 2023, Cuatrocubos Soluciones and contributors
# For license information, please see license.txt

import frappe
from frappe import ValidationError, _, qb, scrub, throw
from frappe.utils import cint, comma_or, flt, getdate, nowdate, get_link_to_form
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.query_builder.functions import Count
# from frappe.core.doctype import Role
from collections import namedtuple
import erpnext
from erpnext.accounts.doctype.bank_account.bank_account import (
	 get_party_bank_account,
)
from erpnext.accounts.utils import (
	get_fiscal_year,
	get_account_currency, 
	get_balance_on, 
	get_outstanding_invoices,
)
from erpnext.controllers.accounts_controller import get_default_taxes_and_charges
from erpnext.accounts.party import get_party_account as get_party_account_from_accounts
from erpnext.accounts.doctype.payment_entry.payment_entry import (
	PaymentEntry,
	get_payment_entry,
	get_bank_cash_account
)

from hrms.hr.utils import validate_active_employee
from hrms.overrides.employee_payment_entry import (
	get_grand_total_and_outstanding_amount,
	get_paid_amount_and_received_amount,
	get_account_currency,
	get_party_account
)
from tekcom_pagos.solicitudes_de_pagos.doctype.solicitud_de_pago.solicitud_de_pago import (
	get_mode_of_payment_bank_cash_account
)

from tekcom_pagos.tekcom_pagos.doctype.configuraciones_de_pagos_y_viaticos.configuraciones_de_pagos_y_viaticos import (
	get_configuraciones_de_pagos
)
from tekcom_pagos.tekcom_pagos.utils import get_employee_cost_center

class LiquidaciondeViaticos(Document):
	def before_save(self):
		if self.workflow_status == 'Rejected':
			self.revisor = ''
			self.aprobador = ''
			self.revisado_por = ''
			self.aprobado_por = ''
			self.fecha_hora_solicitud = ''
			self.fecha_hora_revision = ''
			self.fecha_hora_aprobacion = ''

	def validate(self):
		if len(self.detalle_liquidacion) == 0:
			frappe.throw(_("Detalle de Liquidación no puede estar vacia"), frappe.ValidationError)
		self.set_expense_account(validate=True)
		self.update_workflow_details()
		if (self.workflow_status == 'Entregado a Talento Humano'):
			self.create_expense_claim(submit=True)
	 
	def set_revision(self):
		if (self.workflow_status) == 'Revisado' and self.fecha_hora_revision == None:
			self.fecha_hora_revision = frappe.utils.now_datetime()
			if self.revisado_por == None or self.revisado_por == '':
				frappe.throw(_("Seleccione un revisor para el documento"), frappe.ValidationError)
		
	def set_aprobado(self):
		if (self.workflow_status) == 'Approved' and self.fecha_hora_aprobacion == None:
			self.fecha_hora_aprobacion = frappe.utils.now_datetime()
			if self.aprobado_por == None or self.aprobado_por == '':
				frappe.throw(_("Seleccione un aprobador para el documento"), frappe.ValidationError)
		
	def update_workflow_details(self):
		old_doc = Document.get_doc_before_save(self)
		
		configuracion_pagos = get_configuraciones_de_pagos(self.company, self.cost_center)

		if self.workflow_status == 'Draft':
			self.revisor = configuracion_pagos["revisor_predeterminado"]
			self.aprobador = configuracion_pagos["aprobador_predeterminado"]
			
		if self.revisor == None or self.revisor == '':
			self.revisor = configuracion_pagos["revisor_predeterminado"]
		if self.aprobador == None or self.aprobador == '':
			self.aprobador = configuracion_pagos["aprobador_predeterminado"]
		
		if old_doc != None:
			if old_doc.workflow_status != self.workflow_status:
				if (self.workflow_status) == 'En Revisión' and self.fecha_hora_revision == None:
					# set fecha hora revision
					self.fecha_hora_solicitud = frappe.utils.now_datetime()
					# if self.solicitado_por == None or self.solicitado_por == '':
					#   self.solicitado_por = frappe.session.user
				if (self.workflow_status) == 'Revisado' and self.fecha_hora_revision == None:
					# set fecha hora revision
					self.fecha_hora_revision = frappe.utils.now_datetime()
					if self.revisado_por == None or self.revisado_por == '':
						self.revisado_por = frappe.session.user
				if (self.workflow_status) == 'Approved' and self.fecha_hora_aprobacion == None:
					# set fecha hora aprobacion
					self.fecha_hora_aprobacion = frappe.utils.now_datetime()
					if self.aprobado_por == None or self.aprobado_por == '':
						self.aprobado_por = frappe.session.user

	def set_expense_account(self, validate=False):
		for expense in self.detalle_liquidacion:
			if not expense.default_account or not validate:
				expense.default_account = get_expense_claim_account(expense.expense_type, self.company)[
					"account"
				]

	def create_expense_claim(self, submit=False):
		# create payment entry
		frappe.flags.ignore_account_permissions = True
		
		docs = []
		
		# STEPS:
		# 1. Check if Employee Advance exists for Solicitud de Viaticos
		# 2. Create Employee Advance
		# # 3. Create Payment Entry for Employee Advance
		# & (advance.paid_amount > 0)
		# 	& (advance.status.notin(["Claimed", "Returned", "Partly Claimed and Returned"]))
		# get_expense_claims = frappe.db.count("Employee Advance", { "solicitud_de_viaticos": self.name, "docstatus": 1, "paid_amount": [">", 0], "status": ["not in", ["Claimed", "Returned", "Partly Claimed and Returned"]]  })
		get_expense_claims = frappe.db.exists("Expense Claim", { "liquidacion_de_viaticos": self.name, "docstatus": 1})
		
		if get_expense_claims:
			return docs
		
		self.create_expense_claim_for_employee(docs, submit)
		
		return docs

	def create_expense_claim_for_employee(self, docs=[], submit=False):
		company = frappe.get_cached_value("Employee", self.solicitante, "company")
		
  	# Get configuraciones de pagos
		configuracion_viaticos = get_configuraciones_de_pagos(company, self.cost_center)
		
		payable_account = configuracion_viaticos["cuenta_anticipo_viaticos"]
		payable_account_currency = frappe.db.get_value("Account", payable_account, "account_currency")
		cost_center = get_employee_cost_center(self.solicitante)
		employee_advance = frappe.get_doc("Employee Advance", {"solicitud_de_viaticos": self.solicitud_de_viaticos, "docstatus": 1})
		# bank_account = get_mode_of_payment_bank_cash_account(self.mode_of_payment, self.company)
		# bank = get_bank_cash_account(self, bank_account)
		
		# party_amount = self.total_anticipo_aprobado
		paid_amount = employee_advance.paid_amount
		claimed_amount = employee_advance.claimed_amount
  
		if company == self.company:
			cost_center = self.cost_center
		
		expense_claim = frappe.new_doc("Expense Claim")
		expense_claim.company = company
		expense_claim.employee = self.solicitante
		expense_claim.expense_approver = self.aprobado_por
		expense_claim.currency = self.currency
		expense_claim.exchange_rate = self.exchange_rate
		expense_claim.liquidacion_de_viaticos = self.name
		expense_claim.approval_status = 'Approved'
		# expense_claim.payable_account = self.party_account
  
		expense_claim.payable_account = payable_account
		expense_claim.cost_center = cost_center
		expense_claim.is_paid = 0
		# expense_claim.total_sanctioned_amount = self.total_ejecutado
		# expense_claim.total_taxes_and_charges = self.total_impuestos
		# expense_claim.total_advance_amount = self.total_solicitado
		# expense_claim.total_claimed_amount = self.total_ejecutado
		# expense_claim.grand_total = self.total_ejecutado
		expense_claim.append(
			"advances",
			{
				"employee_advance": employee_advance.name,
				"posting_date": self.fecha_hora_solicitud,
				"advance_paid": flt(paid_amount),
				"unclaimed_amount": flt(paid_amount) - flt(claimed_amount),
				"allocated_amount": flt(self.total_reembolso),
			},
		)
		
		for expense in self.detalle_liquidacion:
			expense_cost_center = expense.cost_center	
			print("expense_cost_center", expense_cost_center)
			print("cost_center", cost_center)
			if company != self.company:
				expense_cost_center = cost_center
			expense_claim.append("expenses",
				{
					"expense_date": expense.expense_date,
					"expense_type": expense.expense_type,
					"description": expense.description,
					"amount": expense.subtotal,
					"sanctioned_amount": expense.subtotal,
					"cost_center": expense_cost_center,
					# "project": expense.project
				}
			)
		if (self.total_impuestos > 0):
			taxes = get_default_taxes_and_charges("Purchase Taxes and Charges Template", company=company)
			# taxesDict = namedtuple(taxes, taxes.keys())
			taxDetails = taxes.get('taxes')
			expense_claim.append("taxes",
				{
					"account_head": taxDetails[0].account_head,
					"tax_amount": self.total_impuestos,
					"description": taxDetails[0].description,
					"cost_center": taxDetails[0].cost_center,
					# "project": taxDetails[0].project
				}
			)
			expense_claim.total_taxes_and_charges = self.total_impuestos
		# expense_claim.calculate_taxes()

		if submit:
			expense_claim.save(ignore_permissions=True)
			expense_claim.submit()
			# get_payment_entry_for_employee(expense_claim.doctype, expense_claim.name, party_amount, reference_date=self.reference_date, reference_no=self.reference_no, solicitud_de_viaticos=self.name, submit=True)
		else:
			expense_claim.save(ignore_permissions=True)
		docs.append(get_link_to_form(expense_claim.doctype, expense_claim.name))

@frappe.whitelist()
def get_solicitud_de_viaticos(docname):
	doc = frappe.get_doc("Solicitud de Viaticos", docname)

	return doc

@frappe.whitelist()
def get_expense_claim_account(expense_claim_type, company):
	account = frappe.db.get_value(
		"Expense Claim Account", {"parent": expense_claim_type, "company": company}, "default_account"
	)
	if not account:
		frappe.throw(
			_("Set the default account for the {0} {1}").format(
				frappe.bold(_("Expense Claim Type")),
				get_link_to_form("Expense Claim Type", expense_claim_type),
			)
		)

	return {"account": account}

@frappe.whitelist()
def make_expense_claim(docname):
	doc = frappe.get_doc("Liquidacion de Viaticos", docname)
	return doc.create_expense_claim(submit=False)