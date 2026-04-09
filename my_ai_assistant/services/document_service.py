"""
document_service.py — ERPNext Document Creation Service
Creates draft entries for all 5 document types.
"""
from datetime import date
import frappe

def _today():
	return date.today().isoformat()

def _safe_date(val):
	if val and isinstance(val, str) and len(val) == 10 and val[4] == "-":
		return val
	return None

def _safe_float(val, default=0.0):
	try:
		return float(val or default)
	except (TypeError, ValueError):
		return default

def _resolve_item_code(item_name, description=None):
	if not item_name:
		item_name = "Scanned Item"
	existing = frappe.db.get_value("Item", {"item_name": item_name}, "name")
	if existing:
		return existing
	if frappe.db.exists("Item", item_name):
		return item_name
	results = frappe.db.get_all("Item", filters=[["item_name", "like", f"%{item_name[:25]}%"]], fields=["name"], limit=1)
	if results:
		return results[0].name
	try:
		item = frappe.get_doc({
			"doctype": "Item", "item_name": item_name, "item_code": item_name[:140],
			"description": description or item_name, "item_group": "All Item Groups",
			"stock_uom": "Nos", "is_stock_item": 0, "is_purchase_item": 1, "is_sales_item": 1,
		})
		item.flags.ignore_mandatory = True
		item.insert(ignore_permissions=True)
		frappe.db.commit()
		return item.name
	except Exception as e:
		frappe.log_error(f"Could not create item '{item_name}': {e}", "AI Document Service")
		return item_name

def _resolve_party(party_name, party_doctype):
	"""Find or create customer/supplier. Cleans name and auto-creates if missing."""
	if not party_name:
		return f"Unknown {party_doctype}"
	
	# Clean up the name - extract just the name from full address string
	import re
	clean_name = party_name
	
	# Take only first line or first comma-separated part
	clean_name = clean_name.split(',')[0].split('\n')[0].strip()
	
	# Remove common prefixes
	clean_name = re.sub(r'^(Customer:|Bill To:|Ship To:|Sold To:|Buyer:|Vendor:|Supplier:)\s*', '', clean_name, flags=re.IGNORECASE).strip()
	
	# Remove phone numbers (10+ digits)
	clean_name = re.sub(r'\b\d{10,}\b', '', clean_name).strip()
	
	# Remove email addresses
	clean_name = re.sub(r'[\w.-]+@[\w.-]+\.\w+', '', clean_name).strip()
	
	# Remove common address keywords and everything after them
	address_keywords = [' Avenue', ' Street', ' Road', ' Block', ' Area', ' City', ' State', ' Pin', ' GSTIN', ' PINCODE', ' Zip', ' Floor', ' Building', ' Complex', ' Apartment', ' Flat', ' Unit']
	for keyword in address_keywords:
		if keyword.lower() in clean_name.lower():
			idx = clean_name.lower().find(keyword.lower())
			clean_name = clean_name[:idx].strip()
	
	# Limit length and clean up
	clean_name = clean_name[:100].strip().rstrip(',')
	
	if not clean_name or len(clean_name) < 2:
		clean_name = f"Unknown {party_doctype}"
	
	# Check if exact name exists
	if frappe.db.exists(party_doctype, clean_name):
		return clean_name
	
	# Try partial match
	results = frappe.db.get_all(party_doctype, filters=[["name", "like", f"%{clean_name[:30]}%"]], fields=["name"], limit=1)
	if results:
		return results[0].name
	
	# Auto-create customer/supplier
	try:
		if party_doctype == "Customer":
			doc = frappe.get_doc({
				"doctype": "Customer",
				"customer_name": clean_name,
				"customer_type": "Individual",
				"customer_group": "All Customer Groups",
				"territory": "All Territories",
			})
		else:
			doc = frappe.get_doc({
				"doctype": "Supplier",
				"supplier_name": clean_name,
				"supplier_type": "Individual",
				"supplier_group": "All Supplier Groups",
			})
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		frappe.logger().info(f"[AI] Auto-created {party_doctype}: {doc.name}")
		return doc.name
	except Exception as e:
		frappe.log_error(f"[AI] Could not auto-create {party_doctype} '{clean_name}': {e}", "AI Document Service")
		return clean_name

