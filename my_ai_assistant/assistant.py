"""
Assistant Orchestrator
Routes user queries → entity_service (intent) → data_service (data) → response
For well-known intents, returns a direct answer WITHOUT calling Gemini.
Gemini is only called for open-ended / analytical questions.
"""

import frappe
from frappe.utils import nowdate, fmt_money
from my_ai_assistant.services import data_service, entity_service, ai_service
from my_ai_assistant.services.doctype_service import discover_doctype


# ─── Intents that can be answered directly (no Gemini needed) ─────────────────

DIRECT_COUNT_INTENTS = {
    "count_customers":       ("Customer",        "customers"),
    "count_suppliers":       ("Supplier",        "suppliers"),
    "count_items":           ("Item",            "items / products"),
    "count_employees":       ("Employee",        "active employees"),
    "count_sales_invoices":  ("Sales Invoice",   "submitted sales invoices"),
    "count_orders":          None,   # special case — two doctypes
}

DIRECT_LIST_INTENTS = {
    "list_customers":         "Customer",
    "list_suppliers":         "Supplier",
    "list_items":             "Item",
    "list_employees":         "Employee",
    "list_leads":             "Lead",
    "list_orders":            "Sales Order",
    "list_purchase_orders":   "Purchase Order",
    "list_quotations":        "Quotation",
    "list_delivery_notes":    "Delivery Note",
    "list_warehouses":        "Warehouse",
    "list_accounts":          "Account",
    "list_sales_invoices":    "Sales Invoice",
    "list_purchase_invoices": "Purchase Invoice",
    "list_opportunities":     "Opportunity",
    "list_projects":          "Project",
    "list_tasks":             "Task",
}


def handle_query(prompt: str, session_history: list = None) -> dict:
    """
    Main entry point. Returns:
      { "response": str, "data": dict|list|None, "intent": str }
    """
    session_history = session_history or []

    intent = entity_service.extract_intent(prompt)
    period = entity_service.extract_period(prompt)
    limit  = entity_service.extract_limit(prompt, default=50)
    entity = entity_service.extract_entity_name(prompt)
    party  = entity_service.extract_party_name(prompt)

    data = _fetch_data(intent, period=period, limit=limit, entity=entity, party=party)

    # ── Direct count response (no Gemini) ─────────────────────────────────────
    if intent in DIRECT_COUNT_INTENTS:
        return _direct_count_response(intent, data, prompt)

    # ── Direct list response (no Gemini) ──────────────────────────────────────
    if intent in DIRECT_LIST_INTENTS and isinstance(data, list):
        doctype = DIRECT_LIST_INTENTS[intent]
        count   = len(data)
        return {
            "response": f"Found {count} {doctype}(s).",
            "data":     data,
            "intent":   intent,
        }

    # ── Revenue / financial summaries (direct, structured) ───────────────────
    if intent in ("revenue_this_month", "revenue_this_year", "revenue_last_month"):
        return _direct_revenue_response(intent, data, prompt)

    if intent == "overdue_invoices" and isinstance(data, list):
        return _direct_overdue_response(data, prompt)

    if intent == "outstanding_invoices" and isinstance(data, list):
        return _direct_outstanding_response(data, prompt)

    if intent == "top_customers" and isinstance(data, list):
        return _direct_top_customers_response(data, prompt)

    if intent == "top_items" and isinstance(data, list):
        return _direct_top_items_response(data, prompt)

    if intent == "stock_balance":
        return _direct_stock_response(data, prompt, entity)

    if intent == "low_stock" and isinstance(data, list):
        return _direct_low_stock_response(data, prompt)

    # ── Help / General ────────────────────────────────────────────────────────
    if intent == "unknown" and _is_help_query(prompt):
        return {"response": _help_text(), "data": None, "intent": "help"}

    # ── Business summary ──────────────────────────────────────────────────────
    if _is_summary_query(prompt):
        return _direct_summary_response(prompt)

    # ── Fallback: send to Gemini with context ────────────────────────────────
    today = nowdate()
    data_context = f"Today's date is {today}.\n\n" + _format_data_for_ai(intent, data, prompt)

    ai_response = ai_service.get_response(
        user_prompt=prompt,
        data_context=data_context,
        session_history=session_history,
    )

    return {
        "response": ai_response,
        "data":     data,
        "intent":   intent,
    }


