# Copyright (c) 2023, Cuatrocubos Soluciones and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, nowdate, get_link_to_form
from frappe.model.document import Document
from erpnext.accounts.utils import get_account_currency
from erpnext.controllers.accounts_controller import get_default_taxes_and_charges

from tekcom_pagos.tekcom_pagos.doctype.configuraciones_de_pagos_y_viaticos.configuraciones_de_pagos_y_viaticos import (
	get_configuraciones_de_pagos,
	get_componentes_viaticos,
)
from tekcom_pagos.tekcom_pagos.utils import (
	get_configuraciones_cuentas,
	get_employee_cost_center,
	get_advance_payment_journal_entries,
	get_party_account as get_party_account_from_utils
)

class LiquidaciondeViaticos(Document):
	def before_save(self):
		if self.workflow_status == 'Rejected':
			self.revisor = ''
			self.aprobador = ''
			self.revisado_por = ''
			self.aprobado_por = ''
			self.fecha_hora_solicitud = ''
			self.fecha_hora_revision = ''
			self.fecha_hora_aprobacion = ''

	def validate(self):
		if len(self.detalle_liquidacion) == 0:
			frappe.throw(_("Detalle de Liquidación no puede estar vacia"), frappe.ValidationError)

		self.consolidate_presupuesto_viaticos()
		self.set_expense_account()
		self.set_posting_date()
		self.update_workflow_details()
		if self.workflow_status == 'En Revisión Contable' and self.solicitud_de_viaticos:
			frappe.db.set_value("Solicitud de Viaticos", self.solicitud_de_viaticos, "viaticos_liquidados", 1)

	def onload(self):
		self.set_onload("empleado_retirado", self.is_empleado_retirado())

	def before_submit(self):
		# fail before any posting if the advance is not there or was already settled by hand
		employee_advance = self.get_employee_advance()
		self.validate_partidas_manuales(employee_advance.name)
		self.validate_flujo_anterior_con_saldo(employee_advance)

	def on_submit(self):
		self.conciliar_anticipo()

	def on_cancel(self):
		self.revertir_conciliacion()

	def update_workflow_details(self):
		old_doc = Document.get_doc_before_save(self)

		try:
			configuracion_pagos = get_configuraciones_de_pagos(self.company, self.cost_center)
		except Exception as e:
			frappe.throw(_("Error al obtener configuraciones de pagos: {0}").format(str(e)))

		if self.workflow_status == 'Draft':
			self.revisor = configuracion_pagos.get("revisor_predeterminado")
			self.aprobador = configuracion_pagos.get("aprobador_predeterminado")

		if not self.revisor:
			self.revisor = configuracion_pagos.get("revisor_predeterminado")
		if not self.aprobador:
			self.aprobador = configuracion_pagos.get("aprobador_predeterminado")

		if old_doc is not None:
			if old_doc.workflow_status != self.workflow_status:
				if (self.workflow_status) == 'En Revisión' and not self.fecha_hora_revision:
					# set fecha hora revision
					self.fecha_hora_solicitud = frappe.utils.now_datetime()
				if (self.workflow_status) == 'Revisado' and not self.fecha_hora_revision:
					# set fecha hora revision
					self.fecha_hora_revision = frappe.utils.now_datetime()
					if not self.revisado_por:
						self.revisado_por = frappe.session.user
				if (self.workflow_status) == 'Approved' and not self.fecha_hora_aprobacion:
					# set fecha hora aprobacion
					self.fecha_hora_aprobacion = frappe.utils.now_datetime()
					if not self.aprobado_por:
						self.aprobado_por = frappe.session.user

	def set_expense_account(self):
		"""Each tipo de gasto posts to the account on its presupuesto row (default: the Expense Claim Type's)"""
		for row in self.presupuesto_viaticos:
			if not row.cuenta:
				row.cuenta = get_expense_claim_account(row.tipo_gasto, self.company)["account"]

			company, is_group = frappe.get_cached_value("Account", row.cuenta, ["company", "is_group"]) or (None, None)
			if company != self.company or is_group:
				frappe.throw(
					_("Fila {0}: la cuenta {1} del tipo de gasto {2} debe ser una cuenta de detalle de la compañía {3}").format(
						row.idx, frappe.bold(row.cuenta), frappe.bold(row.tipo_gasto), self.company
					)
				)

		cuentas = {row.tipo_gasto: row.cuenta for row in self.presupuesto_viaticos}
		for expense in self.detalle_liquidacion:
			expense.default_account = cuentas.get(expense.expense_type)

	def set_posting_date(self):
		old_doc = self.get_doc_before_save()
		fecha_cambiada = (
			old_doc
			and getdate(old_doc.fecha_liquidacion) != getdate(self.fecha_liquidacion)
			and old_doc.posting_date == self.posting_date
		)
		if not self.posting_date or fecha_cambiada:
			self.posting_date = self.fecha_liquidacion

		self.posting_date = get_fecha_contabilizacion(self.posting_date, self.get_companies())

	def get_companies(self):
		employee_company = frappe.get_cached_value("Employee", self.solicitante, "company")
		return list({self.company, employee_company} - {None})

	def consolidate_presupuesto_viaticos(self):
		"""Merge duplicate tipo_gasto rows, add rows for tipo_gasto only in the detalle, and recompute totals"""
		exchange_rate = flt(self.exchange_rate) or 1

		for expense in self.detalle_liquidacion:
			expense.total = flt(expense.subtotal) + flt(expense.impuestos)
			expense.subtotal_base = flt(expense.subtotal) * exchange_rate
			expense.impuestos_base = flt(expense.impuestos) * exchange_rate
			expense.total_base = flt(expense.total) * exchange_rate

		grouped = {}
		for row in self.presupuesto_viaticos:
			existing = grouped.get(row.tipo_gasto)
			if existing:
				existing.monto_solicitado = flt(existing.monto_solicitado) + flt(row.monto_solicitado)
				existing.monto_aprobado = flt(existing.monto_aprobado) + flt(row.monto_aprobado)
				existing.cuenta = existing.cuenta or row.cuenta
			else:
				grouped[row.tipo_gasto] = row

		self.set("presupuesto_viaticos", list(grouped.values()))

		for expense in self.detalle_liquidacion:
			if expense.expense_type and expense.expense_type not in grouped:
				grouped[expense.expense_type] = self.append("presupuesto_viaticos", {
					"tipo_gasto": expense.expense_type,
					"monto_solicitado": 0,
					"monto_aprobado": 0,
				})

		total_solicitado = flt(0)
		total_ejecutado = flt(0)
		total_reembolso = flt(0)

		for row in self.presupuesto_viaticos:
			monto_ejecutado = sum(
				flt(expense.total) for expense in self.detalle_liquidacion if expense.expense_type == row.tipo_gasto
			)
			row.monto_ejecutado = monto_ejecutado
			row.monto_ejecutado_base = flt(monto_ejecutado) * exchange_rate
			row.diferencia = flt(row.monto_aprobado) - flt(monto_ejecutado)
			row.diferencia_base = flt(row.diferencia) * exchange_rate
			row.monto_solicitado_base = flt(row.monto_solicitado) * exchange_rate
			row.monto_aprobado_base = flt(row.monto_aprobado) * exchange_rate

			total_solicitado += flt(row.monto_solicitado)
			total_ejecutado += flt(row.monto_ejecutado)
			total_reembolso += flt(row.diferencia)

		total_impuestos = sum(flt(expense.impuestos) for expense in self.detalle_liquidacion)

		self.total_solicitado = total_solicitado
		self.total_ejecutado = total_ejecutado
		self.total_reembolso = total_reembolso
		self.total_impuestos = total_impuestos
		self.total_solicitado_base = flt(total_solicitado) * exchange_rate
		self.total_ejecutado_base = flt(total_ejecutado) * exchange_rate
		self.total_reembolso_base = flt(total_reembolso) * exchange_rate
		self.total_impuestos_base = flt(total_impuestos) * exchange_rate

	def get_employee_advance(self):
		employee_advance = frappe.db.get_value(
			"Employee Advance", {"solicitud_de_viaticos": self.solicitud_de_viaticos, "docstatus": 1}, "name"
		)
		if not employee_advance:
			frappe.throw(
				_("La Solicitud de Viáticos {0} no tiene un Anticipo de Empleado registrado. Reciba la solicitud en contabilidad para generarlo antes de contabilizar esta liquidación.").format(
					get_link_to_form("Solicitud de Viaticos", self.solicitud_de_viaticos)
				)
			)

		employee_advance = frappe.get_doc("Employee Advance", employee_advance)
		if flt(employee_advance.paid_amount) <= 0:
			frappe.throw(
				_("El Anticipo de Empleado {0} no tiene pagos registrados").format(
					get_link_to_form("Employee Advance", employee_advance.name)
				)
			)

		return employee_advance

	def validate_partidas_manuales(self, employee_advance):
		"""Contabilizar would post the gastos again if the advance was already settled by a hand-made Journal Entry"""
		partidas = get_partidas_manuales(self.name, employee_advance)
		if partidas:
			frappe.throw(
				_("El Anticipo de Empleado {0} ya tiene partidas contables registradas fuera de este flujo, que pueden incluir los gastos de esta liquidación:<br>{1}<br><br>Contabilidad debe revisarlas: si ya contabilizan la liquidación, cancélelas o reviértalas antes de contabilizar, para no registrar los gastos dos veces.").format(
					get_link_to_form("Employee Advance", employee_advance),
					"<br>".join(
						"{0} ({1}) {2}".format(get_link_to_form("Journal Entry", p.name), frappe.format_value(p.posting_date, {"fieldtype": "Date"}), p.title or "")
						for p in partidas
					),
				),
				title=_("Partidas manuales del anticipo"),
			)

	def validate_flujo_anterior_con_saldo(self, employee_advance):
		"""The previous flow's entries were edited by hand and handle the balance in many ways (employee rows,
		intercompany, income...), so a balance cannot be settled on top of them safely"""
		partidas = get_partidas_flujo_anterior(self.name)
		if not partidas:
			return
		montos = self.get_montos(employee_advance)
		saldo = montos.monto_devolucion or montos.monto_reembolso
		if saldo:
			frappe.throw(
				_("Los gastos de esta liquidación ya están contabilizados en {0} (flujo anterior), y queda un saldo de {1} {2}. Contabilidad debe registrar ese saldo de acuerdo con lo que hicieron esas partidas; no se puede contabilizar automáticamente.").format(
					", ".join(get_link_to_form("Journal Entry", je) for je in partidas),
					frappe.format_value(saldo, {"fieldtype": "Currency", "options": self.currency}),
					_("a cargo del empleado") if montos.monto_devolucion else _("a favor del empleado"),
				),
				title=_("Liquidación del flujo anterior con saldo"),
			)

	def get_montos(self, employee_advance):
		precision = employee_advance.precision("paid_amount")
		total_gastos = flt(sum(flt(expense.subtotal) for expense in self.detalle_liquidacion) + flt(self.total_impuestos), precision)
		# the stored return_amount is not reliable on older advances, rebuild it from payroll returns
		devuelto_en_planilla = get_devuelto_en_planilla(employee_advance.name)
		monto_anticipo = flt(flt(employee_advance.paid_amount) - devuelto_en_planilla, precision)
		return frappe._dict(
			devuelto_en_planilla=devuelto_en_planilla,
			monto_anticipo=monto_anticipo,
			monto_liquidado=min(total_gastos, monto_anticipo),
			monto_devolucion=flt(max(monto_anticipo - total_gastos, 0), precision),
			monto_reembolso=flt(max(total_gastos - monto_anticipo, 0), precision),
		)

	def has_payment_details(self):
		return bool(self.mode_of_payment and self.reference_no and self.reference_date)

	def is_empleado_retirado(self):
		"""The solicitante can no longer be paid in payroll: left, or relieved before today"""
		if not self.solicitante:
			return False
		status, relieving_date = frappe.db.get_value("Employee", self.solicitante, ["status", "relieving_date"])
		return status == "Left" or bool(relieving_date and getdate(relieving_date) < getdate(nowdate()))

	def conciliar_anticipo(self):
		"""Post the liquidacion and close its Employee Advance.

		Gastos are applied against the advance (up to what was paid). A leftover balance is either
		returned by the employee (bank deposit if payment details were given, otherwise a payroll
		deduction linked to the advance), or, when gastos exceed the advance, reimbursed in payroll.
		When the employee is no longer in payroll both go through the bank.
		"""
		frappe.flags.ignore_account_permissions = True

		employee_advance = self.get_employee_advance()
		montos = self.get_montos(employee_advance)
		devuelto_en_planilla = montos.devuelto_en_planilla
		monto_anticipo = montos.monto_anticipo
		monto_liquidado = montos.monto_liquidado
		monto_devolucion = montos.monto_devolucion
		monto_reembolso = montos.monto_reembolso
		empleado_retirado = self.is_empleado_retirado()
		if empleado_retirado and (monto_devolucion or monto_reembolso) and not self.has_payment_details():
			# payroll can no longer deduct or pay the balance, it has to go through the bank
			frappe.throw(
				_("{0} ya no está en planilla. Ingrese el Modo de Pago, el No. de Referencia y la Fecha de Referencia {1} de {2}.").format(
					self.nombre_solicitante or self.solicitante,
					_("del depósito de la devolución") if monto_devolucion else _("del pago del reembolso"),
					frappe.format_value(monto_devolucion or monto_reembolso, {"fieldtype": "Currency", "options": self.currency}),
				),
				title=_("Devolución por Banco") if monto_devolucion else _("Reembolso por Banco"),
			)
		devolucion_bancaria = monto_devolucion > 0 and self.has_payment_details()
		reembolso_bancario = monto_reembolso > 0 and empleado_retirado
		# the employee moved to another company: its payroll settles the balance, intercompany with the advance's
		compania_planilla = frappe.get_cached_value("Employee", self.solicitante, "company")
		planilla_otra_compania = not empleado_retirado and compania_planilla != employee_advance.company
		devolucion_otra_compania = monto_devolucion > 0 and not devolucion_bancaria and planilla_otra_compania

		componentes = get_componentes_viaticos()
		if devolucion_otra_compania and not componentes.deduccion_intercompania:
			frappe.throw(
				_("Configure el Componente Deducción por Viáticos Intercompañía en {0}").format(
					get_link_to_form("Configuraciones de Pagos y Viaticos", "Configuraciones de Pagos y Viaticos")
				)
			)

		journal_entries = self.get_legacy_journal_entries()
		if not journal_entries:
			# with previous-flow entries there is nothing left to post: they hold the gastos and a balance is
			# refused in validate_flujo_anterior_con_saldo
			journal_entries = self.make_journal_entries(
				employee_advance,
				monto_liquidado=monto_liquidado,
				monto_devolucion=monto_devolucion if devolucion_bancaria or devolucion_otra_compania else 0,
				monto_reembolso=monto_reembolso,
				componente_reembolso=componentes.reembolso,
				reembolso_bancario=reembolso_bancario,
				compania_planilla=compania_planilla if planilla_otra_compania else None,
				componente_deduccion_intercompania=componentes.deduccion_intercompania if devolucion_otra_compania else None,
			)

		# returned through the bank or the other company's payroll (settled here, not by an advance-linked deduction)
		devuelto_aqui = monto_devolucion if devolucion_bancaria or devolucion_otra_compania else 0
		frappe.db.set_value("Employee Advance", employee_advance.name, {
			"claimed_amount": monto_liquidado,
			"return_amount": devuelto_en_planilla + devuelto_aqui,
		})

		additional_salary = None
		if devolucion_otra_compania:
			additional_salary = self.make_additional_salary(
				employee_advance, componentes.deduccion_intercompania, monto_devolucion, self.doctype, self.name
			)
		elif monto_devolucion and not devolucion_bancaria:
			additional_salary = self.make_additional_salary(
				employee_advance, componentes.deduccion, monto_devolucion, "Employee Advance", employee_advance.name
			)
		elif monto_reembolso and not reembolso_bancario:
			additional_salary = self.make_additional_salary(
				employee_advance, componentes.reembolso, monto_reembolso, self.doctype, self.name
			)

		employee_advance.reload()
		employee_advance.set_status(update=True)

		self.db_set({
			"employee_advance": employee_advance.name,
			"monto_anticipo": monto_anticipo,
			"monto_liquidado": monto_liquidado,
			"monto_devolucion": monto_devolucion,
			"monto_reembolso": monto_reembolso,
			"additional_salary": additional_salary,
		})

		links = [get_link_to_form("Journal Entry", je) for je in journal_entries]
		if additional_salary:
			links.append(get_link_to_form("Additional Salary", additional_salary))
		if links:
			frappe.msgprint(_("Liquidación contabilizada: {0}").format(", ".join(links)), alert=True, indicator="green")

	def get_legacy_journal_entries(self):
		"""Journal Entries made at 'En Revisión Contable' by the previous flow (only linked by title).
		Drafts are discarded so the liquidacion is posted with the reviewed accounts; submitted ones are kept."""
		for je in frappe.get_all(
			"Journal Entry",
			filters={"title": ["like", f"%Liquidación de viáticos {self.name} contra anticipo%"], "docstatus": 0},
			pluck="name",
		):
			frappe.delete_doc("Journal Entry", je, ignore_permissions=True)

		submitted = get_partidas_flujo_anterior(self.name)
		for je in submitted:
			frappe.db.set_value("Journal Entry", je, "liquidacion_de_viaticos", self.name)
		return submitted

	def make_journal_entries(
		self,
		employee_advance,
		monto_liquidado=0,
		monto_devolucion=0,
		monto_reembolso=0,
		componente_reembolso=None,
		reembolso_bancario=False,
		compania_planilla=None,
		componente_deduccion_intercompania=None,
	):
		"""Journal Entry in the employee's company that clears the advance.

		When the employee belongs to another company, the gastos are booked in this company by a second
		Journal Entry against the intercompany receivable, and the first one debits the intercompany payable.
		A deposit or reimbursement through another company's bank is posted in that company too (get_banco), and so
		is a balance settled by the payroll of the company the employee moved to (`compania_planilla`).
		"""
		company = employee_advance.company
		advance_account = employee_advance.advance_account
		cost_center = self.cost_center if company == self.company else get_employee_cost_center(self.solicitante)
		if not cost_center or frappe.get_cached_value("Cost Center", cost_center, "company") != company:
			# the employee may have moved to another company since the advance
			cost_center = frappe.get_cached_value("Company", company, "cost_center")
		total_gastos = flt(monto_liquidado) + flt(monto_reembolso)

		je = self.new_journal_entry(
			company,
			f"Liquidación de viáticos {self.name} contra anticipo {employee_advance.name}",
		)

		if total_gastos:
			if company == self.company:
				self.append_gastos(je, cost_center)
			else:
				configuracion_cuentas_reference_doc = get_configuraciones_cuentas(self.company)
				payable_party = configuracion_cuentas_reference_doc["parte_supplier"]
				payable_account = get_party_account_from_utils("Supplier", payable_party, company)
				precision = je.precision("debit_in_account_currency", "accounts")

				row = {
					"account": payable_account,
					"account_currency": get_account_currency(payable_account),
					"cost_center": cost_center,
					"party_type": "Supplier",
					"party": payable_party,
				}
				# the gastos applied to the advance settle what the other company paid for it; the excess
				# reimbursed to the employee is a new payable
				asignado = 0
				for pago in get_advance_payment_journal_entries(employee_advance.name, payable_account, payable_party):
					monto = flt(min(flt(monto_liquidado) - asignado, flt(pago.outstanding)), precision)
					if monto <= 0:
						break
					je.append("accounts", dict(row, debit_in_account_currency=monto, reference_type="Journal Entry", reference_name=pago.name))
					asignado += monto

				sin_referencia = flt(total_gastos - asignado, precision)
				if sin_referencia > 0:
					je.append("accounts", dict(row, debit_in_account_currency=sin_referencia))

		if monto_liquidado:
			je.append("accounts", self.get_advance_row(advance_account, monto_liquidado, cost_center, employee_advance))

		otras_companias = []
		if monto_reembolso and reembolso_bancario:
			otras_companias.append(self.append_movimiento_bancario(
				je, company, cost_center, -monto_reembolso,
				_("Reembolso al empleado {0} ref. {1}").format(self.mode_of_payment, self.reference_no),
			))
		elif monto_reembolso and compania_planilla:
			otras_companias.append(self.append_planilla_otra_compania(
				je, company, compania_planilla, cost_center, -monto_reembolso, componente_reembolso
			))
		elif monto_reembolso:
			reembolso_account = get_salary_component_account(componente_reembolso, company)
			row = {
				"account": reembolso_account,
				"credit_in_account_currency": monto_reembolso,
				"cost_center": cost_center,
				"user_remark": _("Reembolso al empleado por gastos que exceden el anticipo, pagado en planilla"),
			}
			if frappe.get_cached_value("Account", reembolso_account, "account_type") in ("Receivable", "Payable"):
				row.update({"party_type": "Employee", "party": self.solicitante})
			je.append("accounts", row)

		if monto_devolucion and componente_deduccion_intercompania:
			otras_companias.append(self.append_planilla_otra_compania(
				je, company, compania_planilla, cost_center, monto_devolucion, componente_deduccion_intercompania
			))
			je.append("accounts", self.get_advance_row(advance_account, monto_devolucion, cost_center, employee_advance))
		elif monto_devolucion:
			otras_companias.append(self.append_movimiento_bancario(
				je, company, cost_center, monto_devolucion,
				_("Devolución del empleado {0} ref. {1}").format(self.mode_of_payment, self.reference_no),
			))
			je.append("accounts", self.get_advance_row(advance_account, monto_devolucion, cost_center, employee_advance))

		journal_entries = []
		if je.get("accounts"):
			self.submit_journal_entry(je)
			journal_entries.append(je.name)

		for je_banco in filter(None, otras_companias):
			self.submit_journal_entry(je_banco)
			journal_entries.append(je_banco.name)

		if company != self.company and total_gastos:
			configuracion_cuentas_doc = get_configuraciones_cuentas(company)
			receivable_party = configuracion_cuentas_doc["parte_customer"]
			receivable_account = get_party_account_from_utils("Customer", receivable_party, self.company)

			je2 = self.new_journal_entry(
				self.company,
				f"Cuenta por cobrar por Liquidación de viáticos {self.name} contra anticipo {employee_advance.name}",
			)
			self.append_gastos(je2, self.cost_center)
			je2.append("accounts", {
				"account": receivable_account,
				"account_currency": get_account_currency(receivable_account),
				"credit_in_account_currency": total_gastos,
				"cost_center": self.cost_center,
				"party_type": "Customer",
				"party": receivable_party,
			})
			self.submit_journal_entry(je2)
			journal_entries.append(je2.name)

		return journal_entries

	def new_journal_entry(self, company, title):
		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.posting_date = self.posting_date
		je.company = company
		je.title = title
		je.user_remark = title
		je.liquidacion_de_viaticos = self.name

		company_currency = frappe.get_cached_value("Company", company, "default_currency")
		je.multi_currency = 1 if self.currency != company_currency else 0
		return je

	def get_banco(self, company):
		"""Company whose bank or cash account the Mode of Payment moves, and that account. Other companies map the
		same Mode of Payment to an intercompany receivable, which is not where the money is."""
		bancos = {
			row.company: row.default_account
			for row in frappe.get_all("Mode of Payment Account", filters={"parent": self.mode_of_payment}, fields=["company", "default_account"])
			if row.default_account and frappe.get_cached_value("Account", row.default_account, "account_type") in ("Bank", "Cash")
		}
		for banco_company in (company, self.company):
			if banco_company in bancos:
				return banco_company, bancos[banco_company]
		if len(bancos) == 1:
			return next(iter(bancos.items()))
		frappe.throw(
			_("No se puede determinar a qué compañía pertenece el banco del Modo de Pago {0}: configure su cuenta de banco o caja en {1}.").format(
				get_link_to_form("Mode of Payment", self.mode_of_payment), " o ".join(sorted({company, self.company}))
			)
		)

	def append_movimiento_bancario(self, je, company, cost_center, monto, user_remark):
		"""Add the bank movement to `je` (company of the advance): `monto` > 0 is money the employee deposited,
		< 0 money paid to the employee. Through another company's bank, `je` debits/credits the intercompany payable
		to that company instead, and the Journal Entry returned books the bank there against the receivable."""
		banco_company, bank_account = self.get_banco(company)
		lado = "debit_in_account_currency" if monto > 0 else "credit_in_account_currency"
		contra = "credit_in_account_currency" if monto > 0 else "debit_in_account_currency"
		monto = abs(monto)

		if banco_company == company:
			je.append("accounts", {"account": bank_account, lado: monto, "cost_center": cost_center, "user_remark": user_remark})
			self.set_payment_reference(je)
			return None

		supplier = get_configuraciones_cuentas(banco_company)["parte_supplier"]
		customer = get_configuraciones_cuentas(company)["parte_customer"]
		if not supplier or not customer:
			frappe.throw(
				_("Configure el Cliente y el Proveedor de {0} y {1} en Configuraciones de Pagos y Viáticos para registrar el movimiento por el banco de {0}.").format(
					banco_company, company
				)
			)
		payable_account = get_party_account_from_utils("Supplier", supplier, company)
		je.append("accounts", {
			"account": payable_account,
			"account_currency": get_account_currency(payable_account),
			lado: monto,
			"cost_center": cost_center,
			"party_type": "Supplier",
			"party": supplier,
			"user_remark": user_remark,
		})

		banco_cost_center = self.cost_center if banco_company == self.company else frappe.get_cached_value("Company", banco_company, "cost_center")
		receivable_account = get_party_account_from_utils("Customer", customer, banco_company)
		je_banco = self.new_journal_entry(
			banco_company,
			_("{0} de viáticos {1} por cuenta de {2}").format(
				_("Devolución") if lado == "debit_in_account_currency" else _("Reembolso"), self.name, company
			),
		)
		je_banco.voucher_type = "Bank Entry"
		je_banco.append("accounts", {"account": bank_account, lado: monto, "cost_center": banco_cost_center, "user_remark": user_remark})
		je_banco.append("accounts", {
			"account": receivable_account,
			"account_currency": get_account_currency(receivable_account),
			contra: monto,
			"cost_center": banco_cost_center,
			"party_type": "Customer",
			"party": customer,
		})
		self.set_payment_reference(je_banco)
		return je_banco

	def append_planilla_otra_compania(self, je, company, compania_planilla, cost_center, monto, componente):
		"""The employee is now paid by `compania_planilla`, whose payroll deducts (`monto` > 0) or pays (< 0) the
		balance with `componente`. `je` (company of the advance) takes the balance against that company; the Journal
		Entry returned moves it there from the intercompany account to the component's account, which payroll clears."""
		devolucion = monto > 0
		monto = abs(monto)
		lado, contra = ("debit_in_account_currency", "credit_in_account_currency") if devolucion else ("credit_in_account_currency", "debit_in_account_currency")

		# receivable from / payable to the payroll company here, the opposite one there
		party_type, party_type_planilla = ("Customer", "Supplier") if devolucion else ("Supplier", "Customer")
		party = get_configuraciones_cuentas(compania_planilla)["parte_" + party_type.lower()]
		party_planilla = get_configuraciones_cuentas(company)["parte_" + party_type_planilla.lower()]
		if not party or not party_planilla:
			frappe.throw(
				_("Configure el Cliente y el Proveedor de {0} y {1} en Configuraciones de Pagos y Viáticos para registrar el saldo en la planilla de {0}.").format(
					compania_planilla, company
				)
			)

		remark = _("{0} de viáticos en la planilla de {1}").format(_("Deducción") if devolucion else _("Reembolso"), compania_planilla)
		account = get_party_account_from_utils(party_type, party, company)
		je.append("accounts", {
			"account": account,
			"account_currency": get_account_currency(account),
			lado: monto,
			"cost_center": cost_center,
			"party_type": party_type,
			"party": party,
			"user_remark": remark,
		})

		planilla_cost_center = self.cost_center if compania_planilla == self.company else get_employee_cost_center(self.solicitante)
		if not planilla_cost_center or frappe.get_cached_value("Cost Center", planilla_cost_center, "company") != compania_planilla:
			planilla_cost_center = frappe.get_cached_value("Company", compania_planilla, "cost_center")
		account_planilla = get_party_account_from_utils(party_type_planilla, party_planilla, compania_planilla)
		je_planilla = self.new_journal_entry(
			compania_planilla,
			_("{0} de viáticos {1} en planilla por cuenta de {2}").format(_("Deducción") if devolucion else _("Reembolso"), self.name, company),
		)
		je_planilla.append("accounts", {
			"account": get_salary_component_account(componente, compania_planilla),
			lado: monto,
			"cost_center": planilla_cost_center,
			"user_remark": remark,
		})
		je_planilla.append("accounts", {
			"account": account_planilla,
			"account_currency": get_account_currency(account_planilla),
			contra: monto,
			"cost_center": planilla_cost_center,
			"party_type": party_type_planilla,
			"party": party_planilla,
		})
		return je_planilla

	def set_payment_reference(self, je):
		je.cheque_no = self.reference_no
		je.cheque_date = self.reference_date
		je.mode_of_payment = self.mode_of_payment

	def submit_journal_entry(self, je):
		account_currencies = {get_account_currency(row.account) for row in je.accounts}
		if account_currencies - {frappe.get_cached_value("Company", je.company, "default_currency")}:
			je.multi_currency = 1

		je.flags.ignore_permissions = True
		je.insert()
		je.submit()

	def append_gastos(self, je, cost_center):
		cuentas = {row.tipo_gasto: row.cuenta for row in self.presupuesto_viaticos}
		for expense in self.detalle_liquidacion:
			je.append("accounts", {
				"account": cuentas.get(expense.expense_type) or get_expense_claim_account(expense.expense_type, self.company)["account"],
				"debit_in_account_currency": expense.subtotal,
				"cost_center": expense.cost_center or cost_center,
				"user_remark": "Fecha: {0}\nProveedor: {1}\nFactura No.: {2}\nDescripcion: {3}".format(
					expense.expense_date,
					expense.nombre_proveedor,
					expense.numero_factura,
					expense.description)
			})

		if flt(self.total_impuestos) > 0:
			taxes = get_default_taxes_and_charges("Purchase Taxes and Charges Template", company=je.company)
			if taxes and taxes.get('taxes') and len(taxes.get('taxes')) > 0:
				tax_details = taxes.get('taxes')[0]
				je.append("accounts", {
					"account": tax_details.account_head,
					"debit_in_account_currency": self.total_impuestos,
					"cost_center": tax_details.cost_center
				})
			else:
				frappe.throw(_("No se pudo obtener la configuración de impuestos para la empresa {0}").format(je.company))

	def get_advance_row(self, advance_account, amount, cost_center, employee_advance):
		return {
			"account": advance_account,
			"credit_in_account_currency": amount,
			"cost_center": cost_center,
			"reference_type": "Employee Advance",
			"reference_name": employee_advance.name,
			"party_type": "Employee",
			"party": self.solicitante,
		}

	def make_additional_salary(self, employee_advance, salary_component, amount, ref_doctype, ref_docname):
		"""Payroll line that settles the balance. Reuses an unlinked one already made by hand for the same amount."""
		additional_salary = frappe.db.get_value(
			"Additional Salary",
			{
				"employee": self.solicitante,
				"salary_component": salary_component,
				"amount": amount,
				"docstatus": ["<", 2],
				"ref_docname": ["is", "not set"],
				"liquidacion_de_viaticos": ["is", "not set"],
				"creation": [">=", self.creation],
			},
			["name", "docstatus"],
			as_dict=True,
		)

		if additional_salary and additional_salary.docstatus == 1:
			frappe.db.set_value("Additional Salary", additional_salary.name, {
				"ref_doctype": ref_doctype,
				"ref_docname": ref_docname,
				"liquidacion_de_viaticos": self.name,
			})
			if ref_doctype == "Employee Advance":
				# what on_submit would have done had it been linked
				frappe.db.set_value(
					"Employee Advance", employee_advance.name, "return_amount",
					flt(frappe.db.get_value("Employee Advance", employee_advance.name, "return_amount")) + flt(amount),
				)
			return additional_salary.name

		doc = frappe.get_doc("Additional Salary", additional_salary.name) if additional_salary else frappe.new_doc("Additional Salary")
		doc.update({
			"employee": self.solicitante,
			# the payroll that settles it: the employee's company, which may no longer be the advance's
			"company": frappe.get_cached_value("Employee", self.solicitante, "company"),
			"salary_component": salary_component,
			"currency": employee_advance.currency,
			"amount": amount,
			"payroll_date": self.get_payroll_date(),
			"overwrite_salary_structure_amount": 0,
			"ref_doctype": ref_doctype,
			"ref_docname": ref_docname,
			"liquidacion_de_viaticos": self.name,
		})
		if doc.meta.has_field("tipo_compensacion"):
			doc.tipo_compensacion = "Regular"

		doc.flags.ignore_permissions = True
		try:
			doc.save()
			doc.submit()
		except frappe.ValidationError as e:
			if ref_doctype == "Employee Advance":
				alternativa = _("Si el empleado ya no está en planilla, registre la devolución con el Modo de Pago y la referencia del depósito.")
			else:
				alternativa = _("Si el empleado ya no está en planilla, registre su salida en el Empleado e ingrese el Modo de Pago y la referencia del pago del reembolso.")
			frappe.throw(
				_("No se pudo registrar el {0} de {1} en planilla de {2}: {3}<br>{4}").format(
					salary_component, frappe.format_value(amount, {"fieldtype": "Currency", "options": doc.currency}), self.nombre_solicitante or self.solicitante, e, alternativa
				),
				title=_("Salario Adicional"),
			)
		return doc.name

	def get_payroll_date(self):
		payroll_date = max(getdate(self.posting_date), getdate(nowdate()))
		relieving_date = frappe.db.get_value("Employee", self.solicitante, "relieving_date")
		if relieving_date and payroll_date > getdate(relieving_date):
			payroll_date = getdate(relieving_date)
		return payroll_date

	def revertir_conciliacion(self):
		for additional_salary in frappe.get_all(
			"Additional Salary", filters={"liquidacion_de_viaticos": self.name, "docstatus": ["<", 2]}, fields=["name", "docstatus"]
		):
			if additional_salary.docstatus == 1:
				doc = frappe.get_doc("Additional Salary", additional_salary.name)
				doc.flags.ignore_permissions = True
				doc.cancel()
			else:
				frappe.delete_doc("Additional Salary", additional_salary.name, ignore_permissions=True)

		for je in frappe.get_all(
			"Journal Entry", filters={"liquidacion_de_viaticos": self.name, "docstatus": 1}, pluck="name", order_by="creation desc"
		):
			doc = frappe.get_doc("Journal Entry", je)
			doc.flags.ignore_permissions = True
			doc.cancel()

		if not self.employee_advance:
			return

		frappe.db.set_value("Employee Advance", self.employee_advance, {
			"claimed_amount": 0,
			"return_amount": get_devuelto_en_planilla(self.employee_advance),
		})
		frappe.get_doc("Employee Advance", self.employee_advance).set_status(update=True)

