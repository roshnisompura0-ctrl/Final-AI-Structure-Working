# Configuration Guide

Complete configuration options for my_ai_assistant.

---

## Configuration Methods

Configuration can be set via:

1. **Site Config** (`site_config.json`) - Recommended for production
2. **Environment Variables** - For Docker/containers
3. **AI Assistant Settings** - UI-based configuration
4. **System Settings** - Fallback defaults

---

## Site Config (`site_config.json`)

Located at: `sites/your-site/site_config.json`

### Required Settings

```json
{
    "ai_assistant_api_key": "your-gemini-api-key-here"
}
```

### Complete Configuration

```json
{
    "ai_assistant_api_key": "AIzaSy...",
    "ai_model": "gemini-2.5-flash",
    "ai_max_tokens": 1000,
    "ai_temperature": 0.3,
    "ai_request_timeout": 60,
    "ai_enable_image_processing": 1,
    "ai_enable_chat_widget": 1,
    "ai_auto_create_entities": 1,
    "ai_log_level": "INFO"
}
```

---

## Configuration Options

### API Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `ai_assistant_api_key` | string | - | Gemini AI API key (required) |
| `ai_model` | string | gemini-2.5-flash | AI model to use |
| `ai_max_tokens` | integer | 1000 | Max tokens per response |
| `ai_temperature` | float | 0.3 | Response creativity (0-1) |
| `ai_request_timeout` | integer | 60 | API timeout in seconds |

### Feature Flags

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `ai_enable_image_processing` | boolean | 1 | Enable document upload |
| `ai_enable_chat_widget` | boolean | 1 | Show chat widget on all pages |
| `ai_auto_create_entities` | boolean | 1 | Auto-create missing customers/items |
| `ai_enable_document_chat` | boolean | 1 | Allow document-specific chat |

### Entity Creation Settings

```json
{
    "ai_customer_defaults": {
        "customer_group": "All Customer Groups",
        "territory": "All Territories",
        "customer_type": "Individual"
    },
    "ai_supplier_defaults": {
        "supplier_group": "All Supplier Groups",
        "supplier_type": "Individual"
    },
    "ai_item_defaults": {
        "item_group": "All Item Groups",
        "stock_uom": "Nos",
        "is_stock_item": 0
    }
}
```

### UI Settings

```json
{
    "ai_chat_position": "bottom-right",
    "ai_chat_theme": "light",
    "ai_chat_button_color": "#2490ef",
    "ai_show_suggestions": 1,
    "ai_suggestion_count": 3,
    "ai_max_file_size": 4194304
}
```

### Logging Settings

```json
{
    "ai_log_level": "INFO",
    "ai_log_retention_days": 30,
    "ai_enable_debug_mode": 0
}
```

---

## Environment Variables

For Docker/container deployments:

```bash
export AI_ASSISTANT_API_KEY="your-api-key"
export AI_MODEL="gemini-2.5-flash"
export AI_MAX_TOKENS="1000"
export AI_TEMPERATURE="0.3"
export AI_TIMEOUT="60"
export AI_ENABLE_IMAGE_PROCESSING="1"
export AI_ENABLE_CHAT_WIDGET="1"
```

---

## AI Assistant Settings Doctype

Navigate to: **AI Assistant Settings** in ERPNext

### Fields

| Field | Type | Description |
|-------|------|-------------|
| API Key | Password | Gemini API key |
| Model | Select | AI model selection |
| Max Tokens | Int | Response length limit |
| Temperature | Float | Creativity level |
| Enable Image Processing | Check | Enable document upload |
| Enable Chat Widget | Check | Show chat button |
| Auto-Create Entities | Check | Create missing customers/items |

---

## Model Options

### Google Gemini Models

| Model | Best For | Max Tokens |
|-------|----------|------------|
| `gemini-2.5-flash` | General use, fast | 8192 |
| `gemini-2.5-flash-latest` | Latest flash model | 8192 |
| `gemini-1.5-pro` | Complex analysis | 8192 |
| `gemini-1.5-flash` | Balanced speed/quality | 8192 |

### Model Selection Guide

- **Document Processing**: `gemini-2.5-flash` (fast, accurate)
- **Chat/Queries**: `gemini-2.5-flash` (conversational)
- **Complex Analysis**: `gemini-1.5-pro` (detailed)

---

## Rate Limiting

Built-in rate limits per user:

```json
{
    "ai_rate_limits": {
        "image_processing": {
            "requests": 10,
            "window": 60
        },
        "chat_queries": {
            "requests": 60,
            "window": 60
        },
        "document_creation": {
            "requests": 30,
            "window": 60
        }
    }
}
```

Override in site config if needed.

---

## Security Configuration

### API Key Security

```json
{
    "ai_mask_api_key_in_logs": 1,
    "ai_encrypt_api_key": 1,
    "ai_key_rotation_days": 90
}
```

### Permission Settings

```json
{
    "ai_restrict_to_roles": ["System Manager", "Sales Manager"],
    "ai_allow_guest_access": 0,
    "ai_log_all_requests": 1
}
```

---

## Multi-Site Configuration

Each site has independent settings:

```json
// sites/site1.local/site_config.json
{
    "ai_assistant_api_key": "key-for-site1",
    "ai_model": "gemini-2.5-flash"
}

// sites/site2.local/site_config.json
{
    "ai_assistant_api_key": "key-for-site2",
    "ai_model": "gemini-1.5-pro"
}
```

---

## Configuration Priority

Settings are loaded in this order (later overrides earlier):

1. Default values (code)
2. Environment variables
3. Site config (`site_config.json`)
4. AI Assistant Settings (database)
5. Runtime overrides

---

## Verification

### Test Configuration

```python
# Bench console
bench --site skydot console

# Test settings
from my_ai_assistant.config.settings import get_settings
print(get_settings())

# Test API key
from my_ai_assistant.config.settings import get_api_key
print(get_api_key())  # Should show masked key
```

### Test Connection

```bash
# API endpoint
curl -X GET \
  https://your-site.com/api/method/my_ai_assistant.api.test_connection_api \
  -H "Authorization: token api_key:api_secret"
```

---

## Common Configurations

### Development

```json
{
    "ai_assistant_api_key": "test-key",
    "ai_model": "gemini-2.5-flash",
    "ai_temperature": 0.5,
    "ai_log_level": "DEBUG",
    "ai_enable_debug_mode": 1
}
```

### Production

```json
{
    "ai_assistant_api_key": "production-key",
    "ai_model": "gemini-2.5-flash",
    "ai_temperature": 0.3,
    "ai_log_level": "INFO",
    "ai_mask_api_key_in_logs": 1,
    "ai_encrypt_api_key": 1,
    "ai_rate_limits": {
        "image_processing": {"requests": 10, "window": 60},
        "chat_queries": {"requests": 60, "window": 60}
    }
}
```

### Minimal (API key only)

```json
{
    "ai_assistant_api_key": "your-key"
}
```

All other settings use defaults.