# ─── Direct Response Builders ─────────────────────────────────────────────────

def _direct_count_response(intent: str, data, prompt: str) -> dict:
    """Build a crisp count response without calling Gemini."""

    if intent == "count_orders":
        so = data.get("sales_orders", 0) if isinstance(data, dict) else 0
        po = data.get("purchase_orders", 0) if isinstance(data, dict) else 0
        msg = (
            f"📦 <b>Order Summary</b><br><br>"
            f"🛒 Sales Orders: <b>{so:,}</b><br>"
            f"🏭 Purchase Orders: <b>{po:,}</b><br>"
            f"📊 Total Orders: <b>{so + po:,}</b>"
        )
        return {"response": msg, "data": data, "intent": intent}

    info = DIRECT_COUNT_INTENTS.get(intent)
    if not info:
        return {"response": "No data found.", "data": data, "intent": intent}

    doctype, label = info
    count = data.get("count", 0) if isinstance(data, dict) else 0

    # Pick the right emoji
    emoji_map = {
        "Customer":       "👥",
        "Supplier":       "🏢",
        "Item":           "📦",
        "Employee":       "👤",
        "Sales Invoice":  "🧾",
    }
    emoji = emoji_map.get(doctype, "📊")

    msg = f"{emoji} You have <b>{count:,}</b> {label} in your ERPNext."
    return {"response": msg, "data": data, "intent": intent}


def _direct_revenue_response(intent: str, data, prompt: str) -> dict:
    """Build a revenue summary response."""
    if not isinstance(data, dict) or not data:
        return {"response": "💰 No revenue data found for the selected period.", "data": data, "intent": intent}

    label_map = {
        "revenue_this_month": "This Month",
        "revenue_this_year":  "This Year",
        "revenue_last_month": "Last Month",
    }
    label = label_map.get(intent, "Period")

    total    = data.get("total_revenue") or 0
    count    = data.get("invoice_count") or 0
    avg      = data.get("avg_invoice_value") or 0
    pending  = data.get("total_outstanding") or 0

    def fmt(v):
        try:
            return f"₹{float(v):,.2f}"
        except Exception:
            return "₹0.00"

    msg = (
        f"💰 <b>Revenue — {label}</b><br><br>"
        f"🏦 Total Revenue: <b>{fmt(total)}</b><br>"
        f"🧾 Invoices Raised: <b>{int(count):,}</b><br>"
        f"📊 Avg Invoice Value: <b>{fmt(avg)}</b><br>"
        f"⏳ Outstanding Amount: <b>{fmt(pending)}</b>"
    )
    return {"response": msg, "data": data, "intent": intent}


def _direct_overdue_response(data: list, prompt: str) -> dict:
    if not data:
        return {"response": "✅ Great news! No overdue invoices found.", "data": data, "intent": "overdue_invoices"}

    total_overdue = sum(float(r.get("outstanding_amount") or 0) for r in data)
    count = len(data)
    msg = (
        f"🚨 <b>Overdue Invoices</b><br><br>"
        f"📋 Count: <b>{count:,}</b> overdue invoice(s)<br>"
        f"💸 Total Overdue: <b>₹{total_overdue:,.2f}</b><br><br>"
        f"<i>Showing top results — use the list below to review each invoice.</i>"
    )
    return {"response": msg, "data": data, "intent": "overdue_invoices"}


def _direct_outstanding_response(data: list, prompt: str) -> dict:
    if not data:
        return {"response": "✅ No outstanding invoices found.", "data": data, "intent": "outstanding_invoices"}
    total = sum(float(r.get("outstanding_amount") or 0) for r in data)
    msg = (
        f"⏳ <b>Outstanding Invoices</b><br><br>"
        f"📋 Count: <b>{len(data):,}</b><br>"
        f"💰 Total Outstanding: <b>₹{total:,.2f}</b>"
    )
    return {"response": msg, "data": data, "intent": "outstanding_invoices"}


def _direct_top_customers_response(data: list, prompt: str) -> dict:
    if not data:
        return {"response": "No customer sales data found.", "data": data, "intent": "top_customers"}
    lines = [f"🏆 <b>Top Customers by Revenue</b><br>"]
    for i, r in enumerate(data[:10], 1):
        name  = r.get("customer_name") or r.get("customer") or "—"
        rev   = float(r.get("total_revenue") or 0)
        lines.append(f"{i}. <b>{name}</b> — ₹{rev:,.2f}")
    return {"response": "<br>".join(lines), "data": data, "intent": "top_customers"}