def _get_valid_uom(uom_name):
	"""Get a valid UOM from database, fallback to 'Nos' if invalid."""
	if not uom_name:
		return "Nos"
	
	# Common variations that might be extracted
	uom_mapping = {
		"no": "Nos",
		"nos": "Nos",
		"no.": "Nos",
		"no.s": "Nos",
		"number": "Nos",
		"numbers": "Nos",
		"pc": "Nos",
		"pcs": "Nos",
		"piece": "Nos",
		"pieces": "Nos",
		"ea": "Nos",
		"each": "Nos",
		"kg": "Kg",
		"kgs": "Kg",
		"kilogram": "Kg",
		"kilograms": "Kg",
		"m": "Meter",
		"meter": "Meter",
		"meters": "Meter",
		"ft": "Foot",
		"foot": "Foot",
		"feet": "Foot",
		"box": "Box",
		"boxes": "Box",
		"set": "Set",
		"sets": "Set",
		"pack": "Pack",
		"packs": "Pack",
		"lot": "Nos",
		"unit": "Nos",
		"units": "Nos",
	}
	
	# Normalize the UOM name
	uom_lower = str(uom_name).strip().lower()
	uom_normalized = uom_mapping.get(uom_lower, uom_name)
	
	# Check if it exists in database
	if frappe.db.exists("UOM", uom_normalized):
		return uom_normalized
	
	# Try case-insensitive lookup
	existing = frappe.db.get_value("UOM", {"name": ["like", f"%{uom_normalized}%"]}, "name")
	if existing:
		return existing
	
	# Fallback to Nos
	return "Nos"


def _build_items(raw_items):
	if not raw_items or not isinstance(raw_items, list):
		return [{"item_code": "Scanned Item", "item_name": "Scanned Item", "description": "Auto-created from scan", "qty": 1, "rate": 0, "amount": 0, "uom": "Nos", "conversion_factor": 1}]
	rows = []
	for it in raw_items:
		name = it.get("item_name") or it.get("description") or "Scanned Item"
		qty = _safe_float(it.get("qty"), 1.0)
		rate = _safe_float(it.get("rate"))
		amount = _safe_float(it.get("amount"), qty * rate)
		rows.append({
			"item_code": _resolve_item_code(name, it.get("description")),
			"item_name": name,
			"description": it.get("description") or name,
			"qty": qty,
			"rate": rate,
			"amount": amount,
			"uom": _get_valid_uom(it.get("uom")),
			"conversion_factor": 1,
		})
	return rows

def _build_taxes(raw_taxes, company=None):
	if not raw_taxes or not isinstance(raw_taxes, list):
		return []
	tax_account = ""
	if company:
		tax_account = frappe.db.get_value("Account", {"account_type": "Tax", "company": company, "disabled": 0}, "name") or ""
	rows = []
	for tx in raw_taxes:
		amount = _safe_float(tx.get("amount"))
		if amount == 0:
			continue
		rows.append({"charge_type": "Actual", "description": tx.get("description") or "Tax", "tax_amount": amount, "account_head": tax_account})
	return rows

def _company():
	return frappe.defaults.get_user_default("company") or frappe.db.get_single_value("Global Defaults", "default_company")

def _create_sales_invoice(data):
	co = _company()
	doc = frappe.get_doc({
		"doctype": "Sales Invoice", "company": co,
		"customer": _resolve_party(data.get("customer") or "Unknown Customer", "Customer"),
		"posting_date": _safe_date(data.get("posting_date")) or _today(),
		"due_date": _safe_date(data.get("due_date")), "po_no": data.get("po_no"),
		"currency": data.get("currency") or "INR", "remarks": data.get("remarks"),
		"items": _build_items(data.get("items")), "taxes": _build_taxes(data.get("taxes"), co),
	})
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"doctype": "Sales Invoice", "name": doc.name, "url": f"/app/sales-invoice/{doc.name}", "grand_total": doc.grand_total, "customer": doc.customer}

def _create_purchase_invoice(data):
	co = _company()
	doc = frappe.get_doc({
		"doctype": "Purchase Invoice", "company": co,
		"supplier": _resolve_party(data.get("supplier") or "Unknown Supplier", "Supplier"),
		"bill_no": data.get("bill_no"), "bill_date": _safe_date(data.get("bill_date")),
		"posting_date": _safe_date(data.get("posting_date")) or _today(),
		"due_date": _safe_date(data.get("due_date")),
		"currency": data.get("currency") or "INR", "remarks": data.get("remarks"),
		"items": _build_items(data.get("items")), "taxes": _build_taxes(data.get("taxes"), co),
	})
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"doctype": "Purchase Invoice", "name": doc.name, "url": f"/app/purchase-invoice/{doc.name}", "grand_total": doc.grand_total, "supplier": doc.supplier}

