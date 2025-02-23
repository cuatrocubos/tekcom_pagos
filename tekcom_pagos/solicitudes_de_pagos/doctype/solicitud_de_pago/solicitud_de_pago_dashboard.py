from frappe import _

def get_data():
  return {
    "fieldname": "solicitud_de_pago",
    "non_standard_fieldnames": {
      "Journal Entry": "bill_no",
    },
    "transactions": [
      {"label": _("Payment"), "items": ["Payment Entry", "Employee Advance", "Journal Entry"]},
    ]
  }