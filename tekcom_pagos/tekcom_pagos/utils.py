import json
from collections import OrderedDict, defaultdict

import frappe
from frappe import qb, scrub, _
from frappe.desk.reportview import get_filters_cond, get_match_cond
from frappe.query_builder import Criterion, CustomFunction
from frappe.query_builder.functions import Concat, Locate, Sum
from frappe.utils import nowdate, today, unique, flt, get_link_to_form
from pypika import Order

from hrms.hr.doctype.employee_advance.employee_advance import (
	get_advance_amount_advance_exchange_rate, 
	get_paying_amount_paying_exchange_rate
)

from hrms.overrides.employee_payment_entry import (
	get_grand_total_and_outstanding_amount,
	get_paid_amount_and_received_amount,
	get_account_currency,
	# get_party_account,
)

from erpnext import (
	get_default_cost_center
)

from erpnext.accounts.doctype.journal_entry.journal_entry import (
	get_default_bank_cash_account,
)

from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
	get_accounting_dimensions,
)
from erpnext.accounts.doctype.payment_entry.payment_entry import (
	get_company_defaults,
	get_payment_entry,
	get_bank_cash_account
)

from erpnext.accounts.party import get_party_account, get_party_bank_account
from erpnext.accounts.utils import get_account_currency

from tekcom_pagos.tekcom_pagos.doctype.configuraciones_de_pagos_y_viaticos.configuraciones_de_pagos_y_viaticos import (
	get_configuraciones_de_pagos,
	get_configuraciones_cuentas
)

def get_employee_cost_center(employee):
	payroll_cost_center = frappe.db.get_value("Employee", employee, "payroll_cost_center")
	department = frappe.db.get_value("Employee", employee, "department")
	if not payroll_cost_center and department:
		payroll_cost_center = frappe.db.get_value("Department", department, "payroll_cost_center")

	return payroll_cost_center

@frappe.whitelist()
def add_payment_details(doctype, doc, mode_of_payment, reference_date, reference_no):
	message = []
	
	if (mode_of_payment == None):
		message.append(_('Modo de Pago no puede estar vacio'))
	if (reference_date == None):
		message.append(_('Cheque / Fecha de referencia no puede estar vacio'))
	if (reference_no == None):
		message.append(_('Cheque / No. de Referencia no puede estar vacio'))
		
	if len(message) > 0:
		frappe.throw(msg=message, exc=frappe.ValidationError, title="Error al pagar esta solicitud", as_list=True)
	else:
		doc = frappe.get_cached_doc(doctype, doc)
		doc.mode_of_payment = mode_of_payment
		doc.reference_date = reference_date
		doc.reference_no = reference_no
		doc.save()

@frappe.whitelist()
def get_users_by_role(role):
	usuarios = []
	usuarios = frappe.get_all(
		"Has Role", filters={"role": ['like', role], "parenttype": "User"}, fields=["parent"]
	)
	return usuarios

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def employee_query(doctype, txt, searchfield, start, page_len, filters):
	doctype = "Employee"
	conditions = []
	fields = get_fields(doctype, ["name", "employee_name"])

	return frappe.db.sql(
		"""select {fields} from `tabEmployee`
		where status in ('Active', 'Suspended')
			and docstatus < 2
			and ({key} like %(txt)s
				or employee_name like %(txt)s)
			{fcond}
		order by
			(case when locate(%(_txt)s, name) > 0 then locate(%(_txt)s, name) else 99999 end),
			(case when locate(%(_txt)s, employee_name) > 0 then locate(%(_txt)s, employee_name) else 99999 end),
			idx desc,
			name, employee_name
		limit %(page_len)s offset %(start)s""".format(
			**{
				"fields": ", ".join(fields),
				"key": searchfield,
				"fcond": get_filters_cond(doctype, filters, conditions),
				# "mcond": get_match_cond(doctype),
			}
		),
		{"txt": "%%%s%%" % txt, "_txt": txt.replace("%", ""), "start": start, "page_len": page_len},
	)

