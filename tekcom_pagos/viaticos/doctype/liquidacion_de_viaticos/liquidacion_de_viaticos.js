// Copyright (c) 2023, Cuatrocubos Soluciones and contributors
// For license information, please see license.txt

frappe.provide("erpnext.accounts.dimensions");

frappe.ui.form.on('Liquidacion de Viaticos', {
  onload(frm) {
    erpnext.accounts.dimensions.setup_dimension_filters(frm, frm.doctype)
		// frappe.meta.get_docfield("Configuracion Pagos y Viaticos por Company", "compras", frm.doc.name).reqd=1
  },

  setup(frm) {
    if (frm.doc.docstatus == 0) {
      if (!frm.doc.fecha_liquidacion) {
        frm.set_value("fecha_liquidacion", frappe.datetime.nowdate())
      }
    }

    if (frm.doc.solicitante == "" || frm.doc.solicitante == null) {
      frappe.call({
        method: "frappe.client.get_value",
        args: {
          doctype: 'Employee',
          filters: {
            user_id: frappe.session.user,
          },
          fieldname: ['name']
        },
        callback: function(r) {
          if (r.message != undefined) {
            frm.set_value("solicitante", r.message.name)
          }
        }
      })
    }

    frm.set_query("solicitud_de_viaticos", function() {
      return {
        filters: {
          workflow_status: ["in", ["Pagado", "Entregado a Contabilidad", "Contabilizado"]],
          company: frm.doc.company
        }
      }
    })
  },

  refresh(frm) {
    const workflow_status_for_liquidacion = ['Approved','Entregado a Talento Humano']
    if (!frm.doc.fecha_liquidacion) {
      frm.set_value("fecha_liquidacion", frappe.datetime.nowdate())
    }
    if (frm.doc.solicitud_de_viaticos && frm.doc.__islocal == 1) {
      frm.trigger("solicitud_de_viaticos")
    }
    if (workflow_status_for_liquidacion.includes(frm.doc.workflow_status)) {
      frm.add_custom_button(__('Crear Reembolso de Gastos'), () => {
        frm.events.make_expense_claim()
      })
    }
    frm.events.hide_unhide_fields(frm)
    frm.events.set_dynamic_labels(frm)
  },

  company(frm) {
    frm.events.hide_unhide_fields(frm);
    frm.events.set_dynamic_labels(frm);
    erpnext.accounts.dimensions.update_dimension(frm, frm.doctype)
  },

  solicitud_de_viaticos(frm) {
    return frappe.call({
      method: "tekcom_pagos.viaticos.doctype.liquidacion_de_viaticos.liquidacion_de_viaticos.get_solicitud_de_viaticos",
      args: {
        docname: frm.doc.solicitud_de_viaticos
      },
      callback: function(r) {
        if (r.message) {
          doc = r.message;
          frappe.run_serially([
            () => frm.set_value("fecha_salida_solicitud", doc.fecha_salida),
            () => frm.set_value("fecha_retorno_solicitud", doc.fecha_retorno),
            () => frm.set_value("solicitante", doc.depositar_a),
            () => frm.set_value("project", doc.project),
            () => frm.set_value("cost_center", doc.cost_center),
            () => frm.set_value("currency", doc.currency),
            () => frm.set_value("lugar_viaje", doc.lugar_viaje),
            () => frm.events.set_presupuesto_viaticos(frm, doc.presupuesto),
            () => frm.events.set_totales(frm)
          ])
        }
      }
    })
},

  fecha_salida_solicitud(frm) {
    if (frm.doc.fecha_salida_solicitud) {
      frm.set_value("fecha_salida", frm.doc.fecha_salida_solicitud)
    } 
  },

  fecha_retorno_solicitud(frm) {
    if (frm.doc.fecha_retorno_solicitud) {
      frm.set_value("fecha_retorno", frm.doc.fecha_retorno_solicitud)
    } 
  },

  fecha_salida(frm) {},

  fecha_retorno(frm) {},

  project(frm) {
    if (frm.doc.project) {
      frappe.call({
        method: "erpnext.projects.doctype.project.project.get_cost_center_name",
        args: {
          project: frm.doc.project
        },
        callback: function(r, rt) {
          if (r.message) {
            frappe.run_serially([
              () => frm.set_value("cost_center", r.message),
              () => frappe.msgprint(__("Centro de Costo actualizado al centro de costos del proyecto selecionado.")),
            ])
          }
        }
      })
    }
  },

  cost_center(frm) {},

  currency(frm) {
    if (!frm.doc.currency || !frm.doc.company) return;

    frm.events.set_dynamic_labels(frm)
    let company_currency = frappe.get_doc(":Company", frm.doc.company).default_currency
    if (frm.doc.currency == company_currency) {
      frm.set_value("exchange_rate", 1)
    } else {
      frappe.call({
        method: "erpnext.setup.utils.get_exchange_rate",
        args: {
          from_currency: frm.doc.currency,
          to_currency: company_currency,
          transaction_date: frm.doc.fecha_solicitud
        },
        callback(r, rt) {
          frm.set_value("exchange_rate", r.message)
        }
      })
    }
    frm.events.hide_unhide_fields(frm)
  },

  exchange_rate(frm) {
    if (frm.doc.total_solicitado) {
      frm.set_df_property("exchange_rate", "read_only", erpnext.stale_rate_allowed() ? 0 : 1)
      frm.events.set_totales(frm)
    }
  },

  solicitante(frm) {},

  total_solicitado(frm) {},

  total_ejecutado(frm) {},

  total_reembolso(frm) {},

  hide_unhide_fields: function(frm) {
    var company_currency = frm.doc.company ? frappe.get_doc(":Company", frm.doc.company).default_currency : "";

    frm.toggle_display(["exchange_rate","total_impuestos_base","total_solicitado_base","total_ejecutado_base","total_reembolso_base"], (frm.doc.currency != company_currency));
    
    frm.refresh_fields();
  },

  set_dynamic_labels: function(frm) {
    var company_currency = frm.doc.company? frappe.get_doc(":Company", frm.doc.company).default_currency: "";

    frm.set_currency_labels(["total_impuestos_base","total_solicitado_base","total_ejecutado_base","total_reembolso_base"], company_currency);
    frm.set_currency_labels(["total_impuestos","total_solicitado","total_ejecutado","total_reembolso"], frm.doc.currency);
    frm.set_currency_labels(["monto_solicitado_base","monto_ejecutado_base","monto_aprobado_base", "diferencia_base"], company_currency, "presupuesto_viaticos");
    frm.set_currency_labels(["monto_solicitado","monto_ejecutado","monto_aprobado", "diferencia"], frm.doc.currency, "presupuesto_viaticos");
    frm.set_currency_labels(["subtotal_base","impuestos_base","total_base"], company_currency, "detalle_liquidacion");
    frm.set_currency_labels(["subtotal","impuestos","total"], frm.doc.currency, "detalle_liquidacion");
    
    // frm.set_currency_labels(["monto_pagar"], frm.doc.currency)

    // frm.set_df_property(["total_impuestos_base","total_solicitado_base","total_ejecutado_base","total_reembolso_base"], "options", "currency");

    frm.set_df_property("exchange_rate", "description", "1 " + frm.doc.currency + " = [?]" + company_currency)
    frm.set_df_property("total_reembolso", "description", frm.doc.total_reembolso >= flt(0) ? `A favor de ${frm.doc.company}` : `A favor del empleado`)
    frm.set_df_property("total_reembolso_base", "description", frm.doc.total_reembolso >= flt(0) ? `A favor de ${frm.doc.company}` : `A favor del empleado`)

    // frm.set_currency_labels(["total_amount", "outstanding_amount","allocated_amount"], frm.doc.currency, "references")

    // frm.set_df_property("total_allocated_amount", "options", "currency")
    // frm.set_df_property("unallocated_amount", "options", "currency")

    frm.refresh_fields()
  },

  make_expense_claim() {
    frappe.model.open_mapped_doc({
      method: 'tekcom_pagos.viaticos.doctype.liquidacion_de_viaticos.liquidacion_de_viaticos.make_expense_claim',
      frm: cur_frm
    })
  },

  validate_company(frm) {
    if (!frm.doc.company) {
      frappe.throw({
        message:__("Please select a Company first."),
        title:__("Mandatory")
      })
    }
  },

  get_expense_types_presupuesto_viaticos(frm) {
    if (frm.doc.presupuesto_viaticos.length == 0) {
      return []
    }
    const expense_types = frm.doc.presupuesto_viaticos.reduce((acc, item) => {
      if (!acc.includes(item.tipo_gasto)) {
        acc.push(item.tipo_gasto)
      }
      return acc
    }, [])

    return expense_types
  },

  set_presupuesto_viaticos(frm, presupuesto) {
    frm.clear_table("presupuesto_viaticos")
    if (presupuesto) {
      $.each(presupuesto, function(i, row) {
        var new_row = frm.add_child("presupuesto_viaticos")
        new_row.tipo_gasto = row.tipo_gasto
        new_row.monto_solicitado = row.monto_solicitado
        new_row.monto_aprobado = row.monto_aprobado
        new_row.monto_ejecutado = flt(0)
        new_row.diferencia = flt(row.monto_aprobado) - flt(0)
        new_row.monto_solicitado_base = flt(new_row.monto_solicitado) * flt(frm.doc.exchange_rate)
        new_row.monto_aprobado_base = flt(new_row.monto_aprobado) * flt(frm.doc.exchange_rate)
        new_row.monto_ejecutado_base = flt(new_row.monto_ejecutado) * flt(frm.doc.exchange_rate)
        new_row.monto_diferencia_base = flt(new_row.diferencia) * flt(frm.doc.exchange_rate)
      })
      frm.events.hide_unhide_fields(frm)
    }
  },

  set_totales(frm) {
    var total_solicitado = flt(0)
    var total_ejecutado = flt(0)
    var total_reembolso = flt(0)

    $.each(frm.doc.presupuesto_viaticos || [], function(r, row) {
      if (row.monto_solicitado) {
        total_solicitado += flt(row.monto_solicitado)
      }
      if (row.monto_ejecutado) {
        total_ejecutado += flt(row.monto_ejecutado)
      }
      if (row.diferencia) {
        total_reembolso += flt(row.diferencia)
      }
    })

    frm.set_value("total_solicitado", total_solicitado)
    frm.set_value("total_ejecutado", total_ejecutado)
    frm.set_value("total_reembolso", total_reembolso)

    frm.set_value("total_solicitado_base", flt(total_solicitado) * flt(frm.doc.exchange_rate))
    frm.set_value("total_ejecutado_base", flt(total_ejecutado) * flt(frm.doc.exchange_rate))
    frm.set_value("total_reembolso_base", flt(total_reembolso) * flt(frm.doc.exchange_rate))
    frm.set_df_property("total_reembolso", "description", frm.doc.total_reembolso >= flt(0) ? `A favor de ${frm.doc.company}` : `A favor del empleado`)
    frm.set_df_property("total_reembolso_base", "description", frm.doc.total_reembolso >= flt(0) ? `A favor de ${frm.doc.company}` : `A favor del empleado`)
    frm.events.hide_unhide_fields(frm)
  },

  set_total_ejecutado_presupuesto(frm) {
    $.each(frm.doc.presupuesto_viaticos || [], function(r, row) {
      const total_ejecutado = 
        frm.doc.detalle_liquidacion.reduce(
          (acc, item) => {
            if (item.expense_type == row.tipo_gasto) {
              acc = acc + flt(item.total)
            }
            return acc
          }, flt(0))
      const total_impuestos = 
        frm.doc.detalle_liquidacion.reduce(
          (acc, item) => acc + flt(item.impuestos), flt(0))
      frm.set_value("total_impuestos", total_impuestos)
      frm.set_value("total_impuestos_base", flt(total_impuestos) * flt(frm.doc.exchange_rate))
      frappe.model.set_value(row.doctype, row.name, "monto_ejecutado", total_ejecutado)
      frappe.model.set_value(row.doctype, row.name, "monto_ejecutado_base", flt(total_ejecutado) * flt(frm.doc.exchange_rate))
    })
    frm.events.hide_unhide_fields(frm)
  },

  check_expense_types(frm) {
    let presupuestoViaticosTypes = frm.doc.presupuesto_viaticos.map(item => item.tipo_gasto);
    let missingExpenseTypes = frm.doc.detalle_liquidacion.filter(item => !presupuestoViaticosTypes.includes(item.expense_type));

    if (missingExpenseTypes.length > 0) {
      missingExpenseTypes.forEach(item => {
        if (item.expense_type != "") {
          let newItem = frm.add_child("presupuesto_viaticos");
          newItem.tipo_gasto = item.expense_type;
          newItem.monto_solicitado = 0;
          newItem.monto_aprobado = 0;
          // Add other necessary fields if required
        }
      });
      frm.refresh_field("presupuesto_viaticos");
    }
  },

  async before_workflow_action(frm) {
    return await new Promise((resolve, reject) => {
      frappe.dom.unfreeze()
      if (
        frm.selected_workflow_action == 'Enviar a Revisión' 
        && (!frm.doc.mode_of_payment || !frm.doc.reference_date || !frm.doc.reference_no)) {
          frappe.confirm(__('No ha ingresado los detalles del reembolso en su contra, de continuar, el valor a reembolsar será debitado de su próxima planilla, ¿Está seguro que desea realizar esta acción?'), () => { 
            resolve()
          }, () => {
            reject()
          })
      }
      resolve()
    })
  },
});

