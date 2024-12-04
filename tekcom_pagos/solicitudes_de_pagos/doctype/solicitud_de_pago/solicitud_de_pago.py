# Copyright (c) 2023, Cuatrocubos Soluciones and contributors
# For license information, please see license.txt

import frappe
from frappe import ValidationError, _, qb, scrub, throw
from frappe.utils import cint, comma_or, flt, getdate, nowdate, get_link_to_form
from frappe.model.document import Document

import erpnext
from erpnext.accounts.doctype.bank_account.bank_account import (
	 get_party_bank_account,
)
from erpnext.accounts.party import get_party_account as get_party_account_from_accounts
from erpnext.accounts.utils import get_account_currency, get_balance_on, get_outstanding_invoices
from erpnext.setup.utils import get_exchange_rate
from erpnext.accounts.doctype.journal_entry.journal_entry import (
	get_default_bank_cash_account,
)
from erpnext.accounts.doctype.payment_entry.payment_entry import (
	PaymentEntry,
	get_payment_entry,
	get_bank_cash_account
)
from hrms.overrides.employee_payment_entry import (
	get_grand_total_and_outstanding_amount,
	get_paid_amount_and_received_amount,
	get_account_currency,
	get_party_account,
)

import json
from functools import reduce

from hrms.hr.utils import validate_active_employee

