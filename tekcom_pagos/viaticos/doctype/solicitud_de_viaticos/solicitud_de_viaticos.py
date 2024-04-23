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
      update_presupuesto_monto_aprobado(self)
  
  def validate(self):
    validate_active_employee(self.solicitante)	
    validate_employee_permite_asignar_viaticos(self)
    set_totales_personas_dia(self)
    update_workflow_details(self)
    # set_revision(self)
    # set_aprobado(self)

def validate_employee_permite_asignar_viaticos(self):
  message = []
  for persona in self.personas:
    employee_name = frappe.get_cached_value('Employee', persona.employee, 'employee_name')
    solicitudes_fecha_dia_1 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_1, self.name)
    persona.permite_asignar_viaticos_dia_1 = get_permite_asignar_viaticos_dia(solicitudes_fecha_dia_1)
    solicitudes_fecha_dia_2 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_2, self.name)
    persona.permite_asignar_viaticos_dia_2 = get_permite_asignar_viaticos_dia(solicitudes_fecha_dia_2)
    solicitudes_fecha_dia_3 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_3, self.name)
    persona.permite_asignar_viaticos_dia_3 = get_permite_asignar_viaticos_dia(solicitudes_fecha_dia_3)
    solicitudes_fecha_dia_4 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_4, self.name)
    persona.permite_asignar_viaticos_dia_4 = get_permite_asignar_viaticos_dia(solicitudes_fecha_dia_4)
    solicitudes_fecha_dia_5 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_5, self.name)
    persona.permite_asignar_viaticos_dia_5 = get_permite_asignar_viaticos_dia(solicitudes_fecha_dia_5)
    solicitudes_fecha_dia_6 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_6, self.name)
    persona.permite_asignar_viaticos_dia_6 = get_permite_asignar_viaticos_dia(solicitudes_fecha_dia_6)
    solicitudes_fecha_dia_7 = validate_permite_asignar_viaticos_dia(persona.employee, persona.fecha_dia_7, self.name)
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
      
def get_configuracion_viaticos(self):
  configuracion_viaticos = frappe.get_doc('Configuracion de Viaticos')
  configuracion_centro_costos = configuracion_viaticos.cost_center_predeterminados
  
  revisor_predeterminado = configuracion_viaticos.revisor_predeterminado
  aprobador_predeterminado = configuracion_viaticos.aprobador_predeterminado
  coordinador_pagos_predeterminado = configuracion_viaticos.coordinador_pagos_predeterminado
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
  
  configuracion_viaticos = get_configuracion_viaticos(self)
  if self.revisor == None or self.revisor == '':
    self.revisor = configuracion_viaticos["revisor_predeterminado"]
  if self.aprobador == None or self.aprobador == '':
    self.aprobador = configuracion_viaticos["aprobador_predeterminado"]
  if self.coordinador_pagos == None or self.coordinador_pagos == '':
    self.coordinador_pagos = configuracion_viaticos["coordinador_pagos_predeterminado"]
  
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
def validate_permite_asignar_viaticos_dia(employee, fecha, solicitud):
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