def get_asignacion_diaria_alimentacion(employee):
	Employee = frappe.qb.DocType('Employee')
	query = (frappe.qb.from_(Employee)
					 .select(Employee.custom_asignacion_viaticos_alimentacion)
					 .where(Employee.name == employee)).run(as_dict=True,debug=True)
	
	if len(query) > 0:
		return query[0].custom_asignacion_viaticos_alimentacion

	return "0.0"

def get_fields(doctype, fields=None):
	if fields is None:
		fields = []
	meta = frappe.get_meta(doctype)
	fields.extend(meta.get_search_fields())

	if meta.title_field and not meta.title_field.strip() in fields:
		fields.insert(1, meta.title_field.strip())

	return unique(fields)

@frappe.whitelist()
def get_mode_of_payment_predeterminado(company, doc):
	configuracion_pagos = frappe.get_doc(doc)
	configuracion_mode_of_payment = configuracion_pagos.mode_of_payment_predeterminados
	
	if len(configuracion_mode_of_payment) > 0:
		mode_of_payment_predeterminado = next((ele for ele in configuracion_mode_of_payment if ele.company == company), None)

		if mode_of_payment_predeterminado != None:
			mode_of_payment_predeterminado = mode_of_payment_predeterminado.mode_of_payment
	else:
		return {
			"mode_of_payment_predeterminado": ""
		}
				
	return {
		"mode_of_payment_predeterminado": mode_of_payment_predeterminado,
	}
	
# def get_amount(ref_doc, payment_account=None):
# 	"""get amount based on doctype"""
# 	dt = ref_doc.doctype
# 	if dt in ["Sales Order", "Purchase Order"]:
# 		grand_total = flt(ref_doc.rounded_total) or flt(ref_doc.grand_total)
# 	elif dt in ["Sales Invoice", "Purchase Invoice"]:
# 		if not ref_doc.get("is_pos"):
# 			if ref_doc.party_account_currency == ref_doc.currency:
# 				grand_total = flt(ref_doc.outstanding_amount)
# 			else:
# 				grand_total = flt(ref_doc.outstanding_amount) / ref_doc.conversion_rate
# 		elif dt == "Sales Invoice":
# 			for pay in ref_doc.payments:
# 				if pay.type == "Phone" and pay.account == payment_account:
# 					grand_total = pay.amount
# 					break
# 	elif dt == "POS Invoice":
# 		for pay in ref_doc.payments:
# 			if pay.type == "Phone" and pay.account == payment_account:
# 				grand_total = pay.amount
# 				break
# 	elif dt == "Fees":
# 		grand_total = ref_doc.outstanding_amount

# 	if grand_total > 0:
# 		return grand_total
# 	else:
# 		frappe.throw(_("Payment Entry is already created"))

# # def get_existing_payment_request_amount(ref_dt, ref_dn):
# # 	"""
# # 	Get the existing payment request which are unpaid or partially paid for payment channel other than Phone
# # 	and get the summation of existing paid payment request for Phone payment channel.
# # 	"""
# # 	existing_payment_request_amount = frappe.db.sql(
# # 		"""
# # 		select sum(grand_total)
# # 		from `tabPayment Request`
# # 		where
# # 			reference_doctype = %s
# # 			and reference_name = %s
# # 			and docstatus = 1
# # 			and (status != 'Paid'
# # 			or (payment_channel = 'Phone'
# # 				and status = 'Paid'))
# # 	""",
# # 		(ref_dt, ref_dn),
# # 	)
# # 	return flt(existing_payment_request_amount[0][0]) if existing_payment_request_amount else 0
	
# # @frappe.whitelist(allow_guest=True)
# # def make_payment_request(**args):
# 	"""Make payment request"""

# 	args = frappe._dict(args)

# 	ref_doc = frappe.get_doc(args.dt, args.dn)
# 	# gateway_account = get_gateway_details(args) or frappe._dict()

# 	grand_total = get_amount(ref_doc)
# 	if args.loyalty_points and args.dt == "Sales Order":
# 		from erpnext.accounts.doctype.loyalty_program.loyalty_program import validate_loyalty_points

