import json
from collections import OrderedDict, defaultdict

import frappe
from frappe import qb, scrub
from frappe.desk.reportview import get_filters_cond, get_match_cond
from frappe.query_builder import Criterion, CustomFunction
from frappe.query_builder.functions import Concat, Locate, Sum
from frappe.utils import nowdate, today, unique, flt
from pypika import Order

from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
	get_accounting_dimensions,
)
from erpnext.accounts.doctype.payment_entry.payment_entry import (
	get_company_defaults,
	get_payment_entry,
)

from erpnext.accounts.party import get_party_account, get_party_bank_account
from erpnext.accounts.utils import get_account_currency

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
  
def get_amount(ref_doc, payment_account=None):
	"""get amount based on doctype"""
	dt = ref_doc.doctype
	if dt in ["Sales Order", "Purchase Order"]:
		grand_total = flt(ref_doc.rounded_total) or flt(ref_doc.grand_total)
	elif dt in ["Sales Invoice", "Purchase Invoice"]:
		if not ref_doc.get("is_pos"):
			if ref_doc.party_account_currency == ref_doc.currency:
				grand_total = flt(ref_doc.outstanding_amount)
			else:
				grand_total = flt(ref_doc.outstanding_amount) / ref_doc.conversion_rate
		elif dt == "Sales Invoice":
			for pay in ref_doc.payments:
				if pay.type == "Phone" and pay.account == payment_account:
					grand_total = pay.amount
					break
	elif dt == "POS Invoice":
		for pay in ref_doc.payments:
			if pay.type == "Phone" and pay.account == payment_account:
				grand_total = pay.amount
				break
	elif dt == "Fees":
		grand_total = ref_doc.outstanding_amount

	if grand_total > 0:
		return grand_total
	else:
		frappe.throw(_("Payment Entry is already created"))

# def get_existing_payment_request_amount(ref_dt, ref_dn):
# 	"""
# 	Get the existing payment request which are unpaid or partially paid for payment channel other than Phone
# 	and get the summation of existing paid payment request for Phone payment channel.
# 	"""
# 	existing_payment_request_amount = frappe.db.sql(
# 		"""
# 		select sum(grand_total)
# 		from `tabPayment Request`
# 		where
# 			reference_doctype = %s
# 			and reference_name = %s
# 			and docstatus = 1
# 			and (status != 'Paid'
# 			or (payment_channel = 'Phone'
# 				and status = 'Paid'))
# 	""",
# 		(ref_dt, ref_dn),
# 	)
# 	return flt(existing_payment_request_amount[0][0]) if existing_payment_request_amount else 0
  
# @frappe.whitelist(allow_guest=True)
# def make_payment_request(**args):
	"""Make payment request"""

	args = frappe._dict(args)

	ref_doc = frappe.get_doc(args.dt, args.dn)
	# gateway_account = get_gateway_details(args) or frappe._dict()

	grand_total = get_amount(ref_doc)
	if args.loyalty_points and args.dt == "Sales Order":
		from erpnext.accounts.doctype.loyalty_program.loyalty_program import validate_loyalty_points

		loyalty_amount = validate_loyalty_points(ref_doc, int(args.loyalty_points))
		frappe.db.set_value(
			"Sales Order", args.dn, "loyalty_points", int(args.loyalty_points), update_modified=False
		)
		frappe.db.set_value(
			"Sales Order", args.dn, "loyalty_amount", loyalty_amount, update_modified=False
		)
		grand_total = grand_total - loyalty_amount

	bank_account = (
		get_party_bank_account(args.get("party_type"), args.get("party"))
		if args.get("party_type")
		else ""
	)

	draft_payment_request = frappe.db.get_value(
		"Payment Request",
		{"reference_doctype": args.dt, "reference_name": args.dn, "docstatus": 0},
	)

	existing_payment_request_amount = get_existing_payment_request_amount(args.dt, args.dn)

	if existing_payment_request_amount:
		grand_total -= existing_payment_request_amount

	if draft_payment_request:
		frappe.db.set_value(
			"Payment Request", draft_payment_request, "grand_total", grand_total, update_modified=False
		)
		pr = frappe.get_doc("Payment Request", draft_payment_request)
	else:
		pr = frappe.new_doc("Payment Request")
		pr.update(
			{
				"payment_gateway_account": gateway_account.get("name"),
				"payment_gateway": gateway_account.get("payment_gateway"),
				"payment_account": gateway_account.get("payment_account"),
				"payment_channel": gateway_account.get("payment_channel"),
				"payment_request_type": args.get("payment_request_type"),
				"currency": ref_doc.currency,
				"grand_total": grand_total,
				"mode_of_payment": args.mode_of_payment,
				"email_to": args.recipient_id or ref_doc.owner,
				"subject": _("Payment Request for {0}").format(args.dn),
				"message": gateway_account.get("message") or get_dummy_message(ref_doc),
				"reference_doctype": args.dt,
				"reference_name": args.dn,
				"party_type": args.get("party_type") or "Customer",
				"party": args.get("party") or ref_doc.get("customer"),
				"bank_account": bank_account,
			}
		)

		# Update dimensions
		pr.update(
			{
				"cost_center": ref_doc.get("cost_center"),
				"project": ref_doc.get("project"),
			}
		)

		for dimension in get_accounting_dimensions():
			pr.update({dimension: ref_doc.get(dimension)})

		if args.order_type == "Shopping Cart" or args.mute_email:
			pr.flags.mute_email = True

		pr.insert(ignore_permissions=True)
		if args.submit_doc:
			pr.submit()

	if args.order_type == "Shopping Cart":
		frappe.db.commit()
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = pr.get_payment_url()

	if args.return_doc:
		return pr

	return pr.as_dict()