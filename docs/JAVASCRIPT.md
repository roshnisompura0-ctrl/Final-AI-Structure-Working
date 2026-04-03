# JavaScript Components Documentation

Documentation for frontend JavaScript components.

---

## 1. AI Chat Widget (`ai_chat_widget.js`)

**Location:** `public/js/ai_chat_widget.js`

**Purpose:** Global chat widget that appears on all ERPNext pages.

### Features
- Floating chat button on all pages
- Expandable chat interface
- Real-time AI responses
- Suggested questions
- Document quick links

### Global API

```javascript
// Access the chat widget
frappe.my_ai_chat

// Open chat
frappe.my_ai_chat.open();

// Close chat
frappe.my_ai_chat.close();

// Send message programmatically
frappe.my_ai_chat.send_message('Show me today\'s sales');

// Check if chat is open
frappe.my_ai_chat.is_open;
```

### Events

```javascript
// Listen for chat open
$(document).on('my_ai_chat:opened', () => {
    console.log('Chat opened');
});

// Listen for chat close
$(document).on('my_ai_chat:closed', () => {
    console.log('Chat closed');
});

// Listen for message sent
$(document).on('my_ai_chat:message_sent', (e, message) => {
    console.log('Sent:', message);
});
```

### Configuration

Widget behavior can be customized via site config:

```json
{
    "ai_chat_position": "bottom-right",
    "ai_chat_theme": "light",
    "ai_chat_suggestions": [
        "Show me today's sales",
        "List overdue invoices",
        "Customer summary"
    ]
}
```

---

## 2. AI Document Uploader (`ai_document_uploader.js`)

**Location:** `public/js/ai_document_uploader.js`

**Purpose:** Document upload component with AI extraction.

### Features
- Drag-and-drop file upload
- Document type selection dropdown
- Image preview
- Progress indicator
- Auto-creation of ERPNext documents
- Result display with links

### Global API

```javascript
// Open document uploader
frappe.my_ai_uploader.open({
    document_type: 'Sales Invoice',  // Pre-select type
    on_success: (result) => {
        console.log('Created:', result.name);
        // Navigate to created document
        frappe.set_route('Form', result.doctype, result.name);
    },
    on_error: (error) => {
        console.error('Failed:', error.message);
        frappe.show_alert(error.message, 'red');
    }
});

// Close uploader
frappe.my_ai_uploader.close();
```

### Usage Example

```javascript
// Add button to create Sales Invoice from image
frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
        frm.add_custom_button(__('Upload Image'), () => {
            frappe.my_ai_uploader.open({
                document_type: 'Sales Invoice',
                on_success: (result) => {
                    if (result.success) {
                        frappe.show_alert({
                            message: __('Created: {0}', [result.name]),
                            indicator: 'green'
                        });
                        frappe.set_route('Form', 'Sales Invoice', result.name);
                    }
                }
            });
        });
    }
});
```

### Supported File Types

```javascript
// MIME types accepted
[
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
    'image/bmp',
    'image/tiff',
    'application/pdf'
]

// File extensions
['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.pdf']
```

### Document Types

Dropdown options:
- Auto Detect (AI determines type)
- Sales Invoice
- Purchase Invoice
- Sales Order
- Purchase Order
- Quotation

---

## 3. AI Chat Page (`page/ai_chat/ai_chat.js`)

**Location:** `page/ai_chat/ai_chat.js`

**Purpose:** Full-page AI chat interface.

**Route:** `/app/ai-chat`

### Features
- Larger chat interface
- Chat history sidebar
- Document creation shortcuts
- Settings panel
- Export chat functionality

### Page Structure

```
AI Chat Page
├── Header
│   ├── Title: "AI Business Assistant"
│   └── Actions: Clear, Export, Settings
├── Sidebar (optional)
│   ├── Chat history
│   └── Saved queries
└── Chat Area
    ├── Message history
    ├── Input field
    └── Suggestions
```

### URL Parameters

```
/app/ai-chat?prompt=Show%20sales
/app/ai-chat?doctype=Sales%20Invoice
/app/ai-chat?context={"customer":"ABC"}
```

---

## Component Communication

### Events System

Components communicate via jQuery events:

```javascript
// Document uploaded successfully
$(document).trigger('ai_document:uploaded', {
    doctype: 'Sales Invoice',
    name: 'SINV-2024-00001',
    url: '/app/sales-invoice/SINV-2024-00001'
});

// Chat message received
$(document).trigger('ai_chat:response', {
    message: 'Here are the sales...',
    data: {...},
    suggestions: ['Show more', 'Export']
});
```

---

## Styling

### CSS Classes

```css
/* Chat Widget */
.ai-chat-widget { }
.ai-chat-widget-button { }
.ai-chat-window { }
.ai-chat-message { }
.ai-chat-message-user { }
.ai-chat-message-ai { }

/* Document Uploader */
.ai-uploader-modal { }
.ai-uploader-dropzone { }
.ai-uploader-preview { }
.ai-uploader-progress { }
.ai-uploader-result { }

/* Common */
.ai-suggestion-chip { }
.ai-loading-spinner { }
.ai-error-message { }
```

### Theme Variables

```css
:root {
    --ai-primary-color: #2490ef;
    --ai-secondary-color: #f4f5f6;
    --ai-success-color: #28a745;
    --ai-error-color: #dc3545;
    --ai-border-radius: 8px;
    --ai-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
```

---

## Integration Examples

### Add Upload Button to List View

```javascript
frappe.listview_settings['Sales Invoice'] = {
    onload(listview) {
        listview.page.add_inner_button(__('Upload Image'), () => {
            frappe.my_ai_uploader.open({
                document_type: 'Sales Invoice',
                on_success: (result) => {
                    listview.refresh();
                }
            });
        });
    }
};
```

### Custom Chat Trigger

```javascript
// Add AI chat to custom page
frappe.pages['my-custom-page'].on_page_load = function(wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'My Page'
    });
    
    // Add AI help button
    page.add_inner_button(__('AI Help'), () => {
        frappe.my_ai_chat.open();
        frappe.my_ai_chat.send_message(
            'Help me with this page'
        );
    });
};
```

---

## Error Handling

Components handle errors gracefully:

```javascript
try {
    const result = await frappe.call({
        method: 'my_ai_assistant.api.process_document_image_api',
        args: { image_data: base64 }
    });
    
    if (!result.message.success) {
        frappe.show_alert({
            message: result.message.message,
            indicator: 'red'
        });
    }
} catch (e) {
    frappe.show_alert({
        message: __('Processing failed. Please try again.'),
        indicator: 'red'
    });
}
```

---

## Browser Compatibility

- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

Required features:
- ES6+ JavaScript
- Fetch API
- FileReader API
- CSS Grid/Flexbox
