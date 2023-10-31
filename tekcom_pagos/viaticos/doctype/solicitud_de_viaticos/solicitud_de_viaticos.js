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
			let dias_viaje = frm.events.get_dias_de_viaje(frm)
			$.each(integrantes, function(i, d) {
				var c = frm.add_child("personas")
				c.employee = d.empleado
				c.dias_viaje = dias_viaje
			})
		}

		frm.refresh_fields()
	},

	hide_unhide_fields(frm) {
		// var company_currency = frm.doc.company ? frappe.get_doc(":Company", frm.doc.company).default_currency : "";

		// frm.toggle_display("conversion_rate", (frm.doc.currency != company_currency));
		// frm.toggle_display("monto_pagar_base", (frm.doc.currency != company_currency));
		// var df = frappe.meta.get_docfield("Personas Solicitud de Viaticos", "asignacion_alimentacion", frm.doc.name)
		// df.read_only = 

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

	update_grid_fields(frm) {
		cur_frm.fields_dict['personas'].grid.grid_rows.forEach((row) => {
			if (row.base_asignacion_alimentacion) {
				row.docfields.forEach((df) => {
					if (fieldname_arr.includes(df.fieldname)) {
						df.read_only = 1
					}
				})
			}
		})
	},

	get_dias_de_viaje(frm) {
		if (!frm.doc.fecha_salida || !frm.doc.fecha_retorno) {
			frappe.throw({
				message:__("Ingrese la fecha de salida y retorno antes de agregar personas."),
				title:__("Mandatory")
			})
		}

		let fecha_salida = new Date(frm.doc.fecha_salida)
		let fecha_retorno = new Date(frm.doc.fecha_retorno)

		// let diferencia_en_tiempo = fecha_retorno.getTime() - fecha_salida.getTime()
		// let dias_viaje = Math.ceil(diferencia_en_tiempo / (1000 * 3600 * 24))
		let dias_viaje = (fecha_retorno.getDate() - fecha_salida.getDate()) + 1
		return dias_viaje
	},

	set_totales(frm) {
		var total_anticipo_solicitado = flt(0)
		var total_anticipo_aprobado = flt(0)

		$.each(frm.doc.presupuesto || [], function(i, row) {
			if (row.monto_solicitado) {
				total_anticipo_solicitado += flt(row.monto_solicitado)
			}
			if (row.monto_aprobado) { 
				total_anticipo_aprobado += flt(row.monto_aprobado)
			}
		})

		frm.set_value("total_anticipo_solicitado", total_anticipo_solicitado)
		frm.set_value("total_anticipo_aprobado", total_anticipo_aprobado)

		frm.refresh_fields()
	},

	get_total_solicitado_alimentacion(frm) {
		var total_solicitado = flt(0)

		$.each(frm.doc.personas || [], function(i, row) {
			if (row.total_solicitado) {
				total_solicitado += flt(row.total_solicitado)
			}
		})
		return total_solicitado
	},

	set_or_update_alimentacion(frm) {
		var alimentacion_rows_count = 0
		$.each(frm.doc.presupuesto || [], function(i, row) {
			if (row.tipo_gasto == "Alimentacion") {
				alimentacion_rows_count += 1
			}
		})
		if (alimentacion_rows_count == 0) {
			var p = frm.add_child("presupuesto")
			p.tipo_gasto = "Alimentacion"
			p.monto_solicitado = frm.events.get_total_solicitado_alimentacion(frm)
		} else {
			$.each(frm.doc.presupuesto, function(i, row) {
				console.log(row)
				if (row.tipo_gasto == "Alimentacion") {
					frappe.model.set_value(row.doctype, row.name, "monto_solicitado", frm.events.get_total_solicitado_alimentacion(frm))
				}
			})
		}
		frm.events.set_totales(frm)
	},
});

frappe.ui.form.on("Presupuesto Solicitud de Viaticos", {
	monto_solicitado(frm, cdt, cdn) {
		frm.events.set_totales(frm)
	}
} )