def get_fecha_contabilizacion(posting_date, companies, voucher_type="Journal Entry"):
	"""First date on or after `posting_date` that is open for `voucher_type` in every company:
	past closed Accounting Periods, Period Closing Vouchers and the accounts frozen date."""
	posting_date = getdate(posting_date)
	frozen_upto = frappe.db.get_single_value("Accounts Settings", "acc_frozen_upto")

	moved = True
	while moved:
		moved = False
		for company in companies:
			closed_until = get_cierre_contable(company, posting_date, voucher_type, frozen_upto)
			if closed_until and posting_date <= closed_until:
				posting_date = add_days(closed_until, 1)
				moved = True

	return posting_date

def get_cierre_contable(company, posting_date, voucher_type, frozen_upto=None):
	"""Last closed date that blocks `posting_date`, if any"""
	cierres = []

	if frozen_upto and getdate(frozen_upto) >= posting_date:
		cierres.append(getdate(frozen_upto))

	last_pcv_date = frappe.db.sql(
		"SELECT MAX(period_end_date) FROM `tabPeriod Closing Voucher` WHERE company = %s AND docstatus = 1",
		company,
	)[0][0]
	if last_pcv_date and getdate(last_pcv_date) >= posting_date:
		cierres.append(getdate(last_pcv_date))

	accounting_period_end = frappe.db.sql(
		"""SELECT MAX(ap.end_date)
		FROM `tabAccounting Period` ap
		JOIN `tabClosed Document` cd ON cd.parent = ap.name
		WHERE ap.company = %(company)s
			AND cd.closed = 1
			AND cd.document_type = %(voucher_type)s
			AND %(date)s BETWEEN ap.start_date AND ap.end_date""",
		{"company": company, "voucher_type": voucher_type, "date": posting_date},
	)[0][0]
	if accounting_period_end:
		cierres.append(getdate(accounting_period_end))

	return max(cierres) if cierres else None

