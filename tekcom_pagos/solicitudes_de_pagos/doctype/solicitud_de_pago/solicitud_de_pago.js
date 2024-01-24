// Copyright (c) 2023, Cuatrocubos Soluciones and contributors
// For license information, please see license.txt
{% include "erpnext/public/js/controllers/accounts.js" %}
frappe.provide("erpnext.accounts.dimensions");

frappe.ui.form.on('Solicitud de Pago', {
	onload: function(frm) {
		erpnext.accounts.dimensions.setup_dimension_filters(frm, frm.doctype)
		if (frm.doc.workflow_status == 'Revisado') {
			
		} else {
			
		}
		frm.refresh_fields()
	},

	validate(frm) {
		if (frm.doc.workflow_status == 'Draft' || frm.doc.workflow_status == 'Rejected') {
			frm.set_value("revisado_por", null)
			frm.set_value("aprobado_por", null)
		}
		frm.refresh_fields()
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

		if (frm.doc.workflow_status == 'Solicitado') {
			if (frm.doc.revisado_por == "" || frm.doc.revisado_por == null) {
				frappe.call({
					method: "tekcom_pagos.viaticos_y_pagos.doctype.solicitud_de_viaticos.solicitud_de_viaticos.get_users_by_role",
					args: {
						role: 'Revisor de Solicitudes de Pago'
					},
					callback: function(r) {
						if (r.message != undefined) {
							frm.set_query("revisado_por", function() {
								return {
									filters: {
										name: ["in", r.message.map(c => c.parent)]
									}
								}
							})
						}
					}
				})
			}
		}

		if (frm.doc.workflow_status == 'Revisado') {
			if (frm.doc.aprobado_por == "" || frm.doc.aprobado_por == null) {
				frappe.call({
					method: "tekcom_pagos.viaticos_y_pagos.doctype.solicitud_de_viaticos.solicitud_de_viaticos.get_users_by_role",
					args: {
						role: 'Aprobador de Solicitudes de Pago'
					},
					callback: function(r) {
						if (r.message != undefined) {
							frm.set_query("revisado_por", function() {
								return {
									filters: {
										name: ["in", r.message.map(c => c.parent)]
									}
								}
							})
						}
					}
				})
			}
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
		frm.set_query("departamento_solicitante", function() {
			return {
				filters: {
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
				var doctypes = ["Purchase Order", "Purchase Invoice", "Gastos Varios", "Journal Entry"]
			} else {
				var doctypes = ["Gastos Varios", "Journal Entry"]
			}

			return {
				filters: { "name": ["in", doctypes]}
			}
		})

		frm.set_query("reference_name", "references", function(doc, cdt, cdn) {
			var jvd = frappe.get_doc(cdt, cdn);

			// journal entry
			if(jvd.reference_doctype==="Journal Entry") {
				// frappe.model.validate_missing(jvd, "account");
				return {
					query: "erpnext.accounts.doctype.journal_entry.journal_entry.get_against_jv",
					filters: {
						// account: jvd.account,
						party: doc.party
					}
				};
			}

			var out = {
				filters: [
					[jvd.reference_doctype, "docstatus", "=", 1]
				]
			};

			if(in_list(["Sales Invoice", "Purchase Invoice"], jvd.reference_doctype)) {
				out.filters.push([jvd.reference_doctype, "outstanding_amount", "!=", 0]);
				// Filter by cost center
				if(doc.cost_center) {
					out.filters.push([jvd.reference_doctype, "cost_center", "in", ["", doc.cost_center]]);
				}
				// account filter
				// frappe.model.validate_missing(jvd, "account");
				// var party_account_field = jvd.reference_doctype==="Sales Invoice" ? "debit_to": "credit_to";
				// out.filters.push([jvd.reference_doctype, party_account_field, "=", jvd.account]);

			}

			if(in_list(["Sales Order", "Purchase Order"], jvd.reference_doctype)) {
				// party_type and party mandatory
				// frappe.model.validate_missing(jvd, "party_type");
				// frappe.model.validate_missing(jvd, "party");

				out.filters.push([jvd.reference_doctype, "per_billed", "<", 100]);
			}

			if(doc.party_type && doc.party) {
				var party_field = "";
				if(jvd.reference_doctype.indexOf("Sales")===0) {
					var party_field = "customer";
				} else if (jvd.reference_doctype.indexOf("Purchase")===0) {
					var party_field = "supplier";
				}

				if (party_field) {
					out.filters.push([jvd.reference_doctype, party_field, "=", doc.party]);
				}
			}

			return out;
		});

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

	contact_person: function(frm) {
		frm.set_value("contact_email","");
		erpnext.utils.get_contact_details(frm);
	},

	hide_unhide_fields: function(frm) {
		var company_currency = frm.doc.company ? frappe.get_doc(":Company", frm.doc.company).default_currency : "";

		frm.toggle_display("exchange_rate", (frm.doc.currency != company_currency));
		frm.toggle_display("monto_solicitado_base", (frm.doc.currency != company_currency));

		// frm.toggle_display(["base_total_allocated_amount"],(frm.doc.monto_solicitado && frm.doc.base_total_allocated_amount && (frm.doc.currency != company_currency)))

		frm.refresh_fields();
	},

	set_dynamic_labels: function(frm) {
		var company_currency = frm.doc.company? frappe.get_doc(":Company", frm.doc.company).default_currency: "";

		frm.set_currency_labels(["monto_solicitado_base"], company_currency);
		
		frm.set_currency_labels(["monto_solicitado"], frm.doc.currency)

		frm.set_df_property("monto_solicitado", "options", "currency");

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

		frm.set_value("party_bank_account", "")
		frm.set_value("bank", "")
		frm.set_value("bank_account_no", "")
		frm.set_value("bank_account_type", "")
		
		if (frm.doc.fecha_vencimiento_constancia_pago_cuenta){
			frm.set_value("fecha_vencimiento_constancia_pago_cuenta", null)
		}
		if (frm.doc.party_type == 'Supplier') {
			if (frm.doc.fecha_vencimiento_constancia_pago_cuenta == "" || frm.doc.fecha_vencimiento_constancia_pago_cuenta == null) {
				frappe.call({
					method: "tekcom_pagos.solicitudes_de_pagos.doctype.solicitud_de_pago.solicitud_de_pago.get_constancia_pago_cuenta",
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
				method: "tekcom_pagos.solicitudes_de_pagos.doctype.solicitud_de_pago.solicitud_de_pago.get_party_details",
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
							() => frm.set_value("party_tax_id", r.message.party_tax_id),
							() => {
								if (frm.doc.party_type == 'Supplier' || frm.doc.party_type == 'Customer') {
									if (r.message.bank_account) {
										frm.set_value("party_bank_account", r.message.party_bank_account);
									}
								} else {
									if (r.message.bank_account) {
										frm.set_value("bank", r.message.bank);
										frm.set_value("bank_account_no", r.message.bank_account);
										frm.set_value("bank_account_type", "Ahorros HNL")
									}
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
		if (frm.doc.monto_solicitado) {
			frm.set_value("monto_solicitado_base", flt(frm.doc.monto_solicitado) * flt(frm.doc.exchange_rate));
			frm.set_df_property("exchange_rate", "read_only", erpnext.stale_rate_allowed() ? 0 : 1);
		}
	},

	monto_solicitado: function(frm) {
		frm.set_value("monto_solicitado_base", flt(frm.doc.monto_solicitado) * flt(frm.doc.exchange_rate));
		frm.events.hide_unhide_fields(frm);
	},

	party_bank_account: function(frm) {
		if (frm.doc.party_bank_account) {
			frappe.call({
				method: "tekcom_pagos.solicitudes_de_pagos.doctype.solicitud_de_pago.solicitud_de_pago.get_bank_account_details",
				args: {
					bank_account: frm.doc.party_bank_account
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value("bank", r.message.bank);
						frm.set_value("bank_account_no", r.message.bank_account_no)
						frm.set_value("bank_account_type", r.message.account_type)
					}
				}
			});
		}
	},

	set_monto_solicitado(frm) {
		var monto_solicitado = 0.0
		var monto_solicitado_base = 0.0

		$.each(frm.doc.references || [], function(i, row) {
			if (row.allocated_amount) {
				monto_solicitado += flt(row.allocated_amount)
				monto_solicitado_base += flt(flt(row.allocated_amount) * flt(frm.exchange_rate), precision("monto_solicitado_base"))
			}
		})
		
		frm.set_value("monto_solicitado", monto_solicitado)
		frm.set_value("monto_solicitado_base", monto_solicitado_base)

		// frm.events.set_unallocated_amount(frm)
		// frm.refresh_fields()
	},

	// set_unallocated_amount(frm) {
	// 	var unallocated_amount = 0
		
	// 	if (frm.doc.party) {
	// 		unallocated_amount = (frm.doc.monto_solicitado_base - frm.doc.base_total_allocated_amount) / frm.doc.exchange_rate
	// 	}

	// 	frm.set_value("unallocated_amount", unallocated_amount)
	// 	frm.trigger("set_difference_amount")
	// },

	// set_difference_amount(frm) {
	// 	var difference_amount = 0
	// 	var base_unallocated_amount = flt(frm.doc.unallocated_amount) * frm.doc.exchange_rate

	// 	var base_party_amount = flt(frm.doc.base_total_allocated_amount) + base_unallocated_amount

	// 	difference_amount = flt(frm.doc.monto_solicitado_base) - base_party_amount

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
				method: "erpnext.accounts.doctype.payment_entry.payment_entry.get_reference_details",
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
		frm.events.set_monto_solicitado(frm)
	},

	references_remove(frm) {
		frm.events.set_monto_solicitado(frm)
	}
})
