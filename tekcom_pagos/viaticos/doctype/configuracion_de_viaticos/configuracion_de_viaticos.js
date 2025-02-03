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
            }),
            () => frm.set_query("revisor", "configuracion_viaticos_por_company", function(frm, cdt, cdn) {
              return {
                filters: {
                  name: ["in", r.message.map(c => c.parent)]
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
          frm.set_query("aprobador", "configuracion_viaticos_por_company", function(frm, cdt, cdn) {
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
          frm.set_query("pagos", "configuracion_viaticos_por_company", function(frm, cdt, cdn) {
            return {
              filters: {
                name: ["in", r.message.map(c => c.parent)]
              }
            }
          })
        }
      }
    })

    frm.set_query("expense_claim_account", "cuentas_contables", function(frm, cdt, cdn) {
      row = locals[cdt][cdn]
      return {
        filters: {
          company: row.company
        }
      }
    })

    frm.set_query("employee_advance_account", "cuentas_contables", function(frm, cdt, cdn) {
      row = locals[cdt][cdn]
      return {
        filters: {
          company: row.company
        }
      }
    })
  },

  refresh(frm) {
    frm.events.set_dynamic_labels(frm);
  },

  set_dynamic_labels(frm) {
    // frm.toggle_display(["compras"], true, "configuracion_viaticos_por_company");
    // frm.set_df_property("compras", "mandatory", 1, "configuracion_viaticos_por_company");
    // frm.set_df_property("compras", "read_only", 1, "configuracion_viaticos_por_company");
    frm.set_df_property("compras", "in_list_view", 0, "configuracion_viaticos_por_company");

    frm.refresh_fields()
  },
});

// frappe.ui.form.on("Configuracion de Viaticos por Company", {
//   configuracion_viaticos_por_company_add(frm, cdt, cdn) {
//     var row = locals[cdt][cdn];
//     frm.set_df_property()
//   }
// })
