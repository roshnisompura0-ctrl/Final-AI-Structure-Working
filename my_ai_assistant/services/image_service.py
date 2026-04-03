"""
image_service.py — Two-pass AI document processing.
Supports images (JPEG, PNG, WEBP) and PDFs.
"""
import base64
import json
import re
import io
import frappe
from my_ai_assistant.config.settings import get_settings

DOCUMENT_TYPE_MAP = {
	"sales invoice": "Sales Invoice", "si": "Sales Invoice", "sinv": "Sales Invoice",
	"tax invoice": "Sales Invoice", "invoice": "Sales Invoice",
	"purchase invoice": "Purchase Invoice", "pi": "Purchase Invoice", "pinv": "Purchase Invoice",
	"bill": "Purchase Invoice", "vendor invoice": "Purchase Invoice",
	"sales order": "Sales Order", "so": "Sales Order", "customer order": "Sales Order",
	"order confirmation": "Sales Order",
	"purchase order": "Purchase Order", "po": "Purchase Order", "vendor order": "Purchase Order",
	"quotation": "Quotation", "quote": "Quotation", "rfq": "Quotation",
	"estimate": "Quotation", "proposal": "Quotation",
}
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
SUPPORTED_PDF_TYPE = "application/pdf"
VALID_DOCTYPES = {"Sales Invoice", "Purchase Invoice", "Sales Order", "Purchase Order", "Quotation"}

_DETECT_TYPE_PROMPT = """You are a business document classification expert.
Examine this document and identify what type it is.
Reply with EXACTLY one of these values and nothing else:
Sales Invoice
Purchase Invoice
Sales Order
Purchase Order
Quotation

Rules:
- Heading says SALES ORDER or SO- or Order Confirmation → Sales Order
- Heading says PURCHASE ORDER or PO- → Purchase Order
- Heading says QUOTATION or QUOTE or ESTIMATE or PROPOSAL → Quotation
- Bill/invoice received FROM a vendor → Purchase Invoice
- Invoice issued TO a customer → Sales Invoice"""

_ITEMS = '  "items": [{"item_name": "string", "description": "string or null", "qty": 0, "rate": 0, "amount": 0, "uom": "Nos"}]'
_TAXES = '  "taxes": [{"description": "string", "rate": 0, "amount": 0}]'

_EXTRACT_PROMPTS = {
	"Sales Invoice": f'''Extract this Sales Invoice into JSON. Return ONLY raw JSON, no markdown.

IMPORTANT: For "customer", extract ONLY the person/company NAME (2-4 words max). Do NOT include addresses, phone numbers, emails, or GSTIN.

{{
  "customer": "Just the customer NAME only (e.g., \"Amit Patel\") - no address/phone/email/GSTIN",
  "customer_gstin": null,
  "posting_date": "YYYY-MM-DD or null",
  "due_date": null,
  "invoice_number": null,
  "po_no": null,
{_ITEMS},
{_TAXES},
  "grand_total": 0,
  "currency": "INR",
  "remarks": null
}}''',
	"Purchase Invoice": f'''Extract this Purchase Invoice/Bill into JSON. Return ONLY raw JSON, no markdown.

IMPORTANT: For "supplier", extract ONLY the person/company NAME (2-4 words max). Do NOT include addresses, phone numbers, emails, or GSTIN.

{{
  "supplier": "Just the supplier NAME only (e.g., \"ABC Supplies\") - no address/phone/email/GSTIN",
  "supplier_gstin": null,
  "bill_no": null,
  "bill_date": null,
  "posting_date": "YYYY-MM-DD or null",
  "due_date": null,
{_ITEMS},
{_TAXES},
  "grand_total": 0,
  "currency": "INR",
  "remarks": null
}}''',
	"Sales Order": f'''Extract this Sales Order into JSON. Return ONLY raw JSON, no markdown.

IMPORTANT: For "customer", extract ONLY the person/company NAME (2-4 words max). Do NOT include addresses, phone numbers, emails, or GSTIN.

{{
  "customer": "Just the customer NAME only (e.g., \"Amit Patel\") - no address/phone/email/GSTIN",
  "customer_gstin": null,
  "transaction_date": "YYYY-MM-DD or null",
  "delivery_date": null,
  "order_number": null,
  "po_no": null,
{_ITEMS},
{_TAXES},
  "grand_total": 0,
  "currency": "INR",
  "remarks": null
}}''',
	"Purchase Order": f'''Extract this Purchase Order into JSON. Return ONLY raw JSON, no markdown.

IMPORTANT: For "supplier", extract ONLY the person/company NAME (2-4 words max). Do NOT include addresses, phone numbers, emails, or GSTIN.

{{
  "supplier": "Just the supplier NAME only (e.g., \"XYZ Corp\") - no address/phone/email/GSTIN",
  "supplier_gstin": null,
  "transaction_date": "YYYY-MM-DD or null",
  "schedule_date": null,
  "order_number": null,
{_ITEMS},
{_TAXES},
  "grand_total": 0,
  "currency": "INR",
  "remarks": null
}}''',
	"Quotation": f'''Extract this Quotation/Estimate into JSON. Return ONLY raw JSON, no markdown.

IMPORTANT: For "party_name", extract ONLY the person/company NAME (2-4 words max). Do NOT include addresses, phone numbers, emails, or GSTIN.

{{
  "party_name": "Just the customer NAME only (e.g., \"Amit Patel\") - no address/phone/email/GSTIN",
  "quotation_to": "Customer",
  "customer_gstin": null,
  "transaction_date": "YYYY-MM-DD or null",
  "valid_till": null,
  "quotation_number": null,
{_ITEMS},
{_TAXES},
  "grand_total": 0,
  "currency": "INR",
  "remarks": null
}}''',
}