def _create_sales_order(data):
	co = _company()
	doc = frappe.get_doc({
		"doctype": "Sales Order", "company": co,
		"customer": _resolve_party(data.get("customer") or "Unknown Customer", "Customer"),
		"transaction_date": _safe_date(data.get("transaction_date")) or _today(),
		"delivery_date": _safe_date(data.get("delivery_date")) or _today(),
		"po_no": data.get("po_no"), "currency": data.get("currency") or "INR", "remarks": data.get("remarks"),
		"items": _build_items(data.get("items")), "taxes": _build_taxes(data.get("taxes"), co),
	})
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"doctype": "Sales Order", "name": doc.name, "url": f"/app/sales-order/{doc.name}", "grand_total": doc.grand_total, "customer": doc.customer}

def _create_purchase_order(data):
	co = _company()
	doc = frappe.get_doc({
		"doctype": "Purchase Order", "company": co,
		"supplier": _resolve_party(data.get("supplier") or "Unknown Supplier", "Supplier"),
		"transaction_date": _safe_date(data.get("transaction_date")) or _today(),
		"schedule_date": _safe_date(data.get("schedule_date")) or _today(),
		"currency": data.get("currency") or "INR", "remarks": data.get("remarks"),
		"items": _build_items(data.get("items")), "taxes": _build_taxes(data.get("taxes"), co),
	})
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"doctype": "Purchase Order", "name": doc.name, "url": f"/app/purchase-order/{doc.name}", "grand_total": doc.grand_total, "supplier": doc.supplier}

def _create_quotation(data):
	co = _company()
	
	# Build complete dict - order matters: quotation_to MUST be set before party_name
	# Python 3.7+ preserves dict insertion order
	doc_dict = {
		"doctype": "Quotation",
		"company": co,
		"quotation_to": "Customer",  # Hardcoded - dynamic link target doctype
		"party_name": _resolve_party(data.get("party_name") or "Unknown Customer", "Customer"),
		"transaction_date": _safe_date(data.get("transaction_date")) or _today(),
		"valid_till": _safe_date(data.get("valid_till")) or _today(),
		"currency": data.get("currency") or "INR",
		"remarks": data.get("remarks") or "",
	}
	
	# Add items and taxes
	items = _build_items(data.get("items"))
	if items:
		doc_dict["items"] = items
	
	taxes = _build_taxes(data.get("taxes"), co)
	if taxes:
		doc_dict["taxes"] = taxes
	
	doc = frappe.get_doc(doc_dict)
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"doctype": "Quotation", "name": doc.name, "url": f"/app/quotation/{doc.name}", "grand_total": doc.grand_total, "party_name": doc.party_name}


def _create_customer(data):
	"""Create Customer from chat command."""
	customer_name = data.get("customer_name") or data.get("name") or data.get("party_name")
	if not customer_name:
		return {"type": "text", "success": False, "message": "Customer name is required."}
	
	# Check if already exists
	if frappe.db.exists("Customer", customer_name):
		return {"type": "text", "success": False, "message": f"Customer '{customer_name}' already exists."}
	
	# Create customer
	doc = frappe.get_doc({
		"doctype": "Customer",
		"customer_name": customer_name,
		"customer_type": data.get("customer_type") or "Individual",
		"customer_group": data.get("customer_group") or "All Customer Groups",
		"territory": data.get("territory") or "All Territories",
	})
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	
	# Return HTML formatted response with link
	return {
		"type": "text",
		"success": True,
		"message": f'✅ Customer created: <a href="/app/customer/{doc.name}"><b>{doc.name}</b></a>'
	}


