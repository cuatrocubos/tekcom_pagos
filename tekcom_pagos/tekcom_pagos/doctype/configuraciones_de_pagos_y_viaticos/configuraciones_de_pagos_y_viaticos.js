// Copyright (c) 2025, Cuatrocubos Soluciones and contributors
// For license information, please see license.txt

frappe.ui.form.on("Configuraciones de Pagos y Viaticos", {
	setup(frm) {
    frappe.call({
      method: "tekcom_pagos.tekcom_pagos.utils.get_users_by_role",
      args: {
        role: 'Revisor de Solicitudes de Pago'
      },
      callback: function(r) {
        if (r.message != undefined) {
          frappe.run_serially([
            () => user_list = r.message.map(c => c.parent),
            () => frm.set_query("revisor_predeterminado_pagos", "predeterminados_de_pagos_y_viaticos", function(frm, cdt, cdn) {
              return {
                filters: {
                  name: ["in", user_list]
                }
              }
            }),
            () => frm.set_query("revisor_predeterminado_pagos", "predeterminados_centro_costos", function(frm, cdt, cdn) {
              return {
                filters: {
                  name: ["in", user_list]
                }
              }
            }),
          ])
        }
      } // callback
    }) // frappe.call

    frappe.call({
      method: "tekcom_pagos.tekcom_pagos.utils.get_users_by_role",
      args: {
        role: 'Arobador de Solicitudes de Pago'
      },
      callback: function(r) {
        if (r.message != undefined) {
          frappe.run_serially([
            () => user_list = r.message.map(c => c.parent),
            () => frm.set_query("aprobador_predeterminado_pagos", "predeterminados_de_pagos_y_viaticos", function(frm, cdt, cdn) {
              return {
                filters: {
                  name: ["in", user_list]
                }
              }
            }),
            () => frm.set_query("aprobador_predeterminado_pagos", "predeterminados_centro_costos", function(frm, cdt, cdn) {
              return {
                filters: {
                  name: ["in", user_list]
                }
              }
            }),
          ])
        }
      } // callback
    }) // frappe.call

    frappe.call({
      method: "tekcom_pagos.tekcom_pagos.utils.get_users_by_role",
      args: {
        role: 'Coordinador de Pagos y Viaticos'
      },
      callback: function(r) {
        if (r.message != undefined) {
          frappe.run_serially([
            () => user_list = r.message.map(c => c.parent),
            () => frm.set_query("pagador_predeterminado_pagos", "predeterminados_de_pagos_y_viaticos", function(frm, cdt, cdn) {
              return {
                filters: {
                  name: ["in", user_list]
                }
              }
            }),
            () => frm.set_query("pagador_predeterminado_viaticos", "predeterminados_de_pagos_y_viaticos", function(frm, cdt, cdn) {
              return {
                filters: {
                  name: ["in", user_list]
                }
              }
            }),
            () => frm.set_query("pagador_predeterminado_pagos", "predeterminados_centro_costos", function(frm, cdt, cdn) {
              return {
                filters: {
                  name: ["in", user_list]
                }
              }
            }),
            () => frm.set_query("pagador_predeterminado_viaticos", "predeterminados_centro_costos", function(frm, cdt, cdn) {
              return {
                filters: {
                  name: ["in", user_list]
                }
              }
            }),
          ])
        }
      } // callback
    }) // frappe.call
  }, // setup
});

frappe.ui.form.on("Predeterminados Pagos y Viaticos", {
});

frappe.ui.form.on("Predeterminados Pagos y Viaticos por Centro de Costo", {
  predeterminados_centro_costos_add(frm, cdt, cdn) {
    var row = locals[cdt][cdn];
    var company = row.company;
    console.log("company:", company)
    var predeterminados_de_pagos_y_viaticos = frm.doc.predeterminados_de_pagos_y_viaticos || [];

    var matching_row = predeterminados_de_pagos_y_viaticos.find(r => r.company == company);

    if (matching_row) {
      row.revisor_predeterminado_pagos = matching_row.revisor_predeterminado_pagos;
      row.aprobador_predeterminado_pagos = matching_row.aprobador_predeterminado_pagos;
      row.pagador_predeterminado_pagos = matching_row.pagador_predeterminado_pagos;
      row.revisor_predeterminado_viaticos = matching_row.revisor_predeterminado_viaticos;
      row.aprobador_predeterminado_viaticos = matching_row.aprobador_predeterminado_viaticos;
      row.pagador_predeterminado_viaticos = matching_row.pagador_predeterminado_viaticos;
      row.encargado_compras = matching_row.encargado_compras;

      frm.refresh_field("predeterminados_centro_costos")
    }
  },
});