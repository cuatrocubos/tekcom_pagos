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
  like_user = f"'%{user}%'"

  roles = frappe.get_roles(user)
  if "Administrator" or ("Coordinador de Pagos y Viaticos" in roles):
    pass
  
  if "Revisor de Solicitudes de Pago" in roles or ("Coordinador de Pagos y Viaticos" in roles):
    return "IF(`tabSolicitud de Pago`.workflow_status = 'Draft',`tabSolicitud de Pago`.owner = {user},`tabSolicitud de Pago`.owner LIKE '%%')".format(user=frappe.db.escape(user))
  else:
    if employee:
      return "(`tabSolicitud de Pago`.owner = {user} or `tabSolicitud de Pago`.revisado_por = {user} or `tabSolicitud de Pago`.revisor = {user} or `tabSolicitud de Pago`.aprobado_por = {user} or `tabSolicitud de Pago`.aprobador = {user} or `tabSolicitud de Pago`._assign LIKE {like_user})".format(user=frappe.db.escape(user),employee=frappe.db.escape(employee),like_user=frappe.db.escape(like_user))
    else: 
      return "(`tabSolicitud de Pago`.owner = {user} or `tabSolicitud de Pago`.revisado_por = {user} or `tabSolicitud de Pago`.revisor = {user} or `tabSolicitud de Pago`.aprobado_por = {user} or `tabSolicitud de Pago`.aprobador = {user} or `tabSolicitud de Pago`._assign LIKE {like_user})".format(user=frappe.db.escape(user),employee=frappe.db.escape(employee),like_user=frappe.db.escape(like_user))

def solicitud_de_viaticos_query(user):
  if not user:
    user = frappe.session.user
    
  employee = frappe.db.get_value(
    "Employee", 
    {"user_id": user}, 
    ['name'],
    as_dict=1,
  )
  like_user = f"'%{user}%'"

  roles = frappe.get_roles(user)
  
  if "Administrator" or ("Coordinador de Pagos y Viaticos" in roles):
    pass
  
  if "Revisor de Solicitud de Viaticos" in roles or ("Coordinador de Pagos y Viaticos" in roles):
    return "IF(`tabSolicitud de Viaticos`.workflow_status = 'Draft',`tabSolicitud de Viaticos`.owner = {user},`tabSolicitud de Viaticos`.owner LIKE '%%')".format(user=frappe.db.escape(user))
  else:
    if employee:
      return "(`tabSolicitud de Viaticos`.owner = {user} or `tabSolicitud de Viaticos`.revisado_por = {user} or `tabSolicitud de Viaticos`.revisor = {user} or `tabSolicitud de Viaticos`.aprobado_por = {user} or `tabSolicitud de Viaticos`.aprobador = {user} or `tabSolicitud de Viaticos`._assign LIKE {like_user})".format(user=frappe.db.escape(user),employee=frappe.db.escape(employee),like_user=frappe.db.escape(like_user))
    else: 
      return "(`tabSolicitud de Viaticos`.owner = {user} or `tabSolicitud de Viaticos`.revisado_por = {user} or `tabSolicitud de Viaticos`.revisor = {user} or `tabSolicitud de Viaticos`.aprobado_por = {user} or `tabSolicitud de Viaticos`.aprobador = {user} or `tabSolicitud de Viaticos`._assign LIKE {like_user})".format(user=frappe.db.escape(user),employee=frappe.db.escape(employee),like_user=frappe.db.escape(like_user))
  
### (TODO: Add has_permission method to overide DocType access for solicitud_de_pago and solicitud_de_viaticos)
# has_permission = {
  # "Solicitud de Pago": "app.permissions.event_has_permission"
# }

# NOTE: The method will be passed the doc, user and permission_type as arguments. It shoudl return True or a False value.
# If None is returned, it will fallback to default behavior. apps/frappe/frappe/permissions.py/has_permission
# def doctype_has_permission(doc, user=None, permission_type=None):