class SolicituddePago(Document):
	# def set_indicator(self):
	#   if getdate(self.due_date) >= getdate(nowdate()):
	#     self.indicator_color = "orange"
	#     self.indicator_title = _("Unpaid")
	#   elif getdate(self.due_date) < getdate(nowdate()):
	#     self.indicator_color = "red"
	#     self.indicator_title = _("Overdue")
	#   else:
	#     self.indicator_color = "green"
	#     self.indicator_title = _("Paid")
	def before_save(self):
		if self.workflow_status == 'Rejected':
			self.revisor = ''
			self.aprobador = ''
			self.coordinador_pagos = ''
			self.revisado_por = ''
			self.aprobado_por = ''
			self.fecha_hora_solicitud = ''
			self.fecha_hora_revision = ''
			self.fecha_hora_aprobacion = ''
			self.mode_of_payment = ''
			self.reference_no = ''
			self.reference_date = ''
			# update_presupuesto_monto_aprobado(self)
	
	def validate(self):
		validate_active_employee(self.solicitante)
		self.update_workflow_details()
		if (self.workflow_status == 'Entregado a Contabilidad'):
			self.create_payment_entry(submit=True)
		
	# def on_submit(self):
	#   make_payment_entry(self)

	def get_constancia_date(constancia):
		return constancia['fecha_vencimiento']

	def get_configuracion_pagos(self):
		configuracion_pagos = frappe.get_doc('Configuracion de Solicitudes de Pago')
		configuracion_centro_costos = configuracion_pagos.cost_center_predeterminados
		
		revisor_predeterminado = configuracion_pagos.revisor_predeterminado
		aprobador_predeterminado = configuracion_pagos.aprobador_predeterminado
		coordinador_pagos_predeterminado = configuracion_pagos.coordinador_pagos_predeterminado
		if len(configuracion_centro_costos) > 0:
			cc_predeterminado = next((ele for ele in configuracion_centro_costos if ele.cost_center == self.cost_center), None)

			if cc_predeterminado != None:
				if cc_predeterminado.revisor_predeterminado != None:
					revisor_predeterminado = cc_predeterminado.revisor_predeterminado
				if cc_predeterminado.aprobador_predeterminado != None:
					aprobador_predeterminado = cc_predeterminado.aprobador_predeterminado
				if cc_predeterminado.coordinador_pagos_predeterminado != None:
					coordinador_pagos_predeterminado = cc_predeterminado.coordinador_pagos_predeterminado
					
		return {
			"revisor_predeterminado": revisor_predeterminado,
			"aprobador_predeterminado": aprobador_predeterminado,
			"coordinador_pagos_predeterminado": coordinador_pagos_predeterminado
		}

	def update_workflow_details(self):
		old_doc = Document.get_doc_before_save(self)
		
		configuracion_pagos = self.get_configuracion_pagos()
		
		if self.workflow_status == 'Draft':
			self.revisor = configuracion_pagos["revisor_predeterminado"]
			self.aprobador = configuracion_pagos["aprobador_predeterminado"]
			self.coordinador_pagos = configuracion_pagos["coordinador_pagos_predeterminado"]
			
		if self.revisor == None or self.revisor == '':
			self.revisor = configuracion_pagos["revisor_predeterminado"]
		if self.aprobador == None or self.aprobador == '':
			self.aprobador = configuracion_pagos["aprobador_predeterminado"]
		if self.coordinador_pagos == None or self.coordinador_pagos == '':
			self.coordinador_pagos = configuracion_pagos["coordinador_pagos_predeterminado"]
		
		if old_doc != None:
			if old_doc.workflow_status != self.workflow_status:
				if (self.workflow_status) == 'Solicitado' and self.fecha_hora_revision == None:
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
      
	def create_employee_advance_payment_entry(self, payment_docs=[], submit=False):
		has_existing_payment_entries = frappe.db.count('Employee Advance', {'solicitud_de_pago': self.name, 'docstatus': 1} )

		if has_existing_payment_entries == 0:
			party_account = party_account = get_party_account_from_accounts("Employee", self.party, self.company)
			party_account_currency = self.get("party_account_currency") or get_account_currency(party_account)
			bank_account = get_mode_of_payment_bank_cash_account(self.mode_of_payment, self.company)
			bank = get_bank_cash_account(self, bank_account)
			
			party_amount = self.monto_solicitado
			
			employee_advance = frappe.new_doc("Employee Advance")
			employee_advance.posting_date = self.reference_date
			employee_advance.company = self.company
			employee_advance.employee = self.party
			employee_advance.advance_amount = party_amount
			employee_advance.outstanding_amount = party_amount
			employee_advance.purpose = self.descripcion
			employee_advance.currency = self.currency
			employee_advance.exchange_rate = self.exchange_rate
			# employee_advance.advance_account = self.party_account
			employee_advance.mode_of_payment = self.mode_of_payment
			employee_advance.repay_unclaimed_amount_from_salary = 0
			employee_advance.reference_date = self.reference_date
			employee_advance.reference_no = self.reference_no
			employee_advance.solicitud_de_pago = self.name
			
			if submit:
				employee_advance.save(ignore_permissions=True)
				employee_advance.submit()
				get_payment_entry_for_employee(employee_advance.doctype, employee_advance.name, party_amount, reference_date=self.reference_date, reference_no=self.reference_no, solicitud_de_pago=self.name, submit=True)
			else:
				employee_advance.save(ignore_permissions=True)
			payment_docs.append(get_link_to_form(employee_advance.doctype, employee_advance.name))

	def create_payment_entry(self, submit=False):
		# create payment entry
		frappe.flags.ignore_account_permissions = True
		
		payment_docs = []
		
		# if self.party_type == "Employee":
		#   pass
		# if self.party_type == "Supplier":
		
		if self.party_type == "Employee" and len(self.references) == 0:
			self.create_employee_advance_payment_entry(payment_docs, submit)
		else:
			if len(self.references) > 0:
				for reference in self.references:
					ref_doc = frappe.get_doc(reference.reference_doctype, reference.reference_name)
					
					if reference.reference_doctype in ["Purchase Invoice", "Purchase Order"]:
						party_account = party_account = get_party_account_from_accounts("Supplier", ref_doc.supplier, ref_doc.company)
						
					party_account_currency = ref_doc.get("party_account_currency") or get_account_currency(party_account)
					
					bank_account = get_mode_of_payment_bank_cash_account(self.mode_of_payment, self.company)
					bank_amount = reference.allocated_amount
					if party_account_currency == ref_doc.company_currency and party_account_currency != ref_doc.currency:
						party_amount = ref_doc.get("base_rounded_total") or ref_doc.get("base_grand_total")
					else:
						party_amount = reference.allocated_amount
						
					payment_entry = get_payment_entry(
						reference.reference_doctype,
						reference.reference_name,
						party_amount=party_amount,
						bank_account=bank_account,
						bank_amount=bank_amount,
						party_type = "Supplier",
						payment_type = "Pay",
						reference_date=self.reference_date,
						custom_referencia_de_solicitud_pago=reference.name
					)
					
					payment_entry.update(
						{
							"solicitud_de_pago": self.name,
							"mode_of_payment": self.mode_of_payment,
							"reference_no": self.reference_no,
							"reference_date": self.reference_date,
							"remarks": "Entrada de Pago via Solicitud de Pago {}".format(
								self.name
							),
						}
					)
					
					payment_entry.update(
						{
							"cost_center": ref_doc.get("cost_center"),
							"project": self.get("project")
						}
					)
					
					if party_account_currency == ref_doc.company_currency and party_account_currency != ref_doc.currency:
						amount = payment_entry.base_paid_amount
					else:
						amount = reference.allocated_amount
						
					payment_entry.received_amount = amount
					# esto aplica el monto solicitado a la primera fila de referencias pagadas
					payment_entry.get("references")[0].allocated_amount = amount
					
					payment_entry.insert(ignore_permissions=True)
					if submit:
						payment_entry.submit()
					else:
						payment_entry.save()
					payment_docs.append(get_link_to_form(payment_entry.doctype, payment_entry.name))
			else:
				party_account = party_account = get_party_account_from_accounts("Supplier", self.party, self.company)

				party_account_currency = self.get("party_account_currency") or get_account_currency(party_account)

				bank_account = get_mode_of_payment_bank_cash_account(self.mode_of_payment, self.company)
				bank = get_bank_cash_account(self, bank_account)
				bank_amount = self.monto_solicitado
				# if party_account_currency == self.company_currency and party_account_currency != self.currency:
				#   party_amount = ref_doc.get("base_rounded_total") or ref_doc.get("base_grand_total")
				# else:
				party_amount = self.monto_solicitado
				
				payment_type = "Pay"
				
				payment_entry = frappe.new_doc("Payment Entry")
				payment_entry.payment_type = payment_type
				payment_entry.company = self.company
				payment_entry.cost_center = self.cost_center
				payment_entry.posting_date = self.reference_date
				payment_entry.reference_date = self.reference_date
				payment_entry.reference_no = self.reference_no
				payment_entry.mode_of_payment = self.mode_of_payment
				payment_entry.party_type = self.party_type
				payment_entry.party = self.party
				payment_entry.paid_from = bank.account
				payment_entry.paid_to = party_account
				payment_entry.paid_from_account_currency = bank.account_currency
				payment_entry.paid_to_account_currency = party_account_currency
				payment_entry.paid_amount = party_amount
				payment_entry.received_amount = party_amount
				payment_entry.solicitud_de_pago = self.name
				
				# if party_account_currency == ref_doc.company_currency and party_account_currency != ref_doc.currency:
				#   amount = payment_entry.base_paid_amount
				# else:
				#   amount = reference.a
					
				payment_entry.paid_amount = party_amount
				payment_entry.received_amount = party_amount
				
				payment_entry.setup_party_account_field()
				payment_entry.set_missing_values()
				payment_entry.set_missing_ref_details()
				
				if party_account and bank:
					payment_entry.set_amounts()

				if submit:
					payment_entry.save(ignore_permissions=True)
					payment_entry.submit()
				else:
					payment_entry.save(ignore_permissions=True)
				payment_docs.append(get_link_to_form(payment_entry.doctype, payment_entry.name))
			
		return payment_docs
		