def _create_supplier(data):
	"""Create Supplier from chat command."""
	supplier_name = data.get("supplier_name") or data.get("name") or data.get("party_name")
	if not supplier_name:
		return {"type": "text", "success": False, "message": "Supplier name is required."}
	
	# Check if already exists
	if frappe.db.exists("Supplier", supplier_name):
		return {"type": "text", "success": False, "message": f"Supplier '{supplier_name}' already exists."}
	
	# Create supplier
	doc = frappe.get_doc({
		"doctype": "Supplier",
		"supplier_name": supplier_name,
		"supplier_type": data.get("supplier_type") or "Individual",
		"supplier_group": data.get("supplier_group") or "All Supplier Groups",
	})
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	
	# Return HTML formatted response with link
	return {
		"type": "text",
		"success": True,
		"message": f'✅ Supplier created: <a href="/app/supplier/{doc.name}"><b>{doc.name}</b></a>'
	}


def _create_item(data):
	"""Create Item from chat command."""
	item_name = data.get("item_name") or data.get("name") or data.get("description")
	if not item_name:
		return {"type": "text", "success": False, "message": "Item name is required."}
	
	# Generate item_code from name
	import re
	item_code = re.sub(r'[^a-zA-Z0-9\s]', '', item_name).strip().upper().replace(' ', '-')
	if not item_code:
		item_code = "ITEM-" + str(frappe.utils.now_int())[-6:]
	
	# Check if already exists
	if frappe.db.exists("Item", item_code):
		return {"type": "text", "success": False, "message": f"Item '{item_code}' already exists."}
	
	# Create item
	doc = frappe.get_doc({
		"doctype": "Item",
		"item_code": item_code,
		"item_name": item_name,
		"item_group": data.get("item_group") or "All Item Groups",
		"stock_uom": data.get("stock_uom") or "Nos",
		"is_stock_item": 0,
		"is_purchase_item": 1,
		"is_sales_item": 1,
	})
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	
	# Return HTML formatted response with link
	return {
		"type": "text",
		"success": True,
		"message": f'✅ Item created: <a href="/app/item/{doc.name}"><b>{doc.name}</b></a>'
	}


def _create_customer_from_visiting_card(data):
	"""Create Customer from visiting card data with full contact information."""
	# Get customer name - use full_name or combine first_name + last_name or company_name
	customer_name = data.get("full_name") or data.get("customer_name")
	if not customer_name and (data.get("first_name") or data.get("last_name")):
		customer_name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
	if not customer_name:
		customer_name = data.get("company_name")
	if not customer_name:
		return {"type": "text", "success": False, "message": "Customer name is required - could not extract from visiting card."}
	
	# Truncate customer name if too long (ERPNext limit is usually 140 chars)
	customer_name = customer_name[:140]
	
	# Check if already exists by name
	existing = frappe.db.get_value("Customer", {"customer_name": customer_name}, "name")
	if existing:
		# Return the existing customer with a link instead of failing
		return {
			"type": "text",
			"success": True,
			"name": existing,
			"doctype": "Customer",
			"message": f'ℹ️ Customer already exists: <a href="/app/customer/{existing}"><b>{customer_name}</b></a>'
		}
	
	# Prepare customer data
	customer_data = {
		"doctype": "Customer",
		"customer_name": customer_name,
		"customer_type": "Individual" if data.get("full_name") or data.get("first_name") else "Company",
		"customer_group": "All Customer Groups",
		"territory": "All Territories",
	}
	
	# Add GSTIN if present
	if data.get("gstin"):
		try:
			customer_data["gstin"] = data.get("gstin")
		except Exception:
			pass
	
	# Create customer
	doc = frappe.get_doc(customer_data)
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	
	# Create contact with all the visiting card details
	contact_data = {
		"doctype": "Contact",
		"first_name": data.get("first_name") or data.get("full_name") or customer_name,
		"last_name": data.get("last_name") or "",
		"company_name": data.get("company_name") or "",
		"designation": data.get("designation") or "",
	}
	
	# Add phone numbers
	if data.get("mobile"):
		contact_data["phone_nos"] = [{"phone": data.get("mobile"), "is_primary_phone": 1}]
	if data.get("phone"):
		if "phone_nos" not in contact_data:
			contact_data["phone_nos"] = []
		contact_data["phone_nos"].append({"phone": data.get("phone"), "is_primary_phone": 0})
	if data.get("whatsapp"):
		if "phone_nos" not in contact_data:
			contact_data["phone_nos"] = []
		contact_data["phone_nos"].append({"phone": data.get("whatsapp"), "is_primary_phone": 0})
	
	# Add email
	if data.get("email"):
		contact_data["email_ids"] = [{"email_id": data.get("email"), "is_primary": 1}]
	if data.get("email2"):
		if "email_ids" not in contact_data:
			contact_data["email_ids"] = []
		contact_data["email_ids"].append({"email_id": data.get("email2"), "is_primary": 0})
	
	# Create contact and link to customer
	if contact_data.get("phone_nos") or contact_data.get("email_ids"):
		try:
			contact_doc = frappe.get_doc(contact_data)
			contact_doc.flags.ignore_mandatory = True
			contact_doc.insert(ignore_permissions=True)
			# Link contact to customer
			contact_doc.append("links", {
				"link_doctype": "Customer",
				"link_name": doc.name
			})
			contact_doc.save(ignore_permissions=True)
		except Exception as e:
			frappe.logger().warning(f"[AI] Could not create contact for customer {doc.name}: {e}")
	
	# Create address if address info present
	address_data = {
		"doctype": "Address",
		"address_title": data.get("company_name") or customer_name,
		"address_line1": data.get("address_line1") or "",
		"address_line2": data.get("address_line2") or "",
		"city": data.get("city") or "",
		"state": data.get("state") or "",
		"pincode": data.get("pincode") or "",
		"country": data.get("country") or "India",
		"phone": data.get("mobile") or data.get("phone") or "",
		"email_id": data.get("email") or "",
	}
	
	# Only create address if at least city or address_line1 is present
	if data.get("address_line1") or data.get("city"):
		try:
			address_doc = frappe.get_doc(address_data)
			address_doc.flags.ignore_mandatory = True
			address_doc.insert(ignore_permissions=True)
			# Link address to customer
			address_doc.append("links", {
				"link_doctype": "Customer",
				"link_name": doc.name
			})
			address_doc.save(ignore_permissions=True)
		except Exception as e:
			frappe.logger().warning(f"[AI] Could not create address for customer {doc.name}: {e}")
	
	frappe.db.commit()
	
	# Build summary of extracted info
	extracted_info = []
	if data.get("mobile"): extracted_info.append(f"📱 {data.get('mobile')}")
	if data.get("email"): extracted_info.append(f"📧 {data.get('email')}")
	if data.get("company_name"): extracted_info.append(f"🏢 {data.get('company_name')}")
	if data.get("designation"): extracted_info.append(f"💼 {data.get('designation')}")
	
	info_summary = " | ".join(extracted_info) if extracted_info else ""
	
	return {
		"type": "text",
		"success": True,
		"name": doc.name,
		"doctype": "Customer",
		"message": f'✅ Customer created from visiting card: <a href="/app/customer/{doc.name}"><b>{doc.name}</b></a>' + (f'<br><small>{info_summary}</small>' if info_summary else '')
	}


