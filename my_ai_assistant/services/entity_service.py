"""
Entity Extraction Service
Smart entity detection with fuzzy matching and similarity scoring
"""

import frappe
from difflib import SequenceMatcher

def similarity(a, b):
    """Calculate string similarity ratio"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def extract_entities_from_question(question, entity_types=None):
    """
    Extract entity mentions from user question using fuzzy matching
    Returns dict with detected entities and their ERPNext IDs
    """
    q_lower = question.lower()
    result = {}

    types_to_check = entity_types or ["Customer", "Supplier", "Item", "Employee", "Lead"]

    for entity_type in types_to_check:
        entity_id = find_entity_mention(question, entity_type)
        if entity_id:
            result[entity_type.lower()] = entity_id
            # Also get display name
            result[f"{entity_type.lower()}_display"] = get_display_name(entity_type, entity_id)

    return result

def find_entity_mention(question, doctype):
    """
    Find if a doctype name is mentioned in the question
    Uses fuzzy matching with threshold
    """
    try:
        # Get all entity names
        entities = get_all_entity_names(doctype, limit=2000)

        best_match = None
        best_score = 0.65  # Minimum threshold

        for entity in entities:
            name = entity.get("name", "").strip()
            display = entity.get("display", name).strip()

            # Skip empty names
            if not name or len(name) < 2:
                continue

            # Check exact match first
            if name.lower() in question.lower():
                return name
            if display.lower() in question.lower():
                return name

            # Check similarity for display name
            if display and len(display) > 2:
                score = similarity(display, question)
                if score > best_score:
                    best_score = score
                    best_match = name

            # Check similarity for actual name
            if len(name) > 2:
                score = similarity(name, question)
                if score > best_score:
                    best_score = score
                    best_match = name

        return best_match
    except Exception as e:
        frappe.log_error(f"Find entity mention error for {doctype}: {str(e)}")
        return None

def get_all_entity_names(doctype, limit=2000):
    """Get all names for a doctype with display names"""
    try:
        # Map doctype to its display field
        display_field_map = {
            "Customer": "customer_name",
            "Supplier": "supplier_name",
            "Item": "item_name",
            "Employee": "employee_name",
            "Lead": "lead_name"
        }

        display_field = display_field_map.get(doctype, "name")

        fields = ["name", f"{display_field} as display"]
        return frappe.get_all(doctype, fields=fields, limit=limit, ignore_permissions=True)
    except Exception as e:
        return []

def get_display_name(doctype, name):
    """Get display name for an entity"""
    try:
        display_field_map = {
            "Customer": "customer_name",
            "Supplier": "supplier_name",
            "Item": "item_name",
            "Employee": "employee_name",
            "Lead": "lead_name"
        }

        display_field = display_field_map.get(doctype)
        if display_field:
            display = frappe.db.get_value(doctype, name, display_field)
            return display or name
        return name
    except:
        return name


# Legacy Intent Extraction (for assistant.py compatibility)
import re

def extract_intent(query: str) -> str:
    """Match a natural language query to an intent string."""
    q = query.lower().strip()

    if re.search(r"\b(how many|count|number of|total|no\.?\s*of)\b.*\bcustomer", q):
        return "count_customers"
    if re.search(r"\b(how many|count|number of|total|no\.?\s*of)\b.*\bsupplier", q):
        return "count_suppliers"
    if re.search(r"\b(how many|count|number of|total|no\.?\s*of)\b.*\b(item|product)", q):
        return "count_items"
    if re.search(r"\b(how many|count|number of|total|no\.?\s*of)\b.*\bemployee", q):
        return "count_employees"
    if re.search(r"\b(how many|count|number of|total|no\.?\s*of)\b.*\b(invoice|bill)", q):
        return "count_sales_invoices"
    if re.search(r"\b(how many|count|number of|total|no\.?\s*of)\b.*\border", q):
        return "count_orders"

    if re.search(r"\b(customer|customers)\b", q):
        return "list_customers"
    if re.search(r"\b(supplier|suppliers)\b", q):
        return "list_suppliers"
    if re.search(r"\b(item|items|product|products)\b", q):
        return "list_items"
    if re.search(r"\b(employee|employees|staff|worker)\b", q):
        return "list_employees"
    if re.search(r"\b(lead|leads)\b", q):
        return "list_leads"
    if re.search(r"\border(s)?\b", q):
        return "list_purchase_orders" if re.search(r"\bpurchase\b", q) else "list_orders"
    if re.search(r"\bquotation(s)?\b", q):
        return "list_quotations"
    if re.search(r"\bdelivery note(s)?\b", q):
        return "list_delivery_notes"
    if re.search(r"\bwarehouse(s)?\b", q):
        return "list_warehouses"
    if re.search(r"\baccount(s)?\b", q):
        return "list_accounts"
    if re.search(r"\bopportunit(y|ies)\b", q):
        return "list_opportunities"
    if re.search(r"\bproject(s)?\b", q):
        return "list_projects"
    if re.search(r"\btask(s)?\b", q):
        return "list_tasks"

    if re.search(r"\b(invoice|invoices|bill|bills)\b", q):
        if re.search(r"\b(overdue|late|unpaid)\b", q):
            return "overdue_invoices"
        if re.search(r"\b(outstanding|pending|due)\b", q):
            return "outstanding_invoices"
        return "list_purchase_invoices" if re.search(r"\b(purchase|supplier)\b", q) else "list_sales_invoices"

    if re.search(r"\b(revenue|sales|income|earning)\b", q):
        if re.search(r"\b(year|annual|yearly)\b", q):
            return "revenue_this_year"
        if re.search(r"\blast month\b", q):
            return "revenue_last_month"
        return "revenue_this_month"
    if re.search(r"\btop customer(s)?\b", q):
        return "top_customers"
    if re.search(r"\btop item(s)?\b", q):
        return "top_items"

    if re.search(r"\b(stock|inventory|warehouse)\b", q):
        return "low_stock" if re.search(r"\b(low|out|reorder|below)\b", q) else "stock_balance"

    return "unknown"

def extract_period(query: str) -> str:
    q = query.lower()
    if "last month" in q: return "last_month"
    if "last year" in q: return "last_year"
    if "this year" in q or "current year" in q or "annual" in q or "yearly" in q:
        return "this_year"
    if "this quarter" in q or "current quarter" in q: return "this_quarter"
    if "this month" in q or "current month" in q: return "this_month"
    return "this_month"

def extract_limit(query: str, default: int = 50) -> int:
    match = re.search(r"\b(?:top|first|show|last|limit)\s+(\d+)\b", query, re.IGNORECASE)
    if match:
        return min(int(match.group(1)), 500)
    match = re.search(r"\b(\d+)\s+(?:customer|supplier|item|invoice|order|employee)\b", query, re.IGNORECASE)
    if match:
        return min(int(match.group(1)), 500)
    return default

def extract_entity_name(query: str) -> str | None:
    doc_id_pattern = re.compile(r"\b([A-Z]{2,10}-\d{4}-\d{4,6}|[A-Z]{2,10}-\d{5,})\b")
    match = doc_id_pattern.search(query.upper())
    if match:
        return match.group(1)
    return None

def extract_party_name(query: str) -> str | None:
    patterns = [
        r"(?:for|of|by|from|customer|supplier)\s+([A-Z][a-zA-Z\s&.',-]{2,40})",
        r"([A-Z][a-zA-Z\s&.',-]{2,40})'s\s+(?:invoice|order|bill|payment|balance)",
    ]
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            stop_words = {"customer", "supplier", "item", "invoice", "order", "all", "the", "this", "that", "month", "year"}
            if candidate.lower() not in stop_words and len(candidate) > 2:
                return candidate
    return None
