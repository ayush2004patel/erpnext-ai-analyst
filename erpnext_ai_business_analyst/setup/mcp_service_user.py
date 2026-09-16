"""
One-time setup: creates a dedicated, restricted Frappe user for the MCP
server to run as. Never grants System Manager or any write-capable role —
only read access to exactly the doctypes the current Tools actually need.

Run once via:
    bench --site <site> execute erpnext_ai_business_analyst.setup.mcp_service_user.create_mcp_service_user --args "['mcp-service@yoursite.local']"

Then point the server at it:
    bench --site <site> set-config mcp_service_user "mcp-service@yoursite.local"

Re-running is safe — the role's permission set is fully rebuilt each time
from each Tool's own REQUIRED_READ_DOCTYPES constant (single source of
truth, never duplicated here), so adding a new Tool later and re-running
this picks up its doctypes automatically. Creating the User is skipped if
it already exists; its role is always reset to exactly this one Role.
"""

from __future__ import annotations

import frappe

from erpnext_ai_business_analyst.tools.inventory.item_movement import (
    REQUIRED_READ_DOCTYPES as ITEM_MOVEMENT_DOCTYPES,
)
from erpnext_ai_business_analyst.tools.inventory.reorder import (
    REQUIRED_READ_DOCTYPES as REORDER_DOCTYPES,
)

ROLE_NAME = "MCP Service"


def _required_doctypes() -> list[str]:
    # Union, de-duplicated, order-independent (sorted for stable output) —
    # single source of truth is each Tool's own REQUIRED_READ_DOCTYPES.
    return sorted(set(REORDER_DOCTYPES) | set(ITEM_MOVEMENT_DOCTYPES))


def _ensure_role() -> None:
    if not frappe.db.exists("Role", ROLE_NAME):
        frappe.get_doc({"doctype": "Role", "role_name": ROLE_NAME}).insert(ignore_permissions=True)


def _ensure_read_permissions() -> None:
    # NOTE: frappe.permissions.add_permission's exact signature has shifted
    # across Frappe versions — verify this against your installed Frappe 16
    # if it errors, same as other Frappe-internals spots we've had to debug
    # against real error output earlier in this project.
    from frappe.permissions import add_permission, update_permission_property

    for doctype in _required_doctypes():
        existing = frappe.get_all(
            "Custom DocPerm", filters={"parent": doctype, "role": ROLE_NAME}, limit=1,
        )
        if not existing:
            add_permission(doctype, ROLE_NAME, permlevel=0)
        # add_permission grants read by default, but be explicit and strip
        # any write-capable flags in case a prior run left something set.
        for ptype, value in [
            ("read", 1), ("write", 0), ("create", 0), ("delete", 0),
            ("submit", 0), ("cancel", 0), ("amend", 0), ("report", 1),
            ("export", 0), ("print", 0), ("email", 0), ("share", 0),
        ]:
            update_permission_property(doctype, ROLE_NAME, 0, ptype, value)


def create_mcp_service_user(email: str) -> None:
    _ensure_role()
    _ensure_read_permissions()

    if frappe.db.exists("User", email):
        user = frappe.get_doc("User", email)
    else:
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": "MCP Service",
            "send_welcome_email": 0,
            "user_type": "System User",
        })
        user.insert(ignore_permissions=True)

    # Reset roles to exactly this one — never leave System Manager or any
    # other default role attached, whether newly created or pre-existing.
    user.set("roles", [])
    user.append("roles", {"role": ROLE_NAME})
    user.save(ignore_permissions=True)
    frappe.db.commit()

    print(f"Created/updated MCP service user: {email}")
    print(f"Granted role {ROLE_NAME!r} with read-only access to: {', '.join(_required_doctypes())}")
    print("Now run:")
    print(f'    bench --site <site> set-config mcp_service_user "{email}"')