_CREATORS = {
	"Sales Invoice": _create_sales_invoice,
	"Purchase Invoice": _create_purchase_invoice,
	"Sales Order": _create_sales_order,
	"Purchase Order": _create_purchase_order,
	"Quotation": _create_quotation,
	"Customer": _create_customer,
	"Supplier": _create_supplier,
	"Item": _create_item,
	"Visiting Card": _create_customer_from_visiting_card,
}

def create_document_from_extraction(doctype, extracted_data):
	"""Main creation function — called by api.py."""
	creator = _CREATORS.get(doctype)
	if not creator:
		return {"type": "text", "success": False, "message": f"Unsupported doctype '{doctype}'."}
	try:
		result = creator(extracted_data)
		# If result already has type="text", it's a formatted response (new format for Customer/Supplier/Item)
		if result.get("type") == "text":
			return result
		# For transaction docs (Sales Invoice, Purchase Invoice, etc), return formatted link
		doc_name = result.get('name', 'Unknown')
		doctype_slug = doctype.lower().replace(' ', '-')
		return {
			"type": "text",
			"success": True,
			"name": doc_name,
			"doctype": doctype,
			"message": f'✅ {doctype} draft created: <a href="/app/{doctype_slug}/{doc_name}"><b>{doc_name}</b></a>'
		}
	except Exception as e:
		frappe.log_error(f"[AI] Failed to create {doctype}: {e}", "AI Document Service")
		return {"type": "text", "success": False, "message": f"Failed to create {doctype}: {str(e)}"}

# Backward-compatibility alias — assistant.py imports this name
def create_document(doctype, data):
	"""Alias kept for assistant.py compatibility."""
	return create_document_from_extraction(doctype=doctype, extracted_data=data)
