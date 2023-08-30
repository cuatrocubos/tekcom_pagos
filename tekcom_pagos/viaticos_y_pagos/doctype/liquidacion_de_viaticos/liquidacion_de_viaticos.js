// Copyright (c) 2023, Cuatrocubos Soluciones and contributors
// For license information, please see license.txt

{% include "erpnext/public/js/controllers/accounts.js" %}
frappe.provide("erpnext.accounts.dimensions");

frappe.ui.form.on('Liquidacion de Viaticos', {
	onload: function(frm) {
		erpnext.accounts.dimension.setup_dimension_filters(frm, frm.doctype)
	},

	setup: function(frm) {
		if (frm.doc.docstatus == 0) {
			if (!frm.doc.fecha_liquidacion) {
				frm.set_value("fecha_liquidacion", frappe.datetime.nowdate())
			}
		}

		if (frm.doc.solicitante == "" || frm.doc.solicitante == null) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: 'Employee',
					filters: {
						user_id: frappe.session.user,
					},
					fieldname: ['name']
				},
				callback: function(r) {
					if (r.message != undefined) {
						frm.set_value("solicitante", r.message.name)
					}
				}
			})
		}

		frm.set_query("bank_account", function() {
			return {
				filters: {
					is_company_account: 0,
					party_type: "Employee",
					party: frm.doc.solicitante
				}
			}
		})
	},

	refresh: function(frm) {
		frm.events.hide_unhide_fields(frm)
		frm.events.set_dynamic_labels(frm)
	},

	validate_company(frm) {
		if (!frm.doc.company) {
			frappe.throw({
				message:__("Please select a Company first."),
				title:__("Mandatory")
			})
		}
	},

	company: function(frm) {
		frm.events.hide_unhide_fields(frm);
		frm.events.set_dynamic_labels(frm);
		erpnext.accounts.dimensions.update_dimension(frm, frm.doctype)
	},

	hide_unhide_fields: function(frm) {
		var company_currency = frm.doc.company ? frappe.get_doc(":Company", frm.doc.company).default_currency : "";

		// frm.toggle_display("exchange_rate", (frm.doc.currency != company_currency));
		// frm.toggle_display("monto_pagar_base", (frm.doc.currency != company_currency));

		// frm.toggle_display(["base_total_allocated_amount"],(frm.doc.monto_pagar && frm.doc.base_total_allocated_amount && (frm.doc.currency != company_currency)))

		frm.refresh_fields();
	},

	set_dynamic_labels: function(frm) {
		var company_currency = frm.doc.company? frappe.get_doc(":Company", frm.doc.company).default_currency: "";

		// frm.set_currency_labels(["monto_pagar_base"], company_currency);
		
		// frm.set_currency_labels(["monto_pagar"], frm.doc.currency)

		// frm.set_df_property("monto_pagar", "options", "currency");

		// frm.set_df_property("exchange_rate", "description", "1 " + frm.doc.currency + " = [?]" + company_currency)

		// frm.set_currency_labels(["total_amount", "outstanding_amount","allocated_amount"], frm.doc.currency, "references")

		// frm.set_df_property("total_allocated_amount", "options", "currency")
		// frm.set_df_property("unallocated_amount", "options", "currency")

		frm.refresh_fields()
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

	set_totales(frm) {
		var total_solicitado = flt(0)
		var total_ejecutado = flt(0)
		var total_diferencia = flt(0)

		$.each(frm.doc.detalle_liquidacion || [], function(r, row) {
			if (row.monto_solicitado) {
				total_solicitado += flt(row.monto_solicitado)
			}
			if (row.monto_ejecutado) {
				total_ejecutado += flt(row.monto_ejecutado)
			}
			if (row.monto_diferencia) {
				total_diferencia += flt(row.monto_diferencia)
			}
		})

		frm.set_value("total_solicitado", total_solicitado)
		frm.set_value("total_ejecutado", total_ejecutado)
		frm.set_value("total_diferencia", total_diferencia)

		frm.refresh_fields()
	}
});
