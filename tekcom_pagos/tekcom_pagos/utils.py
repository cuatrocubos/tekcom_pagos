import json
from collections import OrderedDict, defaultdict

import frappe
from frappe import qb, scrub
from frappe.desk.reportview import get_filters_cond, get_match_cond
from frappe.query_builder import Criterion, CustomFunction
from frappe.query_builder.functions import Concat, Locate, Sum
from frappe.utils import nowdate, today, unique
from pypika import Order

@frappe.whitelist()
def get_users_by_role(role):
  usuarios = []
  usuarios = frappe.get_all(
    "Has Role", filters={"role": ['like', role], "parenttype": "User"}, fields=["parent"]
  )
  return usuarios

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def employee_query(doctype, txt, searchfield, start, page_len, filters):
	doctype = "Employee"
	conditions = []
	fields = get_fields(doctype, ["name", "employee_name"])

	return frappe.db.sql(
		"""select {fields} from `tabEmployee`
		where status in ('Active', 'Suspended')
			and docstatus < 2
			and ({key} like %(txt)s
				or employee_name like %(txt)s)
			{fcond}
		order by
			(case when locate(%(_txt)s, name) > 0 then locate(%(_txt)s, name) else 99999 end),
			(case when locate(%(_txt)s, employee_name) > 0 then locate(%(_txt)s, employee_name) else 99999 end),
			idx desc,
			name, employee_name
		limit %(page_len)s offset %(start)s""".format(
			**{
				"fields": ", ".join(fields),
				"key": searchfield,
				"fcond": get_filters_cond(doctype, filters, conditions),
				# "mcond": get_match_cond(doctype),
			}
		),
		{"txt": "%%%s%%" % txt, "_txt": txt.replace("%", ""), "start": start, "page_len": page_len},
	)

def get_asignacion_diaria_alimentacion(employee):
  Employee = frappe.qb.DocType('Employee')
  query = (frappe.qb.from_(Employee)
           .select(Employee.custom_asignacion_viaticos_alimentacion)
           .where(Employee.name == employee)).run(as_dict=True,debug=True)
  
  if len(query) > 0:
    return query[0].custom_asignacion_viaticos_alimentacion

  return "0.0"

def get_fields(doctype, fields=None):
	if fields is None:
		fields = []
	meta = frappe.get_meta(doctype)
	fields.extend(meta.get_search_fields())

	if meta.title_field and not meta.title_field.strip() in fields:
		fields.insert(1, meta.title_field.strip())

	return unique(fields)