def _direct_top_items_response(data: list, prompt: str) -> dict:
    if not data:
        return {"response": "No sales item data found.", "data": data, "intent": "top_items"}
    lines = [f"🛍️ <b>Top Selling Items</b><br>"]
    for i, r in enumerate(data[:10], 1):
        name = r.get("item_name") or r.get("item_code") or "—"
        amt  = float(r.get("total_amount") or 0)
        qty  = float(r.get("total_qty") or 0)
        lines.append(f"{i}. <b>{name}</b> — Qty: {qty:,.0f} | ₹{amt:,.2f}")
    return {"response": "<br>".join(lines), "data": data, "intent": "top_items"}


def _direct_stock_response(data, prompt: str, entity: str) -> dict:
    if not data:
        return {"response": f"No stock data found{' for ' + entity if entity else ''}.", "data": data, "intent": "stock_balance"}
    if isinstance(data, list):
        lines = ["📦 <b>Stock Balance</b><br>"]
        for r in data[:15]:
            item = r.get("item_code") or "—"
            wh   = r.get("warehouse") or "—"
            qty  = r.get("actual_qty") or 0
            lines.append(f"• <b>{item}</b> @ {wh}: <b>{qty}</b> units")
        return {"response": "<br>".join(lines), "data": data, "intent": "stock_balance"}
    return {"response": str(data), "data": data, "intent": "stock_balance"}


def _direct_low_stock_response(data: list, prompt: str) -> dict:
    if not data:
        return {"response": "✅ No items are below reorder level.", "data": data, "intent": "low_stock"}
    lines = [f"⚠️ <b>Low / Out-of-Stock Items ({len(data)})</b><br>"]
    for r in data[:15]:
        item = r.get("item_code") or r.get("item_name") or "—"
        qty  = r.get("actual_qty") or 0
        wh   = r.get("warehouse") or "—"
        lines.append(f"• <b>{item}</b> @ {wh}: <b>{qty}</b> units")
    return {"response": "<br>".join(lines), "data": data, "intent": "low_stock"}


