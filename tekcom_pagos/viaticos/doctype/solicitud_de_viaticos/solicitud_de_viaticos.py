# Copyright (c) 2023, Cuatrocubos Soluciones and contributors
# For license information, please see license.txt

import frappe
from frappe import ValidationError, _, qb, scrub, throw
from frappe.utils import cint, comma_or, flt, getdate, nowdate, get_link_to_form, now
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.query_builder.functions import Count
# from frappe.core.doctype import Role

import erpnext
from erpnext.accounts.doctype.bank_account.bank_account import (
	 get_party_bank_account,
)
from erpnext.accounts.utils import (
	get_fiscal_year,
	get_account_currency, 
	get_balance_on, 
	get_outstanding_invoices
)
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
	make_journal_entry_for_payment_solicitud_de_viaticos,
	get_payment_entry_for_employee,
)

class SolicituddeViaticos(Document):
	# def before_save(self):
	#   presupuesto = dict(self.presupuesto)
		
	#   for presupuesto_disponible, presupuesto_gastos in presupuesto.items():
			
	#     get_presupuesto_disponible(self.fecha_solicitud, self.cost_center)
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
			self.update_presupuesto_monto_aprobado()
	
	def validate(self):
		validate_active_employee(self)	
		self.validate_employee_permite_asignar_viaticos()
		# self.validate_solicitudes_por_liquidar(self)
		self.set_totales_personas_dia()
		self.update_workflow_details()
		if (self.workflow_status == 'Entregado a Contabilidad'):
			self.create_employee_advance(submit=True)
		# set_revision(self)
		# set_aprobado(self)
  
	def validate_solicitudes_por_liquidar(self):
   
		# SELECT tsdv.name, tsdv.workflow_status, tldv.solicitud_de_viaticos 
		# FROM `tabSolicitud de Viaticos` tsdv
		# LEFT JOIN `tabLiquidacion de Viaticos` tldv ON tsdv.name = tldv.solicitud_de_viaticos 
		# WHERE tsdv.depositar_a = 'E-00021'
		# AND NOT tsdv.workflow_status IN ('Draft', 'Solicitad', 'Revisado', 'Approved', 'Rejected')
		# AND NOT tsdv.name = 'GA-FO-001-TEK-2025-00059'
		# AND tldv.name IS NULL;
		
		SolicitudViaticos = frappe.qb.DocType('Solicitud de Viaticos')
		LiquidacionViaticos = frappe.qb.DocType('Liquidacion de Viaticos')
  
		count_all = Count('*').as_("count")
		query = (frappe.qb.from_(SolicitudViaticos)
						.left_join(LiquidacionViaticos)
						.on(SolicitudViaticos.name == LiquidacionViaticos.solicitud_de_viaticos)
						.select(count_all)
						.where(SolicitudViaticos.depositar_a == self.depositar_a)
						.where(SolicitudViaticos.fecha_solicitud > '2025-01-01')
						.where(SolicitudViaticos.workflow_status.notin(['Draft', 'Solicitad', 'Revisado', 'Approved', 'Rejected']))
						.where(SolicitudViaticos.name != self.name)
						.where(LiquidacionViaticos.name.isnull())
						).run()
		
		if self.workflow_status == 'Solicitado':
			if query and query[0][0] > 3:
				frappe.throw(_("No se puede aprobar la solicitud si existen solicitudes por liquidar"), frappe.ValidationError)
		

	def validate_employee_permite_asignar_viaticos(self):
		if self.cost_center == None or self.cost_center == '':
			frappe.throw(_("Seleccione un centro de costos para el documento"), frappe.ValidationError)
		message = []
		for persona in self.personas:
			employee_name = frappe.get_cached_value('Employee', persona.employee, 'employee_name')
			solicitudes_fecha_dia_1 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_1, self.name, cost_center=self.cost_center)
			persona.permite_asignar_viaticos_dia_1 = get_permite_asignar_viaticos_dia(solicitudes_fecha_dia_1)
			solicitudes_fecha_dia_2 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_2, self.name, cost_center=self.cost_center)
			persona.permite_asignar_viaticos_dia_2 = get_permite_asignar_viaticos_dia(solicitudes_fecha_dia_2)
			solicitudes_fecha_dia_3 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_3, self.name, cost_center=self.cost_center)
			persona.permite_asignar_viaticos_dia_3 = get_permite_asignar_viaticos_dia(solicitudes_fecha_dia_3)
			solicitudes_fecha_dia_4 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_4, self.name, cost_center=self.cost_center)
			persona.permite_asignar_viaticos_dia_4 = get_permite_asignar_viaticos_dia(solicitudes_fecha_dia_4)
			solicitudes_fecha_dia_5 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_5, self.name, cost_center=self.cost_center)
			persona.permite_asignar_viaticos_dia_5 = get_permite_asignar_viaticos_dia(solicitudes_fecha_dia_5)
			solicitudes_fecha_dia_6 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_6, self.name, cost_center=self.cost_center)
			persona.permite_asignar_viaticos_dia_6 = get_permite_asignar_viaticos_dia(solicitudes_fecha_dia_6)
			solicitudes_fecha_dia_7 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_7, self.name, cost_center=self.cost_center)
			persona.permite_asignar_viaticos_dia_7 = get_permite_asignar_viaticos_dia(solicitudes_fecha_dia_7)
			
			if persona.permite_asignar_viaticos_dia_1 == 0:
				message.append(_("Fila {0}: Empleado {1} ya tiene viaticos asignados en fecha {2}<br>{3}").format(persona.idx, employee_name, persona.fecha_dia_1, solicitudes_fecha_dia_1))
			if persona.permite_asignar_viaticos_dia_2 == 0:
				message.append(_("Fila {0}: Empleado {1} ya tiene viaticos asignados en fecha {2}<br>{3}").format(persona.idx, employee_name, persona.fecha_dia_2, solicitudes_fecha_dia_2))
			if persona.permite_asignar_viaticos_dia_3 == 0:
				message.append(_("Fila {0}: Empleado {1} ya tiene viaticos asignados en fecha {2}<br>{3}").format(persona.idx, employee_name, persona.fecha_dia_3, solicitudes_fecha_dia_3))
			if persona.permite_asignar_viaticos_dia_4 == 0:
				message.append(_("Fila {0}: Empleado {1} ya tiene viaticos asignados en fecha {2}<br>{3}").format(persona.idx, employee_name, persona.fecha_dia_4, solicitudes_fecha_dia_4))
			if persona.permite_asignar_viaticos_dia_5 == 0:
				message.append(_("Fila {0}: Empleado {1} ya tiene viaticos asignados en fecha {2}<br>{3}").format(persona.idx, employee_name, persona.fecha_dia_5, solicitudes_fecha_dia_5))
			if persona.permite_asignar_viaticos_dia_6 == 0:
				message.append(_("Fila {0}: Empleado {1} ya tiene viaticos asignados en fecha {2}<br>{3}").format(persona.idx, employee_name, persona.fecha_dia_6, solicitudes_fecha_dia_6))
			if persona.permite_asignar_viaticos_dia_7 == 0:
				message.append(_("Fila {0}: Empleado {1} ya tiene viaticos asignados en fecha {2}<br>{3}").format(persona.idx, employee_name, persona.fecha_dia_7, solicitudes_fecha_dia_7))
		
		if (len(message) > 0):
			frappe.throw(msg="<br>".join(message),exc=frappe.ValidationError,title='Alerta de viaticos duplicados',as_list=True)
		
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
			self.coordinador_pagos = configuracion_pagos["pagador_predeterminado"]
			
		if self.revisor == None or self.revisor == '':
			self.revisor = configuracion_pagos["revisor_predeterminado"]
		if self.aprobador == None or self.aprobador == '':
			self.aprobador = configuracion_pagos["aprobador_predeterminado"]
		if self.coordinador_pagos == None or self.coordinador_pagos == '':
			self.coordinador_pagos = configuracion_pagos["pagador_predeterminado"]
		
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
					
	def update_presupuesto_monto_aprobado(self):
		for linea in self.presupuesto:
			# print('monto_aprobado',linea.monto_aprobado)
			linea.monto_aprobado = linea.monto_solicitado
			
	def set_totales_personas_dia(self):
		total_solicitado_alimentacion = flt(0)
		total_anticipo_solicitado = flt(0)
		for persona in self.personas:
			persona.total_solicitado = flt(persona.dia_viaje_1) + flt(persona.dia_viaje_2) + flt(persona.dia_viaje_3) + flt(persona.dia_viaje_4) + flt(persona.dia_viaje_5) + flt(persona.dia_viaje_6) + flt(persona.dia_viaje_7)
			total_solicitado_alimentacion = total_solicitado_alimentacion + persona.total_solicitado
		for presupuesto in self.presupuesto:
			if presupuesto.tipo_gasto == "Alimentación":
				presupuesto.monto_solicitado = total_solicitado_alimentacion
				presupuesto.monto_aprobado = total_solicitado_alimentacion
			total_anticipo_solicitado = total_anticipo_solicitado + presupuesto.monto_solicitado
		self.total_anticipo_solicitado = total_anticipo_solicitado
		self.total_anticipo_aprobado = total_anticipo_solicitado    
	
	def create_employee_advance(self, submit=False):
		# create payment entry
		frappe.flags.ignore_account_permissions = True
		
		docs = []
		
		# STEPS:
		# 1. Check if Employee Advance exists for Solicitud de Viaticos
		# 2. Create Employee Advance
		# 3. Create Payment Entry for Employee Advance
		get_employee_advances = frappe.db.exists("Employee Advance", { "solicitud_de_viaticos": self.name, "docstatus": 1 })
		get_payment_entries = frappe.db.exists("Payment Entry", { "reference_no": self.reference_no, "reference_date": self.reference_date, "mode_of_payment": self.mode_of_payment, "docstatus": 1 })
		get_journal_entries = frappe.db.exists("Journal Entry", { "cheque_no": self.reference_no, "cheque_date": self.reference_date, "mode_of_payment": self.mode_of_payment })
		
		if get_employee_advances or get_payment_entries or get_journal_entries:
			if get_journal_entries:
				frappe.db.set_value(
				"Journal Entry",
				{"bill_no": self.name, "bill_date": self.fecha_solicitud},  # Filters
				{
						"cheque_no": self.reference_no,
						"cheque_date": self.reference_date,
						"mode_of_payment": self.mode_of_payment
				})  # Fields to update
			# frappe.throw(_("Employee Advance or Payment Entry already exists for this Solicitud de Viaticos. {0}").format(get_link_to_form("Employee Advance", get_employee_advances)), frappe.LinkExistsError)
			frappe.msgprint(_("Employee Advance already exists for this Solicitud de Viaticos. {0}").format(get_link_to_form("Employee Advance", get_employee_advances)))
			return docs
		
		self.create_employee_advance_payment_entry(docs, submit)
		frappe.msgprint(_("Employee Advance created successfully. {0}").format(", ".join(docs)))
		return docs
		
	def create_employee_advance_payment_entry(self, payment_docs=[], submit=False):
		# has_existing_payment_entries = frappe.db.count('Employee Advance', {'solicitud_de_viaticos': self.name, 'docstatus': 1} )
		company = frappe.get_cached_value(
			"Employee", self.depositar_a, "company"
		)
  
		# configuracion_viaticos = frappe.get_doc('Configuracion de Viaticos')
		# configuracion_company = configuracion_viaticos.cuentas_contables
		# configuracion_company_customer = configuracion_viaticos.asociacion_cliente_tabla
  
		configuracion_viaticos = get_configuraciones_de_pagos(company, self.cost_center)
	
		advance_account = configuracion_viaticos["cuenta_anticipo_viaticos"]
		advance_account_currency = frappe.db.get_value("Account", advance_account, "account_currency")

		# party_account = party_account = get_party_account_from_accounts("Employee", self.depositar_a, self.company)
		# party_account_currency = self.get("party_account_currency") or get_account_currency(party_account)
		bank_account = get_mode_of_payment_bank_cash_account(self.mode_of_payment, self.company)
		# bank = get_bank_cash_account(self, bank_account)
		
		party_amount = self.total_anticipo_aprobado
		
		employee_advance = frappe.new_doc("Employee Advance")
		employee_advance.posting_date = self.reference_date
		employee_advance.company = company
		employee_advance.employee = self.depositar_a
		employee_advance.advance_amount = party_amount
		employee_advance.outstanding_amount = party_amount
		employee_advance.purpose = self.remarks
		employee_advance.currency = self.currency
		employee_advance.exchange_rate = self.exchange_rate
		employee_advance.target_exchange_rate = self.exchange_rate
		employee_advance.advance_account = advance_account
		employee_advance.mode_of_payment = self.mode_of_payment
		employee_advance.repay_unclaimed_amount_from_salary = 1
		employee_advance.reference_date = self.reference_date
		employee_advance.reference_no = self.reference_no
		employee_advance.solicitud_de_viaticos = self.name
		
		if submit:
			employee_advance.save(ignore_permissions=True)
			employee_advance.submit()
			if company != self.company:
				make_journal_entry_for_payment_solicitud_de_viaticos(employee_advance.doctype, employee_advance.name, self.doctype, self.name, submit)
			if company == self.company:
				get_payment_entry_for_employee(
      		employee_advance.doctype, 
        	employee_advance.name, 
         	bank_account=bank_account, 
          party_amount=party_amount, 
          reference_date=self.reference_date, 
          reference_no=self.reference_no, 
          reference_doctype=self.doctype,
          reference_docname=self.name,
          submit=True)
			# get_payment_entry_for_company(employee_advance.doctype, employee_advance.name, payment_company=self.company, payment_customer=company_customer, bank_account=bank_account, party_amount=party_amount, reference_date=self.reference_date, reference_no=self.reference_no, solicitud_de_viaticos=self.name, submit=True)
		else:
			employee_advance.save(ignore_permissions=True)
		payment_docs.append(get_link_to_form(employee_advance.doctype, employee_advance.name))
	
