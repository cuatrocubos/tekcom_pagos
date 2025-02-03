from frappe import _

def get_data():
  return {
    "fieldname": "liquidacion_de_viaticos",
    "transactions": [
      {"label": _("Viaticos"), "items": ["Expense Claim"]}
    ]
  }