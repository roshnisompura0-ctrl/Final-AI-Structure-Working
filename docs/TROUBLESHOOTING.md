# Troubleshooting Guide

Common issues and solutions for my_ai_assistant.

---

## Quick Diagnostics

### Test Connection

```bash
# Via bench console
bench --site your-site console

from my_ai_assistant.config.settings import get_api_key, get_settings
print("API Key configured:", bool(get_api_key()))
print("Settings:", get_settings())
```

### Check Logs

```bash
# View recent errors
bench --site your-site logview --tail

# View AI-specific errors
bench --site your-site console
frappe.get_all("Error Log", filters={"method": ["like", "%AI%"]}, order_by="creation desc", limit=5)
```

---

## Common Errors

### "API key not configured"

**Cause:** Missing or invalid API key

**Solution:**
```bash
bench --site your-site set-config ai_assistant_api_key "your-key-here"
bench restart
```

Verify:
```python
from my_ai_assistant.config.settings import get_api_key
print(get_api_key())  # Should return key (masked)
```

---

### "Failed to get method for command"

**Cause:** Python indentation/syntax error or missing function

**Solution:**
1. Check file for indentation errors
2. Ensure function is properly defined
3. Run syntax check:
```bash
python -m py_compile apps/my_ai_assistant/my_ai_assistant/api.py
```

4. Restart bench:
```bash
bench restart
```

---

### "Could not find Customer: [Name with address]"

**Cause:** AI extracted full address as customer name

**Solution:** 
- Name cleaning is handled by `_resolve_party()` in `document_service.py`
- Auto-creation is enabled by default
- If still failing, check `ai_auto_create_entities` setting

Verify auto-creation:
```json
{
    "ai_auto_create_entities": 1
}
```

---

### "Unable to process input image"

**Cause:** Image too large, corrupted, or unsupported format

**Solution:**
1. Resize image to max 1024x1024
2. Ensure file is < 4MB
3. Use JPEG/PNG format
4. Check image isn't corrupted

Manual test:
```python
from my_ai_assistant.services.image_service import _prepare_image
with open("test.jpg", "rb") as f:
    base64_data = base64.b64encode(f.read()).decode()
    processed = _prepare_image(base64_data, "image/jpeg")
    print("Processed bytes:", len(processed))
```

---

### "Quotation To must be set first"

**Cause:** Dynamic link validation - party_name set before quotation_to

**Solution:**
- Fixed in `document_service.py` `_create_quotation()`
- Ensure `quotation_to` is hardcoded to "Customer"
- Use two-step creation: create base doc, then add party_name

Current working code:
```python
def _create_quotation(data):
    # Step 1: Create with quotation_to only
    doc = frappe.get_doc({
        "doctype": "Quotation",
        "quotation_to": "Customer",
    })
    doc.insert()
    
    # Step 2: Reload and set party_name
    doc = frappe.get_doc("Quotation", doc.name)
    doc.party_name = party_name
    doc.save()
```

---

### "bad operand type for abs(): 'NoneType'"

**Cause:** Missing numeric value in calculation (likely item amount)

**Solution:**
- Ensure all items have `qty`, `rate`, and `amount` fields
- Check `_build_items()` adds default values:

```python
def _build_items(raw_items):
    for it in raw_items:
        qty = _safe_float(it.get("qty"), 1.0)
        rate = _safe_float(it.get("rate"))
        amount = _safe_float(it.get("amount"), qty * rate)
        # Include amount in item dict
```

---

### "ImportError: cannot import name 'get_settings'"

**Cause:** Missing function in settings.py

**Solution:**
Ensure `config/settings.py` has:
```python
def get_settings():
    return {
        "api_key": get_api_key(),
        "model": get_ai_model(),
        "max_tokens": get_max_tokens(),
        "temperature": get_temperature(),
        "request_timeout": get_request_timeout(),
    }
```

---

### "Failed to create Sales Order: Could not find Customer"

