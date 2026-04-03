/**
 * ai_document_uploader.js
 * Drop-in ERPNext Page JS for the AI Document Upload widget.
 * Works with: Sales Invoice, Purchase Invoice, Sales Order, Purchase Order, Quotation
 * Supports:   JPEG, PNG, WEBP images  +  PDF files
 *
 * Usage: Include in your ERPNext page or desk widget.
 *        Calls: my_ai_assistant.api.process_document_file_api
 */

frappe.provide("my_ai_assistant");

my_ai_assistant.DocumentUploader = class DocumentUploader {
	/**
	 * @param {Object} opts
	 * @param {string|HTMLElement} opts.wrapper  - CSS selector or DOM element to render into
	 * @param {Function}           opts.onSuccess - Callback(result) after document is created
	 * @param {Function}           opts.onError   - Callback(message) on failure
	 */
	constructor(opts = {}) {
		this.wrapper = typeof opts.wrapper === "string" ? document.querySelector(opts.wrapper) : opts.wrapper;
		this.onSuccess = opts.onSuccess || (() => {});
		this.onError = opts.onError || (() => {});

		this.SUPPORTED_TYPES = {
			"image/jpeg": "JPEG Image",
			"image/png": "PNG Image",
			"image/webp": "WEBP Image",
			"application/pdf": "PDF Document",
		};

		this.DOC_TYPES = [
			{ value: "auto", label: "Auto Detect" },
			{ value: "Sales Invoice", label: "Sales Invoice" },
			{ value: "Purchase Invoice", label: "Purchase Invoice" },
			{ value: "Sales Order", label: "Sales Order" },
			{ value: "Purchase Order", label: "Purchase Order" },
			{ value: "Quotation", label: "Quotation" },
		];

		this._render();
	}

	// ── Render UI ────────────────────────────────────────────────────────────

	_render() {
		if (!this.wrapper) return;

		this.wrapper.innerHTML = `
      <div class="ai-doc-uploader" style="
        font-family: var(--font-stack);
        max-width: 560px;
        margin: 0 auto;
        padding: 0;
      ">
        <!-- Header -->
        <div style="
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 16px;
        ">
          <span style="font-size: 22px;">🤖</span>
          <div>
            <div style="font-weight: 700; font-size: 15px; color: var(--heading-color);">
              AI Document Scanner
            </div>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 1px;">
              Upload an image or PDF — AI will read and create the entry in ERPNext
            </div>
          </div>
        </div>

        <!-- Document Type Selector -->
        <div style="margin-bottom: 12px;">
          <label style="font-size: 12px; font-weight: 600; color: var(--text-muted); display: block; margin-bottom: 4px;">
            Document Type
          </label>
          <select id="ai-doc-type" style="
            width: 100%;
            padding: 7px 10px;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            font-size: 13px;
            background: var(--control-bg);
            color: var(--text-color);
            cursor: pointer;
          ">
            ${this.DOC_TYPES.map((d) => `<option value="${d.value}">${d.label}</option>`).join("")}
          </select>
        </div>

        <!-- Drop Zone -->
        <div id="ai-drop-zone" style="
          border: 2px dashed var(--border-color);
          border-radius: 10px;
          padding: 32px 20px;
          text-align: center;
          cursor: pointer;
          transition: all 0.2s;
          background: var(--card-bg);
          margin-bottom: 12px;
        ">
          <div style="font-size: 36px; margin-bottom: 8px;">📄</div>
          <div style="font-weight: 600; color: var(--heading-color); margin-bottom: 4px;">
            Drop file here or <span style="color: var(--primary);">Browse</span>
          </div>
          <div style="font-size: 12px; color: var(--text-muted);">
            Supports: JPG, PNG, WEBP, PDF
          </div>
          <input type="file" id="ai-file-input" style="display: none;"
            accept=".jpg,.jpeg,.png,.webp,.pdf,image/jpeg,image/png,image/webp,application/pdf" />
        </div>

        <!-- Preview -->
        <div id="ai-preview" style="display: none; margin-bottom: 12px; border-radius: 8px; overflow: hidden; border: 1px solid var(--border-color);">
          <div id="ai-preview-inner" style="max-height: 200px; overflow: hidden; background: #f4f5f7;">
          </div>
          <div id="ai-file-info" style="padding: 8px 12px; font-size: 12px; color: var(--text-muted); background: var(--card-bg); border-top: 1px solid var(--border-color);">
          </div>
        </div>

        <!-- Upload Button -->
        <button id="ai-upload-btn" disabled style="
          width: 100%;
          padding: 10px;
          background: var(--primary);
          color: white;
          border: none;
          border-radius: 8px;
          font-size: 14px;
          font-weight: 600;
          cursor: not-allowed;
          opacity: 0.5;
          transition: all 0.2s;
        ">
          🚀 Scan &amp; Create Entry
        </button>

        <!-- Status -->
        <div id="ai-status" style="display: none; margin-top: 12px; padding: 12px; border-radius: 8px; font-size: 13px;">
        </div>
      </div>
    `;

		this._attachEvents();
	}

	// ── Event Handlers ───────────────────────────────────────────────────────

	_attachEvents() {
		const dropZone = this.wrapper.querySelector("#ai-drop-zone");
		const fileInput = this.wrapper.querySelector("#ai-file-input");
		const uploadBtn = this.wrapper.querySelector("#ai-upload-btn");

		// Click to browse
		dropZone.addEventListener("click", () => fileInput.click());

		// Drag events
		dropZone.addEventListener("dragover", (e) => {
			e.preventDefault();
			dropZone.style.borderColor = "var(--primary)";
			dropZone.style.background = "var(--primary-light)";
		});
		dropZone.addEventListener("dragleave", () => {
			dropZone.style.borderColor = "var(--border-color)";
			dropZone.style.background = "var(--card-bg)";
		});
		dropZone.addEventListener("drop", (e) => {
			e.preventDefault();
			dropZone.style.borderColor = "var(--border-color)";
			dropZone.style.background = "var(--card-bg)";
			const file = e.dataTransfer.files[0];
			if (file) this._loadFile(file);
		});

		// File input change
		fileInput.addEventListener("change", () => {
			if (fileInput.files[0]) this._loadFile(fileInput.files[0]);
		});

		// Upload button
		uploadBtn.addEventListener("click", () => this._upload());
	}

	// ── File Loading ─────────────────────────────────────────────────────────

	_loadFile(file) {
		if (!this.SUPPORTED_TYPES[file.type]) {
			this._showStatus(
				`❌ Unsupported file type: ${file.type || "unknown"}. Please use JPG, PNG, WEBP, or PDF.`,
				"error"
			);
			return;
		}

		this.selectedFile = file;

		const reader = new FileReader();
		reader.onload = (e) => {
			this.fileBase64 = e.target.result.split(",")[1];
			this._showPreview(file, e.target.result);
			this._enableUpload();
		};
		reader.readAsDataURL(file);
	}

	_showPreview(file, dataUrl) {
		const preview = this.wrapper.querySelector("#ai-preview");
		const inner = this.wrapper.querySelector("#ai-preview-inner");
		const info = this.wrapper.querySelector("#ai-file-info");

		if (file.type === "application/pdf") {
			inner.innerHTML = `
        <div style="padding: 20px; text-align: center; color: var(--text-muted);">
          <div style="font-size: 40px;">📋</div>
          <div style="font-weight: 600; margin-top: 4px;">PDF Ready to Scan</div>
        </div>`;
		} else {
			inner.innerHTML = `<img src="${dataUrl}" style="width: 100%; max-height: 200px; object-fit: contain; display: block;" />`;
		}

		const sizeMB = (file.size / 1024 / 1024).toFixed(2);
		info.innerHTML = `📎 <strong>${file.name}</strong> · ${this.SUPPORTED_TYPES[file.type]} · ${sizeMB} MB`;
		preview.style.display = "block";
	}

	_enableUpload() {
		const btn = this.wrapper.querySelector("#ai-upload-btn");
		btn.disabled = false;
		btn.style.opacity = "1";
		btn.style.cursor = "pointer";
	}

	// ── Upload & API Call ────────────────────────────────────────────────────

	_upload() {
		if (!this.fileBase64 || !this.selectedFile) return;

		const docType = this.wrapper.querySelector("#ai-doc-type").value;
		const btn = this.wrapper.querySelector("#ai-upload-btn");

		btn.disabled = true;
		btn.textContent = "⏳ Processing…";
		this._showStatus("🤖 AI is reading your document. This may take a few seconds…", "info");

		frappe.call({
			method: "my_ai_assistant.api.process_document_file_api",
			args: {
				file_data: this.fileBase64,
				file_type: this.selectedFile.type,
				document_type: docType,
				filename: this.selectedFile.name,
			},
			callback: (r) => {
				btn.disabled = false;
				btn.textContent = "🚀 Scan & Create Entry";

				if (r.exc || !r.message) {
					const msg = r.exc || "Unknown error occurred.";
					this._showStatus(`❌ ${msg}`, "error");
					this.onError(msg);
					return;
				}

				const res = r.message;
				if (res.success) {
					this._showSuccess(res);
					this.onSuccess(res);
				} else {
					this._showStatus(`❌ ${res.message}`, "error");
					this.onError(res.message);
				}
			},
			error: (err) => {
				btn.disabled = false;
				btn.textContent = "🚀 Scan & Create Entry";
				const msg = err.message || "Network error. Please try again.";
				this._showStatus(`❌ ${msg}`, "error");
				this.onError(msg);
			},
		});
	}

	// ── Status Display ───────────────────────────────────────────────────────

	_showStatus(message, type = "info") {
		const status = this.wrapper.querySelector("#ai-status");
		const colors = {
			info: { bg: "#ebf4ff", color: "#1a56db", border: "#bfdbfe" },
			error: { bg: "#fef2f2", color: "#dc2626", border: "#fecaca" },
			success: { bg: "#f0fdf4", color: "#16a34a", border: "#bbf7d0" },
		};
		const c = colors[type] || colors.info;
		status.style.display = "block";
		status.style.background = c.bg;
		status.style.color = c.color;
		status.style.border = `1px solid ${c.border}`;
		status.innerHTML = message;
	}

	_showSuccess(res) {
		const total = res.grand_total ? `₹${parseFloat(res.grand_total).toLocaleString("en-IN")}` : "—";
		const party = res.customer || res.supplier || res.party_name || "—";

		this._showStatus(
			`✅ <strong>${res.doctype}</strong> created successfully!<br>
      <div style="margin-top: 8px; display: flex; flex-wrap: wrap; gap: 8px;">
        <span>📄 <strong>${res.name}</strong></span>
        <span>👤 ${party}</span>
        <span>💰 ${total}</span>
      </div>
      <div style="margin-top: 10px;">
        <a href="${res.url}" style="
          display: inline-block;
          padding: 6px 14px;
          background: #16a34a;
          color: white;
          border-radius: 6px;
          text-decoration: none;
          font-size: 12px;
          font-weight: 600;
        ">Open in ERPNext →</a>
      </div>`,
			"success"
		);
	}
};

// ── Auto-init when page loads ─────────────────────────────────────────────

frappe.pages["ai-chat"].on_page_load = function (wrapper) {
	// Mount uploader inside the chat page if a container exists
	const container = wrapper.querySelector(".ai-upload-container");
	if (container) {
		new my_ai_assistant.DocumentUploader({
			wrapper: container,
			onSuccess(res) {
				frappe.show_alert({ message: `✅ ${res.doctype} ${res.name} created!`, indicator: "green" }, 5);
			},
			onError(msg) {
				frappe.show_alert({ message: `❌ ${msg}`, indicator: "red" }, 6);
			},
		});
	}
};