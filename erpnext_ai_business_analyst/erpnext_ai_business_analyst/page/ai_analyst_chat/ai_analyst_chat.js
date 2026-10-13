frappe.pages['ai-analyst-chat'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'AI Analyst Chat',
		single_column: true,
	});

	new AIAnalystChat(page);
};

class AIAnalystChat {
	constructor(page) {
		this.page = page;
		this.render();
	}

	render() {
		this.$container = $(`
			<div class="ai-analyst-chat">
				<style>
					.ai-analyst-chat { max-width: 960px; margin: 0 auto; }
					.ai-analyst-messages { max-height: 65vh; min-height: 260px; overflow-y: auto; padding: 20px; background: var(--fg-color, #f8fafc); border: 1px solid var(--border-color, #dfe5ec); border-radius: 14px; }
					.ai-analyst-user-row { display: flex; justify-content: flex-end; margin-bottom: 16px; }
					.ai-analyst-user-bubble { max-width: 78%; padding: 10px 14px; background: #e8f1ff; color: #1e3a5f; border: 1px solid #c9ddfb; border-radius: 14px 14px 3px 14px; line-height: 1.5; }
					.ai-analyst-answer { max-width: 94%; margin-bottom: 20px; }
					.ai-analyst-answer-card { background: var(--card-bg, #fff); border: 1px solid var(--border-color, #dfe5ec); border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(31, 55, 82, .05); }
					.ai-analyst-trail { font-size: 12px; color: var(--text-muted, #6c757d); margin-bottom: 12px; }
					.ai-analyst-findings { margin: 0; border: 0; }
					.ai-analyst-findings thead { display: none; }
					.ai-analyst-findings tbody, .ai-analyst-findings tr, .ai-analyst-findings td { display: block; border: 0 !important; }
					.ai-analyst-findings tr { position: relative; padding: 13px 80px 13px 14px; margin-bottom: 9px; background: #f8fafc; border-left: 4px solid #ed8936 !important; border-radius: 7px; line-height: 1.5; }
					.ai-analyst-findings tr:last-child { margin-bottom: 0; }
					.ai-analyst-findings td { padding: 0 !important; }
					.ai-analyst-finding-title { margin-bottom: 4px; color: var(--heading-color, #1f2937); font-size: 14px; font-weight: 700; }
					.ai-analyst-finding-summary { color: var(--text-color, #334155); }
					.ai-analyst-finding-detail { margin-top: 5px; color: var(--text-muted, #64748b); font-size: 12px; }
					.ai-analyst-finding-why { margin-top: 8px; color: #5b4a13; font-size: 12px; line-height: 1.45; }
					.ai-analyst-finding-action { margin-top: 8px; color: #1f6f43; font-size: 12px; font-weight: 600; }
					.ai-analyst-record-links { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 9px; font-size: 12px; }
					.ai-analyst-record-links a { color: var(--primary, #2490ef); font-weight: 600; }
					.ai-analyst-confidence { position: absolute; top: 12px; right: 12px; padding: 3px 8px !important; background: #e7f7ed; color: #227a45; border-radius: 999px; font-size: 12px; font-weight: 600; }
					.ai-analyst-evidence-toggle { display: inline-block; margin-top: 13px; color: var(--primary, #2490ef); font-size: 13px; font-weight: 600; }
					.ai-analyst-evidence { margin-top: 8px; padding: 12px; background: #f8fafc; border-radius: 8px; font-size: 12px; }
					.ai-analyst-evidence-item { border-left: 3px solid #b8c7d9; padding-left: 10px; margin-bottom: 9px; line-height: 1.45; }
					.ai-analyst-evidence-item:last-child { margin-bottom: 0; }
					.ai-analyst-input { display: flex; gap: 10px; margin-top: 14px; }
					.ai-analyst-input .form-control { min-height: 42px; border-radius: 9px; }
					.ai-analyst-input .btn { min-width: 82px; border-radius: 9px; }
					.ai-analyst-report-selector { display: flex; align-items: center; gap: 8px; margin-top: 10px; color: var(--text-muted, #64748b); font-size: 12px; }
					.ai-analyst-report-selector select { max-width: 320px; min-height: 34px; font-size: 12px; }
					.ai-analyst-suggestions { margin-top: 12px; padding: 12px 14px; background: #f8fafc; border: 1px solid var(--border-color, #dfe5ec); border-radius: 10px; }
					.ai-analyst-suggestions-label { margin-bottom: 8px; color: var(--text-muted, #64748b); font-size: 12px; font-weight: 600; }
					.ai-analyst-suggestion-list { display: flex; flex-wrap: wrap; gap: 7px; }
					.ai-analyst-suggestion { padding: 5px 9px; background: var(--card-bg, #fff); color: var(--primary, #2490ef); border: 1px solid #c9ddfb; border-radius: 999px; cursor: pointer; font-size: 12px; line-height: 1.35; text-align: left; }
					.ai-analyst-suggestion:hover { background: #e8f1ff; border-color: var(--primary, #2490ef); }
					.ai-analyst-history { margin-top: 12px; padding: 12px 14px; background: #f8fafc; border: 1px solid var(--border-color, #dfe5ec); border-radius: 10px; }
					.ai-analyst-history-title { margin-bottom: 7px; color: var(--text-muted, #64748b); font-size: 12px; font-weight: 600; }
					.ai-analyst-history-item { display: flex; align-items: center; gap: 8px; padding: 7px 0; border-top: 1px solid var(--border-color, #dfe5ec); }
					.ai-analyst-history-item:first-of-type { border-top: 0; }
					.ai-analyst-history-question { flex: 1; padding: 0; color: var(--text-color, #334155); background: transparent; border: 0; cursor: pointer; font-size: 12px; overflow: hidden; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
					.ai-analyst-history-question:hover { color: var(--primary, #2490ef); text-decoration: underline; }
					.ai-analyst-history-log { flex: none; color: var(--primary, #2490ef); font-size: 11px; white-space: nowrap; }
					.ai-analyst-report-evidence { margin-top: 12px; font-size: 12px; }
					.ai-analyst-report-evidence summary { color: var(--primary, #2490ef); cursor: pointer; font-weight: 600; }
					.ai-analyst-report-table-wrap { max-height: 300px; overflow: auto; margin-top: 8px; border: 1px solid var(--border-color, #dfe5ec); border-radius: 7px; }
					.ai-analyst-report-table { margin: 0; min-width: 680px; font-size: 12px; }
					.ai-analyst-report-table th { position: sticky; top: 0; padding: 8px 10px; background: #edf3f9; color: var(--heading-color, #1f2937); font-weight: 600; white-space: nowrap; }
					.ai-analyst-report-table td { padding: 8px 10px; vertical-align: top; }
					.ai-analyst-export { margin-top: 9px; padding: 5px 9px; border-radius: 7px; font-size: 12px; }
					.ai-analyst-follow-ups { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border-color, #dfe5ec); }
					.ai-analyst-follow-ups-label { margin-bottom: 8px; color: var(--text-muted, #64748b); font-size: 12px; font-weight: 600; }
					.ai-analyst-follow-up-list { display: flex; flex-wrap: wrap; gap: 7px; }
					.ai-analyst-follow-up { padding: 5px 9px; background: #f8fafc; color: var(--primary, #2490ef); border: 1px solid #c9ddfb; border-radius: 999px; cursor: pointer; font-size: 12px; line-height: 1.35; text-align: left; }
					.ai-analyst-follow-up:hover { background: #e8f1ff; border-color: var(--primary, #2490ef); }
					.ai-analyst-error { display: inline-block; margin-bottom: 15px; padding: 10px 14px; background: #fff0ee; color: #9b2c2c; border: 1px solid #fecaca; border-radius: 10px; }
					@media (max-width: 576px) { .ai-analyst-messages { padding: 13px; } .ai-analyst-user-bubble, .ai-analyst-answer { max-width: 100%; } .ai-analyst-input { align-items: stretch; flex-direction: column; } .ai-analyst-report-selector { align-items: stretch; flex-direction: column; } .ai-analyst-report-selector select { max-width: none; } }
				</style>
				<div class="ai-analyst-messages"></div>
				<div class="ai-analyst-input">
					<input type="text" class="form-control ai-analyst-question"
						placeholder="e.g. Which inventory has not moved for 90 days?">
					<button class="btn btn-primary ai-analyst-ask">Ask</button>
				</div>
				<div class="ai-analyst-report-selector">
					<label for="ai-analyst-report-dataset">Data source</label>
					<select id="ai-analyst-report-dataset" class="form-control ai-analyst-report-dataset">
						<option value="">Auto select</option>
						<option value="stock_balance">Data View: Stock Balance</option>
						<option value="stock_movement">Data View: Stock Movement</option>
						<option value="order_commitments">Data View: Open Orders</option>
						<option value="monthly_consumption">Data View: Monthly Consumption</option>
						<option value="batch_expiry">Data View: Batch Expiry</option>
						<option value="erpnext_stock_balance">ERPNext Report: Stock Balance</option>
						<option value="erpnext_stock_ledger">ERPNext Report: Stock Ledger</option>
						<option value="erpnext_stock_ageing">ERPNext Report: Stock Ageing</option>
						<option value="erpnext_purchase_order_analysis">ERPNext Report: Purchase Order Analysis</option>
						<option value="erpnext_sales_order_analysis">ERPNext Report: Sales Order Analysis</option>
						<option value="erpnext_warehouse_stock_balance">ERPNext Report: Warehouse Wise Stock Balance</option>
						<option value="erpnext_stock_projected_qty">ERPNext Report: Stock Projected Qty</option>
						<option value="erpnext_item_shortage">ERPNext Report: Item Shortage Report</option>
						<option value="erpnext_batch_expiry">ERPNext Report: Batch Item Expiry Status</option>
						<option value="erpnext_item_consumption">ERPNext Report: Item Wise Consumption</option>
						<option value="erpnext_stock_account_value">ERPNext Report: Stock and Account Value Comparison</option>
						<option value="erpnext_purchase_order_trends">ERPNext Report: Purchase Order Trends</option>
						<option value="erpnext_sales_order_trends">ERPNext Report: Sales Order Trends</option>
					</select>
				</div>
				<div class="ai-analyst-suggestions">
					<div class="ai-analyst-suggestions-label">Try asking about your inventory</div>
					<div class="ai-analyst-suggestion-list">
						<button type="button" class="ai-analyst-suggestion" data-question="Which items need to be reordered?">Items to reorder</button>
						<button type="button" class="ai-analyst-suggestion" data-question="Which inventory has not moved for 90 days?">Dead stock</button>
						<button type="button" class="ai-analyst-suggestion" data-question="Which items are at risk of stockout?">Stockout risk</button>
						<button type="button" class="ai-analyst-suggestion" data-question="Which purchase orders will supply stock?">Incoming purchase orders</button>
						<button type="button" class="ai-analyst-suggestion" data-question="What customer demand is still pending?">Pending customer demand</button>
						<button type="button" class="ai-analyst-suggestion" data-question="Which batches expire in 90 days?">Batches expiring soon</button>
					</div>
				</div>
				<div class="ai-analyst-history" style="display: none;">
					<div class="ai-analyst-history-title">Recent investigations</div>
					<div class="ai-analyst-history-list"></div>
				</div>
			</div>
		`).appendTo(this.page.main);

		this.$messages = this.$container.find('.ai-analyst-messages');
		this.$input = this.$container.find('.ai-analyst-question');
		this.$button = this.$container.find('.ai-analyst-ask');
		this.$reportDataset = this.$container.find('.ai-analyst-report-dataset');
		this.$history = this.$container.find('.ai-analyst-history');
		this.$historyList = this.$container.find('.ai-analyst-history-list');

		this.$button.on('click', () => this.ask());
		this.$input.on('keypress', (e) => {
			if (e.which === 13) this.ask();
		});
		this.$container.find('.ai-analyst-suggestion').on('click', (e) => {
			this.$input.val($(e.currentTarget).data('question')).focus();
		});
		this.load_recent_history();
	}

