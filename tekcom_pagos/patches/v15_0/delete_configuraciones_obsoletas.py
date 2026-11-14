import frappe


# Replaced by Configuraciones de Pagos y Viaticos; parents first, then their child tables
DOCTYPES = [
	"Configuracion de Viaticos",
	"Configuracion de Solicitudes de Pago",
	"Configuracion Pagos y Viaticos por Company",
	"Configuracion Viaticos Cuentas Contables",
	"Configuracion Viaticos por Centro de Costo",
	"Cuentas de Viaticos",
	"Modo de Pago de Configuracion de Solicitudes de Viaticos",
	"Configuracion de Solicitudes de Pago por Centro de Costo",
	"Modo de Pago de Configuracion de Solicitudes de Pago",
	"Mapa Company Customer",
]


def execute():
	for doctype in DOCTYPES:
		frappe.delete_doc("DocType", doctype, force=True, ignore_missing=True)
