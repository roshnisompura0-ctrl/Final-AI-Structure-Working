import frappe


@frappe.whitelist()
def get_ai_response(prompt, user=None, conversation_history=None):
	from my_ai_assistant.assistant import ask_ai
	return ask_ai(question=prompt, conversation_history=conversation_history or "")


@frappe.whitelist()
def get_doctypes_list(category="transactions"):
	from my_ai_assistant.services.doctype_service import get_doctypes
	return get_doctypes(category)


@frappe.whitelist()
def process_document_image_api(image_data, document_type="auto"):
	from my_ai_assistant.services.document_service import create_document_from_extraction
	from my_ai_assistant.services.image_service import process_document_file
	extraction = process_document_file(file_data=image_data, file_type="image/jpeg", document_type=document_type)
	if not extraction.get("success"):
		return extraction
	creation = create_document_from_extraction(doctype=extraction["doctype"], extracted_data=extraction["extracted_data"])
	return {**extraction, **creation}


@frappe.whitelist()
def process_document_file_api(file_data, file_type, document_type="auto", filename=None):
	from my_ai_assistant.services.document_service import create_document_from_extraction
	from my_ai_assistant.services.image_service import process_document_file
	extraction = process_document_file(file_data=file_data, file_type=file_type, document_type=document_type, filename=filename)
	if not extraction.get("success"):
		return extraction
	creation = create_document_from_extraction(doctype=extraction["doctype"], extracted_data=extraction["extracted_data"])
	return {"success": creation.get("success", False), "doctype": extraction.get("doctype"), "name": creation.get("name"), "url": creation.get("url"), "grand_total": creation.get("grand_total"), "message": creation.get("message") or extraction.get("message"), "extracted_data": extraction.get("extracted_data"), "filename": filename, "customer": creation.get("customer"), "supplier": creation.get("supplier"), "party_name": creation.get("party_name")}


@frappe.whitelist()
def test_connection_api():
	try:
		from my_ai_assistant.config.settings import get_api_key
		api_key = get_api_key()
		if not api_key:
			return {"success": False, "message": "API key not configured."}
		return {"success": True, "message": "Connection OK. API key is configured."}
	except Exception as e:
		frappe.log_error(f"test_connection_api: {e}", "AI Assistant")
		return {"success": False, "message": str(e)}