@frappe.whitelist()
def get_mode_of_payment_bank_cash_account(mode_of_payment, company):
	account = frappe.db.get_value(
		"Mode of Payment Account", {"parent": mode_of_payment, "company": company}, "default_account"
	)
	if not account:
		frappe.throw(
			_("Please set default Cash or Bank account in Mode of Payment {0}").format(
				get_link_to_form("Mode of Payment", mode_of_payment)
			),
			title=_("Missing Account"),
		)
		
	# bank_account = frappe.get_doc(
	#   "Bank Account", { "account": account, "company": company }
	# )
	return account

@frappe.whitelist()
def get_constancia_pago_cuenta(party_type, party, date):
	fecha_vencimiento_constancia_pago_cuenta = None
	_party = frappe.get_doc(party_type, party).as_dict()
	if party_type == 'Employee':
		pass
	
	_constancias = _party.custom_constancias_pago_a_cuenta
	if len(_constancias) == 0:
		pass
	if len(_constancias) > 0:
		_constancias.sort(key = SolicituddePago.get_constancia_date, reverse = True)
		fecha_vencimiento_constancia_pago_cuenta = getdate(_constancias[0].fecha_vencimiento)
	
	return fecha_vencimiento_constancia_pago_cuenta

# @frappe.whitelist()
# def get_constancia_pago_cuenta(party_type, party, date):
#   fecha_vencimiento_constancia_pago_cuenta = None
#   _party = frappe.get_doc(party_type, party).as_dict()
#   if party_type == 'Employee':
#     pass
	
#   _constancias = _party.custom_constancias_pago_a_cuenta
#   if len(_constancias) == 0:
#     pass
#   if len(_constancias) > 0:
#     fecha_vencimiento_constancia_pago_cuenta = getdate(_constancias[0].fecha_vencimiento)
	
#   return fecha_vencimiento_constancia_pago_cuenta

@frappe.whitelist()
def get_party_details(company, party_type, party, date, cost_center=None):
	bank_account = ""
	bank = ""
	if not frappe.db.exists(party_type, party):
		frappe.throw(_("Invalid {0}: {1}").format(party_type, party))
		
	party_account = get_party_account_from_accounts(party_type, party, company)
	
	account_currency = get_account_currency(party_account)
	account_balance = get_balance_on(party_account, date, cost_center=cost_center)
	_party_name = "title" if party_type == "Shareholder" else party_type.lower() + "_name"
	party_name = frappe.db.get_value(party_type, party, _party_name)
	party_balance = get_balance_on(party_type=party_type, party=party, cost_center=cost_center)
	if party_type in ["Customer", "Supplier"]:
		bank_account = get_party_bank_account(party_type, party)
		party_tax_id = frappe.db.get_value(party_type, party, "tax_id")
	else:
		party_tax_id = frappe.db.get_value(party_type, party, "numero_dni")
		bank_account = frappe.db.get_value(party_type, party, "bank_ac_no")
		bank = frappe.db.get_value(party_type, party, "bank_name")
		
	return {
		"party_account": party_account,
		"party_name": party_name,
		"party_account_currency": account_currency,
		"party_balance": party_balance,
		"account_balance": account_balance,
		"bank_account": bank_account,
		"bank": bank,
		"party_tax_id": party_tax_id
	}
	
