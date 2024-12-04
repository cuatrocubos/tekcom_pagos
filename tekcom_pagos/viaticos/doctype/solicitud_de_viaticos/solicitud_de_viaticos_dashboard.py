from frappe import _

def get_data():
  return {
    "fieldname": "solicitud_de_viaticos",
    "transactions": [
      {"label": _("Payment"), "items": ["Payment Entry", "Employee Advance"]},
      {"label": _("Viaticos"), "items": ["Liquidacion de Viaticos"]}
    ]
  }