	load_recent_history() {
		frappe.call({
			method: 'erpnext_ai_business_analyst.api.get_recent_investigations',
			args: { limit: 8 },
			callback: (r) => {
				const entries = r.message || [];
				if (!entries.length) {
					this.$history.hide();
					return;
				}
				const escape = frappe.utils.escape_html;
				this.$historyList.empty();
				entries.forEach((entry) => {
					const question = escape(entry.question || 'Untitled investigation');
					const log_url = `/app/ai-investigation-log/${encodeURIComponent(entry.name)}`;
					const $item = $(`<div class="ai-analyst-history-item"><button type="button" class="ai-analyst-history-question" title="${question}">${question}</button><a class="ai-analyst-history-log" href="${log_url}" target="_blank">View log</a></div>`);
					$item.find('.ai-analyst-history-question').on('click', () => {
						this.$input.val(entry.question).focus();
					});
					this.$historyList.append($item);
				});
				this.$history.show();
			},
		});
	}

	ask() {
		const question = this.$input.val().trim();
		if (!question) return;

		this.add_user_message(question);
		this.$input.val('');
		this.$button.prop('disabled', true).text('Thinking...');

		frappe.call({
			method: 'erpnext_ai_business_analyst.api.ask_question',
			args: { question, report_dataset: this.$reportDataset.val() || null },
			callback: (r) => {
				this.$button.prop('disabled', false).text('Ask');
				if (r.message) {
					this.add_answer(r.message);
					this.load_recent_history();
				}
			},
			error: () => {
				this.$button.prop('disabled', false).text('Ask');
				this.add_error('Something went wrong. Please try again.');
			},
		});
	}

