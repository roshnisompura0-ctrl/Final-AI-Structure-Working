"""
Safe Data Retrieval Service
Handles all database queries with safety checks and limits
"""

import frappe

def safe_get_list(doctype, fields=None, filters=None, limit=500, order_by="modified desc"):
    """
    Safely get list of documents with error handling
    """
    try:
        if not fields:
            fields = ["name"]

        return frappe.get_all(
            doctype,
            fields=fields,
            filters=filters or {},
            limit=limit,
            ignore_permissions=True,
            order_by=order_by
        )
    except Exception as e:
        frappe.log_error(f"safe_get_list error for {doctype}: {str(e)}")
        return []

def safe_get_full_doc(doctype, doc_name):
    """
    Safely get full document with child tables
    """
    try:
        doc = frappe.get_doc(doctype, doc_name)
        data = doc.as_dict()

        # Include child table data
        for field in doc.meta.get_table_fields():
            if hasattr(doc, field.fieldname):
                items = getattr(doc, field.fieldname)
                data[field.fieldname] = [item.as_dict() for item in items]

        return data
    except Exception as e:
        return {"error": str(e), "doctype": doctype, "name": doc_name}

def safe_count(doctype, filters=None):
    """Safely get count with error handling"""
    try:
        return frappe.db.count(doctype, filters=filters or {})
    except:
        return 0

def get_entity_statistics(entity_type, entity_id):
    """
    Get comprehensive statistics for an entity
    Customer, Supplier, Item, Employee
    """
    stats = {}
    today = frappe.utils.today()
    month_start = str(frappe.utils.get_first_day(today))

    try:
        if entity_type == "Customer":
            # Sales Invoices
            sinv = safe_get_list("Sales Invoice",
                ["name", "status", "posting_date", "grand_total", "outstanding_amount", "docstatus"],
                {"customer": entity_id}, limit=1000)
            submitted = [i for i in sinv if str(i.get("docstatus")) == "1"]

            stats["total_invoices"] = len(sinv)
            stats["submitted_invoices"] = len(submitted)
            stats["total_revenue"] = sum(float(i.get("grand_total", 0)) for i in submitted)
            stats["outstanding_amount"] = sum(float(i.get("outstanding_amount", 0)) for i in submitted)
            stats["paid_count"] = len([i for i in sinv if i.get("status") == "Paid"])
            stats["overdue_count"] = len([i for i in sinv if i.get("status") == "Overdue"])

            # Sales Orders
            so = safe_get_list("Sales Order",
                ["name", "status", "transaction_date", "grand_total"],
                {"customer": entity_id}, limit=500)
            stats["total_orders"] = len(so)

            # Payments
            payments = safe_get_list("Payment Entry",
                ["name", "paid_amount", "posting_date"],
                {"party": entity_id, "party_type": "Customer"}, limit=300)
            stats["total_payments"] = len(payments)
            stats["total_paid"] = sum(float(p.get("paid_amount", 0)) for p in payments)

        elif entity_type == "Supplier":
            # Purchase Invoices
            pinv = safe_get_list("Purchase Invoice",
                ["name", "status", "posting_date", "grand_total", "outstanding_amount", "docstatus"],
                {"supplier": entity_id}, limit=1000)
            submitted = [i for i in pinv if str(i.get("docstatus")) == "1"]

            stats["total_invoices"] = len(pinv)
            stats["total_purchases"] = sum(float(i.get("grand_total", 0)) for i in submitted)
            stats["outstanding_amount"] = sum(float(i.get("outstanding_amount", 0)) for i in submitted)

            # Purchase Orders
            po = safe_get_list("Purchase Order",
                ["name", "status", "transaction_date", "grand_total"],
                {"supplier": entity_id}, limit=500)
            stats["total_orders"] = len(po)

        elif entity_type == "Item":
            # Sales history
            sinv_items = frappe.db.sql("""
                SELECT sii.qty, sii.rate, sii.amount, si.posting_date
                FROM `tabSales Invoice Item` sii
                JOIN `tabSales Invoice` si ON si.name = sii.parent
                WHERE sii.item_code = %s AND si.docstatus = 1
                ORDER BY si.posting_date DESC LIMIT 200
            """, entity_id, as_dict=True)

            stats["total_sold_qty"] = sum(float(r.get("qty", 0)) for r in sinv_items)
            stats["total_revenue"] = sum(float(r.get("amount", 0)) for r in sinv_items)

            # Current stock
            stock = frappe.db.sql("""
                SELECT warehouse, actual_qty, valuation_rate
                FROM `tabBin` WHERE item_code = %s
            """, entity_id, as_dict=True)
            stats["stock_by_warehouse"] = stock
            stats["total_stock"] = sum(float(r.get("actual_qty", 0)) for r in stock)

        elif entity_type == "Employee":
            # Attendance
            attendance = safe_get_list("Attendance",
                ["name", "attendance_date", "status"],
                {"employee": entity_id}, limit=200)
            stats["total_attendance_records"] = len(attendance)
            stats["present_days"] = len([a for a in attendance if a.get("status") == "Present"])
            stats["absent_days"] = len([a for a in attendance if a.get("status") == "Absent"])

            # Salary
            salary_slips = safe_get_list("Salary Slip",
                ["name", "start_date", "end_date", "net_pay", "status"],
                {"employee": entity_id}, limit=24)
            stats["salary_slips"] = salary_slips
            submitted_slips = [s for s in salary_slips if s.get("status") == "Submitted"]
            stats["latest_net_pay"] = submitted_slips[0].get("net_pay") if submitted_slips else None

            # Leaves
            leaves = safe_get_list("Leave Application",
                ["name", "leave_type", "from_date", "to_date", "total_leave_days", "status"],
                {"employee": entity_id}, limit=50)
            stats["leave_applications"] = leaves

    except Exception as e:
        frappe.log_error(f"Entity stats error for {entity_type} {entity_id}: {str(e)}")

    return stats

