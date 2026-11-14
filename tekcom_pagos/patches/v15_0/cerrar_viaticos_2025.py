import frappe

CORTE = "2026-01-01"
LIQUIDACIONES_EN_PROCESO = ("Approved", "En Revisión", "Revisado", "En Revisión Contable")
SOLICITUDES_EN_PROCESO = ("Pagado", "Recibido en Contabilidad")
COMENTARIO = "Marcada como Contabilizado por el cierre de viáticos 2025 (patch cerrar_viaticos_2025), sin generar asientos ni anticipos."


def execute():
	"""Viáticos up to 2025 were settled by hand under the previous flow: close the ones still in progress as
	Contabilizado without posting. Direct updates on purpose: saving would run Contabilizar (liquidaciones) or create
	the Employee Advance and its payment (solicitudes). Their Employee Advances are left as they are; Draft and Rejected
	documents are not touched."""
	cerrar("Liquidacion de Viaticos", "fecha_liquidacion", LIQUIDACIONES_EN_PROCESO)
	cerrar("Solicitud de Viaticos", "fecha_solicitud", SOLICITUDES_EN_PROCESO)


def cerrar(doctype, campo_fecha, estados):
	nombres = frappe.get_all(
		doctype,
		filters={"docstatus": 0, "workflow_status": ["in", estados], campo_fecha: ["<", CORTE]},
		pluck="name",
	)
	if not nombres:
		return

	values = {"docstatus": 1, "workflow_status": "Contabilizado"}
	if frappe.get_meta(doctype).has_field("status"):
		values["status"] = "Submitted"
	for chunk in chunks(nombres):
		frappe.db.set_value(doctype, {"name": ["in", chunk]}, values, update_modified=False)
		for table in frappe.get_meta(doctype).get_table_fields():
			frappe.db.set_value(table.options, {"parent": ["in", chunk], "parenttype": doctype}, "docstatus", 1, update_modified=False)

	for name in nombres:
		frappe.get_doc({
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": doctype,
			"reference_name": name,
			"content": COMENTARIO,
		}).insert(ignore_permissions=True)


def chunks(items, size=500):
	for i in range(0, len(items), size):
		yield items[i:i + size]
