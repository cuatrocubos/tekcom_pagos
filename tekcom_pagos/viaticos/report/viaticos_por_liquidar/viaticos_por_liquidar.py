# Copyright (c) 2024, CuatroCubos and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	"""
	Script Report: Viaticos por Liquidar
	Shows solicitudes de viaticos pending liquidation
	"""
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	"""Define report columns"""
	return [
		{
			"label": "Solicitud de Viático",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Solicitud de Viaticos",
			"width": 150
		},
		{
			"label": "Estado de Liquidación",
			"fieldname": "estado_liquidacion",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": "Fecha Solicitud",
			"fieldname": "fecha_solicitud",
			"fieldtype": "Date",
			"width": 100
		},
		{
			"label": "Fecha Retorno Prevista",
			"fieldname": "fecha_retorno",
			"fieldtype": "Date",
			"width": 100
		},
		{
			"label": "Solicitante",
			"fieldname": "solicitante",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": "Nombre del Solicitante",
			"fieldname": "nombre_solicitante",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": "Compañía",
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 150
		},
		{
			"label": "Total Anticipo Solicitado",
			"fieldname": "total_anticipo_solicitado",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": "Estado Solicitud",
			"fieldname": "workflow_status",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": "Depositar A",
			"fieldname": "depositar_a",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": "Depositar a",
			"fieldname": "nombre_depositar_a",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": "Centro de Costos",
			"fieldname": "cost_center",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": "Proyecto",
			"fieldname": "project",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": "Liquidación de Viaticos",
			"fieldname": "liquidacion_name",
			"fieldtype": "Link",
			"options": "Liquidacion de Viaticos",
			"width": 100
		}
	]


def get_data(filters):
	"""Fetch data based on filters"""
	filters = filters or {}

	# Build the WHERE clause dynamically with safe parameter substitution
	where_conditions = [
		"sv.workflow_status IN ('Recibido en Contabilidad', 'Contabilizado')",
		"(lv.name IS NULL OR NOT lv.workflow_status IN ('En Revisión Contable', 'Contabilizado'))",
		"sv.fecha_solicitud >= '2025-01-01'"
	]

	# Add optional filters
	if filters.get("company"):
		where_conditions.append(f"sv.company = %s")

	if filters.get("cost_center"):
		where_conditions.append(f"sv.cost_center = %s")

	if filters.get("project"):
		where_conditions.append(f"sv.project = %s")

	if filters.get("nombre_solicitante"):
		where_conditions.append(f"sv.nombre_solicitante LIKE %s")

	where_clause = " AND ".join(where_conditions)

	# Prepare query parameters
	params = []
	if filters.get("company"):
		params.append(filters['company'])
	if filters.get("cost_center"):
		params.append(filters['cost_center'])
	if filters.get("project"):
		params.append(filters['project'])
	if filters.get("nombre_solicitante"):
		params.append(f"%{filters['nombre_solicitante']}%")

	query = f"""
		SELECT
			sv.name AS name,
			CASE
				WHEN lv.workflow_status IS NULL AND sv.fecha_retorno > CURDATE() THEN 'A tiempo'
				WHEN lv.workflow_status IS NULL AND sv.fecha_retorno <= CURDATE() THEN 'Pendiente'
				WHEN lv.workflow_status = 'Draft' THEN 'En Preparación'
				WHEN lv.workflow_status = 'Approved' THEN 'Aprobada'
				ELSE COALESCE(lv.workflow_status, '')
			END AS estado_liquidacion,
			sv.fecha_solicitud,
			sv.fecha_retorno,
			sv.solicitante,
			sv.nombre_solicitante,
			sv.company,
			sv.total_anticipo_solicitado,
			sv.workflow_status,
			sv.depositar_a,
			sv.nombre_depositar_a,
			sv.cost_center,
			sv.project,
			lv.name AS liquidacion_name
		FROM
			`tabSolicitud de Viaticos` sv
		LEFT JOIN
			`tabLiquidacion de Viaticos` lv ON sv.name = lv.solicitud_de_viaticos
		WHERE
			{where_clause}
		ORDER BY
			sv.fecha_retorno DESC
	"""

	return frappe.db.sql(query, params, as_dict=True)