@frappe.whitelist()
def get_company_defaults(company):
	fields = ["cost_center"]
	return frappe.get_cached_value("Company", company, fields, as_dict=1)

@frappe.whitelist()
def get_reference_details(reference_doctype, reference_name, party_account_currency):
	total_amount = outstanding_amount = exchange_rate = None
	
	ref_doc = frappe.get_doc(reference_doctype, reference_name)
	company_currency = ref_doc.get("company_currency") or erpnext.get_company_currency(ref_doc.company)
	
	if not total_amount:
		if party_account_currency == company_currency:
			total_amount = ref_doc.get("base_grand_total") or ref_doc.get("base_grand_total")
			exchange_rate = 1
		else:
			total_amount = ref_doc.get("grand_total")
	if not exchange_rate:
		exchange_rate = ref_doc.get("conversion_rate") or get_exchange_rate(party_account_currency, company_currency, ref_doc.posting_date)
	
	if reference_doctype in ("Purchase Invoice", "Gastos Varios"):
		outstanding_amount = ref_doc.get("outstanding_amount")
	else:
		outstanding_amount = flt(total_amount) - flt(ref_doc.get("advance_paid"))
		
	return frappe._dict(
		{
			"due_date": ref_doc.get("due_date"),
			"total_amount": flt(total_amount),
			"outstanding_amount": flt(outstanding_amount),
			"exchange_rate": flt(exchange_rate),
			"bill_no": ref_doc.get("bill_no")
		}
	)
	
@frappe.whitelist()
def make_payment_entry(docname):
	doc = frappe.get_doc("Solicitud de Pago", docname)
	return doc.create_payment_entry(submit=True)
@frappe.whitelist()
def get_bank_account_details(bank_account):
	return frappe.db.get_value(
		"Bank Account", bank_account, ["account", "bank", "bank_account_no", "account_type"], as_dict=1
	)

def get_payment_entry_for_employee(dt, dn, party_amount=None, bank_account=None, bank_amount=None, reference_date=None, reference_no=None, solicitud_de_pago=None, submit=False):
	"""Function to make Payment Entry for Employee Advance, Gratuity, Expense Claim"""
	doc = frappe.get_doc(dt, dn)

	party_account = get_party_account(doc)
	party_account_currency = get_account_currency(party_account)
	payment_type = "Pay"
	grand_total, outstanding_amount = get_grand_total_and_outstanding_amount(
		doc, party_amount, party_account_currency
	)
	# bank or cash
	bank = get_bank_cash_account(doc, bank_account)

	paid_amount, received_amount = get_paid_amount_and_received_amount(
		doc, party_account_currency, bank, outstanding_amount, payment_type, bank_amount
	)

	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = payment_type
	pe.company = doc.company
	pe.cost_center = doc.get("cost_center")
	pe.posting_date = nowdate()
	pe.mode_of_payment = doc.get("mode_of_payment")
	pe.party_type = "Employee"
	pe.party = doc.get("employee")
	pe.contact_person = doc.get("contact_person")
	pe.contact_email = doc.get("contact_email")
	pe.letter_head = doc.get("letter_head")
	pe.paid_from = bank.account
	pe.paid_to = party_account
	pe.paid_from_account_currency = bank.account_currency
	pe.paid_to_account_currency = party_account_currency
	pe.paid_amount = paid_amount
	pe.received_amount = received_amount
	pe.solicitud_de_pago = solicitud_de_pago

	pe.append(
		"references",
		{
			"reference_doctype": dt,
			"reference_name": dn,
			"bill_no": doc.get("bill_no"),
			"due_date": doc.get("due_date"),
			"total_amount": grand_total,
			"outstanding_amount": outstanding_amount,
			"allocated_amount": outstanding_amount,
		},
	)

	pe.setup_party_account_field()
	pe.set_missing_values()
	pe.set_missing_ref_details()

	if party_account and bank:
		reference_doc = None
		if dt == "Employee Advance":
			reference_doc = doc
		pe.set_exchange_rate(ref_doc=reference_doc)
		pe.set_amounts()

	if submit:
		pe.reference_date = reference_date
		pe.reference_no = reference_no
		pe.save(ignore_permissions=True)
		pe.submit()
	return pe