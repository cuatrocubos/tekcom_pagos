# Copyright (c) 2023, Cuatrocubos Soluciones and contributors
# For license information, please see license.txt

import frappe
from frappe import ValidationError, _, qb, scrub, throw
from frappe.utils import cint, comma_or, flt, getdate, nowdate, get_link_to_form
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.query_builder.functions import Count
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
from tekcom_pagos.tekcom_pagos.utils import (
  get_configuraciones_cuentas, 
  get_employee_cost_center,
  get_journal_entry_for_employee_advance,
  get_party_account as get_party_account_from_utils
)

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
		
		# Validate that all required fields are present
		# self.validate_required_fields()
		
		self.set_expense_account(validate=True)
		self.update_workflow_details()
		if (self.workflow_status == 'En Revisión Contable'):
			if self.solicitud_de_viaticos:
				frappe.db.set_value("Solicitud de Viaticos", self.solicitud_de_viaticos, "viaticos_liquidados", 1)
			self.create_expense_claim(submit=False)
	
	def validate_required_fields(self):
		"""Validate required fields based on workflow status"""
		if self.workflow_status == 'Revisado' and not self.revisado_por:
			frappe.throw(_("Revisado por es requerido cuando el estado es 'Revisado'"))
		
		if self.workflow_status == 'Approved' and not self.aprobado_por:
			frappe.throw(_("Aprobado por es requerido cuando el estado es 'Approved'"))
		
		if not self.solicitante:
			frappe.throw(_("Solicitante es requerido"))
		
		if not self.fecha_liquidacion:
			frappe.throw(_("Fecha de liquidación es requerida"))
	 
	def set_revision(self):
		if (self.workflow_status) == 'Revisado' and not self.fecha_hora_revision:
			self.fecha_hora_revision = frappe.utils.now_datetime()
			if not self.revisado_por:
				frappe.throw(_("Seleccione un revisor para el documento"), frappe.ValidationError)
		
	def set_aprobado(self):
		if (self.workflow_status) == 'Approved' and not self.fecha_hora_aprobacion:
			self.fecha_hora_aprobacion = frappe.utils.now_datetime()
			if not self.aprobado_por:
				frappe.throw(_("Seleccione un aprobador para el documento"), frappe.ValidationError)
		
	def update_workflow_details(self):
		old_doc = Document.get_doc_before_save(self)
		
		try:
			configuracion_pagos = get_configuraciones_de_pagos(self.company, self.cost_center)
		except Exception as e:
			frappe.throw(_("Error al obtener configuraciones de pagos: {0}").format(str(e)))

		if self.workflow_status == 'Draft':
			self.revisor = configuracion_pagos.get("revisor_predeterminado")
			self.aprobador = configuracion_pagos.get("aprobador_predeterminado")
			
		if not self.revisor:
			self.revisor = configuracion_pagos.get("revisor_predeterminado")
		if not self.aprobador:
			self.aprobador = configuracion_pagos.get("aprobador_predeterminado")
		
		if old_doc is not None:
			if old_doc.workflow_status != self.workflow_status:
				if (self.workflow_status) == 'En Revisión' and not self.fecha_hora_revision:
					# set fecha hora revision
					self.fecha_hora_solicitud = frappe.utils.now_datetime()
					# if not self.solicitado_por:
					#   self.solicitado_por = frappe.session.user
				if (self.workflow_status) == 'Revisado' and not self.fecha_hora_revision:
					# set fecha hora revision
					self.fecha_hora_revision = frappe.utils.now_datetime()
					if not self.revisado_por:
						self.revisado_por = frappe.session.user
				if (self.workflow_status) == 'Approved' and not self.fecha_hora_aprobacion:
					# set fecha hora aprobacion
					self.fecha_hora_aprobacion = frappe.utils.now_datetime()
					if not self.aprobado_por:
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
		# get_expense_claims = frappe.db.exists("Expense Claim", { "liquidacion_de_viaticos": self.name, "docstatus": 1})
		get_journal_entries = frappe.db.exists("Journal Entry", { "liquidacion_de_viaticos": self.name, "docstatus": 1})
		
		if get_journal_entries:
			return docs
		
		self.create_expense_claim_jv_for_employee(docs, submit)
		
		return docs

	def create_expense_claim_jv_for_employee(self, docs=[], submit=False):
		"""Create journal entries for expense claim liquidation with proper error handling"""
		
		company = frappe.get_cached_value("Employee", self.solicitante, "company")
		try:
			configuracion_viaticos = get_configuraciones_de_pagos(company, self.cost_center)
		except Exception as e:
			frappe.throw(_("Error al obtener configuraciones de viáticos: {0}").format(str(e)))

		advance_account = configuracion_viaticos.get("cuenta_anticipo_viaticos")
		if not advance_account:
			frappe.throw(_("Cuenta de anticipo de viáticos no configurada para la empresa {0}").format(company))
			
		advance_account_currency = frappe.db.get_value("Account", advance_account, "account_currency")
		cost_center = get_employee_cost_center(self.solicitante)
		
		# Get the related employee advance with proper error handling
		try:
			employee_advance = frappe.get_doc("Employee Advance", {"solicitud_de_viaticos": self.solicitud_de_viaticos, "docstatus": 1})
		except frappe.DoesNotExistError:
			frappe.throw(_("No se encontró un anticipo de empleado válido para la solicitud de viáticos {0}").format(self.solicitud_de_viaticos))
		
		paid_amount = employee_advance.paid_amount
		claimed_amount = employee_advance.claimed_amount
		
		if company == self.company:
			cost_center = self.cost_center
		
		# Create Journal Entry
		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.posting_date = self.fecha_liquidacion
		je.company = company
		je.user_remark = f"Liquidación de viáticos {self.name} contra anticipo {employee_advance.name}"
		je.title = f"Liquidación de viáticos {self.name} contra anticipo {employee_advance.name}"
		je.liquidacion_de_viaticos = self.name
		
		# Improved multi-currency handling
		company_currency = frappe.get_cached_value("Company", company, "default_currency")
		is_multi_currency = (advance_account_currency != company_currency) or (self.currency != company_currency)
		je.multi_currency = 1 if is_multi_currency else 0
		
		# Calculate the total amount from all expenses
		total_expense = sum(expense.subtotal for expense in self.detalle_liquidacion)
		
		# Add the expense entries (debit side)
		if self.company == company:
			for expense in self.detalle_liquidacion:
				expense_account = get_expense_claim_account(expense.expense_type, self.company)["account"]
				expense_cost_center = expense.cost_center if expense.cost_center else cost_center
				
				je.append("accounts", {
					"account": expense_account,
					"debit_in_account_currency": expense.subtotal,
					"cost_center": expense_cost_center,
					"user_remark": "Fecha: {0}\nProveedor: {1}\nFactura No.: {2}\nDescripcion: {3}".format(
						expense.expense_date,
						expense.nombre_proveedor,
						expense.numero_factura,
						expense.description)
				})
			
			# Add tax entry if applicable
			if self.total_impuestos > 0:
				taxes = get_default_taxes_and_charges("Purchase Taxes and Charges Template", company=company)
				if taxes and taxes.get('taxes') and len(taxes.get('taxes')) > 0:
					tax_details = taxes.get('taxes')[0]
					
					je.append("accounts", {
						"account": tax_details.account_head,
						"debit_in_account_currency": self.total_impuestos,
						"cost_center": tax_details.cost_center
					})
				else:
					frappe.throw(_("No se pudo obtener la configuración de impuestos para la empresa {0}").format(company))
		else:
			configuracion_cuentas_reference_doc = get_configuraciones_cuentas(self.company)
			payable_party = configuracion_cuentas_reference_doc["parte_supplier"]
			payable_account = get_party_account_from_utils("Supplier", payable_party, company)
			payable_account_currency = get_account_currency(payable_account)

			advance_journal_entry = get_journal_entry_for_employee_advance(employee_advance.name)
			
			# Calculate total amount including taxes for inter-company scenario
			total_amount_with_taxes = total_expense + (self.total_impuestos or 0)
   
			if len(advance_journal_entry) > 0:
				# Get the journal entry for the advance
				je.append("accounts", {
					"account": payable_account,
					"debit_in_account_currency": total_amount_with_taxes,
					"cost_center": cost_center,
					"reference_type": "Journal Entry",
					"reference_name": advance_journal_entry[0].name,
					"party_type": "Supplier",
					"party": payable_party,
				})
			else:
				je.append("accounts", {
					"account": payable_account,
					"debit_in_account_currency": total_amount_with_taxes,
					"account_currency": payable_account_currency,
					"cost_center": cost_center,
					"party_type": "Supplier",
					"party": payable_party,
				})
		
		# Calculate total amount and difference with advance
		total_amount = total_expense + (self.total_impuestos or 0)
		difference = flt(paid_amount) - flt(total_amount)
		
		# Add employee advance entry (credit side) - credit the total amount including taxes
		je.append("accounts", {
			"account": advance_account,
			"credit_in_account_currency": total_amount,
			"cost_center": cost_center,
			"reference_type": "Employee Advance",
			"reference_name": employee_advance.name,
			"party_type": "Employee",
			"party": self.solicitante
		})
  
		# Log journal entry details for debugging
		# frappe.logger().info(f"Creating journal entry for liquidacion {self.name}: {je.as_dict()}")
  
		if submit:
			je.save(ignore_permissions=True)
			je.submit()
		else:
			je.save(ignore_permissions=True)
  
		if self.company != company:
			# Get the receivable account for the intercompany transaction
			configuracion_cuentas_doc = get_configuraciones_cuentas(company)
			
			receivable_party = configuracion_cuentas_doc["parte_customer"]
			receivable_account = get_party_account_from_utils("Customer", receivable_party, self.company)
			receivable_account_currency = frappe.db.get_value("Account", receivable_account, "account_currency")
   
			advance_journal_entry = get_journal_entry_for_employee_advance(employee_advance.name)

			je2 = frappe.new_doc("Journal Entry")
			je2.voucher_type = "Journal Entry"
			je2.posting_date = self.fecha_liquidacion
			je2.company = self.company
			je2.user_remark = f"Cuenta por cobrar por Liquidación de viáticos {self.name} contra anticipo {employee_advance.name}"
			je2.title = f"Cuenta por cobrar por Liquidación de viáticos {self.name} contra anticipo {employee_advance.name}"
			# je2.inter_company_journal_entry_reference = je.name
			
			# Improved multi-currency handling for intercompany entry
			self_company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
			is_multi_currency_je2 = (receivable_account_currency != self_company_currency) or (self.currency != self_company_currency)
			je2.multi_currency = 1 if is_multi_currency_je2 else 0
   
			for expense in self.detalle_liquidacion:
				expense_account = get_expense_claim_account(expense.expense_type, self.company)["account"]
				expense_cost_center = expense.cost_center if expense.cost_center else cost_center
				
				je2.append("accounts", {
					"account": expense_account,
					"debit_in_account_currency": expense.subtotal,
					"cost_center": expense_cost_center,
					"user_remark": "Fecha: {0}\nProveedor: {1}\nFactura No.: {2}\nDescripcion: {3}".format(
						expense.expense_date,
						expense.nombre_proveedor,
						expense.numero_factura,
						expense.description)
				})
			
			# Add tax entry if applicable
			if self.total_impuestos > 0:
				taxes = get_default_taxes_and_charges("Purchase Taxes and Charges Template", company=self.company)
				if taxes and taxes.get('taxes') and len(taxes.get('taxes')) > 0:
					tax_details = taxes.get('taxes')[0]
					
					je2.append("accounts", {
						"account": tax_details.account_head,
						"debit_in_account_currency": self.total_impuestos,
						"cost_center": tax_details.cost_center
					})
				else:
					frappe.throw(_("No se pudo obtener la configuración de impuestos para la empresa {0}").format(self.company))

			if len(advance_journal_entry) > 0:
				# Get the journal entry for the advance
				je2.append("accounts", {
					"account": receivable_account,
					"account_currency": receivable_account_currency,
					"credit_in_account_currency": total_amount,
					"cost_center": self.cost_center,
					"party_type": "Customer",
					"party": receivable_party,
					# "reference_type": "Journal Entry",
					# "reference_name": advance_journal_entry[0].inter_company_journal_entry_reference,
				})
			else:
				je2.append("accounts", {
					"account": receivable_account,
					"account_currency": receivable_account_currency,
					"credit_in_account_currency": total_amount,
					"cost_center": self.cost_center,
					"party_type": "Customer",
					"party": receivable_party
				})
		
		# If employee needs to receive money (expense > advance)
		# if difference < 0:
		# 	# Get default payable account for employees
		# 	employee_payable_account = frappe.get_cached_value("Company", company, "default_payable_account")
		# 	je.append("accounts", {
		# 		"account": employee_payable_account,
		# 		"credit_in_account_currency": abs(difference),
		# 		"party_type": "Employee",
		# 		"party": self.solicitante,
		# 		"reference_type": "Liquidacion de Viaticos",
		# 		"reference_name": self.name
		# 	})
		
		# # If employee needs to return money (advance > expense)
		# elif difference > 0:
		# 	# Get default receivable account for employees
		# 	employee_receivable_account = frappe.get_cached_value("Company", company, "default_employee_advance_account")
		# 	je.append("accounts", {
		# 		"account": employee_receivable_account,
		# 		"debit_in_account_currency": difference,
		# 		"party_type": "Employee",
		# 		"party": self.solicitante,
		# 		"reference_type": "Liquidacion de Viaticos",
		# 		"reference_name": self.name
		# 	})
		
			if submit:
				je2.save(ignore_permissions=True)
				je2.submit()
			else:
				je2.save(ignore_permissions=True)
			
		docs.append(get_link_to_form(je.doctype, je.name))
		
		# Update the employee_advance status and claimed amount
		# if difference <= 0:  # Fully claimed or more
			# employee_advance.status = "Claimed"
			# employee_advance.claimed_amount = paid_amount
		# else:  # Partially claimed
			# frappe.db.set_value("Employee Advance", self.name, "claimed_amount", flt(total_amount))
			# employee_advance.status = "Partly Claimed and Returned"
			# employee_advance.claimed_amount = total_amount
   
		frappe.db.set_value("Employee Advance", employee_advance.name, "claimed_amount", flt(total_amount))
		employee_advance.reload()
		employee_advance.set_status(update=True)
		
		# employee_advance.save(ignore_permissions=True)
		
		return docs

	def create_expense_claim_for_employee(self, docs=[], submit=False):
		company = frappe.get_cached_value("Employee", self.solicitante, "company")
		
		# Get configuraciones de pagos
		try:
			configuracion_viaticos = get_configuraciones_de_pagos(company, self.cost_center)
		except Exception as e:
			frappe.throw(_("Error al obtener configuraciones de viáticos: {0}").format(str(e)))
		
		payable_account = configuracion_viaticos.get("cuenta_anticipo_viaticos")
		if not payable_account:
			frappe.throw(_("Cuenta de anticipo de viáticos no configurada para la empresa {0}").format(company))
			
		payable_account_currency = frappe.db.get_value("Account", payable_account, "account_currency")
		cost_center = get_employee_cost_center(self.solicitante)
		
		# Get employee advance with proper error handling
		try:
			employee_advance = frappe.get_doc("Employee Advance", {"solicitud_de_viaticos": self.solicitud_de_viaticos, "docstatus": 1})
		except frappe.DoesNotExistError:
			frappe.throw(_("No se encontró un anticipo de empleado válido para la solicitud de viáticos {0}").format(self.solicitud_de_viaticos))
		
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
				"unclaimed_amount": flt(paid_amount) - flt(self.total_reembolso),
				"allocated_amount": flt(self.total_reembolso),
			},
		)
		
		for expense in self.detalle_liquidacion:
			expense_cost_center = expense.cost_center	
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
			if taxes and taxes.get('taxes') and len(taxes.get('taxes')) > 0:
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
			else:
				frappe.throw(_("No se pudo obtener la configuración de impuestos para la empresa {0}").format(company))
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