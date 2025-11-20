frappe.listview_settings["Solicitud de Viaticos"] = {
  add_fields: [
    'fecha_solicitud',
    'fecha_retorno',
    'solicitante', 
    'cost_center', 
    'project',
    'total_anticipo_solicitado',
    'status',
    'workflow_status',
    'liquidacion_workflow_state'
  ],
  
  has_indicator_for_draft: true,
  onload: function(listview) {
    // Fetch liquidacion workflow states for all solicitudes in the current view
    const solicitud_names = listview.data.map(d => d.name);
    console.log("Fetching liquidacion states for solicitudes:", listview, listview.data );
    if (solicitud_names.length > 0) {
      frappe.call({
        method: 'frappe.client.get_list',
        args: {
          doctype: 'Liquidacion de Viaticos',
          filters: {
            solicitud_de_viaticos: ['in', solicitud_names]
          },
          fields: ['name', 'solicitud_de_viaticos', 'workflow_state'],
          limit_page_length: 0
        },
        callback: function(r) {
          if (r.message) {
            console.log("Fetched liquidacion states:", r.message);
            // Create a map of solicitud -> liquidacion workflow_state
            const liquidacion_map = {};
            r.message.forEach(function(liq) {
              liquidacion_map[liq.solicitud_de_viaticos] = liq.workflow_state;
            });
            
            // Store the map for use in get_indicator
            frappe.listview_settings["Solicitud de Viaticos"].liquidacion_map = liquidacion_map;
            
            // Add the liquidacion_workflow_state to each doc
            listview.data.forEach(function(doc) {
              doc.liquidacion_workflow_state = liquidacion_map[doc.name] || null;
              console.log("Setting liquidacion_workflow_state for %s: %s", doc.name, doc.liquidacion_workflow_state);
            });
            
            // Refresh the list view to update indicators
            listview.refresh();
          }
        }
      });
    }
  },
  
  get_indicator: function(doc) {
    // Get liquidacion workflow state (if available)
    const liquidacion_status = doc.liquidacion_workflow_state || 
                              frappe.listview_settings["Solicitud de Viaticos"].liquidacion_map?.[doc.name];
    console.log("Liquidacion status for %s: %s", doc.name, doc.liquidacion_workflow_state);
    // If liquidacion is completed/approved, show as Liquidado
    if (liquidacion_status === "Entregado a Talento Humano" || liquidacion_status === "Approved") {
      return [__("Liquidado"), "green", "liquidacion_workflow_state,=,Entregado a Talento Humano"];
    }
    
    // If liquidacion exists but not completed
    if (liquidacion_status && liquidacion_status !== "Draft") {
      return [__("En Liquidación"), "orange", "liquidacion_workflow_state,=," + liquidacion_status];
    }
    
    // Check solicitud workflow status
    if (doc.workflow_status === "Pagado") {
      return [__("Pagado"), "green", "workflow_status,=,Pagado"];
    } else if (doc.workflow_status === "Entregado a Contabilidad") {
      // Check if return date has passed
      const today = frappe.datetime.get_today();
      if (doc.fecha_retorno < today) {
        return [__("Pendiente de Liquidar"), "red", "workflow_status,=,Pagado"];
      } else if (doc.fecha_retorno === today) {
        return [__("En Viaje - Retorna Hoy"), "blue", "workflow_status,=,Pagado"];
      } else {
        return [__("En Viaje"), "blue", "workflow_status,=,Pagado"];
      }
    }
    
    // Fallback for other statuses
    return [__(doc.workflow_status || "Draft"), "gray", "workflow_status,=," + (doc.workflow_status || "Draft")];
  }
};