# 		loyalty_amount = validate_loyalty_points(ref_doc, int(args.loyalty_points))
# 		frappe.db.set_value(
# 			"Sales Order", args.dn, "loyalty_points", int(args.loyalty_points), update_modified=False
# 		)
# 		frappe.db.set_value(
# 			"Sales Order", args.dn, "loyalty_amount", loyalty_amount, update_modified=False
# 		)
# 		grand_total = grand_total - loyalty_amount

# 	bank_account = (
# 		get_party_bank_account(args.get("party_type"), args.get("party"))
# 		if args.get("party_type")
# 		else ""
# 	)

# 	draft_payment_request = frappe.db.get_value(
# 		"Payment Request",
# 		{"reference_doctype": args.dt, "reference_name": args.dn, "docstatus": 0},
# 	)

# 	existing_payment_request_amount = get_existing_payment_request_amount(args.dt, args.dn)

# 	if existing_payment_request_amount:
# 		grand_total -= existing_payment_request_amount

# 	if draft_payment_request:
# 		frappe.db.set_value(
# 			"Payment Request", draft_payment_request, "grand_total", grand_total, update_modified=False
# 		)
# 		pr = frappe.get_doc("Payment Request", draft_payment_request)
# 	else:
# 		pr = frappe.new_doc("Payment Request")
# 		pr.update(
# 			{
# 				"payment_gateway_account": gateway_account.get("name"),
# 				"payment_gateway": gateway_account.get("payment_gateway"),
# 				"payment_account": gateway_account.get("payment_account"),
# 				"payment_channel": gateway_account.get("payment_channel"),
# 				"payment_request_type": args.get("payment_request_type"),
# 				"currency": ref_doc.currency,
# 				"grand_total": grand_total,
# 				"mode_of_payment": args.mode_of_payment,
# 				"email_to": args.recipient_id or ref_doc.owner,
# 				"subject": _("Payment Request for {0}").format(args.dn),
# 				"message": gateway_account.get("message") or get_dummy_message(ref_doc),
# 				"reference_doctype": args.dt,
# 				"reference_name": args.dn,
# 				"party_type": args.get("party_type") or "Customer",
# 				"party": args.get("party") or ref_doc.get("customer"),
# 				"bank_account": bank_account,
# 			}
# 		)

# 		# Update dimensions
# 		pr.update(
# 			{
# 				"cost_center": ref_doc.get("cost_center"),
# 				"project": ref_doc.get("project"),
# 			}
# 		)

# 		for dimension in get_accounting_dimensions():
# 			pr.update({dimension: ref_doc.get(dimension)})

# 		if args.order_type == "Shopping Cart" or args.mute_email:
# 			pr.flags.mute_email = True

# 		pr.insert(ignore_permissions=True)
# 		if args.submit_doc:
# 			pr.submit()

# 	if args.order_type == "Shopping Cart":
# 		frappe.db.commit()
# 		frappe.local.response["type"] = "redirect"
# 		frappe.local.response["location"] = pr.get_payment_url()

# 	if args.return_doc:
# 		return pr

# 	return pr.as_dict()
# # 
@frappe.whitelist()
def get_bank_account_details(bank_account):
	return frappe.db.get_value(
		"Bank Account", bank_account, ["account", "bank", "bank_account_no", "account_type"], as_dict=1
	)

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

def get_payroll_cost_center(employee):
		"""Get payroll cost center from Employee or Department"""
		payroll_cost_center, department = frappe.db.get_value("Employee", employee, ["payroll_cost_center", "department"])
		if not payroll_cost_center and department:
			payroll_cost_center = frappe.db.get_value("Department", department, "payroll_cost_center")

		return payroll_cost_center

