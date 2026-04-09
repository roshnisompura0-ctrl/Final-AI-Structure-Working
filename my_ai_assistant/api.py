"""
API Endpoints for My AI Assistant
"""

import json
import frappe
from my_ai_assistant.assistant import handle_query
from my_ai_assistant.services import data_service
from my_ai_assistant.services.doctype_service import get_all_doctypes


@frappe.whitelist()
def get_ai_response(prompt: str, session_history: list = None,
                    user: str = None, conversation_history: str = None) -> dict:
    if not prompt or not prompt.strip():
        return {"type": "text", "message": "Please enter a question."}

    history = session_history or []
    if conversation_history and isinstance(conversation_history, str):
        try:
            history = json.loads(conversation_history)
        except Exception:
            pass

    create_result = _handle_create_command(prompt.strip())
    if create_result is not None:
        return create_result

    try:
        result        = handle_query(prompt.strip(), history)
        response_text = result.get("response", "")
        data          = result.get("data")
        intent        = result.get("intent", "")

        if intent.startswith("list_") and isinstance(data, list) and data:
            doctype = _list_intent_to_doctype(intent)
            # Transform items to ensure they have display names
            transformed_items = []
            for item in data:
                if isinstance(item, dict):
                    # Extract the best display name
                    display_name = (
                        item.get("customer_name") or 
                        item.get("supplier_name") or 
                        item.get("item_name") or
                        item.get("employee_name") or
                        item.get("name") or
                        str(item)
                    )
                    # Keep original item but add display_name
                    item_copy = dict(item)
                    item_copy["_display_name"] = display_name
                    transformed_items.append(item_copy)
                else:
                    transformed_items.append({"_display_name": str(item), "name": str(item)})
            
            return {
                "type":    "list",
                "title":   f"List of {doctype}s",
                "items":   transformed_items,
                "doctype": doctype,
                "message": response_text,
            }

        return {"type": "text", "message": response_text}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "AI Assistant Error")
        return {"type": "error", "message": f"Sorry, I encountered an error: {str(e)}"}


def _list_intent_to_doctype(intent):
    return {
        "list_customers": "Customer", "list_suppliers": "Supplier",
        "list_items": "Item", "list_employees": "Employee",
        "list_leads": "Lead", "list_orders": "Sales Order",
        "list_purchase_orders": "Purchase Order", "list_quotations": "Quotation",
        "list_delivery_notes": "Delivery Note", "list_warehouses": "Warehouse",
        "list_accounts": "Account", "list_sales_invoices": "Sales Invoice",
        "list_purchase_invoices": "Purchase Invoice", "list_opportunities": "Opportunity",
        "list_projects": "Project", "list_tasks": "Task",
    }.get(intent, "Document")


def _extract_bold_text(html):
    import re
    m = re.search(r'<b>([^<]+)</b>', html)
    return m.group(1) if m else ""


def _handle_create_command(prompt):
    import re
    try:
        from my_ai_assistant.services.document_service import create_document
    except ImportError:
        return None

    p = prompt.lower().strip()
    patterns = [
        (r'(?:create|add|new)\s+customer\s+(?:named?\s+)?(.+)',  "Customer",  "customer_name"),
        (r'(?:create|add|new)\s+supplier\s+(?:named?\s+)?(.+)',  "Supplier",  "supplier_name"),
        (r'(?:create|add|new)\s+item\s+(?:named?\s+)?(.+)',      "Item",      "item_name"),
        (r'(?:create|add|new)\s+employee\s+(?:named?\s+)?(.+)',  "Employee",  "employee_name"),
    ]
    for pattern, doctype, field in patterns:
        m = re.match(pattern, p)
        if m:
            name = re.sub(r'[.!?]+$', '', m.group(1).strip()).strip().title()
            if not name:
                return {"type": "error", "message": f"Please provide a name for the {doctype}."}
            try:
                result = create_document(doctype, {field: name})
                if result.get("success"):
                    doc_name = _extract_bold_text(result.get("message", "")) or name
                    dt_slug  = doctype.lower().replace(" ", "-")
                    return {
                        "type": "success", "message": f"{doctype} <b>{doc_name}</b> created successfully!",
                        "name": doc_name, "doctype": doctype,
                        "link": f"/app/{dt_slug}/{doc_name}",
                    }
                return {"type": "error", "message": result.get("message", "Failed to create record.")}
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), f"Create {doctype} Error")
                return {"type": "error", "message": f"Failed to create {doctype}: {str(e)}"}
    return None


