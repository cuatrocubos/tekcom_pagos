// Copyright (c) 2026, Cuatrocubos Soluciones and contributors
// For license information, please see license.txt

frappe.query_reports["Viaticos por Liquidar"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": "Compañía",
			"fieldtype": "Link",
			"options": "Company",
			"reqd": 0
		},
		{
			"fieldname": "cost_center",
			"label": "Centro de Costos",
			"fieldtype": "Link",
			"options": "Cost Center",
			"reqd": 0
		},
		{
			"fieldname": "project",
			"label": "Proyecto",
			"fieldtype": "Link",
			"options": "Project",
			"reqd": 0
		},
		{
			"fieldname": "nombre_solicitante",
			"label": "Nombre del Solicitante",
			"fieldtype": "Data",
			"reqd": 0
		}
	]
};
