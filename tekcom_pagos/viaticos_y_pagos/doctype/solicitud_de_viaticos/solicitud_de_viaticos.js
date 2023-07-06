// Copyright (c) 2023, Cuatrocubos Soluciones and contributors
// For license information, please see license.txt
{% include "erpnext/public/js/controllers/accounts.js" %}
frappe.provide("erpnext.accounts.dimensions")

frappe.ui.form.on('Solicitud de Viaticos', {
	onload(frm) {
		erpnext.accounts.dimensions.setup_dimension_filters(frm, frm.doctype)
	},

	setup(frm) {
		if (frm.doc.docstatus == 0) {
			if (!frm.doc.fecha_solicitud) {
				frm.set_value("fecha_solicitud", frappe.datetime.nowdate())
			}
		}

		// frm.set_query("solicitante", function() {
		// 	frm.events.validate_company()
		// })
	},

	validate_company(frm) {
		if (!frm.doc.company){
			frappe.throw({message:__("Please select a Company first."), title: __("Mandatory")});
		}
	},

	company(frm) {
		frm.events.hide_unhide_fields(frm);
		frm.events.set_dynamic_labels(frm);
		erpnext.accounts.dimensions.update_dimension(frm, frm.doctype)
	},

	project(frm) {
		if (frm.doc.project) {
			frappe.call({
				method: "erpnext.projects.doctype.project.project.get_cost_center_name",
				args: {
					project: frm.doc.project
				},
				callback: function(r, rt) {
					if (r.message) {
						frappe.run_serially([
							() => frm.set_value("cost_center", r.message),
							() => frappe.msgprint(__("Centro de Costo actualizado al centro de costos del proyecto selecionado.")),
						])
					}
				}
			})
		}
	},

	solicitante(frm) {
		frm.events.validate_company(frm)
		if (frm.doc.solicitante) {
			frappe.call({
				method: "tekcom_pagos.viaticos_y_pagos.doctype.solicitud_de_viaticos.solicitud_de_viaticos.get_cuadrillas_solicitante",
				args: {
					company: frm.doc.company,
					employee: frm.doc.solicitante
				},
				callback: function(r, rt) {
					if (r.message) {
						frappe.run_serially([
							// () => frm.set_value("project", r.message.project),
							() => frm.events.set_cuadrillas_from_solicitante(frm, r.message)
						])
					}
				}
			})
		}
	},

	set_cuadrillas_from_solicitante(frm, cuadrillas) {
		if (cuadrillas) {
			cuadrillas = cuadrillas.map(c => c.name)
			frm.set_query("cuadrilla", function() {
				return {
					filters: {
						"name": ["in", cuadrillas]
					}
				}
			})
		}

		frm.refresh_fields()
	},

	cuadrilla(frm) {
		if (frm.doc.project || frm.doc.cost_center) {
			frm.set_value("project", "")
			frm.set_value("cost_center", "")
		}

		return frappe.call({
			method: "tekcom_pagos.viaticos_y_pagos.doctype.solicitud_de_viaticos.solicitud_de_viaticos.get_cuadrilla_details",
			args: {
				cuadrilla: frm.doc.cuadrilla
			},
			callback: function(r, rt) {
				if (r.message) {
					frappe.run_serially([
						() => {
							if (!frm.doc.supervisor) { 
								frm.set_value("solicitante", r.message.supervisor )
							}
						},
						() => frm.set_value("project", r.message.project),
						() => frm.set_value("cost_center", r.message.cost_center),
						() => frm.events.set_integrantes_cuadrilla(frm, r.message.integrantes_cuadrilla)
					])
				}
			}
		})
	},

	set_integrantes_cuadrilla(frm, integrantes) {
		frm.clear_table("personas")
		if (integrantes) {
			$.each(integrantes, function(i, d) {
				var c = frm.add_child("personas")
				c.employee = d.empleado
			})
		}

		frm.refresh_fields()
	},

	hide_unhide_fields(frm) {
		// var company_currency = frm.doc.company ? frappe.get_doc(":Company", frm.doc.company).default_currency : "";

		// frm.toggle_display("conversion_rate", (frm.doc.currency != company_currency));
		// frm.toggle_display("monto_pagar_base", (frm.doc.currency != company_currency));

		frm.refresh_fields();
	},

	set_dynamic_labels(frm) {
		// var company_currency = frm.doc.company? frappe.get_doc(":Company", frm.doc.company).default_currency: "";

		// frm.set_currency_labels(["monto_pagar_base"], company_currency);
		
		// frm.set_currency_labels(["monto_pagar"], frm.doc.currency)

		// frm.set_df_property("monto_pagar", "options", "currency");

		// cur_frm.set_df_property("conversion_rate", "description", "1 " + frm.doc.currency + " = [?]" + company_currency)

		frm.refresh_fields()
	},
});

frappe.ui.form.on('Personas de Solicitud de Viaticos', {
	employee(frm, cdt, cdn) {
		var row = locals[cdt][cdn]
		if (row.employee) {
			frappe.db.get_value("Employee", row.employee, "asignacion_alimentacion_diaria_viaticos", (values) => {
				// frm.set_df_property(cdt, cdn, "asignacion_alimentacion_diaria_viaticos", "read_only", values.asignacion_alimentacion_diaria_viaticos > 0 ? 1 : 0)
				if (values.asignacion_alimentacion_diaria_viaticos > 0) {
					frappe.model.set_value(cdt, cdn, "base_asignacion_diaria", values.asignacion_alimentacion_diaria_viaticos)
					frappe.model.set_value(cdt, cdn, "asignacion_diaria", values.asignacion_alimentacion_diaria_viaticos)
				}
			})
		}
		frm.refresh_fields()
	},

	dias_viaje(frm, cdt, cdn) {
		var row = locals[cdt][cdn]
		if ((row.dias_viaje > 0) && (row.asignacion_diaria > 0)) {
			total = flt(row.asignacion_diaria) * flt(row.dias_viaje)
			frappe.model.set_value(cdt, cdn, "total", total)
		}
		frm.refresh_fields()
	}
})
