import erpnext
import frappe
from frappe.utils import flt
from erpnext.setup.utils import get_exchange_rate


def execute():
	frappe.reload_doc("Solicitudes de Pagos", "doctype", "solicitud_de_pago")

	# Fill missing currency from company default
	frappe.db.sql(
		"""
		UPDATE `tabSolicitud de Pago` sp
		INNER JOIN `tabCompany` c ON sp.company = c.name
		SET sp.currency = c.default_currency
		WHERE IFNULL(sp.currency, '') = ''
		"""
	)

	# Same-currency (or still empty after join) docs must use rate 1
	frappe.db.sql(
		"""
		UPDATE `tabSolicitud de Pago` sp
		INNER JOIN `tabCompany` c ON sp.company = c.name
		SET sp.conversion_rate = 1
		WHERE IFNULL(sp.conversion_rate, 0) = 0
		AND (IFNULL(sp.currency, '') = '' OR sp.currency = c.default_currency)
		"""
	)

	# Multi-currency docs with missing rate: resolve exchange rate per document
	missing_rate_rows = frappe.db.sql(
		"""
		SELECT sp.name, sp.company, sp.currency, sp.fecha_solicitud, sp.monto_solicitado
		FROM `tabSolicitud de Pago` sp
		INNER JOIN `tabCompany` c ON sp.company = c.name
		WHERE IFNULL(sp.conversion_rate, 0) = 0
		AND IFNULL(sp.currency, '') != ''
		AND sp.currency != c.default_currency
		""",
		as_dict=True,
	)

	for row in missing_rate_rows:
		company_currency = erpnext.get_company_currency(row.company)
		rate = get_exchange_rate(row.currency, company_currency, row.fecha_solicitud) or 1
		frappe.db.set_value(
			"Solicitud de Pago",
			row.name,
			{
				"conversion_rate": rate,
				"monto_solicitado_base": flt(row.monto_solicitado) * flt(rate),
			},
			update_modified=False,
		)

	# Recalculate base for rows where it is empty/0 or not equivalent to monto * rate
	frappe.db.sql(
		"""
		UPDATE `tabSolicitud de Pago`
		SET monto_solicitado_base = ROUND(
			IFNULL(monto_solicitado, 0) * IFNULL(NULLIF(conversion_rate, 0), 1),
			6
		)
		WHERE IFNULL(monto_solicitado, 0) != 0
		AND (
			IFNULL(monto_solicitado_base, 0) = 0
			OR ABS(
				IFNULL(monto_solicitado_base, 0)
				- (IFNULL(monto_solicitado, 0) * IFNULL(NULLIF(conversion_rate, 0), 1))
			) > 0.000001
		)
		"""
	)