frappe.ui.form.on('Personas de Solicitud de Viaticos', {
	personas_add(frm, cdt, cdn) {
		var row = locals[cdt][cdn]
		let dias_viaje = frm.events.get_dias_de_viaje(frm)
		row.dias_viaje = dias_viaje
		frm.refresh_field("personas")
	},

	employee(frm, cdt, cdn) {
		var row = locals[cdt][cdn]
		if (row.employee) {
			frappe.db.get_value("Employee", row.employee, "custom_asignacion_viaticos_alimentacion", (values) => {
				// frm.set_df_property(cdt, cdn, "custom_asignacion_viaticos_alimentacion", "read_only", values.custom_asignacion_viaticos_alimentacion > 0 ? 1 : 0)
				if (values.custom_asignacion_viaticos_alimentacion > 0) {
					frappe.model.set_value(cdt, cdn, "base_asignacion_alimentacion", values.custom_asignacion_viaticos_alimentacion)
					frappe.model.set_value(cdt, cdn, "asignacion_alimentacion", values.custom_asignacion_viaticos_alimentacion)
				}
			})
		}
		frm.refresh_fields()
		// frm.events.update_grid_fields(frm)
	},

	dias_viaje(frm, cdt, cdn) {
		var row = locals[cdt][cdn]
		if ((row.dias_viaje >= 0) && (row.asignacion_alimentacion >= 0)) {
			let hora_salida = new Date(frm.doc.fecha_salida).getHours()
			let hora_retorno = new Date(frm.doc.fecha_retorno).getHours()
			let tiempos_dia_1 = 3
			let tiempos_dia_ultimo = 3
			tiempos_dia_1 = hora_salida > 12 ? 1 : hora_salida > 6 ? 2 : 3
			tiempos_dia_ultimo = hora_retorno > 18 ? 3 : hora_retorno > 12 ? 2 : 1
			switch (row.dias_viaje) {
				case 1:
					frappe.model.set_value(cdt, cdn, "dia_viaje_1", flt(tiempos_dia_1) * flt(row.asignacion_alimentacion))
				case 2:
					frappe.model.set_value(cdt, cdn, "dia_viaje_1", flt(tiempos_dia_1) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_2", flt(tiempos_dia_ultimo) * flt(row.asignacion_alimentacion))
				case 3:
					frappe.model.set_value(cdt, cdn, "dia_viaje_1", flt(tiempos_dia_1) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_2", flt(3) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_3", flt(tiempos_dia_ultimo) * flt(row.asignacion_alimentacion))
				case 4:
					frappe.model.set_value(cdt, cdn, "dia_viaje_1", flt(tiempos_dia_1) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_2", flt(3) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_3", flt(3) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_4", flt(tiempos_dia_ultimo) * flt(row.asignacion_alimentacion))
				case 5:
					frappe.model.set_value(cdt, cdn, "dia_viaje_1", flt(tiempos_dia_1) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_2", flt(3) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_3", flt(3) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_4", flt(3) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_5", flt(tiempos_dia_ultimo) * flt(row.asignacion_alimentacion))
				case 6:
					frappe.model.set_value(cdt, cdn, "dia_viaje_1", flt(tiempos_dia_1) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_2", flt(3) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_3", flt(3) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_4", flt(3) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_5", flt(3) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_6", flt(tiempos_dia_ultimo) * flt(row.asignacion_alimentacion))
				case 7:
					frappe.model.set_value(cdt, cdn, "dia_viaje_1", flt(tiempos_dia_1) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_2", flt(3) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_3", flt(3) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_4", flt(3) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_5", flt(3) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_6", flt(3) * flt(row.asignacion_alimentacion))
					frappe.model.set_value(cdt, cdn, "dia_viaje_7", flt(tiempos_dia_ultimo) * flt(row.asignacion_alimentacion))
			}
			var total = flt(row.dia_viaje_1) + flt(row.dia_viaje_2) + flt(row.dia_viaje_3) + flt(row.dia_viaje_4) + flt(row.dia_viaje_5) + flt(row.dia_viaje_6) + flt(row.dia_viaje_7)
			console.log('total:', total)
			frappe.model.set_value(cdt, cdn, "total_solicitado", total)
		}
		frm.refresh_fields()
		frm.events.set_or_update_alimentacion(frm)
	},

	// asignacion_alimentacion(frm, cdt, cdn) {
	// 	var row = locals[cdt][cdn]
	// 	if ((row.dias_viaje >= 0) && (row.asignacion_alimentacion >= 0)) {
	// 		var total = flt(row.asignacion_alimentacion) * flt(row.dias_viaje)
	// 		frappe.model.set_value(cdt, cdn, "total_solicitado", total)
	// 	}
	// 	frm.events.set_or_update_alimentacion(frm)
	// },

	total_solicitado(frm, cdt, cdn) {
		frm.events.set_or_update_alimentacion(frm)
	}
})