def get_business_overview():
    """Get complete business summary statistics"""
    today = frappe.utils.today()
    month_start = str(frappe.utils.get_first_day(today))
    year_start = today[:4] + "-01-01"

    overview = {}

    # Master data counts
    overview["customers"] = safe_count("Customer")
    overview["suppliers"] = safe_count("Supplier")
    overview["items"] = safe_count("Item")
    overview["employees"] = safe_count("Employee")
    overview["leads"] = safe_count("Lead")

    # Sales data
    sinv = safe_get_list("Sales Invoice",
        ["grand_total", "outstanding_amount", "docstatus", "status", "posting_date"],
        limit=2000)
    submitted_sinv = [i for i in sinv if str(i.get("docstatus")) == "1"]

    overview["total_sales_invoices"] = len(sinv)
    overview["total_revenue"] = sum(float(i.get("grand_total", 0)) for i in submitted_sinv)
    overview["revenue_this_month"] = sum(
        float(i.get("grand_total", 0)) for i in submitted_sinv
        if str(i.get("posting_date", "")) >= month_start
    )
    overview["total_outstanding"] = sum(float(i.get("outstanding_amount", 0)) for i in submitted_sinv)
    overview["overdue_invoices"] = len([i for i in sinv if i.get("status") == "Overdue"])
    overview["paid_invoices"] = len([i for i in sinv if i.get("status") == "Paid"])

    # Purchase data
    pinv = safe_get_list("Purchase Invoice",
        ["grand_total", "outstanding_amount", "docstatus"],
        limit=2000)
    submitted_pinv = [i for i in pinv if str(i.get("docstatus")) == "1"]

    overview["total_purchase_invoices"] = len(pinv)
    overview["total_purchases"] = sum(float(i.get("grand_total", 0)) for i in submitted_pinv)
    overview["total_payable"] = sum(float(i.get("outstanding_amount", 0)) for i in submitted_pinv)

    # Orders
    overview["sales_orders"] = safe_count("Sales Order")
    overview["purchase_orders"] = safe_count("Purchase Order")
    overview["quotations"] = safe_count("Quotation")

    return overview