def _resolve_hint(document_type):
	if not document_type or document_type.strip().lower() == "auto":
		return None
	h = document_type.strip().lower()
	if h in DOCUMENT_TYPE_MAP:
		return DOCUMENT_TYPE_MAP[h]
	for key, val in DOCUMENT_TYPE_MAP.items():
		if key in h:
			return val
	if document_type.strip() in VALID_DOCTYPES:
		return document_type.strip()
	return None

def _parse_ai_json(raw_text):
	text = raw_text.strip()
	text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.MULTILINE)
	text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE)
	text = text.strip()
	try:
		return json.loads(text)
	except json.JSONDecodeError:
		match = re.search(r"\{.*\}", text, re.DOTALL)
		if match:
			try:
				return json.loads(match.group())
			except Exception:
				pass
		raise ValueError(f"Could not parse AI JSON: {text[:300]}")

def _prepare_image(file_base64, mime_type):
	"""Prepare image data for Gemini API - handles base64 cleanup and conversion."""
	from PIL import Image
	
	# Strip data URL prefix if present
	if "," in file_base64:
		file_base64 = file_base64.split(",")[1]
	
	# Add padding if needed
	padding = 4 - (len(file_base64) % 4)
	if padding != 4:
		file_base64 += "=" * padding
	
	try:
		image_bytes = base64.b64decode(file_base64)
		img = Image.open(io.BytesIO(image_bytes))
	except Exception as e:
		raise ValueError(f"Could not decode image: {str(e)}")
	
	# Convert to RGB if necessary (handles PNG with transparency)
	if img.mode != "RGB":
		img = img.convert("RGB")
	
	# Resize if too large (Gemini limits)
	max_size = (1024, 1024)
	img.thumbnail(max_size, Image.Resampling.LANCZOS)
	
	# Convert back to JPEG bytes
	buffer = io.BytesIO()
	img.save(buffer, format="JPEG", quality=85)
	return buffer.getvalue()

def _get_model(settings):
	import google.generativeai as genai
	genai.configure(api_key=settings["api_key"])
	return genai.GenerativeModel(settings.get("model", "gemini-2.5-flash"))

def _part(image_bytes, mime_type="image/jpeg"):
	return {"mime_type": mime_type, "data": image_bytes}

def _ai_detect_doc_type(image_bytes, mime_type, settings):
	model = _get_model(settings)
	response = model.generate_content([_part(image_bytes), _DETECT_TYPE_PROMPT])
	raw = response.text.strip()
	for doctype in VALID_DOCTYPES:
		if doctype.lower() == raw.lower():
			return doctype
	r = raw.lower()
	if "purchase order" in r: return "Purchase Order"
	if "purchase invoice" in r or "vendor bill" in r: return "Purchase Invoice"
	if "sales order" in r: return "Sales Order"
	if "quotation" in r or "quote" in r or "estimate" in r: return "Quotation"
	if "sales invoice" in r: return "Sales Invoice"
	frappe.log_error(f"Doc type unclear, got: '{raw}'. Defaulting Sales Invoice.", "AI Image Service")
	return "Sales Invoice"

def _ai_extract_data(image_bytes, mime_type, doc_type, settings):
	prompt = _EXTRACT_PROMPTS.get(doc_type, _EXTRACT_PROMPTS["Sales Invoice"])
	model = _get_model(settings)
	response = model.generate_content([_part(image_bytes), prompt])
	return _parse_ai_json(response.text)

def process_document_file(file_data, file_type, document_type="auto", filename=None):
	settings = get_settings()
	if not settings.get("api_key"):
		return {"success": False, "message": "AI API key not configured."}
	if file_type not in SUPPORTED_IMAGE_TYPES and file_type != SUPPORTED_PDF_TYPE:
		return {"success": False, "message": f"Unsupported file type '{file_type}'."}
	try:
		# Prepare image bytes for AI processing
		if file_type in SUPPORTED_IMAGE_TYPES:
			image_bytes = _prepare_image(file_data, file_type)
		else:
			# For PDF, decode and process as image if needed, or handle differently
			if "," in file_data:
				file_data = file_data.split(",")[1]
			padding = 4 - (len(file_data) % 4)
			if padding != 4:
				file_data += "=" * padding
			image_bytes = base64.b64decode(file_data)
		
		resolved_type = _resolve_hint(document_type)
		if resolved_type is None:
			resolved_type = _ai_detect_doc_type(image_bytes, file_type, settings)
		frappe.logger().info(f"[AI] Auto-detected '{resolved_type}' from '{filename}'")
		raw_data = _ai_extract_data(image_bytes, file_type, resolved_type, settings)
		return {
			"success": True,
			"doctype": resolved_type,
			"extracted_data": raw_data,
			"message": f"Extracted {resolved_type} from '{filename or 'file'}'",
			"filename": filename,
		}
	except Exception as e:
		frappe.log_error(f"[AI] Extraction failed '{filename}': {e}", "AI Document Service")
		return {"success": False, "message": f"Extraction failed: {str(e)}"}

# Backward-compatibility alias — assistant.py imports this name
def process_document_image(image_data, document_type="auto"):
	"""Alias kept for assistant.py compatibility."""
	return process_document_file(
		file_data=image_data,
		file_type="image/jpeg",
		document_type=document_type,
	)