	add_user_message(text) {
		this.$messages.append(`
			<div class="ai-analyst-user-row">
				<div class="ai-analyst-user-bubble">
					${frappe.utils.escape_html(text)}
				</div>
			</div>
		`);
		this.scroll_to_bottom();
	}

	add_error(text) {
		this.$messages.append(`
			<div>
				<div class="ai-analyst-error">
					${frappe.utils.escape_html(text)}
				</div>
			</div>
		`);
		this.scroll_to_bottom();
	}

	format_finding(claim) {
		const raw_claim = String(claim || '');
		const matched_skill = raw_claim.match(/^\[([^\]]+)\]\s*/);
		const skill_name = matched_skill ? matched_skill[1] : '';
		const finding_text = raw_claim.replace(/^\[[^\]]+\]\s*/, '');
		const escape = frappe.utils.escape_html;

		const dead_stock = finding_text.match(/^(.+?) \((.+?)\) at (.+?): ([\d.]+) in stock, last moved (\d+) days ago \((.+?)\)\.$/);
		if (dead_stock) {
			const [, item_code, item_name, warehouse, quantity, days] = dead_stock;
			return {
				title: 'Dead stock',
				summary: `${escape(item_name)} has ${escape(quantity)} units at ${escape(warehouse)}.`,
				detail: `No stock movement for ${escape(days)} days. Item code: ${escape(item_code)}.`,
				why: 'Cash is tied up in stock that is not contributing to sales or production.',
				action: 'Action: review disposal, discounting, or transfer options.',
				item_code,
				warehouse,
			};
		}

		const overstock = finding_text.match(/^(.+?) \((.+?)\) at (.+?): stock ([\d.]+) is ([\d.]+)x its ROL \(([^)]+)\) — (.+?)\. \((.+?)\)$/);
		if (overstock) {
			const [, item_code, item_name, warehouse, quantity, multiple, reorder_level, severity, consumption] = overstock;
			return {
				title: 'Overstock',
				summary: `${escape(item_name)} has ${escape(quantity)} units at ${escape(warehouse)}.`,
				detail: `${escape(multiple)}× above the recommended reorder level of ${escape(reorder_level)} units — ${escape(severity)}; ${escape(consumption)}. Item code: ${escape(item_code)}.`,
				why: 'Excess stock increases holding costs and the risk of future obsolescence.',
				action: 'Action: pause replenishment and review the stock plan.',
				item_code,
				warehouse,
			};
		}

		const labels = {
			'inventory.reorder_demand': 'Reorder needed',
			'inventory.stockout_risk': 'Stockout risk',
			'inventory.dead_stock': 'Dead stock',
			'inventory.overstock': 'Overstock',
			'inventory.slow_moving_stock': 'Slow-moving stock',
			'inventory.abc_xyz_classification': 'ABC/XYZ classification',
			'inventory.ageing_value': 'Ageing stock value',
			'inventory.inventory_turnover': 'Low inventory turnover',
			'inventory.overdue_purchase_orders': 'Overdue purchase orders',
			'inventory.supplier_delivery_risk': 'Supplier delivery risk',
			'inventory.purchase_delay_stockout_risk': 'Purchase-delay stockout risk',
			'inventory.demand_forecast_vs_actual': 'Demand forecast vs actual',
			'inventory.data_quality_audit': 'Inventory data quality issue',
			'inventory.inventory_concentration': 'Warehouse concentration',
			'inventory.stock_balance': 'Stock balance',
			'inventory.available_stock': 'Available stock',
			'inventory.negative_stock': 'Negative stock',
			'inventory.inventory_valuation': 'Inventory value',
			'inventory.warehouse_imbalance': 'Warehouse transfer opportunity',
			'inventory.stock_coverage': 'Stock coverage',
			'inventory.fast_moving_stock': 'Fast-moving stock',
			'inventory.open_purchase_orders': 'Open purchase order',
			'inventory.sales_commitments': 'Sales commitment',
			'inventory.expiring_batches': 'Expiring batch',
			'inventory.reorder_configuration_gap': 'Missing reorder setting',
			'inventory.stock_movement_summary': 'Stock movement summary',
		};
		const actions = {
			'inventory.reorder_demand': 'Action: raise or review a replenishment request.',
			'inventory.stockout_risk': 'Action: expedite supply or transfer stock from another warehouse.',
			'inventory.slow_moving_stock': 'Action: review demand, promotions, or future purchasing.',
			'inventory.inventory_concentration': 'Action: review whether stock should be redistributed.',
			'inventory.stock_balance': 'Action: use this as the current stock position.',
			'inventory.available_stock': 'Action: use available quantity for sales or allocation decisions.',
			'inventory.negative_stock': 'Action: investigate stock entries and reconcile the balance.',
			'inventory.inventory_valuation': 'Action: review high-value stock for financial exposure.',
			'inventory.warehouse_imbalance': 'Action: consider a warehouse transfer.',
			'inventory.stock_coverage': 'Action: compare coverage with supplier lead time and reorder needs.',
			'inventory.fast_moving_stock': 'Action: monitor replenishment closely to avoid stockouts.',
			'inventory.open_purchase_orders': 'Action: track the expected receipt date with the supplier.',
			'inventory.sales_commitments': 'Action: reserve or procure stock before the delivery date.',
			'inventory.expiring_batches': 'Action: prioritize use, sale, or disposal before expiry.',
			'inventory.reorder_configuration_gap': 'Action: set a reorder level for this stocked item.',
			'inventory.stock_movement_summary': 'Action: use this movement trend for inventory planning.',
			'inventory.abc_xyz_classification': 'Action: give A/Z items the closest planning control.',
			'inventory.ageing_value': 'Action: reduce ageing stock to release tied-up value.',
			'inventory.inventory_turnover': 'Action: review demand and future purchase quantities.',
			'inventory.overdue_purchase_orders': 'Action: follow up with the supplier immediately.',
			'inventory.supplier_delivery_risk': 'Action: review supplier lead time and alternatives.',
			'inventory.purchase_delay_stockout_risk': 'Action: expedite the PO or arrange an alternate supply.',
			'inventory.demand_forecast_vs_actual': 'Action: review the forecast and future replenishment plan.',
			'inventory.data_quality_audit': 'Action: correct the inventory data or setup issue before relying on planning results.',
		};
		const why_matters = {
			'inventory.reorder_demand': 'Without replenishment, demand may exceed the stock available to fulfil it.',
			'inventory.stockout_risk': 'A stockout can delay customer deliveries or interrupt production.',
			'inventory.slow_moving_stock': 'Slow-moving stock ties up cash and may become obsolete.',
			'inventory.inventory_concentration': 'Uneven stock distribution can create shortages in one warehouse while another has excess.',
			'inventory.negative_stock': 'Negative stock usually signals an inventory posting or process problem.',
			'inventory.inventory_valuation': 'High-value stock represents material working-capital exposure.',
			'inventory.warehouse_imbalance': 'A transfer may fulfil demand faster than waiting for a new purchase.',
			'inventory.stock_coverage': 'Low coverage can become a stockout before the next supply arrives.',
			'inventory.fast_moving_stock': 'Fast-moving items need closer replenishment monitoring.',
			'inventory.open_purchase_orders': 'Incoming supply affects whether future demand can be fulfilled.',
			'inventory.sales_commitments': 'Open customer demand must be covered before the promised delivery date.',
			'inventory.expiring_batches': 'Expiry can turn usable inventory into a loss if it is not used or sold in time.',
			'inventory.reorder_configuration_gap': 'Without a reorder setting, the system cannot reliably flag replenishment needs.',
			'inventory.stock_movement_summary': 'Movement trends help identify demand changes before they affect availability.',
			'inventory.abc_xyz_classification': 'High-value or unpredictable items need tighter planning control.',
			'inventory.ageing_value': 'Ageing inventory locks up working capital and may need recovery action.',
			'inventory.inventory_turnover': 'Low turnover indicates inventory is being held longer than expected.',
			'inventory.overdue_purchase_orders': 'Late supply can create stockouts or delay customer commitments.',
			'inventory.supplier_delivery_risk': 'Unreliable supplier delivery makes replenishment plans less dependable.',
			'inventory.purchase_delay_stockout_risk': 'A late purchase order may directly cause an item to run out.',
			'inventory.demand_forecast_vs_actual': 'A large forecast error can lead to excess stock or shortages.',
			'inventory.data_quality_audit': 'Poor inventory data can make every planning recommendation unreliable.',
		};
		let summary = finding_text.replace(/\bROL\b/g, 'recommended reorder level');
		let detail = '';
		let item_code = '';
		let warehouse = '';
		const item_at_warehouse = summary.match(/^(.+?) \((.+?)\) at (.+?):\s*(.+)$/);
		if (item_at_warehouse) {
			const [, parsed_item_code, item_name, parsed_warehouse, message] = item_at_warehouse;
			item_code = parsed_item_code;
			warehouse = parsed_warehouse;
			summary = `${item_name} at ${warehouse}: ${message}`;
			detail = `Item code: ${item_code}.`;
		} else {
			const item_only = summary.match(/^(.+?) \((.+?)\):\s*(.+)$/);
			if (item_only) {
				const [, parsed_item_code, item_name, message] = item_only;
				item_code = parsed_item_code;
				summary = `${item_name}: ${message}`;
				detail = `Item code: ${item_code}.`;
			}
		}
		return {
			title: labels[skill_name] || 'Inventory finding',
			summary: escape(summary),
			detail: escape(detail),
			why: why_matters[skill_name] || 'This can affect inventory availability, cost, or service if it is not reviewed.',
			action: actions[skill_name] || 'Action: review this inventory finding.',
			item_code,
			warehouse,
		};
	}

	format_record_links(item_code, warehouse) {
		const links = [];
		if (item_code) links.push(`<a href="/app/item/${encodeURIComponent(item_code)}">Open item</a>`);
		if (warehouse) links.push(`<a href="/app/warehouse/${encodeURIComponent(warehouse)}">Open warehouse</a>`);
		return links.length ? `<div class="ai-analyst-record-links">${links.join('')}</div>` : '';
	}

	no_data_message(steps) {
		const skill_name = steps[steps.length - 1]?.skill_name;
		const messages = {
			'inventory.reorder_demand': 'No items currently need a reorder. I checked configured reorder levels against stock and incoming supply.',
			'inventory.stockout_risk': 'No items are currently below their configured reorder level.',
			'inventory.dead_stock': 'No stocked items matched the selected inactive-stock period.',
			'inventory.slow_moving_stock': 'No items have stock coverage above the selected slow-moving threshold.',
			'inventory.overstock': 'No items have stock above the selected overstock threshold.',
			'inventory.inventory_concentration': 'No multi-warehouse item has stock concentrated above the selected threshold.',
			'inventory.stock_balance': 'No stock balance records matched the selected filters.',
			'inventory.available_stock': 'No available-stock records matched the selected filters.',
			'inventory.negative_stock': 'Good news: no item has negative stock in the checked records.',
			'inventory.inventory_valuation': 'No valued stock records matched the selected filters.',
			'inventory.warehouse_imbalance': 'No item needs a warehouse-transfer review based on the selected threshold.',
			'inventory.stock_coverage': 'There is not enough recent consumption data to calculate stock coverage.',
			'inventory.fast_moving_stock': 'No item met the selected fast-moving threshold in the checked period.',
			'inventory.open_purchase_orders': 'No submitted purchase orders have outstanding quantities to receive.',
			'inventory.sales_commitments': 'No submitted sales orders have outstanding quantities to deliver.',
			'inventory.expiring_batches': 'No active batches expire within the selected period.',
			'inventory.reorder_configuration_gap': 'All stocked items in the checked records have a reorder level configured.',
			'inventory.stock_movement_summary': 'No stock movement records matched the selected period and filters.',
			'inventory.abc_xyz_classification': 'No stocked items with a positive inventory value were available to classify.',
			'inventory.ageing_value': 'No stocked items have been inactive for the selected ageing period.',
			'inventory.inventory_turnover': 'No items met the selected low-turnover threshold in the checked period.',
			'inventory.overdue_purchase_orders': 'No open purchase orders are past their scheduled delivery date.',
			'inventory.supplier_delivery_risk': 'No supplier has a positive average delivery delay in the available delivery history.',
			'inventory.purchase_delay_stockout_risk': 'No overdue purchase order is currently needed to reach a configured reorder level.',
			'inventory.demand_forecast_vs_actual': 'No item differed from its demand forecast by the selected amount in the latest completed month.',
			'inventory.data_quality_audit': 'No common inventory data-quality issues were found in the checked records.',
		};
		return messages[skill_name] || 'No matching inventory records were found for this question.';
	}

	format_report_column_name(name) {
		return String(name).replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
	}

	format_report_value(value) {
		if (value === null || value === undefined || value === '') return '—';
		const text = typeof value === 'object' ? JSON.stringify(value) : String(value);
		return text.length > 160 ? `${text.slice(0, 157)}...` : text;
	}

	format_report_cell(column, value) {
		const text = frappe.utils.escape_html(this.format_report_value(value));
		const route = column === 'item_code' || column === 'item' ? 'item' : (column === 'warehouse' ? 'warehouse' : '');
		return route && value ? `<a href="/app/${route}/${encodeURIComponent(value)}">${text}</a>` : text;
	}

	format_report_table(records) {
		const rows = records.filter((record) => record && typeof record === 'object' && !Array.isArray(record));
		if (!rows.length) return '';
		const columns = [...new Set(rows.slice(0, 10).flatMap((record) => Object.keys(record)))].slice(0, 10);
		const escape = frappe.utils.escape_html;
		let html = `<details class="ai-analyst-report-evidence"><summary>View ${rows.length} returned report row${rows.length === 1 ? '' : 's'}</summary><div class="ai-analyst-report-table-wrap"><table class="table table-bordered ai-analyst-report-table"><thead><tr>`;
		columns.forEach((column) => {
			html += `<th>${escape(this.format_report_column_name(column))}</th>`;
		});
		html += '</tr></thead><tbody>';
		rows.forEach((row) => {
			html += '<tr>';
			columns.forEach((column) => {
				html += `<td>${this.format_report_cell(column, row[column])}</td>`;
			});
			html += '</tr>';
		});
		return `${html}</tbody></table></div></details>`;
	}

	export_report_rows(records, source_label) {
		const rows = records.filter((record) => record && typeof record === 'object' && !Array.isArray(record));
		if (!rows.length) return;
		const columns = [...new Set(rows.flatMap((record) => Object.keys(record)))];
		const csv_cell = (value) => {
			const text = value === null || value === undefined ? '' : (typeof value === 'object' ? JSON.stringify(value) : String(value));
			return `"${text.replace(/"/g, '""')}"`;
		};
		const csv = [columns.map(csv_cell).join(','), ...rows.map((row) => columns.map((column) => csv_cell(row[column])).join(','))].join('\n');
		const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8;' });
		const url = URL.createObjectURL(blob);
		const link = document.createElement('a');
		link.href = url;
		link.download = `${String(source_label || 'inventory-report').toLowerCase().replace(/[^a-z0-9]+/g, '-')}-shown-rows.csv`;
		document.body.appendChild(link);
		link.click();
		link.remove();
		URL.revokeObjectURL(url);
	}

	follow_up_questions(data) {
		const investigated = (data.steps || []).map((step) => step.skill_name).join(' ').toLowerCase();
		if (investigated.includes('purchase') || investigated.includes('supplier')) {
			return ['Which purchase orders are overdue?', 'Which suppliers have delivery delays?'];
		}
		if (investigated.includes('sales') || investigated.includes('customer')) {
			return ['What customer demand is still pending?', 'Which items are at risk of stockout?'];
		}
		if (investigated.includes('batch') || investigated.includes('expiry')) {
			return ['Which batches expire in 90 days?', 'Which items need to be reordered?'];
		}
		if (investigated.includes('movement') || investigated.includes('ageing') || investigated.includes('dead_stock')) {
			return ['Which inventory has not moved for 90 days?', 'Which items are slow moving?'];
		}
		return ['Which items need to be reordered?', 'Which items are at risk of stockout?'];
	}

	format_follow_ups(data) {
		if (!data.report_answer && !(data.steps && data.steps.length)) return '';
		const escape = frappe.utils.escape_html;
		let html = '<div class="ai-analyst-follow-ups"><div class="ai-analyst-follow-ups-label">Related questions</div><div class="ai-analyst-follow-up-list">';
		this.follow_up_questions(data).forEach((question) => {
			html += `<button type="button" class="ai-analyst-follow-up" data-question="${escape(question)}">${escape(question)}</button>`;
		});
		return `${html}</div></div>`;
	}

	add_answer(data) {
		let html = `<div class="ai-analyst-answer"><div class="ai-analyst-answer-card">`;

		const ranAnySkill = data.steps && data.steps.length > 0;

		if (ranAnySkill) {
			const trail = data.steps.map((s) => frappe.utils.escape_html(s.skill_name)).join(' &rarr; ');
			html += `<div class="ai-analyst-trail">
				Investigated: ${trail}
			</div>`;
		}

		if (data.report_answer) {
			html += `<div class="ai-analyst-finding-title">${frappe.utils.escape_html(data.report_source || 'Approved ERP report')}</div>`;
			html += `<div class="ai-analyst-finding-summary">${frappe.utils.escape_html(data.report_answer)}</div>`;
			html += `<div class="ai-analyst-finding-detail">${frappe.utils.escape_html(data.report_evidence_summary || '')}</div>`;
			if (data.report_records && data.report_records.length) {
				html += this.format_report_table(data.report_records);
				html += '<button type="button" class="btn btn-default btn-sm ai-analyst-export">Export shown rows (CSV)</button>';
			}
		} else if (ranAnySkill && data.findings && data.findings.length > 0) {
			html += `<table class="table ai-analyst-findings">
				<thead><tr><th>Finding</th><th style="width: 90px;">Confidence</th></tr></thead>
				<tbody>`;
			data.findings.forEach((f) => {
				const finding = this.format_finding(f.claim);
				html += `<tr>
					<td><div class="ai-analyst-finding-title">${finding.title}</div>
						<div class="ai-analyst-finding-summary">${finding.summary}</div>
						${finding.detail ? `<div class="ai-analyst-finding-detail">${finding.detail}</div>` : ''}
						${finding.why ? `<div class="ai-analyst-finding-why"><strong>Why this matters:</strong> ${frappe.utils.escape_html(finding.why)}</div>` : ''}
						${finding.action ? `<div class="ai-analyst-finding-action">Recommended action: ${frappe.utils.escape_html(finding.action.replace(/^Action:\s*/, ''))}</div>` : ''}
						${this.format_record_links(finding.item_code, finding.warehouse)}</td>
					<td class="ai-analyst-confidence">${Math.round(f.confidence * 100)}%</td>
				</tr>`;
			});
			html += `</tbody></table>`;

			if (data.evidence && data.evidence.length) {
				const evidence_id = 'ai-analyst-evidence-' + frappe.utils.get_random(8);
				html += `<a href="#" class="ai-analyst-toggle-evidence ai-analyst-evidence-toggle" data-target="${evidence_id}">&#9656; Evidence (${data.evidence.length})</a>`;
				html += `<div id="${evidence_id}" class="ai-analyst-evidence" style="display: none;">`;
				data.evidence.forEach((e) => {
					html += `<div class="ai-analyst-evidence-item">
						<strong>${frappe.utils.escape_html(e.source_tool)}</strong>:
						${frappe.utils.escape_html(e.summary)}
					</div>`;
				});
				html += `</div>`;
			}
		} else if (ranAnySkill) {
			html += `<div class="text-muted">${this.no_data_message(data.steps)}</div>`;
		} else if (data.category === 'conversational') {
			html += `<div class="text-muted">I'm a focused inventory analyst, not a general
				assistant. Ask me about stock levels, reorder needs, stockout risk, movement,
				valuation, batch expiry, purchase orders, sales commitments, or inventory health.</div>`;
		} else if (data.category === 'no_matching_skill') {
			html += `<div class="text-muted">That looks like a real business question, but it's
				outside what I can analyze right now. I currently support stock levels, demand,
				stockout risk, movement, valuation, expiry, purchase orders, sales commitments,
				and inventory health.</div>`;
		} else {
			// category missing/unrecognized — e.g. the planner hit a
			// decision_errors fail-safe before ever reaching a valid CONCLUDE.
			html += `<div class="text-muted">I wasn't able to process that question. Try
				rephrasing it, or ask about stock levels, reorder needs, stockout risk,
				movement, valuation, expiry, purchase orders, or sales commitments.</div>`;
		}

		if (data.decision_errors && data.decision_errors.length) {
			html += `<div class="text-muted" style="font-size: 11px; margin-top: 8px;">
				(This investigation hit ${data.decision_errors.length} internal decision issue(s) —
				see the full log for details.)
			</div>`;
		}

		html += this.format_follow_ups(data);

		if (data.log_name) {
			html += `<div style="margin-top: 6px;">
				<a href="/app/ai-investigation-log/${encodeURIComponent(data.log_name)}"
					target="_blank" style="font-size: 12px;">View full investigation log &rarr;</a>
			</div>`;
		}

		html += `</div></div>`;

		const $answer = $(html).appendTo(this.$messages);
		$answer.find('.ai-analyst-toggle-evidence').on('click', (e) => {
			e.preventDefault();
			$('#' + $(e.currentTarget).data('target')).slideToggle();
		});
		$answer.find('.ai-analyst-follow-up').on('click', (e) => {
			this.$input.val($(e.currentTarget).data('question')).focus();
		});
		$answer.find('.ai-analyst-export').on('click', () => {
			this.export_report_rows(data.report_records || [], data.report_source);
		});
		this.scroll_to_bottom();
	}

	scroll_to_bottom() {
		this.$messages.scrollTop(this.$messages[0].scrollHeight);
	}
}
