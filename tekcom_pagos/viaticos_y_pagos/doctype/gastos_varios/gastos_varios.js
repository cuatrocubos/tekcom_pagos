// Copyright (c) 2023, Cuatrocubos Soluciones and contributors
// For license information, please see license.txt
{% include "erpnext/public/js/controllers/accounts.js" %}
frappe.provide("erpnext.accounts.dimensions");

frappe.ui.form.on('Gastos Varios', {
	onload(frm) {
		erpnext.accounts.dimensions.setup_dimension_filters(frm, frm.doctype)
	},

	setup(frm) {
		if (frm.doc.docstatus == 0) {
			if (!frm.doc.posting_date) {
				frm.set_value("posting_date", frappe.datetime.nowdate())
			}
		}

		frm.set_query("party_type", function() {
			frm.events.validate_company(frm)
			return {
				filters: {
					"name": ["in", ["Employee", "Supplier"]]
				}
			}
		})

		frm.set_query("credit_to", function() {
			frm.events.validate_company(frm)
			return {
				filters: {
					"account_type": "Payable",
					"is_group": 0,
					"company": frm.doc.company
				}
			}
		})

		frm.set_query("expense_account", "references", function() {
			frm.events.validate_company(frm)
			return {
				query: "erpnext.controllers.queries.get_expense_account",
				filters: {
					"company": frm.doc.company
				}
			}
		})
	},

	refresh(frm) {
		frm.events.hide_unhide_fields(frm);
		frm.events.set_dynamic_labels(frm);
	},

	validate_company(frm) {
		if (!frm.doc.company) {
			frappe.throw({
				message:__("Please select a Company first."),
				title:__("Mandatory")
			})
		}
	},

	company(frm) {
		frm.events.hide_unhide_fields(frm)
		frm.events.set_dynamic_labels(frm)
		erpnext.accounts.dimensions.update_dimension(frm, frm.doctype)

		if (frm.doc.company && frm.doc.party_type && frm.doc.party) {
			frappe.call({
				method: "erpnext.accounts.party.get_party_account",
				args: {
					party_type: frm.doc.party_type,
					party: frm.doc.party,
					company: frm.doc.company
				},
				callback: (response) => {
					if (response) frm.set_value("credit_to", response.message)
				}
			})
		}
	},

	hide_unhide_fields(frm) {
		var company_currency = frm.doc.company ? frappe.get_doc(":Company", frm.doc.company).default_currency : "";

		frm.toggle_display("exchange_rate", (frm.doc.currency != company_currency))
		frm.toggle_display("base_grand_total", (frm.doc.currency != company_currency))

		var references_grid = frm.fields_dict["references"].grid

		$.each(["base_total"], function(i, fname) {
			if (frappe.meta.get_docfield(references_grid.doctype, fname)) {
				references_grid.set_column_disp(fname, frm.doc.currency != company_currency)
			}
		})

		frm.refresh_fields()
	},

	set_dynamic_labels(frm) {
		var company_currency = frm.doc.company ? frappe.get_doc(":Company", frm.doc.company).default_currency : "";

		frm.set_currency_labels(["grand_total"], frm.doc.currency)

		frm.set_currency_labels(["base_grand_total"], company_currency)

		frm.set_df_property("grand_total", "options", "currency")
		
		frm.set_df_property("exchange_rate", "description", "1 " + frm.doc.currency + " = [?]" + company_currency)
		
		frm.set_currency_labels(["total"], frm.doc.currency, "references")
		frm.set_currency_labels(["base_total"], company_currency, "references")
		
		frm.refresh_fields()
	},

	party_type(frm) {
		let party_types = Object.keys(frappe.boot.party_account_types)

		if (frm.doc.party_type && !party_types.includes(frm.doc.party_type)) {
			frm.set_value("party_type", "")
			frappe.throw(__("Party can only be one of {0}", e[party_types.join(", ")]))
		}

		frm.set_query("party", function() {
			if (frm.doc.party_type == 'Employee') {
				return {
					query: "erpnext.controllers.queries.employee_query"
				}
			} else if (frm.doc.party_type == 'Customer') {
				return {
					query: "erpnext.controllers.queries.customer_query"
				}
			} else if (frm.doc.party_type == 'Supplier') {
				return {
					query: "erpnext.controllers.queries.supplier_query"
				}
			}
		})

		if (frm.doc.party) {
			$.each(["party"], function(i, field) {
				frm.set_value(field, null)
			})
		}
	},

	party(frm) {
		if (frm.doc.party_type && frm.doc.party && frm.doc.company) {
			if (!frm.doc.posting_date) {
				frappe.msgprint(__("Por favor seleccione posting_date antes de seleccionar el Tercero"))
				frm.set_value("party", "")
				return
			}

			let company_currency = frappe.get_doc(":Company", frm.doc.company).default_currency

			return frappe.call({
				method: "tekcom_pagos.viaticos_y_pagos.doctype.gastos_varios.gastos_varios.get_party_details",
				args: {
					company: frm.doc.company,
					party_type: frm.doc.party_type,
					party: frm.doc.party,
					date: frm.doc.posting_date,
					cost_center: frm.doc.cost_center
				},
				callback: function(r, rt) {
					if (r.message) {
						frappe.run_serially([
							() => frm.set_value("party_name", r.message.party_name),
							() => frm.set_value("credit_to", r.message.party_account),
							() => frm.events.hide_unhide_fields(frm),
							() => frm.events.set_dynamic_labels(frm),
							() => frm.events.set_current_exchange_rate(frm, "exchange_rate", frm.doc.currency, company_currency)
						]);
					}
				}
			});
		}
	},
	
	credit_to(frm) {
		if (frm.doc.credit_to) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Account",
					fieldname: "account_currency",
					filters: { name: frm.doc.credit_to },
				},
				callback: function(r, rt) {
					if (r.message) {
						frm.set_value("party_account_currency", r.message.account_currency)
						frm.set_dynamic_labels(frm)
					}
				}
			})
		}
	},

	currency(frm) {
		if (!frm.doc.currency || !frm.doc.company) return

		frm.events.set_dynamic_labels(frm)

		var company_currency = frappe.get_doc(":Company", frm.doc.company).default_currency

		if (frm.doc.currency == company_currency) {
			frm.set_value("exchange_rate", 1)
		} else {
			frappe.call({
				method: "erpnext.setup.utils.get_exchange_rate",
				args: {
					from_currency: frm.doc.currency,
					to_currency: company_currency,
					transaction_date: frm.doc.posting_date
				},
				callback: function(r, rt) {
					frm.set_value("exchange_rate", r.message)
					frm.events.set_exchange_rate_for_references(frm, r.message)
				}
			})
		}

		frm.events.hide_unhide_fields(frm);
	},

	set_exchange_rate_for_references(frm,exchange_rate) {
		$.each(frm.doc.references || [], function(i, d) {
			frappe.model.set_value(d.doctype, d.name, "base_total", flt(d.total) * flt(exchange_rate))
		})
	},

	set_current_exchange_rate(frm, exchange_rate_field, from_currency, to_currency) {
		frappe.call({
			method: "erpnext.setup.utils.get_exchange_rate",
			args: {
				from_currency: from_currency,
				to_currency: to_currency,
				transaction_date: frm.doc.posting_date
			},
			callback: function(r, rt) {
				const ex_rate = flt(r.message, frm.get_field(exchange_rate_field).get_precision())
				frm.set_value(exchange_rate_field, ex_rate)
			}
		})
	},

	posting_date(frm) {
		frm.events.currency(frm)
	},

	exchange_rate(frm) {
		if (frm.doc.grand_total) {
			frm.set_value("base_grand_total", flt(frm.doc.grand_total) * flt(frm.doc.exchange_rate))
			frm.set_df_property("exchange_rate", "read_only", erpnext.stale_rate_allowed() ? 0 : 1)
		}
	},

	// grand_total(frm) {
	// 	frm.set_value("base_grand_total", flt(frm.doc.grand_total) * flt(frm.doc.conversion_rate))
	// 	frm.events.hide_unhide_fields(frm)
	// },

	project(frm) {
		if (frm.doc.project) {
			frappe.call({
				method: 'erpnext.projects.doctype.project.project.get_cost_center_name',
				args: {
					project: frm.doc.project
				},
				callback: function(r, rt) {
					if (!r.exc) {
						$.each(frm.doc["references_table"] || [], function(i, row) {
							if (r.message) {
								frappe.model.set_value(row.supplier, row.reference, "cost_center", r.message)
								frappe.msgprint(__("Cost Center actualizado para la referencia {0} ha sido actualizado a {1}", [row.reference, r.message]))
							}
						})
					}
				}
			})
		}
	},

	set_total_amount(frm) {
		var grand_total = 0.0
		var base_grand_total = 0.0

		$.each(frm.doc.references || [], function(i, row) {
			if (row.total) {
				grand_total += flt(row.total)
				base_grand_total += flt(flt(row.total) * flt(row.exchange_rate), precision("base_grand_total"))
			}
		})
		
		frm.set_value("grand_total", grand_total)
		frm.set_value("base_grand_total", base_grand_total)
		frm.set_value("outstanding_amount", grand_total)
	}
});

frappe.ui.form.on('Detalle de Gastos Varios', {
	total(frm) {
		frm.events.set_total_amount(frm)
	},

	references_remove(frm) {
		frm.events.set_total_amount(frm)
	}
})