@frappe.whitelist()
def get_asignacion_diaria_alimentacion(employee):
	Employee = frappe.qb.DocType('Employee')
	query = (frappe.qb.from_(Employee)
					 .select(Employee.custom_asignacion_viaticos_alimentacion)
					 .where(Employee.name == employee)).run(as_dict=True,debug=True)
	
	if len(query) > 0:
		return query[0].custom_asignacion_viaticos_alimentacion

	return "0.0"

@frappe.whitelist()
def validate_permite_asignar_viaticos_dia(employee, fecha, solicitud, cost_center):
	if fecha == None:
		return 1
	
	PersonasSolicitudViaticos = frappe.qb.DocType('Personas de Solicitud de Viaticos')
	SolicitudViaticos = frappe.qb.DocType('Solicitud de Viaticos')
	# count_all = Count('*').as_("count")
	query = (frappe.qb.from_(PersonasSolicitudViaticos)
					 .left_join(SolicitudViaticos)
					 .on(SolicitudViaticos.name == PersonasSolicitudViaticos.parent)
					 .select(SolicitudViaticos.name)
					 .where(PersonasSolicitudViaticos.employee == employee)
					 .where(PersonasSolicitudViaticos.parent != solicitud)
					 .where(SolicitudViaticos.cost_center == cost_center)
					 .where(
						 (PersonasSolicitudViaticos.fecha_dia_1 == fecha)
						 | (PersonasSolicitudViaticos.fecha_dia_2 == fecha)
						 | (PersonasSolicitudViaticos.fecha_dia_3 == fecha)
						 | (PersonasSolicitudViaticos.fecha_dia_4 == fecha)
						 | (PersonasSolicitudViaticos.fecha_dia_5 == fecha)
						 | (PersonasSolicitudViaticos.fecha_dia_6 == fecha)
						 | (PersonasSolicitudViaticos.fecha_dia_7 == fecha))).run(as_dict=True)
	
	reference_links = []
	if len(query) > 0:
		for doc_name in query:
			reference_links.append(f'<a href="/app/solicitud-de-viaticos/{doc_name.name}">{doc_name.name}</a>')

	return ",".join(reference_links)

