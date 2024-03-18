# Copyright (c) 2023, Cuatrocubos Soluciones and contributors
# For license information, please see license.txt

import frappe
from frappe import ValidationError, _, qb, scrub, throw
from frappe.utils import cint, comma_or, flt, getdate, nowdate
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.query_builder.functions import Count
# from frappe.core.doctype import Role

import erpnext
from erpnext.accounts.utils import get_fiscal_year

from hrms.hr.utils import validate_active_employee

class SolicituddeViaticos(Document):
  # def before_save(self):
  #   presupuesto = dict(self.presupuesto)
    
  #   for presupuesto_disponible, presupuesto_gastos in presupuesto.items():
      
  #     get_presupuesto_disponible(self.fecha_solicitud, self.cost_center)
  def before_save(self):
    if self.workflow_status == 'Rejected':
      self.revisado_por = ''
      self.aprobado_por = ''
      self.fecha_hora_revision = ''
      self.fecha_hora_aprobacion = ''
      self.mode_of_payment = ''
      self.reference_no = ''
      self.reference_date = ''
      update_presupuesto_monto_aprobado(self)
  
  def validate(self):
    validate_active_employee(self.solicitante)	
    validate_employee_permite_asignar_viaticos(self)
    set_revision(self)
    set_aprobado(self)

def validate_employee_permite_asignar_viaticos(self):
  message = []
  for persona in self.personas:
    persona.permite_asignar_viaticos_dia_1 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_1, self.name)
    # print(persona.employee, persona.permite_asignar_viaticos_dia_1, persona.fecha_dia_1)

    persona.permite_asignar_viaticos_dia_2 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_2, self.name)
    # print(persona.employee, persona.permite_asignar_viaticos_dia_2, persona.fecha_dia_2)

    persona.permite_asignar_viaticos_dia_3 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_3, self.name)
    # print(persona.employee, persona.permite_asignar_viaticos_dia_3, persona.fecha_dia_3)

    persona.permite_asignar_viaticos_dia_4 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_4, self.name)
    # print(persona.employee, persona.permite_asignar_viaticos_dia_4, persona.fecha_dia_4)

    persona.permite_asignar_viaticos_dia_5 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_5, self.name)
    # print(persona.employee, persona.permite_asignar_viaticos_dia_5, persona.fecha_dia_5)

    persona.permite_asignar_viaticos_dia_6 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_6, self.name)
    # print(persona.employee, persona.permite_asignar_viaticos_dia_6, persona.fecha_dia_6)

    persona.permite_asignar_viaticos_dia_7 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_7, self.name)
    # print(persona.employee, persona.permite_asignar_viaticos_dia_7, persona.fecha_dia_7)
    if persona.permite_asignar_viaticos_dia_1 == 0:
      message.append(_("Fila {0}: Empleado {1} ya tiene viaticos asignados en fecha {2}").format(persona.idx, persona.employee, persona.fecha_dia_1))
    if persona.permite_asignar_viaticos_dia_2 == 0:
      message.append(_("Fila {0}: Empleado {1} ya tiene viaticos asignados en fecha {2}").format(persona.idx, persona.employee, persona.fecha_dia_2))
    if persona.permite_asignar_viaticos_dia_3 == 0:
      message.append(_("Fila {0}: Empleado {1} ya tiene viaticos asignados en fecha {2}").format(persona.idx, persona.employee, persona.fecha_dia_3))
    if persona.permite_asignar_viaticos_dia_4 == 0:
      message.append(_("Fila {0}: Empleado {1} ya tiene viaticos asignados en fecha {2}").format(persona.idx, persona.employee, persona.fecha_dia_4))
    if persona.permite_asignar_viaticos_dia_5 == 0:
      message.append(_("Fila {0}: Empleado {1} ya tiene viaticos asignados en fecha {2}").format(persona.idx, persona.employee, persona.fecha_dia_5))
    if persona.permite_asignar_viaticos_dia_6 == 0:
      message.append(_("Fila {0}: Empleado {1} ya tiene viaticos asignados en fecha {2}").format(persona.idx, persona.employee, persona.fecha_dia_6))
    if persona.permite_asignar_viaticos_dia_7 == 0:
      message.append(_("Fila {0}: Empleado {1} ya tiene viaticos asignados en fecha {2}").format(persona.idx, persona.employee, persona.fecha_dia_7))
  if (len(message) > 0):
    frappe.msgprint(msg=message,title='Alerta de viaticos duplicados',as_list=True)
  
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
        
def update_presupuesto_monto_aprobado(self):
  for linea in self.presupuesto:
    # print('monto_aprobado',linea.monto_aprobado)
    linea.monto_aprobado = 0
    
@frappe.whitelist()
def validate_permite_asignar_viaticos_dia(employee, fecha, solicitud):
  if fecha == None:
    return 1
  
  PersonasSolicitudViaticos = frappe.qb.DocType('Personas de Solicitud de Viaticos')
  SolicitudViaticos = frappe.qb.DocType('Solicitud de Viaticos')
  count_all = Count('*').as_("count")
  query = (frappe.qb.from_(PersonasSolicitudViaticos)
           .left_join(SolicitudViaticos)
           .on(SolicitudViaticos.name == PersonasSolicitudViaticos.parent)
           .select(count_all)
           .where(PersonasSolicitudViaticos.employee == employee)
           .where(PersonasSolicitudViaticos.parent != solicitud)
           .where(
             (PersonasSolicitudViaticos.fecha_dia_1 == fecha)
             | (PersonasSolicitudViaticos.fecha_dia_2 == fecha)
             | (PersonasSolicitudViaticos.fecha_dia_3 == fecha)
             | (PersonasSolicitudViaticos.fecha_dia_4 == fecha)
             | (PersonasSolicitudViaticos.fecha_dia_5 == fecha)
             | (PersonasSolicitudViaticos.fecha_dia_6 == fecha)
             | (PersonasSolicitudViaticos.fecha_dia_7 == fecha))).run(as_dict=True)
  
  if query[0].count > 0:
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
  doc = get_mapped_doc(
    "Solicitud de Viaticos",
    source_name,
    {
      "Solicitud de Viaticos": {
        "doctype": "Liquidacion de Viaticos",
        "field_map": {},
      },
      "Presupuesto Solicitud de Viaticos": {
        "doctype": "Detalle de Liquidacion de Viaticos",
        "field_map": {},
      }
    },
    target_doc
  )
  
  return doc