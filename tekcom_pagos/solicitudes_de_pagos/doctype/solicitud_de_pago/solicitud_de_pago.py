# Copyright (c) 2023, Cuatrocubos Soluciones and contributors
# For license information, please see license.txt

import frappe
from frappe import ValidationError, _, qb, scrub, throw
from frappe.utils import cint, comma_or, flt, getdate, nowdate
from frappe.model.document import Document

import erpnext
from erpnext.accounts.doctype.bank_account.bank_account import (
  get_bank_account_details,
   get_party_bank_account,
)
from erpnext.accounts.party import get_party_account
from erpnext.accounts.utils import get_account_currency, get_balance_on, get_outstanding_invoices
from erpnext.setup.utils import get_exchange_rate
from erpnext.accounts.doctype.journal_entry.journal_entry import (
  get_default_bank_cash_account,
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
    update_workflow_details(self)

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
  
  configuracion_pagos = get_configuracion_pagos(self)
  
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
    _constancias.sort(key = get_constancia_date, reverse = True)
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
    
  party_account = get_party_account(party_type, party, company)
  
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
  
# @frappe.whitelist()
# def get_bank_account_details(bank_account):
#   return frappe.db.get_value(
#     "Bank Account", bank_account, ["account", "bank", "bank_account_no", "account_type"], as_dict=1
#   )