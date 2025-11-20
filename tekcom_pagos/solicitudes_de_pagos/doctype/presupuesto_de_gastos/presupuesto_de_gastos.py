# Copyright (c) 2023, Cuatrocubos Soluciones and contributors
# For license information, please see license.txt

import frappe
from frappe import ValidationError, _, qb, scrub, throw
from frappe.utils import cint, comma_or, flt, getdate, nowdate, get_link_to_form, now
from frappe.model.document import Document

class PresupuestodeGastos(Document):
  def validate(self):
    self.obtener_solicitado()
    self.obtener_aprobado()
    self.calcular_totales()
    
  # def submit(self):
  #   # self.calcular_totales()
  
  def calcular_totales(self):
    total_presupuesto = flt(self.presupuesto_total)
    total_presupuesto_por_gasto = flt(0)
    total_solicitado_por_gasto = flt(0)
    total_aprobado_por_gasto = flt(0)
    total_disponible_por_gasto = flt(0)
    
    total_presupuesto_sin_asignar = flt(0)
    total_solicitado_sin_tipo_de_gasto = flt(self.total_solicitado_sin_tipo_de_gasto)
    total_aprobado_sin_tipo_de_gasto = flt(self.total_aprobado_sin_tipo_de_gasto)
    
    for gasto in self.gastos:
      monto_presupuestado = flt(gasto.monto)
      monto_solicitado = flt(gasto.monto_total_solicitado)
      monto_aprobado = flt(gasto.monto_total_aprobado)
      monto_disponible = monto_presupuestado - monto_aprobado
      
      total_presupuesto_por_gasto += monto_presupuestado
      total_solicitado_por_gasto += monto_solicitado
      total_aprobado_por_gasto += monto_aprobado
      total_disponible_por_gasto += monto_disponible
      
      gasto.monto_disponible = monto_disponible
      
    total_presupuesto_sin_asignar = total_presupuesto - total_presupuesto_por_gasto
    total_solicitado = total_solicitado_por_gasto + total_solicitado_sin_tipo_de_gasto
    total_aprobado = total_aprobado_por_gasto + total_aprobado_sin_tipo_de_gasto
    total_disponible = total_presupuesto - total_aprobado_por_gasto - total_aprobado_sin_tipo_de_gasto
    
    self.total_presupuesto_sin_asignar = total_presupuesto_sin_asignar
    self.total_presupuesstado = total_presupuesto
    self.total_solicitado = total_solicitado
    self.total_aprobado = total_aprobado
    self.total_disponible = total_disponible
    
  def obtener_solicitado(self):
    """ 
    Obtener los montos solicitados y aprobados de las solicitudes de pagos y solicitudes de viaticos relacionadas
    dependiendo del campo presupuesto contra, si es centro de costos, contra el centro de costos de las solicitudes,
    y si es proyecto, contra el proyecto de las solicitudes.
    """
    total_solicitado_sin_tipo_de_gasto = flt(0)
    
    ## Referencias de Solicitudes de Pago en estado no en estado Draft, Revisado, En Revisión, Rechazado
    if self.presupuesto_contra == "Project":
      referencias_solicitudes_de_pago = frappe.db.sql(
        """
        SELECT tcsp.expense_type, sum(tcsp.allocated_amount) as monto
        FROM `tabComprobante de Solicitud de Pago` tcsp
        LEFT JOIN `tabSolicitud de Pago` tsp ON tcsp.parent = tsp.name
        WHERE tsp.docstatus != 2
        AND NOT tsp.workflow_status IN ('Draft', 'Rechazado')
        AND tsp.project = %s
        GROUP BY tcsp.expense_type
        """,(self.project), as_dict=True)
      
      solicitudes_de_pago_sin_referencia = frappe.db.sql(
        """
        SELECT sum(tsp.monto_solicitado_base) as monto_solicitado
        FROM `tabSolicitud de Pago` tsp
        WHERE tsp.docstatus != 2
        AND NOT tsp.workflow_status IN ('Draft', 'Rechazado')
        AND tsp.project = %s
        AND tsp.name NOT IN (
          SELECT DISTINCT tcsp.parent
          FROM `tabComprobante de Solicitud de Pago` tcsp
          WHERE tsp.docstatus != 2
          AND tcsp.parent = tsp.name
        )
        """,(self.project), as_dict=True)
      
      solicitudes_de_viaticos = frappe.db.sql(
        """
        SELECT tpsv.tipo_gasto, sum(tpsv.monto_solicitado_base) as monto_solicitado
        FROM `tabPresupuesto Solicitud de Viaticos` tpsv
        LEFT JOIN `tabSolicitud de Viaticos` tsv ON tpsv.parent = tsv.name
        WHERE 
          tsv.docstatus != 2
        AND NOT tsv.workflow_status IN ('Draft', 'Rechazado')
        AND tsv.project = %s
        GROUP BY tpsv.tipo_gasto
        """,(self.project), as_dict=True)
    else:
      referencias_solicitudes_de_pago = frappe.db.sql(
        """
        SELECT tcsp.expense_type, sum(tcsp.allocated_amount) as monto
        FROM `tabComprobante de Solicitud de Pago` tcsp
        LEFT JOIN `tabSolicitud de Pago` tsp ON tcsp.parent = tsp.name
        WHERE tsp.docstatus != 2
        AND NOT tsp.workflow_status IN ('Draft', 'Rechazado')
        AND tsp.cost_center = %s
        GROUP BY tcsp.expense_type
        """,(self.cost_center), as_dict=True)
      solicitudes_de_pago_sin_referencia = frappe.db.sql(
        """
        SELECT sum(tsp.monto_solicitado_base) as monto_solicitado
        FROM `tabSolicitud de Pago` tsp
        WHERE tsp.docstatus != 2
        AND NOT tsp.workflow_status IN ('Draft', 'Rechazado')
        AND tsp.cost_center = %s
        AND tsp.name NOT IN (
          SELECT DISTINCT tcsp.parent
          FROM `tabComprobante de Solicitud de Pago` tcsp
          WHERE tcsp.parenttype = 'Solicitud de Pago'
          AND tcsp.parent = tsp.name
        )
        """,(self.cost_center), as_dict=True)
      solicitudes_de_viaticos = frappe.db.sql(
        """
        SELECT tpsv.tipo_gasto, sum(tpsv.monto_solicitado_base) as monto_solicitado
        FROM `tabPresupuesto Solicitud de Viaticos` tpsv
        LEFT JOIN `tabSolicitud de Viaticos` tsv ON tpsv.parent = tsv.name
        WHERE 
          tsv.docstatus != 2
        AND NOT tsv.workflow_status IN ('Draft', 'Rechazado')
        AND tsv.cost_center = %s
        GROUP BY tpsv.tipo_gasto
        """,(self.cost_center), as_dict=True)
    
    # referencias_solicitudes_de_pago
    # solicitudes_de_pago_sin_referencia
    # solicitudes_de_viaticos
    
    for presupuesto_de_gasto in self.gastos:
      tipo_de_gasto = presupuesto_de_gasto.expense_claim_type
      total_solicitado = flt(0)
      
      # Buscar en referencias_solicitudes_de_pago
      for referencia in referencias_solicitudes_de_pago:
        if referencia.expense_type == tipo_de_gasto:
          monto = flt(referencia.monto)
          total_solicitado += monto
      
      # Buscar en solicitudes_de_viaticos
      for solicitud in solicitudes_de_viaticos:
        if solicitud.tipo_gasto == tipo_de_gasto:
          monto = flt(solicitud.monto_solicitado)
          total_solicitado += monto
          
      presupuesto_de_gasto.monto_total_solicitado = total_solicitado
          
    self.total_solicitado_sin_tipo_de_gasto = flt(solicitudes_de_pago_sin_referencia[0].monto_solicitado)
    
  def obtener_aprobado(self):
    """ 
    Obtener los montos solicitados y aprobados de las solicitudes de pagos y solicitudes de viaticos relacionadas
    dependiendo del campo presupuesto contra, si es centro de costos, contra el centro de costos de las solicitudes,
    y si es proyecto, contra el proyecto de las solicitudes.
    """
    total_solicitado_sin_tipo_de_gasto = flt(0)
    
    ## Referencias de Solicitudes de Pago en estado no en estado Draft, Revisado, En Revisión, Rechazado
    if self.presupuesto_contra == "Project":
      referencias_solicitudes_de_pago = frappe.db.sql(
        """
        SELECT tcsp.expense_type, sum(tcsp.allocated_amount) as monto
        FROM `tabComprobante de Solicitud de Pago` tcsp
        LEFT JOIN `tabSolicitud de Pago` tsp ON tcsp.parent = tsp.name
        WHERE tsp.docstatus != 2
        AND NOT tsp.workflow_status IN ('Draft', 'Solicitado', 'Revisado', 'Rechazado')
        AND tsp.project = %s
        GROUP BY tcsp.expense_type
        """,(self.project), as_dict=True)
      
      solicitudes_de_pago_sin_referencia = frappe.db.sql(
        """
        SELECT sum(tsp.monto_solicitado_base) as monto_solicitado
        FROM `tabSolicitud de Pago` tsp
        WHERE tsp.docstatus != 2
        AND NOT tsp.workflow_status IN ('Draft', 'Solicitado', 'Revisado', 'Rechazado')
        AND tsp.project = %s
        AND tsp.name NOT IN (
          SELECT DISTINCT tcsp.parent
          FROM `tabComprobante de Solicitud de Pago` tcsp
          WHERE tsp.docstatus != 2
          AND tcsp.parent = tsp.name
        )
        """,(self.project), as_dict=True)
      
      solicitudes_de_viaticos = frappe.db.sql(
        """
        SELECT tpsv.tipo_gasto, sum(tpsv.monto_solicitado_base) as monto_solicitado
        FROM `tabPresupuesto Solicitud de Viaticos` tpsv
        LEFT JOIN `tabSolicitud de Viaticos` tsv ON tpsv.parent = tsv.name
        WHERE 
          tsv.docstatus != 2
        AND NOT tsv.workflow_status IN ('Draft', 'Solicitado', 'Revisado', 'Rechazado')
        AND tsv.project = %s
        GROUP BY tpsv.tipo_gasto
        """,(self.project), as_dict=True)
    else:
      referencias_solicitudes_de_pago = frappe.db.sql(
        """
        SELECT tcsp.expense_type, sum(tcsp.allocated_amount) as monto
        FROM `tabComprobante de Solicitud de Pago` tcsp
        LEFT JOIN `tabSolicitud de Pago` tsp ON tcsp.parent = tsp.name
        WHERE tsp.docstatus != 2
        AND NOT tsp.workflow_status IN ('Draft', 'Solicitado', 'Revisado', 'Rechazado')
        AND tsp.cost_center = %s
        GROUP BY tcsp.expense_type
        """,(self.cost_center), as_dict=True)
      solicitudes_de_pago_sin_referencia = frappe.db.sql(
        """
        SELECT sum(tsp.monto_solicitado_base) as monto_solicitado
        FROM `tabSolicitud de Pago` tsp
        WHERE tsp.docstatus != 2
        AND NOT tsp.workflow_status IN ('Draft', 'Solicitado', 'Revisado', 'Rechazado')
        AND tsp.cost_center = %s
        AND tsp.name NOT IN (
          SELECT DISTINCT tcsp.parent
          FROM `tabComprobante de Solicitud de Pago` tcsp
          WHERE tcsp.parenttype = 'Solicitud de Pago'
          AND tcsp.parent = tsp.name
        )
        """,(self.cost_center), as_dict=True)
      solicitudes_de_viaticos = frappe.db.sql(
        """
        SELECT tpsv.tipo_gasto, sum(tpsv.monto_solicitado_base) as monto_solicitado
        FROM `tabPresupuesto Solicitud de Viaticos` tpsv
        LEFT JOIN `tabSolicitud de Viaticos` tsv ON tpsv.parent = tsv.name
        WHERE 
          tsv.docstatus != 2
        AND NOT tsv.workflow_status IN ('Draft', 'Solicitado', 'Revisado', 'Rechazado')
        AND tsv.cost_center = %s
        GROUP BY tpsv.tipo_gasto
        """,(self.cost_center), as_dict=True)
    
    # referencias_solicitudes_de_pago
    # solicitudes_de_pago_sin_referencia
    # solicitudes_de_viaticos
    
    for presupuesto_de_gasto in self.gastos:
      tipo_de_gasto = presupuesto_de_gasto.expense_claim_type
      total_aprobado = flt(0)
      
      # Buscar en referencias_solicitudes_de_pago
      for referencia in referencias_solicitudes_de_pago:
        if referencia.expense_type == tipo_de_gasto:
          monto = flt(referencia.monto)
          total_aprobado += monto
      
      # Buscar en solicitudes_de_viaticos
      for solicitud in solicitudes_de_viaticos:
        if solicitud.tipo_gasto == tipo_de_gasto:
          monto = flt(solicitud.monto_solicitado)
          total_aprobado += monto
      
      presupuesto_de_gasto.monto_total_aprobado = total_aprobado
          
    self.total_aprobado_sin_tipo_de_gasto = flt(solicitudes_de_pago_sin_referencia[0].monto_solicitado)
    
@frappe.whitelist()
def actualizar_presupuesto_de_gastos(project=None, cost_center=None):
  """ 
  Actualizar el presupuesto de gastos asociado a un proyecto o centro de costos.
  Si se proporciona un proyecto, se actualizará el presupuesto de gastos asociado a ese proyecto.
  Si se proporciona un centro de costos, se actualizará el presupuesto de gastos asociado a ese centro de costos.
  """
  filtros = {}
  if project:
    filtros["project"] = project
    filtros["docstatus"] = 1
  elif cost_center:
    filtros["cost_center"] = cost_center
    filtros["docstatus"] = 1
  
  presupuestos = frappe.get_all(
    "Presupuesto de Gastos",
    filters=filtros,
    fields=["name"]
  )
  
  for presupuesto_info in presupuestos:
    presupuesto = frappe.get_doc("Presupuesto de Gastos", presupuesto_info.name)
    presupuesto.obtener_solicitado()
    presupuesto.obtener_aprobado()
    presupuesto.calcular_totales()
    presupuesto.save(ignore_permissions=True)