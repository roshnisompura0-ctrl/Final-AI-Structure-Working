# Services Documentation

Detailed documentation of all service modules in my_ai_assistant.

---

## 1. AI Service (`ai_service.py`)

**Purpose:** Handles all AI/LLM interactions using Google Gemini AI.

### Key Functions

#### `get_ai_response(prompt, session_id=None, context=None)`
- **Purpose:** Get AI response for user queries
- **Parameters:**
  - `prompt` (str): User's question
  - `session_id` (str): Optional session for context
  - `context` (dict): Additional context data
- **Returns:** AI response text

#### `detect_doctype_from_question(question)`
- **Purpose:** Determine which ERPNext doctype a user is asking about
- **Parameters:**
  - `question` (str): User's question
- **Returns:** Tuple of (doctype, name) or (None, None)

#### `generate_summary(doctype, data)`
- **Purpose:** Generate human-readable summary of document data
- **Parameters:**
  - `doctype` (str): Document type
  - `data` (dict): Document data
- **Returns:** Formatted summary string

### System Prompt
The AI uses a comprehensive system prompt that includes:
- ERPNext context and role definition
- Doctype descriptions for all supported entities
- Formatting rules (HTML, currency symbols, number formatting)
- Response guidelines for maintaining conversation flow

---

## 2. Data Service (`data_service.py`)

**Purpose:** Safe data retrieval from ERPNext with permission checks.

### Key Functions

#### `get_safe_data(doctype, filters=None, fields=None, limit=10)`
- **Purpose:** Retrieve data respecting user permissions
- **Parameters:**
  - `doctype` (str): Document type
  - `filters` (dict): Query filters
  - `fields` (list): Fields to retrieve
  - `limit` (int): Maximum records
- **Returns:** List of records

#### `get_document_summary(doctype, name)`
- **Purpose:** Get formatted summary of a specific document
- **Parameters:**
  - `doctype` (str): Document type
  - `name` (str): Document name
- **Returns:** Summary text or None

#### `get_list_data(doctype, fields=None, limit=20)`
- **Purpose:** Get list view data for a doctype
- **Parameters:**
  - `doctype` (str): Document type
  - `fields` (list): Fields to include
  - `limit` (int): Maximum records
- **Returns:** Formatted list data

---

## 3. Document Service (`document_service.py`)

**Purpose:** Create ERPNext documents from extracted data.

### Supported Document Types

| Function | Creates | Auto-Creates |
|----------|---------|--------------|
| `_create_sales_invoice()` | Sales Invoice | Customer, Items |
| `_create_purchase_invoice()` | Purchase Invoice | Supplier, Items |
| `_create_sales_order()` | Sales Order | Customer, Items |
| `_create_purchase_order()` | Purchase Order | Supplier, Items |
| `_create_quotation()` | Quotation | Customer, Items |

### Key Functions

#### `create_document_from_extraction(doctype, extracted_data)`
- **Purpose:** Main entry point for document creation
- **Parameters:**
  - `doctype` (str): Target document type
  - `extracted_data` (dict): Data extracted by AI
- **Returns:** Creation result with success flag, name, URL

#### `_resolve_party(party_name, party_doctype)`
- **Purpose:** Find or create Customer/Supplier
- **Features:**
  - Name cleaning (removes addresses, phones, emails)
  - Partial matching
  - Auto-creation if not found
- **Returns:** Party name or created party

#### `_resolve_item_code(item_name, description=None)`
- **Purpose:** Find or create Item
- **Features:**
  - Searches by item_name
  - Creates new item if not found
- **Returns:** Item code

#### `_build_items(raw_items)`
- **Purpose:** Build item rows from extracted data
- **Features:**
  - Calculates amount = qty * rate
  - Handles UOM normalization
  - Adds conversion_factor
- **Returns:** List of item dictionaries

#### `_build_taxes(raw_taxes, company=None)`
- **Purpose:** Build tax rows from extracted data
- **Returns:** List of tax dictionaries

---

## 4. Doctype Service (`doctype_service.py`)

**Purpose:** Doctype detection and discovery.

### Key Functions

#### `detect_doctype_from_question(question)`
- **Purpose:** Determine which doctype a question refers to
- **Parameters:**
  - `question` (str): User's question
- **Returns:** (doctype, name) tuple or (None, None)

#### `get_all_doctypes(category=None)`
- **Purpose:** Get list of all ERPNext doctypes
- **Parameters:**
  - `category` (str): Filter by category
- **Returns:** List of doctype info dictionaries

#### `get_doctype_fields(doctype)`
- **Purpose:** Get field structure for a doctype
- **Parameters:**
  - `doctype` (str): Document type
- **Returns:** Field definitions

#### `find_entity_mention(question, doctype)`
- **Purpose:** Find entity name mentioned in question
- **Parameters:**
  - `question` (str): User's question
  - `doctype` (str): Entity type to search
- **Returns:** Entity name or None