def get_permite_asignar_viaticos_dia(query):
	if isinstance(query, int):
		return 1
	if len(query) > 0:
		return 0
	
	return 1
			
@frappe.whitelist()
def get_users_by_role(role):
	usuarios = []
	usuarios = frappe.get_all(
		"Has Role", filters={"role": ['like', role], "parenttype": "User"}, fields=["parent"]
	)
	return usuarios

@frappe.whitelist()
def get_cuadrillas_solicitante(company, employee):
	cuadrillas = []
	
	cuadrillas = frappe.db.get_list("Cuadrilla",
		filters={
			'company': company,
			'supervisor': employee
		},
		fields=['name']
	)
	
	return cuadrillas

@frappe.whitelist()
def get_cuadrilla_details(cuadrilla):
	cuadrilla_doc = frappe.get_doc("Cuadrilla", cuadrilla)
	return cuadrilla_doc

@frappe.whitelist()
def get_presupuesto_disponible(company, fecha, cost_center):
	if not frappe.db.exists("Cost Center", cost_center):
		frappe.throw(_("Invalid Cost Center: {1}").format("Cost Center", cost_center))
		
	current_fiscal_year = get_fiscal_year(nowdate(), as_dict=True)
	
	presupuesto_de_centro_costos = frappe.db.get_last_doc(
		"Presupuesto de Gastos", 
		filters={
			"docstatus": 1, 
			"company": company, 
			"fiscal_year": current_fiscal_year.name,
			"cost_center": cost_center
		}
	).as_dict()
	
	company_wise_presupuesto_disponible = frappe.get_all(
		"Solicitud de Viaticos",
		filters={
			"docstatus": 1,
			"company": company,
			"cost_center": cost_center,
			"fecha_solicitud": (
				"between",
				[current_fiscal_year.year_start_date, current_fiscal_year.year_end_date],
			)
		},
		 group_by="company",
		fields=[
			"company",
			 "sum(total_anticipo_solicitado) as total_anticipo_solicitado",
			"sum(total_anticipo_aprobado) as total_anticipo_aprobado",
		]
	)
	
	return presupuesto_de_centro_costos

