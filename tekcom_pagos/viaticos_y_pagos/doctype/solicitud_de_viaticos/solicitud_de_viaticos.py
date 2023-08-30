# Copyright (c) 2023, Cuatrocubos Soluciones and contributors
# For license information, please see license.txt

import frappe
from frappe import ValidationError, _, qb, scrub, throw
from frappe.utils import cint, comma_or, flt, getdate, nowdate
from frappe.model.document import Document

import erpnext
from erpnext.accounts.utils import get_fiscal_year

from hrms.hr.utils import validate_active_employee

class SolicituddeViaticos(Document):
  # def before_save(self):
  #   presupuesto = dict(self.presupuesto)
    
  #   for presupuesto_disponible, presupuesto_gastos in presupuesto.items():
      
  #     get_presupuesto_disponible(self.fecha_solicitud, self.cost_center)
  
  def validate(self):
    validate_active_employee(self.solicitante)	

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