def _direct_summary_response(prompt: str) -> dict:
    """Quick business dashboard summary — no Gemini needed."""
    try:
        customers  = data_service.get_doctype_count("Customer",         {"disabled": 0})
        suppliers  = data_service.get_doctype_count("Supplier",         {"disabled": 0})
        items      = data_service.get_doctype_count("Item",             {"disabled": 0})
        employees  = data_service.get_doctype_count("Employee",         {"status": "Active"})
        so         = data_service.get_doctype_count("Sales Order",      {"docstatus": 1})
        po         = data_service.get_doctype_count("Purchase Order",   {"docstatus": 1})
        si         = data_service.get_doctype_count("Sales Invoice",    {"docstatus": 1})
        revenue    = data_service.get_revenue_summary("this_month")
        overdue    = data_service.get_overdue_invoices(limit=500)
        total_rev  = float(revenue.get("total_revenue") or 0)

        msg = (
            f"📊 <b>Business Summary</b><br><br>"
            f"👥 Customers: <b>{customers:,}</b> &nbsp;|&nbsp; 🏢 Suppliers: <b>{suppliers:,}</b><br>"
            f"📦 Items: <b>{items:,}</b> &nbsp;|&nbsp; 👤 Employees: <b>{employees:,}</b><br><br>"
            f"🛒 Sales Orders: <b>{so:,}</b> &nbsp;|&nbsp; 🏭 Purchase Orders: <b>{po:,}</b><br>"
            f"🧾 Sales Invoices: <b>{si:,}</b><br><br>"
            f"💰 Revenue This Month: <b>₹{total_rev:,.2f}</b><br>"
            f"🚨 Overdue Invoices: <b>{len(overdue):,}</b>"
        )
        return {"response": msg, "data": None, "intent": "summary"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Summary Error")
        return {"response": f"Could not load summary: {str(e)}", "data": None, "intent": "summary"}


def _help_text() -> str:
    return (
        "🤖 <b>What can I help you with?</b><br><br>"
        "<b>📊 Counts:</b><br>"
        "• How many customers / suppliers / items / employees?<br>"
        "• How many sales invoices / orders?<br><br>"
        "<b>📋 Lists:</b><br>"
        "• List all customers / suppliers / items<br>"
        "• Show sales invoices / purchase orders<br>"
        "• List leads / opportunities / projects<br><br>"
        "<b>💰 Finance:</b><br>"
        "• Total revenue this month / year / last month<br>"
        "• Overdue invoices / outstanding invoices<br>"
        "• Top customers / top selling items<br><br>"
        "<b>📦 Stock:</b><br>"
        "• Stock balance / low stock items<br><br>"
        "<b>➕ Create Records:</b><br>"
        "• Create customer &lt;name&gt;<br>"
        "• Create supplier &lt;name&gt;<br>"
        "• Create item &lt;name&gt;<br><br>"
        "<b>📸 Document Scan:</b><br>"
        "• Click 🖼 to upload a bill/invoice image for auto-entry"
    )


# ─── Data Fetcher ──────────────────────────────────────────────────────────────

def _fetch_data(intent, *, period, limit, entity, party):
    """Route intent to the correct data_service function."""

    # ── Counts ─────────────────────────────────────────────────────────────
    if intent == "count_customers":
        return {"count": data_service.get_doctype_count("Customer", {"disabled": 0})}
    if intent == "count_suppliers":
        return {"count": data_service.get_doctype_count("Supplier", {"disabled": 0})}
    if intent == "count_items":
        return {"count": data_service.get_doctype_count("Item", {"disabled": 0})}
    if intent == "count_employees":
        return {"count": data_service.get_doctype_count("Employee", {"status": "Active"})}
    if intent == "count_sales_invoices":
        return {"count": data_service.get_doctype_count("Sales Invoice", {"docstatus": 1})}
    if intent == "count_orders":
        return {
            "sales_orders":   data_service.get_doctype_count("Sales Order",    {"docstatus": 1}),
            "purchase_orders": data_service.get_doctype_count("Purchase Order", {"docstatus": 1}),
        }

    # ── Lists ──────────────────────────────────────────────────────────────
    if intent == "list_customers":
        return data_service.get_all_customers(limit=limit)
    if intent == "list_suppliers":
        return data_service.get_all_suppliers(limit=limit)
    if intent == "list_items":
        return data_service.get_all_items(limit=limit)
    if intent == "list_employees":
        return data_service.get_all_employees(limit=limit)
    if intent == "list_leads":
        return data_service.get_leads(limit=limit)
    if intent == "list_orders":
        filters = {}
        if party:
            filters["customer"] = ["like", f"%{party}%"]
        return data_service.get_sales_orders(filters=filters, limit=limit)
    if intent == "list_purchase_orders":
        filters = {}
        if party:
            filters["supplier"] = ["like", f"%{party}%"]
        return data_service.get_purchase_orders(filters=filters, limit=limit)
    if intent == "list_quotations":
        return data_service.get_quotations(limit=limit)
    if intent == "list_delivery_notes":
        return data_service.get_delivery_notes(limit=limit)
    if intent == "list_warehouses":
        return data_service.get_warehouses()
    if intent == "list_accounts":
        return data_service.get_accounts(limit=limit)
    if intent == "list_sales_invoices":
        filters = {}
        if party:
            filters["customer"] = ["like", f"%{party}%"]
        return data_service.get_sales_invoices(filters=filters, limit=limit)
    if intent == "list_purchase_invoices":
        filters = {}
        if party:
            filters["supplier"] = ["like", f"%{party}%"]
        return data_service.get_purchase_invoices(filters=filters, limit=limit)

    # ── Invoices ───────────────────────────────────────────────────────────
    if intent == "overdue_invoices":
        party_type = "Supplier" if _mentions_supplier_in_prompt(intent) else "Customer"
        return data_service.get_overdue_invoices(party_type=party_type, limit=limit)
    if intent == "outstanding_invoices":
        return data_service.get_outstanding_invoices(party_type="Customer", party=party, limit=limit)

    # ── Financial ──────────────────────────────────────────────────────────
    if intent == "revenue_this_month":
        return data_service.get_revenue_summary(period="this_month")
    if intent == "revenue_this_year":
        return data_service.get_revenue_summary(period="this_year")
    if intent == "revenue_last_month":
        return data_service.get_revenue_summary(period="last_month")
    if intent == "purchase_summary":
        return data_service.get_purchase_summary(period=period)
    if intent == "top_customers":
        return data_service.get_top_customers(limit=limit, period=period)
    if intent == "top_suppliers":
        return data_service.get_top_suppliers(limit=limit, period=period)
    if intent == "top_items":
        return data_service.get_top_selling_items(limit=limit, period=period)

    # ── Stock ──────────────────────────────────────────────────────────────
    if intent == "stock_balance":
        if entity:
            return data_service.get_stock_balance(item_code=entity)
        return data_service.get_stock_balance()
    if intent == "low_stock":
        return data_service.get_items_below_reorder(limit=limit)
    if intent == "stock_movement":
        if entity:
            return data_service.get_stock_ledger(entity, limit=20)
        return {"error": "Please specify an item code for stock movement."}

    # ── HR ─────────────────────────────────────────────────────────────────
    if intent == "salary_slips":
        return data_service.get_salary_slips(limit=limit)
    if intent == "leave_applications":
        return data_service.get_leave_applications(limit=limit)

    # ── CRM / Projects ─────────────────────────────────────────────────────
    if intent == "list_opportunities":
        return data_service.get_opportunities(limit=limit)
    if intent == "list_projects":
        return data_service.get_projects(limit=limit)
    if intent == "list_tasks":
        return data_service.get_tasks(limit=limit)
    if intent == "payment_entries":
        return data_service.get_payment_entries(limit=limit)

    # ── Single Document Lookup ─────────────────────────────────────────────
    if entity:
        doctype = _guess_doctype_from_name(entity)
        if doctype:
            doc = data_service.get_document(doctype, entity)
            return doc or {"error": f"Document {entity} not found."}

    # ── Dynamic / Unknown Doctype ──────────────────────────────────────────
    discovered = discover_doctype(entity or "")  # avoid passing full prompt to avoid false matches
    if discovered:
        return data_service.get_doctype_list(discovered, limit=limit)

    return None


# ─── Format helpers ────────────────────────────────────────────────────────────

def _format_data_for_ai(intent: str, data, prompt: str) -> str:
    """
    Convert fetched data into a readable string for Gemini.
    Includes intent label so the model understands the context.
    """
    intent_label = intent.replace("_", " ").title() if intent else "General query"

    if data is None:
        return f"Query type: {intent_label}\nNo relevant data was retrieved from ERPNext."

    if isinstance(data, dict):
        if "error" in data:
            return f"Query type: {intent_label}\nError: {data['error']}"
        lines = [f"Query type: {intent_label}", "Data from ERPNext:"]
        for k, v in data.items():
            if v is not None:
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    if isinstance(data, list):
        if not data:
            return f"Query type: {intent_label}\nNo records found in ERPNext."
        count  = len(data)
        sample = data[:20]
        rows   = []
        for rec in sample:
            if isinstance(rec, dict):
                row = ", ".join(f"{k}={v}" for k, v in rec.items() if v is not None)
            else:
                row = str(rec)
            rows.append(row)
        return (
            f"Query type: {intent_label}\n"
            f"Found {count} record(s) in ERPNext:\n" +
            "\n".join(rows)
        )

    return f"Query type: {intent_label}\nData: {str(data)}"


def _is_help_query(prompt: str) -> bool:
    p = prompt.lower()
    return any(w in p for w in ["help", "what can you do", "what can i ask", "commands", "features"])


def _is_summary_query(prompt: str) -> bool:
    p = prompt.lower()
    return any(w in p for w in ["business summary", "dashboard", "overview", "summary"])


def _mentions_supplier_in_prompt(query: str) -> bool:
    return "supplier" in query.lower() or "purchase" in query.lower()


def _guess_doctype_from_name(name: str) -> str | None:
    """Guess doctype from document ID prefix."""
    prefix_map = {
        "SINV": "Sales Invoice",
        "PINV": "Purchase Invoice",
        "SO":   "Sales Order",
        "PO":   "Purchase Order",
        "DN":   "Delivery Note",
        "PR":   "Purchase Receipt",
        "JV":   "Journal Entry",
        "PE":   "Payment Entry",
        "QTN":  "Quotation",
        "SAL":  "Salary Slip",
        "EMP":  "Employee",
    }
    prefix = name.split("-")[0].upper()
    return prefix_map.get(prefix)