@frappe.whitelist()
def make_liquidacion_viaticos(source_name, target_doc=None):
	liquidacion_viaticos_exists = frappe.db.exists("Liquidacion de Viaticos", { "solicitud_de_viaticos": source_name, "docstatus": ["!=", 2] })
	if liquidacion_viaticos_exists:
		frappe.throw(("Liquidacion ya existe para esta solicitud."), title='Error', exc=frappe.LinkExistsError)
	doc = frappe.new_doc("Liquidacion de Viaticos")
	
	doc.solicitud_de_viaticos = source_name
	
	return doc

@frappe.whitelist()
def make_employee_advance(docname):
	doc = frappe.get_doc("Solicitud de Viaticos", docname)
	return doc.create_employee_advance(submit=True)

# def get_payment_entry_for_employee(dt, dn, party_amount=None, bank_account=None, bank_amount=None, reference_date=None, reference_no=None, solicitud_de_viaticos=None, submit=False):
# 	"""Function to make Payment Entry for Employee Advance, Gratuity, Expense Claim"""
# 	doc = frappe.get_doc(dt, dn)

# 	party_account = get_party_account(doc)
# 	party_account_currency = get_account_currency(party_account)
# 	payment_type = "Pay"
# 	grand_total, outstanding_amount = get_grand_total_and_outstanding_amount(
# 		doc, party_amount, party_account_currency
# 	)
# 	bank = get_bank_cash_account(doc, bank_account)
# 	party_company = frappe.get_cached_value("Employee", doc.employee, "company")
# 	paid_amount, received_amount = get_paid_amount_and_received_amount(
# 		doc, party_account_currency, bank, outstanding_amount, payment_type, bank_amount
# 	)