def get_partidas_flujo_anterior(liquidacion):
	"""Submitted Journal Entries the previous flow made for this liquidacion (only linked by title)"""
	return frappe.get_all(
		"Journal Entry",
		filters={"title": ["like", f"%Liquidación de viáticos {liquidacion} contra anticipo%"], "docstatus": 1},
		pluck="name",
		order_by="posting_date, name",
	)

def get_partidas_manuales(liquidacion, employee_advance):
	"""Submitted Journal Entries on the advance that settle it outside this flow: they credit the advance account
	against the advance, or book expenses. Not counted: the advance's payment (only debits it; older payments carry the
	advance reference on the bank or intercompany row), the previous flow's entries for this liquidacion (found by
	title, see get_legacy_journal_entries) and the ones Contabilizar made."""
	return frappe.db.sql(
		"""SELECT DISTINCT je.name, je.posting_date, je.title
		FROM `tabJournal Entry` je
		JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
			AND jea.reference_type = 'Employee Advance' AND jea.reference_name = %(advance)s
		WHERE je.docstatus = 1
			AND IFNULL(je.title, '') NOT LIKE %(legacy_title)s
			AND IFNULL(je.liquidacion_de_viaticos, '') != %(liquidacion)s
			AND (
				EXISTS(SELECT 1 FROM `tabJournal Entry Account` x
					JOIN `tabAccount` a ON a.name = x.account
					WHERE x.parent = je.name AND a.account_number = %(advance_account_number)s AND x.reference_type = 'Employee Advance'
						AND x.reference_name = %(advance)s AND x.credit_in_account_currency > 0)
				OR EXISTS(SELECT 1 FROM `tabJournal Entry Account` x JOIN `tabAccount` a ON a.name = x.account
					WHERE x.parent = je.name AND a.root_type = 'Expense')
			)
		ORDER BY je.posting_date, je.name""",
		{
			"advance": employee_advance,
			# by number: the entry may be in another company when the employee changed companies
			"advance_account_number": frappe.db.get_value(
				"Account", frappe.db.get_value("Employee Advance", employee_advance, "advance_account"), "account_number"
			),
			"liquidacion": liquidacion,
			"legacy_title": f"%Liquidación de viáticos {liquidacion} contra anticipo%",
		},
		as_dict=True,
	)