def _create_document_from_extracted_data(doctype, data):
    """
    Create an ERPNext document from AI-extracted image data.
    Returns {"success": True/False, "name": doc_name, "message": str}
    """
    try:
        # Special handling for Visiting Card - pass data directly to document service
        if doctype == "Visiting Card":
            from my_ai_assistant.services.document_service import create_document
            result = create_document(doctype, data)
            return result
        
        doc_data = {}
        
        # Map common fields based on doctype
        if doctype == "Sales Invoice":
            doc_data["customer"] = _find_or_create_party("Customer", data.get("customer"), data.get("customer_gstin"))
            doc_data["posting_date"] = data.get("posting_date") or frappe.utils.today()
            doc_data["due_date"] = data.get("due_date")
            doc_data["po_no"] = data.get("po_no")
            if data.get("remarks"):
                doc_data["remarks"] = data.get("remarks")
        
        elif doctype == "Purchase Invoice":
            doc_data["supplier"] = _find_or_create_party("Supplier", data.get("supplier"), data.get("supplier_gstin"))
            doc_data["bill_no"] = data.get("bill_no")
            doc_data["bill_date"] = data.get("bill_date")
            doc_data["posting_date"] = data.get("posting_date") or frappe.utils.today()
            doc_data["due_date"] = data.get("due_date")
            if data.get("remarks"):
                doc_data["remarks"] = data.get("remarks")
        
        elif doctype == "Sales Order":
            doc_data["customer"] = _find_or_create_party("Customer", data.get("customer"), data.get("customer_gstin"))
            doc_data["transaction_date"] = data.get("transaction_date") or frappe.utils.today()
            doc_data["delivery_date"] = data.get("delivery_date")
            doc_data["po_no"] = data.get("po_no")
            if data.get("remarks"):
                doc_data["remarks"] = data.get("remarks")
        
        elif doctype == "Purchase Order":
            doc_data["supplier"] = _find_or_create_party("Supplier", data.get("supplier"), data.get("supplier_gstin"))
            doc_data["transaction_date"] = data.get("transaction_date") or frappe.utils.today()
            doc_data["schedule_date"] = data.get("schedule_date")
            if data.get("remarks"):
                doc_data["remarks"] = data.get("remarks")
        
        elif doctype == "Quotation":
            doc_data["party_name"] = _find_or_create_party("Customer", data.get("party_name"))
            doc_data["quotation_to"] = "Customer"
            doc_data["transaction_date"] = data.get("transaction_date") or frappe.utils.today()
            doc_data["valid_till"] = data.get("valid_till")
            if data.get("remarks"):
                doc_data["remarks"] = data.get("remarks")
        
        # Process items
        items = []
        extracted_items = data.get("items", [])
        for item in extracted_items:
            item_row = {
                "item_name": item.get("item_name", "Unknown Item"),
                "description": item.get("description") or item.get("item_name", "Unknown Item"),
                "qty": float(item.get("qty", 1)),
                "rate": float(item.get("rate", 0)),
                "amount": float(item.get("amount", 0)) or (float(item.get("qty", 1)) * float(item.get("rate", 0))),
                "uom": item.get("uom", "Nos"),
            }
            items.append(item_row)
        
        if items:
            doc_data["items"] = items
        
        # Process taxes if present
        taxes = []
        extracted_taxes = data.get("taxes", [])
        for tax in extracted_taxes:
            tax_row = {
                "charge_type": "Actual" if tax.get("amount") else "On Net Total",
                "account_head": _get_default_tax_account(),
                "description": tax.get("description", "Tax"),
                "rate": float(tax.get("rate", 0)),
                "tax_amount": float(tax.get("amount", 0)),
            }
            taxes.append(tax_row)
        
        if taxes:
            doc_data["taxes"] = taxes
        
        # Set grand total if provided
        if data.get("grand_total"):
            doc_data["grand_total"] = float(data.get("grand_total"))
        
        # Create the document using document_service
        from my_ai_assistant.services.document_service import create_document
        result = create_document(doctype, doc_data)
        return result
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Create {doctype} from Image Error")
        return {"success": False, "message": str(e)}


