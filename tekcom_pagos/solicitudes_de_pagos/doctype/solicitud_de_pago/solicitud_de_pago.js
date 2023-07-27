// Copyright (c) 2023, Cuatrocubos Soluciones and contributors
// For license information, please see license.txt
{% include "erpnext/public/js/controllers/accounts.js" %}
frappe.provide("erpnext.accounts.dimensions");

frappe.ui.form.on('Solicitud de Pago', {
	onload: function(frm) {
		erpnext.accounts.dimensions.setup_dimension_filters(frm, frm.doctype)
	},

	setup: function(frm) {
		if (frm.doc.docstatus == 0) {
			if (!frm.doc.fecha_solicitud) {
				frm.set_value("fecha_solicitud", frappe.datetime.nowdate())
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

		frm.set_query("party_type", function() {
			frm.events.validate_company(frm);
			return{
				filters: {
					"name": ["in", ["Supplier","Employee"]]
				}
			}
		})
		frm.set_query("party_bank_account", function() {
			return {
				filters: {
					is_company_account: 0,
					party_type: frm.doc.party_type,
					party: frm.doc.party
				}
			}
		})
		frm.set_query("bank_account", function() {
			return {
				filters: {
					is_company_account: 1,
					company: frm.doc.company
				}
			}
		})
		frm.set_query("contact_person", function() {
			if (frm.doc.party) {
				return {
					query: 'frappe.contacts.doctype.contact.contact.contact_query',
					filters: {
						link_doctype: frm.doc.party_type,
						link_name: frm.doc.party
					}
				};
			}
		})

		frm.set_query("reference_doctype", "references", function() {
			if (frm.doc.party_type == "Supplier") {
				var doctypes = ["Purchase Order", "Purchase Invoice", "Gastos Varios"]
			} else {
				var doctypes = ["Gastos Varios"]
			}

			return {
				filters: { "name": ["in", doctypes]}
			}
		})

		frm.set_query('payment_term', 'references', function(frm, cdt, cdn) {
			const child = locals[cdt][cdn];
			if (in_list(['Purchase Invoice', 'Sales Invoice'], child.reference_doctype) && child.reference_name) {
				let payment_term_list = []
				frappe.db.get_list('Payment Schedule', { 
					fields: ["name","payment_term"],
					filters: {
						parent: child.reference_name
					} 
				}).then(records => {
					payment_term_list = records
					payment_term_list = payment_term_list.map(pt => pt.payment_term);
				return {
					filters: {
						'name': ['in', payment_term_list]
					}
				}
				});
			}
		})
	},

	refresh: function(frm) {
		// erpnext.hide_company();
		frm.events.hide_unhide_fields(frm);
		frm.events.set_dynamic_labels(frm);
		// frm.events.show_general_ledger(frm);
	},

	validate_company: (frm) => {
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

	contact_person: function(frm) {
		frm.set_value("contact_email","");
		erpnext.utils.get_contact_details(frm);
	},

	hide_unhide_fields: function(frm) {
		var company_currency = frm.doc.company ? frappe.get_doc(":Company", frm.doc.company).default_currency : "";

		frm.toggle_display("exchange_rate", (frm.doc.currency != company_currency));
		frm.toggle_display("monto_pagar_base", (frm.doc.currency != company_currency));

		// frm.toggle_display(["base_total_allocated_amount"],(frm.doc.monto_pagar && frm.doc.base_total_allocated_amount && (frm.doc.currency != company_currency)))

		frm.refresh_fields();
	},

	set_dynamic_labels: function(frm) {
		var company_currency = frm.doc.company? frappe.get_doc(":Company", frm.doc.company).default_currency: "";

		frm.set_currency_labels(["monto_pagar_base"], company_currency);
		
		frm.set_currency_labels(["monto_pagar"], frm.doc.currency)

		frm.set_df_property("monto_pagar", "options", "currency");

		frm.set_df_property("exchange_rate", "description", "1 " + frm.doc.currency + " = [?]" + company_currency)

		frm.set_currency_labels(["total_amount", "outstanding_amount","allocated_amount"], frm.doc.currency, "references")

		frm.set_df_property("total_allocated_amount", "options", "currency")
		frm.set_df_property("unallocated_amount", "options", "currency")

		frm.refresh_fields()
	},

	party_type: function(frm) {
		let party_types = Object.keys(frappe.boot.party_account_types);

		if(frm.doc.party_type && !party_types.includes(frm.doc.party_type)) {
			frm.set_value("party_type", "");
			frappe.throw(__("Party can only be one of {0}", [party_types.join(", ")]));
		};

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
		});

		if (frm.doc.party) {
			$.each(["party"], function(i, field) {
				frm.set_value(field, null)
			})
		}
	},

	party: function(frm) {
		if (frm.doc.contact_email || frm.doc.contact_person) {
			frm.set_value("contact_email", "");
			frm.set_value("contact_person", "");
		};

		if (frm.doc.fecha_vencimiento_constancia_pago_cuenta){
			frm.set_value("fecha_vencimiento_constancia_pago_cuenta", null)
		}

		if (frm.doc.fecha_vencimiento_constancia_pago_cuenta == "" || frm.doc.fecha_vencimiento_constancia_pago_cuenta == null) {
			frappe.call({
				method: "tekcom_pagos.viaticos_y_pagos.doctype.solicitud_de_pago.solicitud_de_pago.get_constancia_pago_cuenta",
				args: {
					party_type: frm.doc.party_type,
					party: frm.doc.party,
					date: frm.doc.fecha_solicitud
				},
				callback: function (r) {
					if (r.message) {
						frm.set_value("fecha_vencimiento_constancia_pago_cuenta", r.message)
					}
				}
			})
		}

		if (frm.doc.party_type && frm.doc.party && frm.doc.company) {
			if (!frm.doc.fecha_solicitud) {
				frappe.msgprint(__("Por favor seleccione fecha de solicitud antes de seleccionar el Tercero"))
				frm.set_value("party", "");
				return ;
			}
			frm.set_query("contact_person", function() {
				if (frm.doc.party) {
					return {
						query: 'frappe.contacts.doctype.contact.contact.contact_query',
						filters: {
							link_doctype: frm.doc.party_type,
							link_name: frm.doc.party
						}
					};
				}
			});

			let company_currency = frappe.get_doc(":Company", frm.doc.company).default_currency;

			return frappe.call({
				method: "tekcom_pagos.viaticos_y_pagos.doctype.solicitud_de_pago.solicitud_de_pago.get_party_details",
				args: {
					company: frm.doc.company,
					party_type: frm.doc.party_type,
					party: frm.doc.party,
					date: frm.doc.fecha_solicitud,
					cost_center: frm.doc.cost_center
				},
				callback: function(r, rt) {
					if (r.message) {
						frappe.run_serially([
							() => frm.set_value("party_name", r.message.party_name),
							() => frm.events.hide_unhide_fields(frm),
							() => frm.events.set_dynamic_labels(frm),
							() => {
								if (r.message.bank_account) {
									frm.set_value("bank_account", r.message.party_bank_account);
								}
							},
							() => frm.events.set_current_exchange_rate(frm, "exchange_rate", frm.doc.currency, company_currency)
						]);
					}
				}
			});
		}
	},

	currency: function(frm) {
		if (!frm.doc.currency || !frm.doc.company) return;

		frm.events.set_dynamic_labels(frm);
		let company_currency = frappe.get_doc(":Company", frm.doc.company).default_currency;
		if (frm.doc.currency == company_currency) {
			frm.set_value("exchange_rate", 1);
		} else {
			frappe.call({
				method: "erpnext.setup.utils.get_exchange_rate",
				args: {
					from_currency: frm.doc.currency,
					to_currency: company_currency,
					transaction_date: frm.doc.fecha_solicitud
				},
				callback: function(r, rt) {
					frm.set_value("exchange_rate", r.message)
				}
			})
		}
		frm.events.hide_unhide_fields(frm);
	},

	set_current_exchange_rate: function(frm, exchange_rate_field, from_currency, to_currency) {
		frappe.call({
			method: "erpnext.setup.utils.get_exchange_rate",
			args: {
				transaction_date: frm.doc.fecha_solicitud,
				from_currency: from_currency,
				to_currency: to_currency
			},
			callback: function(r, rt) {
				const ex_rate = flt(r.message, frm.get_field(exchange_rate_field).get_precision());
				frm.set_value(exchange_rate_field, ex_rate);
			}
		})
	},

	fecha_solicitud: function(frm) {
		frm.events.currency(frm);
	},

	exchange_rate: function(frm) {
		if (frm.doc.monto_pagar) {
			frm.set_value("monto_pagar_base", flt(frm.doc.monto_pagar) * flt(frm.doc.exchange_rate));
			frm.set_df_property("exchange_rate", "read_only", erpnext.stale_rate_allowed() ? 0 : 1);
		}
	},

	monto_pagar: function(frm) {
		frm.set_value("monto_pagar_base", flt(frm.doc.monto_pagar) * flt(frm.doc.exchange_rate));
		frm.events.hide_unhide_fields(frm);
	},

	bank_account: function(frm) {
		if (frm.doc.bank_account) {
			frappe.call({
				method: "erpnext.accounts.doctype.bank_account.bank_account.get_bank_account_details",
				args: {
					bank_account: frm.doc.bank_account
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value("bank", r.message.bank);
						frm.set_value("bank_account_no", r.message.bank_account_no)
					}
				}
			});
		}
	},

	set_monto_pagar(frm) {
		var monto_pagar = 0.0
		var monto_pagar_base = 0.0

		$.each(frm.doc.references || [], function(i, row) {
			if (row.allocated_amount) {
				monto_pagar += flt(row.allocated_amount)
				monto_pagar_base += flt(flt(row.allocated_amount) * flt(frm.exchange_rate), precision("monto_pagar_base"))
			}
		})
		
		frm.set_value("monto_pagar", monto_pagar)
		frm.set_value("monto_pagar_base", monto_pagar_base)

		// frm.events.set_unallocated_amount(frm)
		// frm.refresh_fields()
	},

	// set_unallocated_amount(frm) {
	// 	var unallocated_amount = 0
		
	// 	if (frm.doc.party) {
	// 		unallocated_amount = (frm.doc.monto_pagar_base - frm.doc.base_total_allocated_amount) / frm.doc.exchange_rate
	// 	}

	// 	frm.set_value("unallocated_amount", unallocated_amount)
	// 	frm.trigger("set_difference_amount")
	// },

	// set_difference_amount(frm) {
	// 	var difference_amount = 0
	// 	var base_unallocated_amount = flt(frm.doc.unallocated_amount) * frm.doc.exchange_rate

	// 	var base_party_amount = flt(frm.doc.base_total_allocated_amount) + base_unallocated_amount

	// 	difference_amount = flt(frm.doc.monto_pagar_base) - base_party_amount

	// 	frm.set_value("difference_amount", difference_amount)

	// 	frm.events.hide_unhide_fields(frm)
	// },

	// unallocated_amount(frm) {
	// 	frm.trigger("set_difference_amount")
	// }
});

frappe.ui.form.on('Comprobante de Solicitud de Pago', {
	reference_doctype(frm, cdt, cdn) {
		var row = locals[cdt][cdn]
	},

	reference_name(frm, cdt, cdn) {
		var row = locals[cdt][cdn]

		if (row.reference_name && row.reference_doctype) {
			return frappe.call({
				method: "tekcom_pagos.viaticos_y_pagos.doctype.solicitud_de_pago.solicitud_de_pago.get_reference_details",
				args: {
					reference_doctype: row.reference_doctype,
					reference_name: row.reference_name,
					party_account_currency: frm.doc.currency,
				},
				callback: function(r, rt) {
					if (r.message) {
						$.each(r.message, function(field, value) {
							frappe.model.set_value(cdt, cdn, field, value)
						})

						frappe.model.set_value(cdt, cdn, "allocated_amount", row.outstanding_amount)

						frm.refresh_fields()
					}
				}
			})
		}
	},

	allocated_amount(frm) {
		frm.events.set_monto_pagar(frm)
	},

	references_remove(frm) {
		frm.events.set_monto_pagar(frm)
	}
})
