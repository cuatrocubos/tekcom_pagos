# Copyright (c) 2025, Cuatrocubos Soluciones and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ConfiguracionesdePagosyViaticos(Document):
	def validate(self):
		self.has_user_changed();	

	def has_user_changed(self):
		old_doc = self.get_doc_before_save()
  
		if self.is_new():
			return

		if old_doc is not None:
			# Iterate through all fields in the document
			for field in self.meta.fields:
				# Check if the field type is 'Link' and the option is 'User'
				if field.fieldtype == 'Link' and field.options == 'User':
					fieldname = field.fieldname
					# Compare the value in the current document with the old document
					if self.get(fieldname) != old_doc.get(fieldname):
						# Determine the doctype based on the fieldname suffix
						if fieldname.endswith('_pagos'):
							doctype = "Solicitud de Pago"
						elif fieldname.endswith('_viaticos'):
							doctype = ["Solicitud de Viaticos", "Liquidacion de Viaticos"]
						else:
							continue

						# Perform bulk update for the determined doctype(s)
						if isinstance(doctype, list):
							for dt in doctype:
								frappe.db.bulk_update(dt, {
									fieldname.split('_')[0]: self.get(fieldname)
								}, "name", update_modified=False)
						else:
							frappe.db.bulk_update(doctype, {
								fieldname.split('_')[0]: self.get(fieldname)
							}, "name", update_modified=False)

@frappe.whitelist()
def get_configuraciones_de_pagos(company, cost_center=None):
	configuracion_pagos_viaticos = frappe.get_doc('Configuraciones de Pagos y Viaticos')

	configuracion_predeterminada = configuracion_pagos_viaticos.predeterminados_de_pagos_y_viaticos
	configuracion_centro_costos = configuracion_pagos_viaticos.predeterminados_centro_costos

	revisor_predeterminado = None
	aprobador_predeterminado = None
	pagador_predeterminado = None
	cuenta_cobrar_empleado = None
	cuenta_anticipo_viaticos = None

	# Filter configuracion_predeterminada by company
	predeterminado = next((ele for ele in configuracion_predeterminada if ele.company == company), None)
	if predeterminado:
		revisor_predeterminado = predeterminado.revisor_predeterminado_pagos
		aprobador_predeterminado = predeterminado.aprobador_predeterminado_pagos
		pagador_predeterminado = predeterminado.pagador_predeterminado_pagos
		cuenta_cobrar_empleado = predeterminado.cuenta_cobrar_empleado
		cuenta_anticipo_viaticos = predeterminado.cuenta_anticipo_viaticos

	# Filter configuracion_centro_costos by company and cost_center
	if cost_center is not None:
		cc_predeterminado = next((ele for ele in configuracion_centro_costos if ele.company == company and ele.cost_center == cost_center), None)
		if cc_predeterminado:
			revisor_predeterminado = cc_predeterminado.revisor_predeterminado_pagos
			aprobador_predeterminado = cc_predeterminado.aprobador_predeterminado_pagos
			pagador_predeterminado = cc_predeterminado.pagador_predeterminado_pagos

	return {
		"revisor_predeterminado": revisor_predeterminado,
		"aprobador_predeterminado": aprobador_predeterminado,
		"pagador_predeterminado": pagador_predeterminado,
		"cuenta_cobrar_empleado": cuenta_cobrar_empleado,
		"cuenta_anticipo_viaticos": cuenta_anticipo_viaticos
	}

@frappe.whitelist()
def get_configuraciones_de_viaticos(company, cost_center=None):
	configuracion_pagos_viaticos = frappe.get_doc('Configuraciones de Pagos y Viaticos')

	configuracion_predeterminada = configuracion_pagos_viaticos.predeterminados_de_pagos_y_viaticos
	configuracion_centro_costos = configuracion_pagos_viaticos.predeterminados_centro_costos

	revisor_predeterminado = None
	aprobador_predeterminado = None
	pagador_predeterminado = None

	# Filter configuracion_predeterminada by company
	predeterminado = next((ele for ele in configuracion_predeterminada if ele.company == company), None)
	if predeterminado:
		revisor_predeterminado = predeterminado.revisor_predeterminado_viaticos
		aprobador_predeterminado = predeterminado.aprobador_predeterminado_viaticos
		pagador_predeterminado = predeterminado.pagador_predeterminado_viaticos

	# Filter configuracion_centro_costos by company and cost_center
	if cost_center is not None:
		cc_predeterminado = next((ele for ele in configuracion_centro_costos if ele.company == company and ele.cost_center == cost_center), None)
		if cc_predeterminado:
			revisor_predeterminado = cc_predeterminado.revisor_predeterminado_viaticos
			aprobador_predeterminado = cc_predeterminado.aprobador_predeterminado_viaticos
			pagador_predeterminado = cc_predeterminado.pagador_predeterminado_viaticos

	return {
		"revisor_predeterminado": revisor_predeterminado,
		"aprobador_predeterminado": aprobador_predeterminado,
		"pagador_predeterminado": pagador_predeterminado
	}
 
@frappe.whitelist()
def get_configuraciones_de_compras(company, cost_center=None):
	configuracion_pagos_viaticos = frappe.get_doc('Configuraciones de Pagos y Viaticos')

	configuracion_predeterminada = configuracion_pagos_viaticos.predeterminados_de_pagos_y_viaticos
	configuracion_centro_costos = configuracion_pagos_viaticos.predeterminados_centro_costos

	revisor_predeterminado = None
	aprobador_predeterminado = None

	# Filter configuracion_predeterminada by company
	predeterminado = next((ele for ele in configuracion_predeterminada if ele.company == company), None)
	if predeterminado:
		revisor_predeterminado = predeterminado.revisor_predeterminado_compras
		aprobador_predeterminado = predeterminado.aprobador_predeterminado_compras

	# Filter configuracion_centro_costos by company and cost_center
	if cost_center is not None:
		cc_predeterminado = next((ele for ele in configuracion_centro_costos if ele.company == company and ele.cost_center == cost_center), None)
		if cc_predeterminado:
			revisor_predeterminado = cc_predeterminado.revisor_predeterminado_compras
			aprobador_predeterminado = cc_predeterminado.aprobador_predeterminado_compras
  
	return {
		"revisor_predeterminado": revisor_predeterminado,
		"aprobador_predeterminado": aprobador_predeterminado,
	}
 
@frappe.whitelist()
def get_configuraciones_cuentas(company):
	configuracion_pagos_viaticos = frappe.get_doc('Configuraciones de Pagos y Viaticos')

	configuracion_predeterminada = configuracion_pagos_viaticos.contabilidad

	parte_customer = None
	parte_supplier = None

	# Filter configuracion_predeterminada by company
	predeterminado = next((ele for ele in configuracion_predeterminada if ele.company == company), None)
	if predeterminado:
		parte_customer = predeterminado.customer
		parte_supplier = predeterminado.supplier
		

	return {
		"parte_customer": parte_customer,
		"parte_supplier": parte_supplier
	}