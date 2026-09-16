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
				<div class="ai-analyst-messages" style="max-height: 65vh; overflow-y: auto; padding: 10px 4px;"></div>
				<div class="ai-analyst-input" style="display: flex; gap: 8px; margin-top: 10px;">
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
			<div class="text-right" style="margin-bottom: 10px;">
				<div style="display: inline-block; background: #e3f2fd; padding: 8px 12px;
					border-radius: 8px; max-width: 80%; text-align: left;">
					${frappe.utils.escape_html(text)}
				</div>
			</div>
		`);
		this.scroll_to_bottom();
	}

	add_error(text) {
		this.$messages.append(`
			<div class="text-left" style="margin-bottom: 15px;">
				<div style="display: inline-block; background: #fdecea; color: #611a15;
					padding: 8px 12px; border-radius: 8px; max-width: 80%;">
					${frappe.utils.escape_html(text)}
				</div>
			</div>
		`);
		this.scroll_to_bottom();
	}

	add_answer(data) {
		let html = `<div class="ai-analyst-answer" style="margin-bottom: 18px; max-width: 90%;">`;

		const ranAnySkill = data.steps && data.steps.length > 0;

		if (ranAnySkill) {
			const trail = data.steps.map((s) => frappe.utils.escape_html(s.skill_name)).join(' &rarr; ');
			html += `<div style="font-size: 12px; color: #888; margin-bottom: 8px;">
				Investigated: ${trail}
			</div>`;
		}

		if (ranAnySkill && data.findings && data.findings.length > 0) {
			html += `<table class="table table-bordered" style="margin-bottom: 8px;">
				<thead><tr><th>Finding</th><th style="width: 90px;">Confidence</th></tr></thead>
				<tbody>`;
			data.findings.forEach((f) => {
				html += `<tr>
					<td>${frappe.utils.escape_html(f.claim)}</td>
					<td>${Math.round(f.confidence * 100)}%</td>
				</tr>`;
			});
			html += `</tbody></table>`;

			if (data.evidence && data.evidence.length) {
				const evidence_id = 'ai-analyst-evidence-' + frappe.utils.get_random(8);
				html += `<a href="#" class="ai-analyst-toggle-evidence" data-target="${evidence_id}"
					style="font-size: 12px;">&#9656; Evidence (${data.evidence.length})</a>`;
				html += `<div id="${evidence_id}" style="display: none; margin-top: 6px; font-size: 12px;">`;
				data.evidence.forEach((e) => {
					html += `<div style="border-left: 2px solid #ddd; padding-left: 8px; margin-bottom: 6px;">
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

		html += `</div>`;

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