**Cause:** Customer doesn't exist and auto-creation failed

**Solution:**
1. Check `_resolve_party()` function
2. Verify customer creation permissions
3. Check error logs for creation failure details

Debug:
```python
from my_ai_assistant.services.document_service import _resolve_party
result = _resolve_party("Test Customer", "Customer")
print("Resolved to:", result)
```

---

## Document Processing Issues

### Document Type Not Detected Correctly

**Symptom:** Sales Order image creates Sales Invoice

**Solution:**
1. User should manually select document type from dropdown
2. Check `image_service.py` prompts are clear
3. Verify `_ai_detect_doc_type()` function

---

### Extracted Data Missing Fields

**Symptom:** Items or taxes not extracted

**Solution:**
1. Check extraction prompts in `image_service.py`
2. Ensure image quality is good
3. Verify `_EXTRACT_PROMPTS` has complete structure

---

### UOM Errors ("No.'s not found")

**Symptom:** Invalid UOM errors

**Solution:**
- UOM normalization is handled in `_build_items()`
- Common mappings:
  - "No.'s" → "Nos"
  - "Pcs" → "Nos"
  - "Kg" → "Kg"

Add more mappings if needed:
```python
uom_map = {
    "no.'s": "Nos",
    "nos.": "Nos",
    "pcs": "Nos",
    # Add more
}
```

---

## Performance Issues

### Slow Image Processing

**Causes:**
- Large image files (>4MB)
- High resolution images
- Network latency to AI API

**Solutions:**
1. Resize images before upload
2. Use lower quality JPEG (85%)
3. Increase timeout:
```json
{
    "ai_request_timeout": 120
}
```

---

### Chat Response Slow

**Solutions:**
1. Use faster model (`gemini-2.5-flash`)
2. Reduce `ai_max_tokens`
3. Enable caching for repeated queries

---

## Debug Mode

Enable detailed logging:

```json
{
    "ai_log_level": "DEBUG",
    "ai_enable_debug_mode": 1
}
```

View debug output:
```bash
bench --site your-site console
frappe.logger("AI Assistant").debug("Debug message")
```

---

## Reset and Cleanup

### Clear AI Chat History

```sql
-- Run in MariaDB
DELETE FROM `tabAI Chat Session`;
DELETE FROM `tabAI Chat Message`;
```

### Clear Document Processing Cache

```bash
bench --site your-site clear-cache
bench --site your-site clear-website-cache
```

### Restart Services

```bash
bench restart
sudo supervisorctl restart all
```

---

## Getting Help

### Collect Debug Info

```bash
# Export configuration
bench --site your-site console
import json
from my_ai_assistant.config.settings import get_settings
print(json.dumps(get_settings(), indent=2, default=str))

# Export recent errors
errors = frappe.get_all("Error Log", 
    filters={"method": ["like", "%AI%"]},
    fields=["creation", "method", "error"],
    order_by="creation desc",
    limit=10
)
print(json.dumps(errors, indent=2, default=str))
```

### Check Module Version

```python
import my_ai_assistant
print(my_ai_assistant.__version__)
```

---

## FAQ

**Q: Can I use a different AI model?**
A: Yes, set `ai_model` in config. Supports Gemini models.

**Q: How do I add custom doctypes?**
A: Edit `doctype_service.py` to add detection patterns and prompts.

**Q: Can I disable auto-creation?**
A: Yes, set `ai_auto_create_entities: 0` in site config.

**Q: Where are error logs stored?**
A: Check `Error Log` doctype in ERPNext or site logs.

**Q: Can I customize the prompts?**
A: Yes, edit prompts in `ai_service.py` and `image_service.py`.

---

## Contact Support

For unresolved issues:
- GitHub Issues: https://github.com/your-repo/my_ai_assistant/issues
- Email: support@yourcompany.com
- Include: Error logs, configuration (mask API key), steps to reproduce