@frappe.whitelist()
def get_payment_entry_for_employee(
	dt, dn, 
	party_amount=None, 
	bank_account=None, 
	bank_amount=None, 
	reference_date=None, reference_no=None, 
	reference_doctype=None, reference_docname=None, 
	submit=False):
	"""Function to make Payment Entry for Employee Advance, Gratuity, Expense Claim"""
	doc = frappe.get_doc(dt, dn)
	ref_doc = frappe.get_doc(reference_doctype, reference_docname)
 
	if reference_doctype == "Solicitud de Viaticos":
		party_type = "Employee"
		party = doc.employee
		party_account = get_configuraciones_de_pagos(doc.company, ref_doc.cost_center)["cuenta_anticipo_viaticos"]
	else:
		party_type = doc.party_type
		party = doc.party
		party_account = get_configuraciones_de_pagos(doc.company, ref_doc.cost_center)["cuenta_anticipo_viaticos"]
	
	party_account_currency = frappe.db.get_value("Account", party_account, "account_currency")
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
	if reference_doctype == "Solicitud de Pago":
		pe.solicitud_de_pago = reference_docname
	if reference_doctype == "Solicitud de Viaticos":
		pe.solicitud_de_viaticos = reference_docname

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
		frappe.msgprint(
				_(f"{dt} Getting exchange rate from {pe.paid_to_account_currency} to {pe.company_currency} for date {pe.posting_date}"), 
				indicator="blue",
				alert=True
		)	
		reference_doc = None
		if dt == "Employee Advance":
			reference_doc = doc
		pe.set_exchange_rate(ref_doc=reference_doc)
		pe.set_amounts()

	if submit:
		pe.reference_date = reference_date
		pe.reference_no = reference_no
		frappe.msgprint("Party Account {0}, Bank Account {1}".format(party_account, bank.account))
		pe.save(ignore_permissions=True)
		pe.submit()
	return pe

@frappe.whitelist()
def make_journal_entry_for_payment_solicitud_de_pago(dt, dn, reference_doctype, reference_docname, submit=False):
	doc = frappe.get_doc(dt, dn)
	reference_doc = frappe.get_cached_doc(reference_doctype, reference_docname)
 
	configuracion_pagos = get_configuraciones_de_pagos(doc.company)
	configuracion_cuentas_doc = get_configuraciones_cuentas(doc.company)
	configuracion_cuentas_reference_doc = get_configuraciones_cuentas(reference_doc.company)
 
	advance_account = configuracion_pagos["cuenta_cobrar_empleado"]
	advance_account_currency = frappe.db.get_value("Account", advance_account, "account_currency")
 
	payable_party = configuracion_cuentas_reference_doc["parte_supplier"]
	payable_account = get_party_account("Supplier", payable_party, doc.company)
	payable_account_currency = get_account_currency(payable_account)
	
	receivable_party = configuracion_cuentas_doc["parte_customer"]
	receivable_account = get_party_account("Customer", payable_party, reference_doc.company)
 
	bank_account = get_mode_of_payment_bank_cash_account(reference_doc.mode_of_payment, reference_doc.company)
	bank = get_bank_cash_account(reference_doc, bank_account)

	payment_account = get_default_bank_cash_account(
		reference_doc.company, account_type="Bank", mode_of_payment=reference_doc.mode_of_payment
	)
 
	# Paso 1: Create Journal Entry for Employee
 
	employee_cost_center = get_payroll_cost_center(doc.employee)

	je = frappe.new_doc("Journal Entry")
	je.posting_date = reference_doc.reference_date
	je.voucher_type = "Journal Entry"
	je.company = doc.company
	je.remark = "Solicitud de Pago {0} a favor de {1} contra Avance de Empleado {2}".format(reference_doc.name, reference_doc.party_name, dn)
	je.title = "Solicitud de Pago {0} de Empleado {1}".format(reference_docname, dn)
	je.multi_currency = 1 if advance_account_currency != payable_account_currency else 0
	# // crear asiento contable para Cuenta por Cobrar a Empleado
	je.append(
		"accounts",
		{
			"account": advance_account,
			"account_currency": advance_account_currency,
			"debit_in_account_currency": doc.advance_amount,
			"reference_type": "Employee Advance",
			"reference_name": doc.name,
			"party_type": "Employee",
			"cost_center": employee_cost_center,
			"party": doc.employee,
			"is_advance": "Yes",
		}
	)

	je.append(
		"accounts",
		{
			"account": payable_account,
			"cost_center": employee_cost_center,
			"credit_in_account_currency": doc.advance_amount,
			"account_currency": advance_account_currency,
			"exchange_rate": flt(doc.exchange_rate),
			"party_type": "Supplier",
			"party": payable_party,
			"account_type": "Payable"
		},
	)

	if submit:
		je.save(ignore_permissions=True)
		je.submit()
 
	# Paso 2: Create Journal Entry for Paying Company (reference_doc.company)
	
	je2 = frappe.new_doc("Journal Entry")
	je2.posting_date = reference_doc.reference_date
	je2.voucher_type = "Bank Entry"
	je2.company = reference_doc.company
	je2.user_remark = "Cuenta por Cobrar por Solicitud de Pago {0} a favor de {1} con Avance de Empleado {2}".format(reference_doc.name, reference_doc.party_name, dn)
	je2.title = "Cuenta por Cobrar por Solicitud de Pago {0} Avance de Empleado {1}".format(reference_doc.name, dn)
	je2.cheque_no = reference_doc.reference_no
	je2.cheque_date = reference_doc.reference_date
	je2.mode_of_payment = reference_doc.mode_of_payment
	je2.multi_currency = 1 if advance_account_currency != payable_account_currency else 0
	je2.inter_company_journal_entry_reference = je.name
	# // crear asiento contable para Cuenta por Cobrar a Empleado
	je2.append(
		"accounts",
		{
			"account": receivable_account,
			"account_currency": advance_account_currency,
			"debit_in_account_currency": doc.advance_amount,
			"party_type": "Customer",
			"account_type": "Receivable",
			"cost_center": reference_doc.cost_center,
			"party": receivable_party,
		}
	)

	je2.append(
		"accounts",
		{
			"account": bank.account,
			"cost_center": reference_doc.cost_center,
			"credit_in_account_currency": doc.advance_amount,
			"account_currency": advance_account_currency,
			"exchange_rate": flt(doc.exchange_rate),
		},
	)
 
	if submit:
		je2.save(ignore_permissions=True)
		je2.submit()

	return je2.as_dict()

