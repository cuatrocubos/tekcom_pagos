// Copyright (c) 2023, Cuatrocubos Soluciones and contributors
// For license information, please see license.txt
{% include "erpnext/public/js/controllers/accounts.js" %}
frappe.provide("erpnext.accounts.dimensions")

frappe.ui.form.on('Cuadrilla', {
	onload(frm) {
		erpnext.accounts.dimensions.setup_dimension_filters(frm, frm.doctype)
	},

	setup(frm) {
		frm.set_query("supervisor", function() {
			frm.events.validate_company(frm)
			return {
				filters: {
					"company": frm.doc.company
				}
			}
		})
	},

	validate_company(frm) {
		if (!frm.doc.company) {
			frappe.throw({
				message: __("Please select a Company first."),
				title: __("Mandatory")
			})
		}
	},

	company(frm) {
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
					if (!r.exc) {
						console.log(r)
						frm.set_value("cost_center", r.message)
						frappe.msgprint(__("Centro de Costo actualizado al centro de costos del proyecto selecionado."))
					}
				}
			})
		}
	}
});
