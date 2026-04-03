# API Documentation

This document describes all API endpoints available in the my_ai_assistant module.

## Table of Contents

1. [Chat & AI Response](#chat--ai-response)
2. [Document Processing](#document-processing)
3. [Doctype Management](#doctype-management)
4. [Testing & Configuration](#testing--configuration)

---

## Chat & AI Response

### Get AI Response

**Endpoint:** `my_ai_assistant.api.get_ai_response`

**Method:** POST

**Description:** Send a message to the AI assistant and get a response.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `message` | string | Yes | The user's query/message |
| `session_id` | string | No | Optional session ID for context |

**Response:**
```json
{
    "success": true,
    "response": "AI response text",
    "html": "<b>Formatted</b> HTML response",
    "data": {...},
    "suggestions": ["suggestion1", "suggestion2"]
}
```

**Example:**
```javascript
frappe.call({
    method: 'my_ai_assistant.api.get_ai_response',
    args: {
        message: 'Show me sales for last month',
        session_id: 'sess_123'
    },
    callback: (r) => {
        console.log(r.message.response);
    }
});
```

---

## Document Processing

### Process Document Image

**Endpoint:** `my_ai_assistant.api.process_document_image_api`

**Method:** POST

**Description:** Process an image and extract document data.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `image_data` | string | Yes | Base64-encoded image data |
| `document_type` | string | No | Document type or "auto" (default: "auto") |

**Response:**
```json
{
    "success": true,
    "doctype": "Sales Invoice",
    "name": "SINV-2024-00001",
    "url": "/app/sales-invoice/SINV-2024-00001",
    "grand_total": 12500.00,
    "customer": "Customer Name",
    "message": "Sales Invoice draft created: SINV-2024-00001"
}
```

**Example:**
```javascript
frappe.call({
    method: 'my_ai_assistant.api.process_document_image_api',
    args: {
        image_data: 'data:image/jpeg;base64,/9j/4AAQ...',
        document_type: 'Sales Invoice'
    },
    callback: (r) => {
        if (r.message.success) {
            frappe.show_alert(`Created: ${r.message.name}`);
        }
    }
});
```

---

### Process Document File

**Endpoint:** `my_ai_assistant.api.process_document_file_api`

**Method:** POST

**Description:** Process a file (PDF or image) and extract document data.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_data` | string | Yes | Base64-encoded file data |
| `file_type` | string | Yes | MIME type (e.g., "application/pdf", "image/jpeg") |
| `document_type` | string | No | Document type or "auto" (default: "auto") |
| `filename` | string | No | Original filename |

**Response:** Same as `process_document_image_api`

**Example:**
```javascript
frappe.call({
    method: 'my_ai_assistant.api.process_document_file_api',
    args: {
        file_data: base64String,
        file_type: 'application/pdf',
        document_type: 'Purchase Invoice',
        filename: 'bill.pdf'
    },
    callback: (r) => {
        console.log(r.message);
    }
});
```

---

## Doctype Management

### Get Doctypes List

**Endpoint:** `my_ai_assistant.api.get_doctypes_list`

**Method:** GET

**Description:** Get list of available doctypes by category.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | No | Filter category ("transactions", "masters", etc.) |

**Response:**
```json
{
    "success": true,
    "doctypes": [
        {"name": "Sales Invoice", "category": "transactions"},
        {"name": "Customer", "category": "masters"}
    ]
}
```

---

### Get Document Details

**Endpoint:** `my_ai_assistant.api.get_document_details`

**Method:** GET

**Description:** Get detailed information about a specific document.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doctype` | string | Yes | Document type |
| `name` | string | Yes | Document name/ID |

**Response:**
```json
{
    "success": true,
    "document": {...},
    "summary": "Document summary text"
}
```

---

## Testing & Configuration

### Test Connection

**Endpoint:** `my_ai_assistant.api.test_connection_api`

**Method:** GET

**Description:** Test if the AI API key is configured and working.

**Parameters:** None

**Response:**
```json
{
    "success": true,
    "message": "Connection OK. API key is configured."
}
```

**Example:**
```javascript
frappe.call({
    method: 'my_ai_assistant.api.test_connection_api',
    callback: (r) => {
        if (r.message.success) {
            console.log('AI service is ready');
        }
    }
});
```

---

### Get AI Settings

**Endpoint:** `my_ai_assistant.config.settings.get_settings`

**Method:** GET

**Description:** Get current AI configuration settings.

**Response:**
```json
{
    "api_key": "***masked***",
    "model": "gemini-2.5-flash",
    "max_tokens": 1000,
    "temperature": 0.3,
    "request_timeout": 60
}
```

---

## Error Handling

All endpoints return errors in this format:

```json
{
    "success": false,
    "message": "Error description",
    "error": "Detailed error information"
}
```

Common error codes:
- `API key not configured` - Missing API key in settings
- `Failed to create {doctype}` - Document creation failed
- `Could not find {entity}` - Entity not found in database
- `Unable to process input image` - Image processing failed

---

## Rate Limits

- Image processing: 10 requests/minute per user
- Chat queries: 60 requests/minute per user
- Document creation: 30 requests/minute per user

---

## Authentication

All endpoints use Frappe's built-in authentication:
- Requires valid Frappe session
- Respects ERPNext role permissions
- `ignore_permissions=True` used only for auto-creation of entities

---

## JavaScript Integration

### Chat Widget

The AI chat widget is automatically loaded on all ERPNext pages:

```javascript
// Open chat
frappe.my_ai_chat.open();

// Send message programmatically
frappe.my_ai_chat.send_message('Show me today\'s sales');
```

### Document Upload Component

```javascript
// Open document uploader
frappe.my_ai_uploader.open({
    document_type: 'Sales Invoice',
    on_success: (result) => {
        console.log('Created:', result.name);
    }
});
```
