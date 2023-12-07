import frappe

def solicitud_de_pago_query(user):
  if not user:
    user = frappe.session.user
  employee = frappe.db.get_value(
    "Employee", 
    {"user_id": user}, 
    ['name'],
    as_dict=1,
  )
  # role = frappe.get_all(
  #   "Has Role",  filters={"parent": user, "parenttype": "User", "role": "Revisor de Solicitudes de Pagos"}, fields=["role"]
  # )
  roles = frappe.get_roles(user)
  # can_view_all = any(obj.role in  ['Revisor de Solicitudes de Pago'] for obj in roles)
  # print ('view all', can_view_all)
  if "Revisor de Solicitudes de Pago" in roles or "Coordinador de Pagos y Viaticos" in roles:
    return None
  else:
    if employee:
      return "(`tabSolicitud de Pago`.owner = {user} or `tabSolicitud de Pago`.solicitante = {employee})".format(user=frappe.db.escape(user))
    else: 
      return "(`tabSolicitud de Pago`.owner = {user})".format(user=frappe.db.escape(user))
  
    