# Legacy function aliases for assistant.py compatibility
def get_doctype_count(doctype, filters=None):
    """Get count of documents for a doctype"""
    return safe_count(doctype, filters)

def get_document(doctype, name):
    """Get a single document by name"""
    return safe_get_full_doc(doctype, name)

def get_doctype_list(doctype, limit=50):
    """Get list of documents for a doctype"""
    return safe_get_list(doctype, limit=limit)

# === All legacy functions for assistant.py compatibility ===

def get_all_customers(limit=50):
    return safe_get_list("Customer", ["name", "customer_name"], {"disabled": 0}, limit)

def get_all_suppliers(limit=50):
    return safe_get_list("Supplier", ["name", "supplier_name"], {"disabled": 0}, limit)

def get_all_items(limit=50):
    return safe_get_list("Item", ["name", "item_name", "item_group"], {"disabled": 0}, limit)

def get_all_employees(limit=50):
    return safe_get_list("Employee", ["name", "employee_name"], {"status": "Active"}, limit)

def get_leads(limit=50):
    return safe_get_list("Lead", ["name", "lead_name", "status"], limit=limit)

def get_sales_orders(filters=None, limit=50):
    return safe_get_list("Sales Order", ["name", "customer", "transaction_date", "status", "grand_total"], filters, limit)

def get_purchase_orders(filters=None, limit=50):
    return safe_get_list("Purchase Order", ["name", "supplier", "transaction_date", "status", "grand_total"], filters, limit)

def get_quotations(limit=50):
    return safe_get_list("Quotation", ["name", "customer", "transaction_date", "status", "grand_total"], limit=limit)

def get_delivery_notes(limit=50):
    return safe_get_list("Delivery Note", ["name", "customer", "posting_date", "status"], limit=limit)

def get_warehouses():
    return safe_get_list("Warehouse", ["name", "warehouse_name", "is_group"])

def get_accounts(limit=100):
    return safe_get_list("Account", ["name", "account_name", "account_type", "root_type"], limit=limit)

def get_sales_invoices(filters=None, limit=50):
    return safe_get_list("Sales Invoice", ["name", "customer", "posting_date", "status", "grand_total", "outstanding_amount"], filters, limit)

def get_purchase_invoices(filters=None, limit=50):
    return safe_get_list("Purchase Invoice", ["name", "supplier", "posting_date", "status", "grand_total", "outstanding_amount"], filters, limit)

def get_overdue_invoices(party_type="Customer", limit=50):
    invoices = safe_get_list("Sales Invoice" if party_type == "Customer" else "Purchase Invoice",
        ["name", "customer" if party_type == "Customer" else "supplier", "posting_date", "due_date", "outstanding_amount"],
        {"status": "Overdue", "docstatus": 1}, limit)
    return invoices

def get_outstanding_invoices(party_type="Customer", party=None, limit=50):
    filters = {"docstatus": 1, "outstanding_amount": [">", 0]}
    if party:
        filters["customer" if party_type == "Customer" else "supplier"] = ["like", f"%{party}%"]
    doctype = "Sales Invoice" if party_type == "Customer" else "Purchase Invoice"
    return safe_get_list(doctype, ["name", "customer" if party_type == "Customer" else "supplier", "posting_date", "outstanding_amount"], filters, limit)

def get_revenue_summary(period="this_month"):
    from frappe.utils import today, get_first_day, get_last_day
    t = today()
    if period == "this_month":
        start = get_first_day(t)
        end = get_last_day(t)
    elif period == "last_month":
        from frappe.utils import add_months
        last_month = add_months(t, -1)
        start = get_first_day(last_month)
        end = get_last_day(last_month)
    elif period == "this_year":
        start = t[:4] + "-01-01"
        end = t[:4] + "-12-31"
    else:
        start = get_first_day(t)
        end = get_last_day(t)
    invoices = safe_get_list("Sales Invoice", ["grand_total", "outstanding_amount"], {"docstatus": 1, "posting_date": ["between", [start, end]]}, 10000)
    total = sum(float(i.get("grand_total", 0)) for i in invoices)
    outstanding = sum(float(i.get("outstanding_amount", 0)) for i in invoices)
    return {
        "total_revenue": total,
        "invoice_count": len(invoices),
        "avg_invoice_value": total / len(invoices) if invoices else 0,
        "total_outstanding": outstanding
    }