@frappe.whitelist()
def make_journal_entry_for_payment_solicitud_de_viaticos(dt, dn, reference_doctype, reference_docname, submit=False):
	# Employee Advance doc
	doc = frappe.get_doc(dt, dn)
	# Solicitud de Viaticos doc
	reference_doc = frappe.get_cached_doc(reference_doctype, reference_docname)

	# Get configuraciones de pagos and cuentas
	configuracion_pagos = get_configuraciones_de_pagos(doc.company)
	configuracion_cuentas_doc = get_configuraciones_cuentas(doc.company)
	configuracion_cuentas_reference_doc = get_configuraciones_cuentas(reference_doc.company)

	# Get Advance Account from configuraciones de pagos
	advance_account = configuracion_pagos["cuenta_anticipo_viaticos"]
	advance_account_currency = frappe.db.get_value("Account", advance_account, "account_currency")

	# Get Payable Party and Account from configuraciones de cuentas
	payable_party = configuracion_cuentas_reference_doc["parte_supplier"]
	payable_account = get_party_account("Supplier", payable_party, doc.company)
	payable_account_currency = get_account_currency(payable_account)

	# Get Receivable Party and Account from configuraciones de cuentas
	receivable_party = configuracion_cuentas_doc["parte_customer"]
	receivable_account = get_party_account("Customer", receivable_party, reference_doc.company)

	bank_account = get_mode_of_payment_bank_cash_account(reference_doc.mode_of_payment, reference_doc.company)
	bank = get_bank_cash_account(reference_doc, bank_account)
 
	payment_account = get_default_bank_cash_account(
		reference_doc.company, account_type="Bank", mode_of_payment=reference_doc.mode_of_payment
	)

