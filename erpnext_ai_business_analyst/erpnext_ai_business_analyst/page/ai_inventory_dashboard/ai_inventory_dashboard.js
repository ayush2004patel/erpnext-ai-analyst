frappe.pages['ai-inventory-dashboard'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Inventory Health Dashboard',
		single_column: true,
	});
	new InventoryHealthDashboard(page);
};

class InventoryHealthDashboard {
	constructor(page) {
		this.page = page;
		this.render();
		this.load();
	}

	render() {
		this.$container = $(`
			<div class="ai-inventory-dashboard">
				<style>
					.ai-inventory-dashboard { max-width: 1120px; margin: 0 auto; }
					.ai-dashboard-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; }
					.ai-dashboard-subtitle { color: var(--text-muted, #64748b); margin: 3px 0 0; }
					.ai-dashboard-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; }
					.ai-dashboard-card { background: var(--card-bg, #fff); border: 1px solid var(--border-color, #dfe5ec); border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(31, 55, 82, .05); }
					.ai-dashboard-card.danger { border-top: 4px solid #dc3545; }
					.ai-dashboard-card.warning { border-top: 4px solid #ed8936; }
					.ai-dashboard-label { color: var(--text-muted, #64748b); font-size: 13px; font-weight: 600; }
					.ai-dashboard-count { color: var(--heading-color, #1f2937); font-size: 34px; font-weight: 700; line-height: 1.25; margin: 6px 0; }
					.ai-dashboard-status { color: var(--text-muted, #64748b); font-size: 12px; }
					.ai-dashboard-details { margin-top: 24px; background: var(--card-bg, #fff); border: 1px solid var(--border-color, #dfe5ec); border-radius: 12px; padding: 18px; }
					.ai-dashboard-details h4 { margin: 0 0 12px; }
					.ai-dashboard-exception { padding: 10px 0; border-top: 1px solid var(--border-color, #edf0f2); line-height: 1.45; }
					.ai-dashboard-exception:first-of-type { border-top: 0; }
					.ai-dashboard-exception strong { display: block; margin-bottom: 3px; }
					@media (max-width: 576px) { .ai-dashboard-header { align-items: flex-start; gap: 10px; flex-direction: column; } }
				</style>
				<div class="ai-dashboard-header">
					<div><h3>Inventory health</h3><p class="ai-dashboard-subtitle">Priority exceptions from your current ERP data.</p></div>
					<button class="btn btn-default btn-sm ai-dashboard-refresh">Refresh</button>
				</div>
				<div class="ai-dashboard-grid"></div>
				<div class="ai-dashboard-details"><h4>Priority details</h4><div class="ai-dashboard-detail-list text-muted">Loading…</div></div>
			</div>
		`).appendTo(this.page.main);
		this.$grid = this.$container.find('.ai-dashboard-grid');
		this.$details = this.$container.find('.ai-dashboard-detail-list');
		this.$refresh = this.$container.find('.ai-dashboard-refresh');
		this.$refresh.on('click', () => this.load());
	}

	load() {
		this.$refresh.prop('disabled', true).text('Refreshing…');
		frappe.call({
			method: 'erpnext_ai_business_analyst.api.get_inventory_health_summary',
			callback: (r) => this.show(r.message?.cards || []),
			error: () => this.show_error(),
			always: () => this.$refresh.prop('disabled', false).text('Refresh'),
		});
	}

	show(cards) {
		this.$grid.empty();
		const details = [];
		cards.forEach((card) => {
			const count_label = card.error ? '—' : card.count;
			const status = card.error ? 'Unable to check' : card.count ? 'Needs attention' : 'No issues found';
			this.$grid.append(`<div class="ai-dashboard-card ${card.tone}"><div class="ai-dashboard-label">${frappe.utils.escape_html(card.label)}</div><div class="ai-dashboard-count">${count_label}</div><div class="ai-dashboard-status">${status}</div></div>`);
			card.examples.forEach((example) => details.push(`<div class="ai-dashboard-exception"><strong>${frappe.utils.escape_html(card.label)}</strong>${frappe.utils.escape_html(example)}</div>`));
		});
		this.$details.html(details.length ? details.join('') : 'No priority inventory exceptions found.');
	}

	show_error() {
		this.$grid.html('<div class="text-danger">Unable to load inventory health data. Please try again.</div>');
		this.$details.html('No details available.');
	}
}