frappe.ui.form.on("Detalle de Liquidacion de Viaticos", {
  detalle_liquidacion_add(frm, cdt, cdn) {
    var row = locals[cdt][cdn]
    row.cost_center = frm.doc.cost_center
    row.project = frm.doc.project
    // frappe.model.set_value(cdt, cdn, "cost_center", frm.doc.cost_center)
    // frappe.model.set_value(cdt, cdn, "project", frm.doc.project)
  },

  detalle_liquidacion_remove(frm, cdt, cdn) {
    frm.events.hide_unhide_fields(frm)
    frm.events.set_total_ejecutado_presupuesto(frm)
  },

  expense_type(frm, cdt, cdn) {
    var d = locals[cdt][cdn];
    if (!frm.doc.company) {
      d.expense_type = "";
      frappe.msgprint(__("Please set the Company"));
      this.frm.refresh_fields();
      return;
    }

    if (!d.expense_type) {
      return;
    }
    frm.events.check_expense_types(frm)
    return frappe.call({
      method: "hrms.hr.doctype.expense_claim.expense_claim.get_expense_claim_account_and_cost_center",
      args: {
        expense_claim_type: d.expense_type,
        company: frm.doc.company,
      },
      callback: function (r) {
        if (r.message) {
          d.default_account = r.message.account;
          d.cost_center = frm.doc.cost_center ? frm.doc.cost_center : r.message.cost_center;
          frm.events.set_total_ejecutado_presupuesto(frm)
          frm.events.hide_unhide_fields(frm)
        }
      },
    });
  },

  subtotal(frm, cdt, cdn) {
    var row = locals[cdt][cdn]
    total = flt(row.subtotal) + flt(row.impuestos)
    row.total = total
    row.total_base = flt(row.total) * flt(frm.doc.exchange_rate)
    frm.events.set_total_ejecutado_presupuesto(frm)
    frm.events.hide_unhide_fields(frm)
  },
  impuestos(frm, cdt, cdn) {
    var row = locals[cdt][cdn]
    if (row.subtotal && flt(row.impuestos) >= flt(row.subtotal)) {
      frappe.throw({
        message: __("Valor de impuestos no puede ser mayor al subtotal de la fila"), title: __("Error")
      })
    } else {
      total = flt(row.subtotal) + flt(row.impuestos)
      row.total = total
      row.total_base = flt(row.total) * flt(frm.doc.exchange_rate)
      frm.events.set_total_ejecutado_presupuesto(frm)
      frm.events.hide_unhide_fields(frm)
    }
  },
})

frappe.ui.form.on("Presupuesto de Liquidacion de Viaticos", {
  monto_ejecutado(frm, cdt, cdn) {
    var row = locals[cdt][cdn]
    diferencia = flt(row.monto_aprobado) - flt(row.monto_ejecutado)
    row.diferencia = diferencia
    row.diferencia_base = flt(row.diferencia) * flt(frm.doc.exchange_rate)
    frm.events.set_totales(frm)
    frm.events.hide_unhide_fields(frm)
  },
})
