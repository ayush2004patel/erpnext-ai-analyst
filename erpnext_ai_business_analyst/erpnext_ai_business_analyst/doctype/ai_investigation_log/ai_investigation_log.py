# Copyright (c) 2026, erpnext_ai_business_analyst and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AIInvestigationLog(Document):
	def before_insert(self):
		# Link field defaults don't support a "current session user" magic
		# string in Frappe — set it explicitly here instead.
		if not self.user:
			self.user = frappe.session.user