def get_purchase_summary(period="this_month"):
    return {"total_purchases": 0, "message": "Not implemented"}

def get_top_customers(limit=10, period=None):
    from frappe.utils import today, get_first_day, add_months
    t = today()
    if period == "last_month":
        start = get_first_day(add_months(t, -1))
    else:
        start = get_first_day(t)
    data = frappe.db.sql("""
        SELECT customer, SUM(grand_total) as total_revenue, COUNT(*) as invoice_count
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND posting_date >= %s
        GROUP BY customer
        ORDER BY total_revenue DESC
        LIMIT %s
    """, (start, limit), as_dict=True)
    for d in data:
        d["customer_name"] = frappe.db.get_value("Customer", d["customer"], "customer_name")
    return data

def get_top_suppliers(limit=10, period=None):
    return []

def get_top_selling_items(limit=10, period=None):
    from frappe.utils import today, get_first_day, add_months
    t = today()
    if period == "last_month":
        start = get_first_day(add_months(t, -1))
    else:
        start = get_first_day(t)
    data = frappe.db.sql("""
        SELECT item_code, SUM(amount) as total_amount, SUM(qty) as total_qty
        FROM `tabSales Invoice Item`
        WHERE parent IN (SELECT name FROM `tabSales Invoice` WHERE docstatus = 1 AND posting_date >= %s)
        GROUP BY item_code
        ORDER BY total_amount DESC
        LIMIT %s
    """, (start, limit), as_dict=True)
    for d in data:
        d["item_name"] = frappe.db.get_value("Item", d["item_code"], "item_name")
    return data

def get_stock_balance(item_code=None, limit=100):
    if item_code:
        return frappe.db.sql("""
            SELECT item_code, warehouse, actual_qty, reserved_qty, projected_qty
            FROM `tabBin` WHERE item_code = %s
        """, item_code, as_dict=True)
    return safe_get_list("Bin", ["item_code", "warehouse", "actual_qty", "reserved_qty", "projected_qty"], limit=limit)

def get_items_below_reorder(limit=50):
    return frappe.db.sql("""
        SELECT i.name as item_code, i.item_name, i.re_order_level,
               SUM(b.actual_qty) as actual_qty
        FROM `tabItem` i
        LEFT JOIN `tabBin` b ON i.name = b.item_code
        WHERE i.re_order_level > 0
        GROUP BY i.name
        HAVING actual_qty < i.re_order_level OR actual_qty IS NULL
        LIMIT %s
    """, limit, as_dict=True)

def get_stock_ledger(item_code, limit=20):
    return frappe.db.sql("""
        SELECT posting_date, warehouse, actual_qty, valuation_rate, stock_value
        FROM `tabStock Ledger Entry`
        WHERE item_code = %s
        ORDER BY posting_date DESC
        LIMIT %s
    """, (item_code, limit), as_dict=True)

def get_salary_slips(limit=50):
    return safe_get_list("Salary Slip", ["name", "employee", "employee_name", "start_date", "end_date", "net_pay", "status"], limit=limit)

def get_leave_applications(limit=50):
    return safe_get_list("Leave Application", ["name", "employee", "employee_name", "leave_type", "from_date", "to_date", "status"], limit=limit)

def get_opportunities(limit=50):
    return safe_get_list("Opportunity", ["name", "customer_name", "opportunity_type", "status", "expected_closing"], limit=limit)

def get_projects(limit=50):
    return safe_get_list("Project", ["name", "project_name", "status", "expected_start_date", "expected_end_date"], limit=limit)

def get_tasks(limit=50):
    return safe_get_list("Task", ["name", "subject", "project", "status", "priority", "exp_start_date"], limit=limit)

def get_payment_entries(limit=50):
    return safe_get_list("Payment Entry", ["name", "party_type", "party", "posting_date", "paid_amount", "status"], limit=limit)
