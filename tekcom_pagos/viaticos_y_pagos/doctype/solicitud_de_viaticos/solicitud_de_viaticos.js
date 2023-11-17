// Copyright (c) 2023, Cuatrocubos Soluciones and contributors
// For license information, please see license.txt
{% include "erpnext/public/js/controllers/accounts.js" %}
frappe.provide("erpnext.accounts.dimensions")

frappe.ui.form.on('Solicitud de Viaticos', {
	onload(frm) {
		erpnext.accounts.dimensions.setup_dimension_filters(frm, frm.doctype)
		if (frm.doc.workflow_status == 'Revisado') {
			frappe.meta.get_docfield("Presupuesto Solicitud de Viaticos", "monto_aprobado", frm.doc.name).reqd=1
			frappe.meta.get_docfield("Presupuesto Solicitud de Viaticos", "monto_aprobado", frm.doc.name).read_only=0
		} else {
			frappe.meta.get_docfield("Presupuesto Solicitud de Viaticos", "monto_aprobado", frm.doc.name).reqd=0
			frappe.meta.get_docfield("Presupuesto Solicitud de Viaticos", "monto_aprobado", frm.doc.name).read_only=1
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
		if (frm.doc.workflow_status == 'Solicitado') {
			if (frm.doc.revisado_por == "" || frm.doc.revisado_por == null) {
				frappe.call({
					method: "tekcom_pagos.viaticos_y_pagos.doctype.solicitud_de_viaticos.solicitud_de_viaticos.get_users_by_role",
					args: {
						role: 'Revisor de Solicitud de Viaticos'
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
						role: 'Aprobador de Solicitud de Viaticos'
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

		frm.set_query("depositar_a_cuenta", function() {
			return {
				filters: {
					is_company_account: 0,
					party_type: 'Employee',
					party: frm.doc.depositar_a
				}
			}
		})

		// frm.set_query("solicitante", function() {
		// 	frm.events.validate_company()
		// })
	},

	validate_company(frm) {
		if (!frm.doc.company){
			frappe.throw({message:__("Please select a Company first."), title: __("Mandatory")});
		}
	},

	fecha_salida(frm) {
		if (frm.doc.fecha_salida && frm.doc.fecha_retorno) {
			let dias_viaje = frm.events.get_dias_de_viaje(frm)
			if (dias_viaje > 7 || dias_viaje < 0) {
				frappe.throw({ message:__("Días de viaje superior a 7, favor corregir fecha de salida o retorno."), tile: __("Mandatory")})
			}
		}
	},

	fecha_retorno(frm) {
		if (frm.doc.fecha_salida && frm.doc.fecha_retorno) {
			let dias_viaje = frm.events.get_dias_de_viaje(frm)
			if (dias_viaje > 7 || dias_viaje < 0) {
				frappe.throw({ message:__("Días de viaje superior a 7, favor corregir fecha de salida o retorno."), tile: __("Mandatory")})
			}
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

	refresh(frm) {
		if (frm.doc.workflow_status == 'Pagado' || frm.doc.workflow_status == 'Contabilizado') {
			frm.add_custom_button(__('Liquidacion de Viaticos'), () => {
				frm.events.make_liquidacion_viaticos()
			})
		}
	},

	make_liquidacion_viaticos() {
		frappe.model.open_mapped_doc({
			method: 'tekcom_pagos.viaticos_y_pagos.doctype.solicitud_de_viaticos.solicitud_de_viaticos.make_liquidacion_viaticos',
			frm: cur_frm
		})
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
		cur_frm.set_df_property

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
		var total_solicitado = frm.events.get_total_solicitado_alimentacion(frm)
		$.each(frm.doc.presupuesto || [], function(i, row) {
			if (row.tipo_gasto == "Alimentación") {
				alimentacion_rows_count += 1
			}
		})
		if (alimentacion_rows_count == 0) {
			var p = frm.add_child("presupuesto")
			p.tipo_gasto = "Alimentación"
			p.monto_solicitado = total_solicitado
		} else {
			$.each(frm.doc.presupuesto, function(i, row) {
				if (row.tipo_gasto == "Alimentación") {
					frappe.model.set_value(row.doctype, row.name, "monto_solicitado", total_solicitado)
				}
			})
		}
		frm.events.set_totales(frm)
	},

	set_asignacion_diaria_alimentacion(frm, row, cdt, cdn) {
		let hora_salida = new Date(frm.doc.fecha_salida).getHours()
		let hora_retorno = new Date(frm.doc.fecha_retorno).getHours()
		let tiempos_dia_1 = 3
		let tiempos_dia_ultimo = 3
		tiempos_dia_1 = hora_salida > 12 ? 1 : hora_salida > 7 ? 2 : 3
		tiempos_dia_ultimo = hora_retorno >= 17 ? 3 : hora_retorno > 12 ? 2 : 1
		frappe.model.set_value(cdt, cdn, "tiempos_dia_1", tiempos_dia_1)
		switch (row.dias_viaje) {
			case 1:
				frappe.model.set_value(cdt, cdn, "dia_viaje_1", flt(tiempos_dia_1) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_2", flt(0))
				frappe.model.set_value(cdt, cdn, "dia_viaje_3", flt(0))
				frappe.model.set_value(cdt, cdn, "dia_viaje_4", flt(0))
				frappe.model.set_value(cdt, cdn, "dia_viaje_5", flt(0))
				frappe.model.set_value(cdt, cdn, "dia_viaje_6", flt(0))
				frappe.model.set_value(cdt, cdn, "dia_viaje_7", flt(0))
				frappe.model.set_value(cdt, cdn, "tiempos_dia_2", 0)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_3", 0)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_4", 0)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_5", 0)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_6", 0)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_7", 0)
				break;
			case 2:
				frappe.model.set_value(cdt, cdn, "dia_viaje_1", flt(tiempos_dia_1) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_2", flt(tiempos_dia_ultimo) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "tiempos_dia_2", tiempos_dia_ultimo)
				frappe.model.set_value(cdt, cdn, "dia_viaje_3", flt(0))
				frappe.model.set_value(cdt, cdn, "dia_viaje_4", flt(0))
				frappe.model.set_value(cdt, cdn, "dia_viaje_5", flt(0))
				frappe.model.set_value(cdt, cdn, "dia_viaje_6", flt(0))
				frappe.model.set_value(cdt, cdn, "dia_viaje_7", flt(0))
				frappe.model.set_value(cdt, cdn, "tiempos_dia_3", 0)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_4", 0)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_5", 0)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_6", 0)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_7", 0)
				break;
			case 3:
				frappe.model.set_value(cdt, cdn, "dia_viaje_1", flt(tiempos_dia_1) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_2", flt(3) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_3", flt(tiempos_dia_ultimo) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "tiempos_dia_3", tiempos_dia_ultimo)
				frappe.model.set_value(cdt, cdn, "dia_viaje_4", flt(0))
				frappe.model.set_value(cdt, cdn, "dia_viaje_5", flt(0))
				frappe.model.set_value(cdt, cdn, "dia_viaje_6", flt(0))
				frappe.model.set_value(cdt, cdn, "dia_viaje_7", flt(0))
				frappe.model.set_value(cdt, cdn, "tiempos_dia_2", 3)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_4", 0)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_5", 0)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_6", 0)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_7", 0)
				break;
			case 4:
				frappe.model.set_value(cdt, cdn, "dia_viaje_1", flt(tiempos_dia_1) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_2", flt(3) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_3", flt(3) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_4", flt(tiempos_dia_ultimo) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "tiempos_dia_4", tiempos_dia_ultimo)
				frappe.model.set_value(cdt, cdn, "dia_viaje_5", flt(0))
				frappe.model.set_value(cdt, cdn, "dia_viaje_6", flt(0))
				frappe.model.set_value(cdt, cdn, "dia_viaje_7", flt(0))
				frappe.model.set_value(cdt, cdn, "tiempos_dia_2", 3)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_3", 3)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_5", 0)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_6", 0)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_7", 0)
				break;
			case 5:
				frappe.model.set_value(cdt, cdn, "dia_viaje_1", flt(tiempos_dia_1) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_2", flt(3) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_3", flt(3) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_4", flt(3) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_5", flt(tiempos_dia_ultimo) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "tiempos_dia_5", tiempos_dia_ultimo)
				frappe.model.set_value(cdt, cdn, "dia_viaje_6", flt(0))
				frappe.model.set_value(cdt, cdn, "dia_viaje_7", flt(0))
				frappe.model.set_value(cdt, cdn, "tiempos_dia_2", 3)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_3", 3)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_4", 3)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_6", 0)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_7", 0)
				break;
			case 6:
				frappe.model.set_value(cdt, cdn, "dia_viaje_1", flt(tiempos_dia_1) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_2", flt(3) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_3", flt(3) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_4", flt(3) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_5", flt(3) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_6", flt(tiempos_dia_ultimo) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "tiempos_dia_6", tiempos_dia_ultimo)
				frappe.model.set_value(cdt, cdn, "dia_viaje_7", flt(0))
				frappe.model.set_value(cdt, cdn, "tiempos_dia_2", 3)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_3", 3)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_4", 3)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_5", 3)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_7", 0)
			case 7:
				frappe.model.set_value(cdt, cdn, "dia_viaje_1", flt(tiempos_dia_1) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_2", flt(3) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_3", flt(3) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_4", flt(3) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_5", flt(3) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_6", flt(3) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "dia_viaje_7", flt(tiempos_dia_ultimo) * flt(row.asignacion_alimentacion))
				frappe.model.set_value(cdt, cdn, "tiempos_dia_2", 3)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_3", 3)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_4", 3)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_5", 3)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_6", 3)
				frappe.model.set_value(cdt, cdn, "tiempos_dia_7", tiempos_dia_ultimo)
				break;
			default:
				frappe.model.set_value(cdt, cdn, "dia_viaje_1", flt(tiempos_dia_1) * flt(row.asignacion_alimentacion))
				break;
			}
			var total = flt(row.dia_viaje_1) + flt(row.dia_viaje_2) + flt(row.dia_viaje_3) + flt(row.dia_viaje_4) + flt(row.dia_viaje_5) + flt(row.dia_viaje_6) + flt(row.dia_viaje_7)
			frappe.model.set_value(cdt, cdn, "total_solicitado", total)

			if ((row.dias_viaje >= 0)) {
				switch (row.dias_viaje) {
					case 1:
						frappe.model.set_value(cdt, cdn, "fecha_dia_1", frm.doc.fecha_salida)
						frappe.model.set_value(cdt, cdn, "fecha_dia_2", "")
						frappe.model.set_value(cdt, cdn, "fecha_dia_3", "")
						frappe.model.set_value(cdt, cdn, "fecha_dia_4", "")
						frappe.model.set_value(cdt, cdn, "fecha_dia_5", "")
						frappe.model.set_value(cdt, cdn, "fecha_dia_6", "")
						frappe.model.set_value(cdt, cdn, "fecha_dia_7", "")
						break;
					case 2:
						frappe.model.set_value(cdt, cdn, "fecha_dia_1", frm.doc.fecha_salida)
						frappe.model.set_value(cdt, cdn, "fecha_dia_2", frm.doc.fecha_retorno)
						frappe.model.set_value(cdt, cdn, "fecha_dia_3", "")
						frappe.model.set_value(cdt, cdn, "fecha_dia_4", "")
						frappe.model.set_value(cdt, cdn, "fecha_dia_5", "")
						frappe.model.set_value(cdt, cdn, "fecha_dia_6", "")
						frappe.model.set_value(cdt, cdn, "fecha_dia_7", "")
						break;
					case 3:
						frappe.model.set_value(cdt, cdn, "fecha_dia_1", frm.doc.fecha_salida)
						frappe.model.set_value(cdt, cdn, "fecha_dia_2", frappe.datetime.add_days(frm.doc.fecha_salida, 1))
						frappe.model.set_value(cdt, cdn, "fecha_dia_3", frm.doc.fecha_retorno)
						frappe.model.set_value(cdt, cdn, "fecha_dia_4", "")
						frappe.model.set_value(cdt, cdn, "fecha_dia_5", "")
						frappe.model.set_value(cdt, cdn, "fecha_dia_6", "")
						frappe.model.set_value(cdt, cdn, "fecha_dia_7", "")
						break;
					case 4:
						frappe.model.set_value(cdt, cdn, "fecha_dia_1", frm.doc.fecha_salida)
						frappe.model.set_value(cdt, cdn, "fecha_dia_2", frappe.datetime.add_days(frm.doc.fecha_salida, 1))
						frappe.model.set_value(cdt, cdn, "fecha_dia_3", frappe.datetime.add_days(frm.doc.fecha_salida, 2))
						frappe.model.set_value(cdt, cdn, "fecha_dia_4", frm.doc.fecha_retorno)
						frappe.model.set_value(cdt, cdn, "fecha_dia_5", "")
						frappe.model.set_value(cdt, cdn, "fecha_dia_6", "")
						frappe.model.set_value(cdt, cdn, "fecha_dia_7", "")
						break;
					case 5:
						frappe.model.set_value(cdt, cdn, "fecha_dia_1", frm.doc.fecha_salida)
						frappe.model.set_value(cdt, cdn, "fecha_dia_2", frappe.datetime.add_days(frm.doc.fecha_salida, 1))
						frappe.model.set_value(cdt, cdn, "fecha_dia_3", frappe.datetime.add_days(frm.doc.fecha_salida, 2))
						frappe.model.set_value(cdt, cdn, "fecha_dia_4", frappe.datetime.add_days(frm.doc.fecha_salida, 3))
						frappe.model.set_value(cdt, cdn, "fecha_dia_5", frm.doc.fecha_retorno)
						frappe.model.set_value(cdt, cdn, "fecha_dia_6", "")
						frappe.model.set_value(cdt, cdn, "fecha_dia_7", "")
						break;
					case 6:
						frappe.model.set_value(cdt, cdn, "fecha_dia_1", frm.doc.fecha_salida)
						frappe.model.set_value(cdt, cdn, "fecha_dia_2", frappe.datetime.add_days(frm.doc.fecha_salida, 1))
						frappe.model.set_value(cdt, cdn, "fecha_dia_3", frappe.datetime.add_days(frm.doc.fecha_salida, 2))
						frappe.model.set_value(cdt, cdn, "fecha_dia_4", frappe.datetime.add_days(frm.doc.fecha_salida, 3))
						frappe.model.set_value(cdt, cdn, "fecha_dia_5", frappe.datetime.add_days(frm.doc.fecha_salida, 4))
						frappe.model.set_value(cdt, cdn, "fecha_dia_6", frm.doc.fecha_retorno)
						frappe.model.set_value(cdt, cdn, "fecha_dia_6", "")
						frappe.model.set_value(cdt, cdn, "fecha_dia_7", "")
					case 7:
						frappe.model.set_value(cdt, cdn, "fecha_dia_1", frm.doc.fecha_salida)
						frappe.model.set_value(cdt, cdn, "fecha_dia_2", frappe.datetime.add_days(frm.doc.fecha_salida, 1))
						frappe.model.set_value(cdt, cdn, "fecha_dia_3", frappe.datetime.add_days(frm.doc.fecha_salida, 2))
						frappe.model.set_value(cdt, cdn, "fecha_dia_4", frappe.datetime.add_days(frm.doc.fecha_salida, 3))
						frappe.model.set_value(cdt, cdn, "fecha_dia_5", frappe.datetime.add_days(frm.doc.fecha_salida, 4))
						frappe.model.set_value(cdt, cdn, "fecha_dia_6", frappe.datetime.add_days(frm.doc.fecha_salida, 5))
						frappe.model.set_value(cdt, cdn, "fecha_dia_7", frm.doc.fecha_retorno)
						break;
					default:
						frappe.model.set_value(cdt, cdn, "fecha_dia_1", frm.doc.fecha_salida)
						break;
					}
			}
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
		console.log('dias_viaje')
		var row = locals[cdt][cdn]
		
		frm.refresh_fields()
		frm.events.set_asignacion_diaria_alimentacion(frm, row, cdt, cdn)
		frm.events.set_or_update_alimentacion(frm)
	},

	asignacion_alimentacion(frm, cdt, cdn) {
		var row = locals[cdt][cdn]
		frm.refresh_fields()
		frm.events.set_asignacion_diaria_alimentacion(frm, row, cdt, cdn)
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