### Document ID Patterns
The service recognizes document IDs with company prefixes:
- `ACC-SINV-YYYY-XXXXX` - Sales Invoice
- `ACC-PINV-YYYY-XXXXX` - Purchase Invoice
- `ACC-SO-YYYY-XXXXX` - Sales Order
- `ACC-PO-YYYY-XXXXX` - Purchase Order
- `ACC-QUOT-YYYY-XXXXX` - Quotation

---

## 5. Entity Service (`entity_service.py`)

**Purpose:** Entity recognition and display name resolution.

### Key Functions

#### `find_entity_mention(question, doctype)`
- **Purpose:** Find if an entity is mentioned in text
- **Parameters:**
  - `question` (str): Text to search
  - `doctype` (str): Entity type
- **Returns:** Entity name or None

#### `get_all_entity_names(doctype, limit=2000)`
- **Purpose:** Get all names for a doctype
- **Parameters:**
  - `doctype` (str): Entity type
  - `limit` (int): Maximum records
- **Returns:** List of {name, display} dictionaries

#### `get_display_name(doctype, name)`
- **Purpose:** Get human-readable display name
- **Parameters:**
  - `doctype` (str): Entity type
  - `name` (str): Entity ID
- **Returns:** Display name (e.g., customer_name for Customer)

#### `similarity(a, b)`
- **Purpose:** Calculate text similarity score
- **Parameters:**
  - `a` (str): First text
  - `b` (str): Second text
- **Returns:** Similarity score (0.0 to 1.0)

---

## 6. Image Service (`image_service.py`)

**Purpose:** Process images and PDFs for document extraction.

### Key Functions

#### `process_document_file(file_data, file_type, document_type="auto", filename=None)`
- **Purpose:** Main entry point for document processing
- **Parameters:**
  - `file_data` (str): Base64-encoded file
  - `file_type` (str): MIME type
  - `document_type` (str): Document type or "auto"
  - `filename` (str): Original filename
- **Returns:** Extraction result with structured data

#### `process_image(file_base64, mime_type, document_type_hint="auto")`
- **Purpose:** Process image file
- **Parameters:**
  - `file_base64` (str): Base64 image data
  - `mime_type` (str): Image MIME type
  - `document_type_hint` (str): Type hint
- **Returns:** Extracted structured data

#### `_ai_detect_doc_type(image_bytes, filename=None)`
- **Purpose:** First pass - detect document type from image
- **Parameters:**
  - `image_bytes` (bytes): Image data
  - `filename` (str): Filename for context
- **Returns:** Detected document type

#### `_ai_extract_data(image_bytes, doc_type)`
- **Purpose:** Second pass - extract structured data
- **Parameters:**
  - `image_bytes` (bytes): Image data
  - `doc_type` (str): Document type
- **Returns:** Extracted data dictionary

#### `_prepare_image(file_base64, mime_type)`
- **Purpose:** Preprocess image for AI processing
- **Processing steps:**
  1. Strip base64 prefix
  2. Add padding if needed
  3. Convert to RGB
  4. Resize to max 1024x1024
  5. Convert to JPEG bytes
- **Returns:** Processed JPEG bytes

### Supported File Types
- **Images:** JPEG, PNG, WebP, GIF, BMP, TIFF
- **Documents:** PDF
- **Max Size:** 4MB (recommended 1-2MB)

### Extraction Prompts
Each document type has a specialized extraction prompt:
- Sales Invoice
- Purchase Invoice
- Sales Order
- Purchase Order
- Quotation

All prompts instruct the AI to:
- Extract clean customer/supplier names (no addresses)
- Extract items with qty, rate, amount, uom
- Extract taxes with description and amount
- Extract document numbers and dates

---

## Service Dependencies

```
ai_service
├── Uses: config/settings.py
├── Uses: data_service.py
├── Uses: doctype_service.py
└── Uses: entity_service.py

data_service
├── Uses: frappe.get_all
└── Uses: frappe.get_doc

document_service
├── Uses: frappe.get_doc
├── Uses: frappe.new_doc
└── Uses: frappe.db

doctype_service
├── Uses: frappe.get_all
└── Uses: frappe.get_meta

entity_service
├── Uses: frappe.get_all
└── Uses: frappe.db.get_value

image_service
├── Uses: config/settings.py
├── Uses: PIL (Image processing)
└── Uses: google.generativeai
```

---

## Configuration Integration

All services use `config/settings.py` for:
- API keys
- Model selection
- Timeout settings
- Feature flags

Configuration hierarchy:
1. Site config (`site_config.json`)
2. Environment variables
3. Default values

---

## Error Handling

All services follow consistent error handling:
- Log errors using `frappe.log_error()`
- Return dict with `success: False` on failure
- Include descriptive error messages
- Never crash the main application

Example error response:
```python
{
    "success": False,
    "message": "Failed to create Sales Invoice: Could not find Customer",
    "error": "Detailed traceback"
}
```
