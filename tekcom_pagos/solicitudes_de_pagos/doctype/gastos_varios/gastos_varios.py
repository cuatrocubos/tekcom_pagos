# Copyright (c) 2023, Cuatrocubos Soluciones and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import ValidationError, _, qb, scrub, throw
from frappe.utils import cint, comma_or, flt, getdate, nowdate
from frappe.model.document import Document

import erpnext
from erpnext.accounts.doctype.bank_account.bank_account import (
	get_bank_account_details,
 	get_party_bank_account
)
from erpnext.accounts.party import get_party_account
from erpnext.accounts.utils import get_account_currency, get_balance_on, get_outstanding_invoices
from erpnext.setup.utils import get_exchange_rate

import json
from functools import reduce

class GastosVarios(Document):
	pass

@frappe.whitelist()
def get_party_details(company, party_type, party, date, cost_center=None):
  bank_account = ""
  if not frappe.db.exists(party_type, party):
    frappe.throw(_("Invalid {0}: {1}").format(party_type, party))
    
  party_account = get_party_account(party_type, party, company)
  
  account_currency = get_account_currency(party_account)
  account_balance = get_balance_on(party_account, date, cost_center=cost_center)
  _party_name = "title" if party_type == "Shareholder" else party_type.lower() + "_name"
  party_name = frappe.db.get_value(party_type, party, _party_name)
  party_balance = get_balance_on(party_type=party_type, party=party, cost_center=cost_center)
    
  return {
		"party_account": party_account,
		"party_name": party_name,
		"party_account_currency": account_currency,
		"party_balance": party_balance,
		"account_balance": account_balance,
	}
  
@frappe.whitelist()
def get_company_defaults(company):
  fields = ["cost_center"]
  return frappe.get_cached_value("Company", company, fields, as_dict=1)