import frappe
from frappe.utils import flt


def execute():
	frappe.reload_doc("Viaticos", "doctype", "presupuesto_de_liquidacion_de_viaticos")
	frappe.reload_doc("Viaticos", "doctype", "detalle_de_liquidacion_de_viaticos")
	frappe.reload_doc("Viaticos", "doctype", "liquidacion_de_viaticos")

	duplicate_parents = frappe.db.sql(
		"""
		SELECT parent
		FROM `tabPresupuesto de Liquidacion de Viaticos`
		GROUP BY parent, tipo_gasto
		HAVING COUNT(*) > 1
		""",
		as_dict=True,
	)
	affected_parents = {row.parent for row in duplicate_parents}

	for parent in affected_parents:
		# docs may be submitted, so fix via direct db writes instead of doc.save()
		exchange_rate = flt(frappe.db.get_value("Liquidacion de Viaticos", parent, "exchange_rate")) or 1

		presupuesto_rows = frappe.get_all(
			"Presupuesto de Liquidacion de Viaticos",
			filters={"parent": parent},
			fields=["name", "tipo_gasto", "monto_solicitado", "monto_aprobado"],
			order_by="idx asc",
		)
		detalle_rows = frappe.get_all(
			"Detalle de Liquidacion de Viaticos",
			filters={"parent": parent},
			fields=["expense_type", "total", "impuestos"],
		)

		grouped = {}
		for row in presupuesto_rows:
			existing = grouped.get(row.tipo_gasto)
			if existing:
				existing["monto_solicitado"] += flt(row.monto_solicitado)
				existing["monto_aprobado"] += flt(row.monto_aprobado)
				existing["extra_names"].append(row.name)
			else:
				grouped[row.tipo_gasto] = {
					"name": row.name,
					"monto_solicitado": flt(row.monto_solicitado),
					"monto_aprobado": flt(row.monto_aprobado),
					"extra_names": [],
				}

		total_solicitado = flt(0)
		total_ejecutado = flt(0)
		total_reembolso = flt(0)

		for tipo_gasto, data in grouped.items():
			monto_ejecutado = sum(flt(d.total) for d in detalle_rows if d.expense_type == tipo_gasto)
			diferencia = flt(data["monto_aprobado"]) - flt(monto_ejecutado)

			frappe.db.set_value(
				"Presupuesto de Liquidacion de Viaticos",
				data["name"],
				{
					"monto_solicitado": data["monto_solicitado"],
					"monto_solicitado_base": flt(data["monto_solicitado"]) * exchange_rate,
					"monto_aprobado": data["monto_aprobado"],
					"monto_aprobado_base": flt(data["monto_aprobado"]) * exchange_rate,
					"monto_ejecutado": monto_ejecutado,
					"monto_ejecutado_base": flt(monto_ejecutado) * exchange_rate,
					"diferencia": diferencia,
					"diferencia_base": flt(diferencia) * exchange_rate,
				},
				update_modified=False,
			)

			if data["extra_names"]:
				frappe.db.delete("Presupuesto de Liquidacion de Viaticos", {"name": ["in", data["extra_names"]]})

			total_solicitado += flt(data["monto_solicitado"])
			total_ejecutado += flt(monto_ejecutado)
			total_reembolso += flt(diferencia)

		total_impuestos = sum(flt(d.impuestos) for d in detalle_rows)

		frappe.db.set_value(
			"Liquidacion de Viaticos",
			parent,
			{
				"total_solicitado": total_solicitado,
				"total_solicitado_base": flt(total_solicitado) * exchange_rate,
				"total_ejecutado": total_ejecutado,
				"total_ejecutado_base": flt(total_ejecutado) * exchange_rate,
				"total_reembolso": total_reembolso,
				"total_reembolso_base": flt(total_reembolso) * exchange_rate,
				"total_impuestos": total_impuestos,
				"total_impuestos_base": flt(total_impuestos) * exchange_rate,
			},
			update_modified=False,
		)

		frappe.logger().info(f"fix_duplicate_presupuesto_viaticos: merged duplicate rows for {parent}")