def get_devuelto_en_planilla(employee_advance):
	return flt(frappe.db.get_value(
		"Additional Salary",
		{"ref_doctype": "Employee Advance", "ref_docname": employee_advance, "docstatus": 1},
		"sum(amount)",
	))

def get_salary_component_account(salary_component, company):
	account = frappe.db.get_value(
		"Salary Component Account", {"parent": salary_component, "company": company}, "account"
	)
	if not account:
		frappe.throw(
			_("Configure la cuenta del componente {0} para la compañía {1}").format(
				get_link_to_form("Salary Component", salary_component), company
			)
		)
	return account

@frappe.whitelist()
def get_fecha_contabilizacion_liquidacion(fecha, company, solicitante=None):
	companies = {company}
	if solicitante:
		companies.add(frappe.get_cached_value("Employee", solicitante, "company"))
	return get_fecha_contabilizacion(fecha, list(companies - {None}))

@frappe.whitelist()
def get_solicitud_de_viaticos(docname):
	doc = frappe.get_doc("Solicitud de Viaticos", docname)

	return doc

@frappe.whitelist()
def get_expense_claim_account(expense_claim_type, company):
	account = frappe.db.get_value(
		"Expense Claim Account", {"parent": expense_claim_type, "company": company}, "default_account"
	)
	if not account:
		frappe.throw(
			_("Set the default account for the {0} {1}").format(
				frappe.bold(_("Expense Claim Type")),
				get_link_to_form("Expense Claim Type", expense_claim_type),
			)
		)

	return {"account": account}