def _find_or_create_party(party_type, name, gstin=None):
    """
    Find existing party by name or GSTIN, or create new one.
    Returns the party ID (name field).
    """
    if not name:
        return None
    
    name = name.strip()
    
    # Try to find by GSTIN first (most reliable) - wrap in try/except in case field doesn't exist
    if gstin:
        try:
            existing = frappe.db.get_value(party_type, {"gstin": gstin}, "name")
            if existing:
                return existing
        except Exception:
            pass  # GSTIN field may not exist, continue with name lookup
    
    # Try exact match on name field
    name_field = "customer_name" if party_type == "Customer" else "supplier_name"
    existing = frappe.db.get_value(party_type, {name_field: name}, "name")
    if existing:
        return existing
    
    # Try fuzzy match on name
    existing = frappe.db.get_value(party_type, {name_field: ["like", f"%{name}%"]}, "name")
    if existing:
        return existing
    
    # Create new party
    try:
        doc = frappe.new_doc(party_type)
        if party_type == "Customer":
            doc.customer_name = name
            if gstin:
                try:
                    doc.gstin = gstin
                except Exception:
                    pass  # Field may not exist
        else:
            doc.supplier_name = name
            if gstin:
                try:
                    doc.gstin = gstin
                except Exception:
                    pass  # Field may not exist
        
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return doc.name
    except Exception as e:
        frappe.log_error(f"Failed to create {party_type} '{name}': {e}")
        # Return a fallback - try to get any existing
        fallback = frappe.db.get_value(party_type, {}, "name")
        return fallback or name[:30]  # Truncate if needed


def _get_default_tax_account():
    """Get a default tax account for auto-created documents."""
    # Try common tax account names
    common_accounts = ["CGST", "SGST", "GST", "VAT", "Tax", "Output Tax", "Input Tax"]
    for acc in common_accounts:
        found = frappe.db.get_value("Account", {"account_name": ["like", f"%{acc}%"]}, "name")
        if found:
            return found
    # Return any expense account as fallback
    fallback = frappe.db.get_value("Account", {"account_type": "Tax"}, "name")
    return fallback or "Expenses - Indirect"


@frappe.whitelist()
def get_customers(limit: int = 100, search: str = None) -> list:
    filters = {"disabled": 0}
    if search: filters["customer_name"] = ["like", f"%{search}%"]
    return data_service.get_all_customers(filters=filters, limit=int(limit))

@frappe.whitelist()
def get_suppliers(limit: int = 100, search: str = None) -> list:
    filters = {"disabled": 0}
    if search: filters["supplier_name"] = ["like", f"%{search}%"]
    return data_service.get_all_suppliers(filters=filters, limit=int(limit))

@frappe.whitelist()
def get_items(limit: int = 200, search: str = None, item_group: str = None) -> list:
    filters = {"disabled": 0}
    if search: filters["item_name"] = ["like", f"%{search}%"]
    if item_group: filters["item_group"] = item_group
    return data_service.get_all_items(filters=filters, limit=int(limit))

@frappe.whitelist()
def get_stock_balance(item_code: str = None, warehouse: str = None) -> list:
    return data_service.get_stock_balance(item_code=item_code, warehouse=warehouse)

@frappe.whitelist()
def get_outstanding_invoices(party_type: str = "Customer", party: str = None) -> list:
    return data_service.get_outstanding_invoices(party_type=party_type, party=party)

@frappe.whitelist()
def get_overdue_invoices(party_type: str = "Customer") -> list:
    return data_service.get_overdue_invoices(party_type=party_type)

@frappe.whitelist()
def get_revenue_summary(period: str = "this_month") -> dict:
    return data_service.get_revenue_summary(period=period)

@frappe.whitelist()
def get_top_customers(limit: int = 10, period: str = "this_year") -> list:
    return data_service.get_top_customers(limit=int(limit), period=period)

@frappe.whitelist()
def get_top_selling_items(limit: int = 10, period: str = "this_year") -> list:
    return data_service.get_top_selling_items(limit=int(limit), period=period)

@frappe.whitelist()
def get_doctypes_list(category: str = "all") -> list:
    return get_all_doctypes(category=category)