# 	pe = frappe.new_doc("Payment Entry")
# 	pe.payment_type = payment_type
# 	pe.company = party_company
# 	pe.cost_center = doc.get("cost_center")
# 	pe.posting_date = nowdate()
# 	pe.mode_of_payment = doc.get("mode_of_payment")
# 	pe.party_type = "Employee"
# 	pe.party = doc.get("employee")
# 	pe.contact_person = doc.get("contact_person")
# 	pe.contact_email = doc.get("contact_email")
# 	pe.letter_head = doc.get("letter_head")
# 	pe.paid_from = bank.account
# 	pe.paid_to = party_account
# 	pe.paid_from_account_currency = bank.account_currency
# 	pe.paid_to_account_currency = party_account_currency
# 	pe.paid_amount = paid_amount
# 	pe.received_amount = received_amount
# 	pe.solicitud_de_viaticos = solicitud_de_viaticos

# 	pe.append(
# 		"references",
# 		{
# 			"reference_doctype": dt,
# 			"reference_name": dn,
# 			"bill_no": doc.get("bill_no"),
# 			"due_date": doc.get("due_date"),
# 			"total_amount": grand_total,
# 			"outstanding_amount": outstanding_amount,
# 			"allocated_amount": outstanding_amount,
# 		},
# 	)

