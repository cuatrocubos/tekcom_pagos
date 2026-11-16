// ERPNext 15.125 only shows Create > Payment Request to users who can create a Payment Request
// (erpnext 9c9ecc77f8). make_payment_request builds a Solicitud de Pago here (erpnext.patch),
// so show the same button to users who can create a Solicitud de Pago instead.
frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		const doc = frm.doc;
		if (
			doc.docstatus == 1 &&
			doc.outstanding_amount > 0 &&
			!cint(doc.is_return) &&
			!doc.on_hold &&
			!frappe.boot.user.in_create.includes("Payment Request") &&
			frappe.model.can_create("Solicitud de Pago")
		) {
			frm.add_custom_button(
				__("Payment Request"),
				() => frm.cscript.make_payment_request(),
				__("Create")
			);
		}
	},
});
