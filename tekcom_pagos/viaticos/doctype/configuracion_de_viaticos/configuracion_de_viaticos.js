// Copyright (c) 2024, Cuatrocubos Soluciones and contributors
// For license information, please see license.txt

frappe.ui.form.on("Configuracion de Viaticos", {
  setup(frm) {
    frappe.call({
      method: "tekcom_pagos.tekcom_pagos.utils.get_users_by_role",
      args: {
        role: 'Revisor de Solicitud de Viaticos'
      },
      callback: function(r) {
        if (r.message != undefined) {
          frappe.run_serially([
            () => user_list = r.message.map(c => c.parent),
            () => frm.set_query("revisor_predeterminado", function() {
              return {
                filters: {
                  name: ["in", user_list]
                }
              }
            }),
            () => frm.set_query("revisor_predeterminado", "cost_center_predeterminados", function(frm, cdt, cdn) {
              return {
                filters: {
                  name: ["in", user_list]
                }
              }
            })
          ])
        }
      }
    })

    frappe.call({
      method: "tekcom_pagos.tekcom_pagos.utils.get_users_by_role",
      args: {
        role: 'Aprobador de Solicitud de Viaticos'
      },
      callback: function(r) {
        if (r.message != undefined) {
          frm.set_query("aprobador_predeterminado", function() {
            return {
              filters: {
                name: ["in", r.message.map(c => c.parent)]
              }
            }
          })
          frm.set_query("aprobador_predeterminado", "cost_center_predeterminados", function(frm, cdt, cdn) {
            return {
              filters: {
                name: ["in", r.message.map(c => c.parent)]
              }
            }
          })
        }
      }
    })

    frappe.call({
      method: "tekcom_pagos.tekcom_pagos.utils.get_users_by_role",
      args: {
        role: 'Coordinador de Pagos y Viaticos'
      },
      callback: function(r) {
        if (r.message != undefined) {
          frm.set_query("coordinador_pagos_predeterminado", function() {
            return {
              filters: {
                name: ["in", r.message.map(c => c.parent)]
              }
            }
          })
          frm.set_query("coordinador_pagos_predeterminado", "cost_center_predeterminados", function(frm, cdt, cdn) {
            return {
              filters: {
                name: ["in", r.message.map(c => c.parent)]
              }
            }
          })
        }
      }
    })
  },
});