# 	pe.setup_party_account_field()
# 	pe.set_missing_values()
# 	pe.set_missing_ref_details()

# 	if party_account and bank:
# 		reference_doc = None
# 		if dt == "Employee Advance":
# 			reference_doc = doc
# 		pe.set_exchange_rate(ref_doc=reference_doc)
# 		pe.set_amounts()

# 	if submit:
# 		pe.reference_date = reference_date
# 		pe.reference_no = reference_no
# 		pe.save(ignore_permissions=True)
# 		pe.submit()
# 	return pe

# def get_payment_entry_for_company(dt, dn, party_amount=None, payment_company=None, payment_customer=None, bank_account=None, bank_amount=None, reference_date=None, reference_no=None, solicitud_de_viaticos=None, submit=False):
# 	"""Function to make Payment Entry for Employee Advance, Gratuity, Expense Claim"""
# 	doc = frappe.get_doc(dt, dn)

# 	party_account = get_party_account(doc)
# 	party_account_currency = get_account_currency(party_account)
# 	payment_type = "Pay"
# 	grand_total, outstanding_amount = get_grand_total_and_outstanding_amount(
# 		doc, party_amount, party_account_currency
# 	)
# 	bank = get_bank_cash_account(doc, bank_account)
# 	party_company = frappe.get_cached_value("Employee", doc.employee, "company")
# 	paid_amount, received_amount = get_paid_amount_and_received_amount(
# 		doc, party_account_currency, bank, outstanding_amount, payment_type, bank_amount
# 	)

# 	pe = frappe.new_doc("Payment Entry")
# 	pe.payment_type = payment_type
# 	pe.company = payment_company
# 	pe.cost_center = doc.get("cost_center")
# 	pe.posting_date = nowdate()
# 	pe.mode_of_payment = doc.get("mode_of_payment")
# 	pe.party_type = "Company"
# 	pe.party = doc.get("employee")
# 	pe.contact_person = doc.get("contact_person")
# 	pe.contact_email = doc.get("contact_email")
# 	pe.letter_head = doc.get("letter_head")
# 	pe.paid_from = bank.account
# 	pe.paid_to = party_account
# 	pe.paid_from_account_currency = bank.account_currency
# 	pe.paid_to_account_currency = party_account_currency
# 	pe.paid_amount = paid_amount
# 	pe.received_amount = received_amount
# 	pe.solicitud_de_viaticos = solicitud_de_viaticos

# 	pe.append(
# 		"references",
# 		{
# 			"reference_doctype": dt,
# 			"reference_name": dn,
# 			"bill_no": doc.get("bill_no"),
# 			"due_date": doc.get("due_date"),
# 			"total_amount": grand_total,
# 			"outstanding_amount": outstanding_amount,
# 			"allocated_amount": outstanding_amount,
# 		},
# 	)

# 	pe.setup_party_account_field()
# 	pe.set_missing_values()
# 	pe.set_missing_ref_details()

# 	if party_account and bank:
# 		reference_doc = None
# 		if dt == "Employee Advance":
# 			reference_doc = doc
# 		pe.set_exchange_rate(ref_doc=reference_doc)
# 		pe.set_amounts()

# 	if submit:
# 		pe.reference_date = reference_date
# 		pe.reference_no = reference_no
# 		pe.save(ignore_permissions=True)
# 		pe.submit()
# 	return pe