# Advance Account: 10020111 - Cuentas por cobrar empleado por viaticos - NAVI
# Payable Account: 20010106 - Otras cuentas por pagar - TEK
# Payable Party: PROV-2023-00048 TEKCOM
# Receivable Account: 10020102 - Cuentas por cobrar comerciales - NAVI
# Receivable Party: 24181 NAVI
 
	# Paso 1: Create Journal Entry for Employee
 
	employee_cost_center = get_payroll_cost_center(doc.employee)

	je = frappe.new_doc("Journal Entry")
	je.posting_date = reference_doc.reference_date
	je.voucher_type = "Journal Entry"
	je.company = doc.company
	je.remark = "Solicitud de Viaticos {0} a favor de {1} contra Avance de Empleado {2}".format(reference_doc.name, reference_doc.nombre_depositar_a, dn)
	je.title = "Avance de Empleado {0}".format(dn)
	je.multi_currency = 1 if advance_account_currency != payable_account_currency else 0
	# // crear asiento contable para Cuenta por Cobrar a Empleado
	je.append(
		"accounts",
		{
			"account": advance_account,
			"account_currency": advance_account_currency,
			"debit_in_account_currency": doc.advance_amount,
			"reference_type": "Employee Advance",
			"reference_name": doc.name,
			"party_type": "Employee",
			"cost_center": employee_cost_center,
			"party": doc.employee,
			"is_advance": "Yes",
		}
	)

	je.append(
		"accounts",
		{
			"account": payable_account,
			"cost_center": employee_cost_center,
			"credit_in_account_currency": doc.advance_amount,
			"account_currency": advance_account_currency,
			"exchange_rate": flt(doc.exchange_rate),
			"party_type": "Supplier",
			"party": payable_party,
			"account_type": "Payable"
		},
	)

	if submit:
		je.save(ignore_permissions=True)
		je.submit()
 
	# Paso 2: Create Journal Entry for Paying Company (reference_doc.company)
	
	je2 = frappe.new_doc("Journal Entry")
	je2.posting_date = reference_doc.reference_date
	je2.voucher_type = "Bank Entry"
	je2.company = reference_doc.company
	je2.user_remark = "Cuenta por Cobrar por Solicitud de Viaticos {0} a favor de {1} con Avance de Empleado {2}".format(reference_doc.name, reference_doc.nombre_depositar_a, dn)
	je2.title = "Cuenta por Cobrar por Solicitud de Viaticos {0} Avance de Empleado {1}".format(reference_doc.name, dn)
	je2.cheque_no = reference_doc.reference_no
	je2.cheque_date = reference_doc.reference_date
	je2.mode_of_payment = reference_doc.mode_of_payment
	je2.multi_currency = 1 if advance_account_currency != payable_account_currency else 0
	je2.inter_company_journal_entry_reference = je.name
	# // crear asiento contable para Cuenta por Cobrar a Empleado
	je2.append(
		"accounts",
		{
			"account": receivable_account,
			"account_currency": advance_account_currency,
			"debit_in_account_currency": doc.advance_amount,
			"party_type": "Customer",
			"account_type": "Receivable",
			"cost_center": reference_doc.cost_center,
			"party": receivable_party,
		}
	)

	je2.append(
		"accounts",
		{
			"account": bank.account,
			"cost_center": reference_doc.cost_center,
			"credit_in_account_currency": doc.advance_amount,
			"account_currency": advance_account_currency,
			"exchange_rate": flt(doc.exchange_rate),
		},
	)
 
	if submit:
		je2.save(ignore_permissions=True)
		je2.submit()
	
	# frappe.db.set_value("Journal Entry", je.name, "inter_company_journal_entry_reference", je2.name, update_modified=False)

	return je2.as_dict()

def validate_expense_cost_center(self):
	if not self.cost_center:
		return

	is_group, company = frappe.get_cached_value("Cost Center", self.cost_center, ["is_group", "company"])

	if company != self.company:
		frappe.throw(
			_("{0} {1}: Cost Center {2} does not belong to Company {3}").format(
				self.voucher_type, self.voucher_no, self.cost_center, self.company
			)
		)

	if self.voucher_type != "Period Closing Voucher" and is_group:
		frappe.throw(
			_(
				"""{0} {1}: Cost Center {2} is a group cost center and group cost centers cannot be used in transactions"""
			).format(self.voucher_type, self.voucher_no, frappe.bold(self.cost_center))
		)