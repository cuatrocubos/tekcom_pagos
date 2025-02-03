# Copyright (c) 2025, Cuatrocubos Soluciones and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.nestedset import get_descendants_of
from erpnext.accounts.report.financial_statements import get_cost_centers_with_children
from frappe.query_builder.custom import ConstantColumn

def execute(filters=None):
	filters = frappe._dict(filters or {})
	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date cannot be greater than To Date"))
	
	columns = get_columns(filters)
	data = get_data(filters)

	return columns, data

def get_columns(filters):
	return [
		{
			'label': _('Company'),
			'fieldname': 'company',
			'fieldtype': 'Link',
			'options': 'Company',
			'width': 140
		},
		{
			'label': _('Solicitud de Pago'),
			'fieldname': 'solicitud_de_pago',
			'fieldtype': 'Link',
			'options': 'Solicitud de Pago',
			'width': 250
		},
		{
			'label': _('Cost Center') + ' ' + _('Solicitud de Pago'),
			'fieldname': 'cost_center',
			'fieldtype': 'Link',
			'options': 'Cost Center',
			'width': 120
		},
  	{
			'label': _('Cost Center'),
			'fieldname': 'item_cost_center',
			'fieldtype': 'Link',
			'options': 'Cost Center',
			'width': 120
		},
		{
			'label': _('Reference Doctype'),
			'fieldname': 'reference_doctype',
			'fieldtype': 'Data',
			'width': 120
		},
		{
			'label': _('Reference Name'),
			'fieldname': 'reference_name',
			'fieldtype': 'Dynamic Link',
			'options': 'reference_doctype',
			'width': 180
		},
		{
			'label': _('Amount'),
			'fieldname': 'item_amount',
			'fieldtype': 'Currency',
			'width': 120	
		},
		{
			'label': _('Supplier'),
			'fieldname': 'supplier',
			'fieldtype': 'Link',
			'options': 'Supplier',
			'width': 120
		},
		{
			'label': _('Supplier Name'),
			'fieldname': 'supplier_name',
			'fieldtype': 'Data',
			'width': 140
		},
		{
			'label': _('Description'),
			'fieldname': 'item_name',
			'fieldtype': 'Data',
			'width': 200
		}
		# {
		# 	'label': _('Billed Amount'),
		# 	'fieldname': 'billed_amt',
		# 	'fieldtype': 'Currency',
		# 	'width': 120
		# }
	]

def get_data(filters):
	data = []
	
	company_list = get_descendants_of('Company', filters.get('company'))
	company_list.append(filters.get('company'))
	solicitudes_de_pago_records = get_solicitudes_de_pago(company_list, filters)

	for record in solicitudes_de_pago_records:
		item_records = get_reference_details(record.reference_doctype, record.reference_name, filters)
		for item_record in item_records:
			row = {
				"company": record.company,
				"solicitud_de_pago": record.name,
				"cost_center": record.cost_center,
				"item_cost_center": item_record.cost_center or '',
				"reference_doctype": record.reference_doctype,
				"reference_name": record.reference_name,
				"total_amount": record.total_amount,
				"outstanding_amount": record.outstanding_amount,
				"allocated_amount": record.allocated_amount,
				"billed_amt": item_record.billed_amt,
				"item_amount": item_record.grand_total or item_record.amount,
    		"supplier": item_record.supplier or '',
    		"supplier_name": item_record.supplier_name,
				"item_name": item_record.item_name
			}
			data.append(row)

	return data

def get_solicitudes_de_pago(company_list, filters):
	db_sp = frappe.qb.DocType('Solicitud de Pago')
	db_sp_reference = frappe.qb.DocType('Comprobante de Solicitud de Pago')

	query = (
		frappe.qb.from_(db_sp)
		.left_join(db_sp_reference)
		.on(db_sp.name == db_sp_reference.parent)
		.select(
			db_sp.name,
			db_sp.company,
			db_sp.cost_center,
			db_sp_reference.reference_doctype,
			db_sp_reference.reference_name,
			db_sp_reference.total_amount,
			db_sp_reference.outstanding_amount,
			db_sp_reference.allocated_amount
		)
		.where(db_sp.workflow_status.isin(['Paid', 'Entregado a Contabilidad']))
		.where(db_sp.company.isin(tuple(company_list)))
	)

	if filters.get('from_date'):
		query = query.where(db_sp.fecha_solicitud >= filters.get('from_date'))

	if filters.get('to_date'):
		query = query.where(db_sp.fecha_solicitud <= filters.get('to_date'))

	if filters.get('cost_center'):
		filters.cost_center = get_cost_centers_with_children(filters.cost_center)
		query = query.where(db_sp.cost_center.isin(tuple(filters.cost_center)))

	return query.run(as_dict=True, debug=True)

def get_reference_details(reference_doctype, reference_name, filters):
	if not reference_doctype or not reference_name:
		return {}

	db_ref = frappe.qb.DocType(reference_doctype)
	db_ref_item = frappe.qb.DocType(reference_doctype + ' Item')
 
	item_name = db_ref_item.item_name
	amount = db_ref_item.amount
	item_cost_center = db_ref_item.cost_center
	supplier = db_ref.supplier
	supplier_name = db_ref.supplier_name
 
	if reference_doctype == 'Gastos Varios':
		db_ref_item = frappe.qb.DocType('Detalle de Gastos Varios')
		billed_amt = db_ref_item.total
		amount = db_ref_item.grand_total
		item_name = db_ref_item.tipo_gasto
		item_cost_center = db_ref_item.cost_center
		supplier = db_ref_item.supplier
		supplier = ConstantColumn('').as_('supplier')
		supplier_name = db_ref_item.supplier.as_('supplier_name')
	
	if reference_doctype == 'Purchase Order':
		billed_amt = db_ref_item.billed_amt * db_ref.conversion_rate
	if reference_doctype == 'Purchase Invoice':
		billed_amt = db_ref_item.amount

	query = (
		frappe.qb.from_(db_ref)
		.inner_join(db_ref_item)
		.on(db_ref.name == db_ref_item.parent)
		.select(
			db_ref.name,
			supplier,
			supplier_name,
			item_name,
			amount,
			item_cost_center,
			billed_amt
		)
		.where(db_ref.name == reference_name)
	)

	if filters.get('item_cost_center'):
		filters.item_cost_center = get_cost_centers_with_children(filters.item_cost_center)
		query = query.where(db_ref_item.cost_center.isin(tuple(filters.item_cost_center)))
  
	return query.run(as_dict=True, debug=True)

def get_conditions(filters):
	conditions = []
	if filters.get('cost_center'):
		filters.cost_center = get_cost_centers_with_children(filters.cost_center)
		conditions.append("cost_center in %(cost_center)s")

	return "and {}".format(" and ".join(conditions)) if conditions else ""