// Copyright (c) 2023, Cuatrocubos Soluciones and contributors
// For license information, please see license.txt

frappe.ui.form.on('Presupuesto de Gastos', {
	refresh(frm) {
		frm.events.set_dynamic_labels(frm)
	},

	presupuesto_contra(frm) {
		frm.events.set_dynamic_labels(frm)
	},

	presupuesto_total(frm) {
		frm.events.update_totals(frm)
	},

	set_dynamic_labels(frm) {
		if (frm.doc.presupuesto_contra == "Project") {
			frm.set_df_property("project", "reqd", 1);
			frm.set_df_property("cost_center", "reqd", 0);
		} else if (frm.doc.presupuesto_contra == "Cost Center") {
			frm.set_df_property("cost_center", "reqd", 1);
			frm.set_df_property("project", "reqd", 0);
		} else {
			frm.set_df_property("project", "reqd", 0);
			frm.set_df_property("cost_center", "reqd", 0);
		}

		frm.refresh_fields()
	},
	update_totals(frm) {
		let total_presupuesto = flt(frm.doc.presupuesto_total) || flt(0)
		let total_presupuesto_por_gasto = flt(0)
		let total_solicitado_por_gasto = flt(0)
		let total_aprobado_por_gasto = flt(0)
		let total_disponible_por_gasto = flt(0)

		let total_presupuesto_sin_asignar = flt(0)

		let total_solicitado_sin_tipo_de_gasto = flt(frm.doc.total_solicitado_sin_tipo_de_gasto) || flt(0)
		let total_aprobado_sin_tipo_de_gasto = flt(frm.doc.total_aprobado_sin_tipo_de_gasto) || flt(0)

		$.each(frm.doc.gastos, function(i, row) {
			let monto_presupuestado = flt(row.monto) || flt(0)
			let monto_solicitado = flt(row.monto_total_solicitado) || flt(0)
			let monto_aprobado = flt(row.monto_total_aprobado) || flt(0)
			let monto_disponible = monto_presupuestado - monto_aprobado

			total_presupuesto_por_gasto += monto_presupuestado
			total_solicitado_por_gasto += monto_solicitado
			total_aprobado_por_gasto += monto_aprobado
			total_disponible_por_gasto += monto_disponible

			frappe.model.set_value(row.doctype, row.name, "monto_disponible", monto_disponible)
		})

		total_presupuesto_sin_asignar = total_presupuesto - total_presupuesto_por_gasto
		total_solicitado = total_solicitado_por_gasto + total_solicitado_sin_tipo_de_gasto
		total_aprobado = total_aprobado_por_gasto + total_aprobado_sin_tipo_de_gasto
		total_disponible = total_presupuesto - total_aprobado_por_gasto - total_aprobado_sin_tipo_de_gasto

		frm.set_value("total_presupuesto_sin_asignar", total_presupuesto_sin_asignar)
		frm.set_value("total_presupuestado", total_presupuesto)
		frm.set_value("total_solicitado", total_solicitado)
		frm.set_value("total_aprobado", total_aprobado)
		frm.set_value("total_disponible", total_disponible)

		frm.refresh_fields()
	}
});

frappe.ui.form.on('Detalle de Presupuesto de Gastos', {
	gastos_add(frm, cdt, cdn) {
		frm.events.update_totals(frm)
	},
	gastos_remove(frm, cdt, cdn) {
		frm.events.update_totals(frm)
	},
	monto(frm, cdt, cdn) {
		frm.events.update_totals(frm)
	}
});
