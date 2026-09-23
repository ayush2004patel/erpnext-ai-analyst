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
					.ai-analyst-confidence { position: absolute; top: 12px; right: 12px; padding: 3px 8px !important; background: #e7f7ed; color: #227a45; border-radius: 999px; font-size: 12px; font-weight: 600; }
					.ai-analyst-evidence-toggle { display: inline-block; margin-top: 13px; color: var(--primary, #2490ef); font-size: 13px; font-weight: 600; }
					.ai-analyst-evidence { margin-top: 8px; padding: 12px; background: #f8fafc; border-radius: 8px; font-size: 12px; }
					.ai-analyst-evidence-item { border-left: 3px solid #b8c7d9; padding-left: 10px; margin-bottom: 9px; line-height: 1.45; }
					.ai-analyst-evidence-item:last-child { margin-bottom: 0; }
					.ai-analyst-input { display: flex; gap: 10px; margin-top: 14px; }
					.ai-analyst-input .form-control { min-height: 42px; border-radius: 9px; }
					.ai-analyst-input .btn { min-width: 82px; border-radius: 9px; }
					.ai-analyst-error { display: inline-block; margin-bottom: 15px; padding: 10px 14px; background: #fff0ee; color: #9b2c2c; border: 1px solid #fecaca; border-radius: 10px; }
					@media (max-width: 576px) { .ai-analyst-messages { padding: 13px; } .ai-analyst-user-bubble, .ai-analyst-answer { max-width: 100%; } .ai-analyst-input { align-items: stretch; flex-direction: column; } }
				</style>
				<div class="ai-analyst-messages"></div>
				<div class="ai-analyst-input">
					<input type="text" class="form-control ai-analyst-question"
						placeholder="e.g. Which inventory has not moved for 90 days?">
					<button class="btn btn-primary ai-analyst-ask">Ask</button>
				</div>
			</div>
		`).appendTo(this.page.main);

		this.$messages = this.$container.find('.ai-analyst-messages');
		this.$input = this.$container.find('.ai-analyst-question');
		this.$button = this.$container.find('.ai-analyst-ask');

		this.$button.on('click', () => this.ask());
		this.$input.on('keypress', (e) => {
			if (e.which === 13) this.ask();
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
			args: { question },
			callback: (r) => {
				this.$button.prop('disabled', false).text('Ask');
				if (r.message) {
					this.add_answer(r.message);
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
			};
		}

		const overstock = finding_text.match(/^(.+?) \((.+?)\) at (.+?): stock ([\d.]+) is ([\d.]+)x its ROL \(([^)]+)\) — (.+?)\. \((.+?)\)$/);
		if (overstock) {
			const [, item_code, item_name, warehouse, quantity, multiple, reorder_level, severity, consumption] = overstock;
			return {
				title: 'Overstock',
				summary: `${escape(item_name)} has ${escape(quantity)} units at ${escape(warehouse)}.`,
				detail: `${escape(multiple)}× above the recommended reorder level of ${escape(reorder_level)} units — ${escape(severity)}; ${escape(consumption)}. Item code: ${escape(item_code)}.`,
			};
		}

		const labels = {
			'inventory.dead_stock': 'Dead stock',
			'inventory.overstock': 'Overstock',
			'inventory.slow_moving_stock': 'Slow-moving stock',
		};
		return {
			title: labels[skill_name] || 'Inventory finding',
			summary: escape(finding_text.replace(/\bROL\b/g, 'recommended reorder level')),
			detail: '',
		};
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

		if (ranAnySkill && data.findings && data.findings.length > 0) {
			html += `<table class="table ai-analyst-findings">
				<thead><tr><th>Finding</th><th style="width: 90px;">Confidence</th></tr></thead>
				<tbody>`;
			data.findings.forEach((f) => {
				const finding = this.format_finding(f.claim);
				html += `<tr>
					<td><div class="ai-analyst-finding-title">${finding.title}</div>
						<div class="ai-analyst-finding-summary">${finding.summary}</div>
						${finding.detail ? `<div class="ai-analyst-finding-detail">${finding.detail}</div>` : ''}</td>
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
			// A Skill ran and genuinely found nothing — distinct from never
			// having run one at all.
			html += `<div class="text-muted">Checked — no issues found for that question.</div>`;
		} else if (data.category === 'conversational') {
			html += `<div class="text-muted">I'm a focused inventory analyst, not a general
				assistant. Ask me about reorder levels, stockout risk, dead stock, slow-moving
				stock, overstock, or inventory concentration.</div>`;
		} else if (data.category === 'no_matching_skill') {
			html += `<div class="text-muted">That looks like a real business question, but it's
				outside what I can analyze right now. I currently support: reorder/demand,
				stockout risk, dead stock, slow-moving stock, overstock, and inventory
				concentration.</div>`;
		} else {
			// category missing/unrecognized — e.g. the planner hit a
			// decision_errors fail-safe before ever reaching a valid CONCLUDE.
			html += `<div class="text-muted">I wasn't able to process that question. Try
				rephrasing it, or ask about reorder levels, stockout risk, dead stock,
				slow-moving stock, overstock, or inventory concentration.</div>`;
		}

		if (data.decision_errors && data.decision_errors.length) {
			html += `<div class="text-muted" style="font-size: 11px; margin-top: 8px;">
				(This investigation hit ${data.decision_errors.length} internal decision issue(s) —
				see the full log for details.)
			</div>`;
		}

		if (data.log_name) {
			html += `<div style="margin-top: 6px;">
				<a href="/app/ai-investigation-log/${encodeURIComponent(data.log_name)}"
					target="_blank" style="font-size: 12px;">View full investigation log &rarr;</a>
			</div>`;
		}

		html += `</div></div>`;

		this.$messages.append(html);
		this.$messages.find('.ai-analyst-toggle-evidence').last().on('click', (e) => {
			e.preventDefault();
			$('#' + $(e.currentTarget).data('target')).slideToggle();
		});
		this.scroll_to_bottom();
	}

	scroll_to_bottom() {
		this.$messages.scrollTop(this.$messages[0].scrollHeight);
	}
}
