// Copyright (c) 2024, Cuatrocubos Soluciones and contributors
// For license information, please see license.txt

frappe.ui.form.on("Firma Digital", {
  setup(frm) {
    // frm.set_query("employee", function() {
		// 	return{		
		// 		filters: {
		// 			"user_id": ["in", frappe.session.user]
		// 		}
		// 	}
		// })
  },
  refresh(frm) {
    if (!frm.doc.employee) {
    frappe.db.get_value("Employee", { "user_id": frappe.session.user }, ["name","employee_name"])
      .then(response => {
        const full_name = response.message.employee_name
        const name = response.message.name
        cur_frm.set_value('employee', name)
        cur_frm.set_value('employee_name', full_name)
      })
      .catch(err => {

      })
    }
	},
});
