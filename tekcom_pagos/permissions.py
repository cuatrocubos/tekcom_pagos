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
  if "Revisor de Solicitudes de Pago" in roles or "Coordinador de Pagos y Viaticos" in roles:
    return "IF(`tabSolicitud de Pago`.workflow_status = 'Draft',`tabSolicitud de Pago`.owner = {user},`tabSolicitud de Pago`.owner LIKE '%%')".format(user=frappe.db.escape(user))
  else:
    if employee:
      return "(`tabSolicitud de Pago`.owner = {user} or `tabSolicitud de Pago`.revisado_por = {user} or `tabSolicitud de Pago`.aprobado_por = {user} or `tabSolicitud de Pago`._assign LIKE {like_user})".format(user=frappe.db.escape(user),employee=frappe.db.escape(employee),like_user=frappe.db.escape(like_user))
    else: 
      return "(`tabSolicitud de Pago`.owner = {user} or `tabSolicitud de Pago`.revisado_por = {user} or `tabSolicitud de Pago`.aprobado_por = {user} or `tabSolicitud de Pago`._assign LIKE {like_user})".format(user=frappe.db.escape(user),employee=frappe.db.escape(employee),like_user=frappe.db.escape(like_user))

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
  if "Revisor de Solicitud de Viaticos" in roles or "Coordinador de Pagos y Viaticos" in roles:
    return "IF(`tabSolicitud de Viaticos`.workflow_status = 'Draft',`tabSolicitud de Viaticos`.owner = {user},`tabSolicitud de Viaticos`.owner LIKE '%%')".format(user=frappe.db.escape(user))
  else:
    if employee:
      return "(`tabSolicitud de Viaticos`.owner = {user} or `tabSolicitud de Viaticos`.revisado_por = {user} or `tabSolicitud de Viaticos`.aprobado_por = {user} or `tabSolicitud de Viaticos`._assign LIKE {like_user})".format(user=frappe.db.escape(user),employee=frappe.db.escape(employee),like_user=frappe.db.escape(like_user))
    else: 
      return "(`tabSolicitud de Viaticos`.owner = {user} or `tabSolicitud de Viaticos`.revisado_por = {user} or `tabSolicitud de Viaticos`.aprobado_por = {user} or `tabSolicitud de Viaticos`._assign LIKE {like_user})".format(user=frappe.db.escape(user),employee=frappe.db.escape(employee),like_user=frappe.db.escape(like_user))
  
    