@frappe.whitelist()
def get_document_details(doctype: str, name: str) -> dict:
    if not frappe.has_permission(doctype, "read"):
        frappe.throw("Not permitted", frappe.PermissionError)
    doc = data_service.get_document(doctype, name)
    if not doc:
        frappe.throw(f"{doctype} {name} not found", frappe.DoesNotExistError)
    return doc

@frappe.whitelist()
def get_generic_list(doctype: str, fields: str = None, filters: str = None, limit: int = 50) -> list:
    if not frappe.has_permission(doctype, "read"):
        frappe.throw("Not permitted", frappe.PermissionError)
    parsed_fields  = json.loads(fields)  if fields  else None
    parsed_filters = json.loads(filters) if filters else None
    return data_service.get_doctype_list(doctype, fields=parsed_fields, filters=parsed_filters, limit=int(limit))

@frappe.whitelist()
def process_document_image_api(image_data: str, document_type: str = "auto",
                                file_name: str = None, invoice_type: str = None,
                                auto_create: bool = True) -> dict:
    try:
        from my_ai_assistant.services.image_service import process_image
        result = process_image(image_data=image_data, document_type=invoice_type or document_type)
        
        # If extraction successful and auto_create enabled, create the document
        if result.get("success") and auto_create:
            extracted_data = result.get("extracted_data", {})
            doctype = result.get("doctype")
            
            if extracted_data and doctype:
                create_result = _create_document_from_extracted_data(doctype, extracted_data)
                if create_result.get("success"):
                    doc_name = create_result.get("name")
                    # For Visiting Card, the actual doctype created is Customer
                    link_doctype = create_result.get("doctype") or doctype
                    # Frappe set_route needs 'Form' prefix for document editing
                    return {
                        "type": "success",
                        "success": True,
                        "created": True,
                        "created_doc_name": doc_name,
                        "doctype": link_doctype,
                        "name": doc_name,
                        "link": f"/app/Form/{link_doctype}/{doc_name}",
                        "message": f"✅ Created {link_doctype} from '{file_name or 'file'}'",
                        "extracted_data": extracted_data,
                        "filename": file_name
                    }
                else:
                    return {
                        "type": "info",
                        "success": True,
                        "created": False,
                        "create_error": create_result.get("message"),
                        "doctype": doctype,
                        "message": f"📄 Extracted {doctype} (creation failed: {create_result.get('message')})",
                        "extracted_data": extracted_data,
                        "filename": file_name
                    }
        
        # Return standard result if not auto-creating or if creation skipped
        if result.get("success"):
            return {
                "type": "info",
                "success": True,
                "message": result.get("message", "Document processed"),
                "doctype": result.get("doctype"),
                "extracted_data": result.get("extracted_data"),
                "filename": file_name
            }
        else:
            return {
                "type": "error",
                "success": False,
                "message": result.get("message", "Processing failed")
            }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Image Processing Error")
        return {"type": "error", "message": str(e)}

@frappe.whitelist()
def get_dashboard_summary() -> dict:
    try:
        overdue = data_service.get_overdue_invoices(limit=500)
        return {
            "customers":          data_service.get_doctype_count("Customer",         {"disabled": 0}),
            "suppliers":          data_service.get_doctype_count("Supplier",         {"disabled": 0}),
            "items":              data_service.get_doctype_count("Item",             {"disabled": 0}),
            "employees":          data_service.get_doctype_count("Employee",         {"status": "Active"}),
            "sales_invoices":     data_service.get_doctype_count("Sales Invoice",    {"docstatus": 1}),
            "purchase_invoices":  data_service.get_doctype_count("Purchase Invoice", {"docstatus": 1}),
            "sales_orders":       data_service.get_doctype_count("Sales Order",      {"docstatus": 1}),
            "purchase_orders":    data_service.get_doctype_count("Purchase Order",   {"docstatus": 1}),
            "revenue_this_month": data_service.get_revenue_summary("this_month"),
            "revenue_this_year":  data_service.get_revenue_summary("this_year"),
            "overdue_invoices":   len(overdue),
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Dashboard Summary Error")
        return {"error": str(e)}

@frappe.whitelist()
def test_connection_api() -> dict:
    return {"status": "connected", "success": True,
            "timestamp": frappe.utils.now(), "version": frappe.__version__}