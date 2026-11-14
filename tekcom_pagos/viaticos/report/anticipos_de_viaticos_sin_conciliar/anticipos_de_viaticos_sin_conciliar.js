// Copyright (c) 2026, Cuatrocubos Soluciones and contributors
// For license information, please see license.txt

frappe.query_reports["Anticipos de Viaticos sin Conciliar"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "solo_liquidadas",
			label: __("Solo con Liquidación Contabilizada"),
			fieldtype: "Check",
			default: 1,
		},
	],
};
