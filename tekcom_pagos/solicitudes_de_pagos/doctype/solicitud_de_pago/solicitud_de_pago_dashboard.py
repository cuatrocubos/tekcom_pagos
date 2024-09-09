from frappe import _

def get_data():
  return {
    "fieldname": "solicitud_de_pago",
    "non_standard_fieldnames": {
      "Payment Entry": "custom_solicitud_de_pago"
    },
    "transactions": [
      {"label": _("Payment"), "items": ["Payment Entry"]},
    ]
  }