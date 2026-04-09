/**
 * Camera Capture Module — My AI Assistant v2.0
 * Plain JS version compatible with Frappe's AMD module system.
 */

(function() {
    "use strict";

    // Store references globally for Frappe integration
    window.AICameraCapture = {
        init: initCameraCapture,
        _openModal: _openCameraModal,
        _triggerUpload: _triggerFileUpload
    };

    var _stream = null;
    var _capturedDataUrl = null;
    var _facingMode = "environment";
    var _currentCallbacks = null;

    /**
     * Initialize camera capture
     * @param {Object} opts
     * @param {Function} opts.onResult - receives API response
     * @param {Function} [opts.onStatus] - receives status updates
     */
    function initCameraCapture(opts) {
        opts = opts || {};
        _currentCallbacks = {
            onResult: opts.onResult || function() {},
            onStatus: opts.onStatus || function() {}
        };

        // Build modal
        _ensureModal();

        // Bind button events using jQuery delegation
        $(document).off('click.ai-camera').on('click.ai-camera', '[data-ai-camera]', function(e) {
            e.preventDefault();
            e.stopPropagation();
            _openCameraModal(_currentCallbacks);
        });

        $(document).off('click.ai-upload').on('click.ai-upload', '[data-ai-upload]', function(e) {
            e.preventDefault();
            e.stopPropagation();
            _triggerFileUpload(_currentCallbacks);
        });
    }

    function _ensureModal() {
        if (document.getElementById("ai-camera-modal")) return;

        var modalHtml = [
            '<div id="ai-camera-modal" role="dialog" aria-modal="true" aria-label="Capture document photo" style="display:none;position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.72);align-items:center;justify-content:center;">',
                '<div id="ai-camera-box" style="background:#fff;border-radius:14px;padding:20px;width:min(480px,95vw);max-height:92vh;display:flex;flex-direction:column;gap:14px;overflow-y:auto;box-shadow:0 8px 32px rgba(0,0,0,0.25);">',
                    '<div style="display:flex;justify-content:space-between;align-items:center;">',
                        '<span style="font-weight:600;font-size:15px;">📷 Scan Document</span>',
                        '<button id="ai-cam-close" style="background:none;border:none;font-size:20px;cursor:pointer;line-height:1;color:#333;">×</button>',
                    '</div>',
                    '<div>',
                        '<label style="font-size:12px;font-weight:500;display:block;margin-bottom:4px;">Document type</label>',
                        '<select id="ai-cam-doctype" style="width:100%;padding:8px 10px;border-radius:8px;font-size:13px;border:1px solid #ccc;background:#fff;">',
                            '<option value="auto">Auto-detect</option>',
                            '<option value="purchase">Purchase Invoice / Bill</option>',
                            '<option value="sales">Sales Invoice</option>',
                            '<option value="visiting_card">Visiting Card / Business Card</option>',
                        '</select>',
                    '</div>',
                    '<div id="ai-cam-stream-wrap" style="display:none;flex-direction:column;gap:10px;">',
                        '<video id="ai-cam-video" autoplay playsinline muted style="width:100%;border-radius:8px;background:#000;max-height:300px;object-fit:cover;"></video>',
                        '<canvas id="ai-cam-canvas" style="display:none;"></canvas>',
                        '<div style="display:flex;gap:10px;">',
                            '<button id="ai-cam-snap" style="flex:1;padding:10px;border-radius:8px;border:none;background:#4CAF50;color:#fff;font-weight:600;cursor:pointer;font-size:14px;">📸 Capture</button>',
                            '<button id="ai-cam-switch" style="padding:10px 14px;border-radius:8px;border:1px solid #ccc;background:none;cursor:pointer;font-size:14px;" title="Switch camera">🔄</button>',
                        '</div>',
                    '</div>',
                    '<div id="ai-cam-preview-wrap" style="display:none;flex-direction:column;gap:10px;">',
                        '<img id="ai-cam-preview-img" alt="Preview" style="width:100%;border-radius:8px;max-height:320px;object-fit:contain;border:1px solid #eee;">',
                        '<div style="display:flex;gap:10px;">',
                            '<button id="ai-cam-send" style="flex:1;padding:10px;border-radius:8px;border:none;background:#5b6fe6;color:#fff;font-weight:600;cursor:pointer;font-size:14px;">✅ Scan & Create</button>',
                            '<button id="ai-cam-retake" style="padding:10px 14px;border-radius:8px;border:1px solid #ccc;background:none;cursor:pointer;font-size:14px;">🔄 Retake</button>',
                        '</div>',
                    '</div>',
                    '<div id="ai-cam-actions" style="display:flex;flex-direction:column;gap:10px;">',
                        '<button id="ai-cam-open-camera" style="padding:12px;border-radius:8px;border:none;background:#5b6fe6;color:#fff;font-weight:600;cursor:pointer;font-size:14px;display:flex;align-items:center;justify-content:center;gap:8px;">📷 Open Camera</button>',
                        '<label style="padding:12px;border-radius:8px;border:1px dashed #aaa;text-align:center;cursor:pointer;font-size:14px;display:flex;align-items:center;justify-content:center;gap:8px;">',
                            '📁 Upload Image / PDF',
                            '<input id="ai-cam-file-input" type="file" accept="image/*,.pdf" style="display:none;">',
                        '</label>',
                    '</div>',
                    '<div id="ai-cam-status" style="display:none;text-align:center;font-size:13px;color:#666;padding:10px 0;"></div>',
                '</div>',
            '</div>'
        ].join('');

        $('body').append(modalHtml);
        _bindModalEvents();
    }

    function _bindModalEvents() {
        // Close modal
        $(document).off('click.ai-cam-close').on('click.ai-cam-close', '#ai-cam-close', function() {
            _closeModal();
        });

        $('#ai-camera-modal').off('click.backdrop').on('click.backdrop', function(e) {
            if (e.target === this) _closeModal();
        });

        // Open camera
        $(document).off('click.ai-cam-open').on('click.ai-cam-open', '#ai-cam-open-camera', function() {
            _startCamera();
        });

        // Snap photo
        $(document).off('click.ai-cam-snap').on('click.ai-cam-snap', '#ai-cam-snap', function() {
            _captureFrame();
        });

        // Switch camera
        $(document).off('click.ai-cam-switch').on('click.ai-cam-switch', '#ai-cam-switch', function() {
            _switchCamera();
        });

        // Retake
        $(document).off('click.ai-cam-retake').on('click.ai-cam-retake', '#ai-cam-retake', function() {
            $('#ai-cam-preview-wrap').hide();
            _capturedDataUrl = null;
            _startCamera();
        });

        // File upload
        $(document).off('change.ai-cam-file').on('change.ai-cam-file', '#ai-cam-file-input', function(e) {
            _onFileSelected(e);
        });

        // Keyboard
        $(document).off('keydown.ai-cam').on('keydown.ai-cam', function(e) {
            if (e.key === "Escape" && $('#ai-camera-modal').is(':visible')) {
                _closeModal();
            }
        });
    }

    async function _startCamera() {
        // Check for HTTPS requirement
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            _setStatus("⚠️ Camera requires HTTPS. Please upload a file instead.");
            return;
        }

        _setStatus("Opening camera…");
        $('#ai-cam-actions').hide();
        $('#ai-cam-stream-wrap').css('display', 'flex');

        try {
            if (_stream) _stopStream();

            _stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: { ideal: _facingMode },
                    width: { ideal: 1920 },
                    height: { ideal: 1080 }
                },
                audio: false
            });

            var video = document.getElementById("ai-cam-video");
            video.srcObject = _stream;
            await video.play();
            _clearStatus();
        } catch (err) {
            _stopStream();
            $('#ai-cam-stream-wrap').hide();
            $('#ai-cam-actions').show();
            _setStatus("❌ Camera error: " + (err.message || err));
        }
    }

    function _captureFrame() {
        var video = document.getElementById("ai-cam-video");
        var canvas = document.getElementById("ai-cam-canvas");

        canvas.width = video.videoWidth || 1280;
        canvas.height = video.videoHeight || 720;

        var ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0);

        _capturedDataUrl = canvas.toDataURL("image/jpeg", 0.88);

        _stopStream();
        $('#ai-cam-stream-wrap').hide();
        _showPreview(_capturedDataUrl, null);
    }

    function _stopStream() {
        if (_stream) {
            _stream.getTracks().forEach(function(t) { t.stop(); });
            _stream = null;
        }
    }

    async function _switchCamera() {
        _facingMode = _facingMode === "environment" ? "user" : "environment";
        await _startCamera();
    }

    function _onFileSelected(e) {
        var file = e.target.files[0];
        if (!file) return;

        $('#ai-cam-actions').hide();
        _setStatus("Reading file…");

        var reader = new FileReader();
        reader.onload = function(ev) {
            _capturedDataUrl = ev.target.result;
            _clearStatus();
            _showPreview(_capturedDataUrl, file.name);
        };
        reader.onerror = function() {
            _setStatus("❌ Could not read the file.");
        };
        reader.readAsDataURL(file);
    }

    function _showPreview(dataUrl, fileName) {
        var previewImg = document.getElementById("ai-cam-preview-img");

        if (dataUrl.startsWith("data:application/pdf")) {
            previewImg.src = "";
            previewImg.alt = "📄 " + (fileName || "PDF document");
            previewImg.style.minHeight = "80px";
        } else {
            previewImg.src = dataUrl;
            previewImg.alt = "Document preview";
            previewImg.style.minHeight = "";
        }

        $('#ai-cam-preview-wrap').css('display', 'flex');

        // Wire send button
        $(document).off('click.ai-cam-send').on('click.ai-cam-send', '#ai-cam-send', function() {
            _submitImage({ dataUrl: _capturedDataUrl, fileName: fileName });
        });
    }

    async function _submitImage(args) {
        var dataUrl = args.dataUrl;
        var fileName = args.fileName;
        
        var doctype = document.getElementById("ai-cam-doctype").value;

        $('#ai-cam-send, #ai-cam-retake').prop('disabled', true);
        _setStatus("🔍 Scanning document with AI…");

        try {
            var result = await frappe.call({
                method: "my_ai_assistant.api.process_document_image_api",
                args: {
                    image_data: dataUrl,
                    file_name: fileName,
                    invoice_type: doctype
                },
                freeze: false
            });

            var data = result.message || result;
            _closeModal();

            // Deliver result back
            if (_currentCallbacks && typeof _currentCallbacks.onResult === 'function') {
                _currentCallbacks.onResult(data, fileName);
            } else if (window.__aiChatWidget && window.__aiChatWidget._handleCameraResult) {
                window.__aiChatWidget._handleCameraResult(data, fileName);
            }
        } catch (err) {
            _setStatus("❌ Error: " + (err.message || "Scan failed. Try again."));
            $('#ai-cam-send, #ai-cam-retake').prop('disabled', false);
        }
    }

    function _openCameraModal(callbacks) {
        _currentCallbacks = callbacks || _currentCallbacks;
        _resetModal();
        $('#ai-camera-modal').css('display', 'flex');

        // Auto-open camera only on HTTPS mobile
        if (window.innerWidth < 768 && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            _startCamera();
        }
    }

    function _triggerFileUpload(callbacks) {
        _currentCallbacks = callbacks || _currentCallbacks;
        _resetModal();
        $('#ai-camera-modal').css('display', 'flex');
        $('#ai-cam-file-input').click();
    }

    function _resetModal() {
        _stopStream();
        _capturedDataUrl = null;
        $('#ai-cam-actions').show();
        $('#ai-cam-stream-wrap, #ai-cam-preview-wrap').hide();
        $('#ai-cam-file-input').val('');
        _clearStatus();
    }

    function _closeModal() {
        _stopStream();
        $('#ai-camera-modal').hide();
        _resetModal();
    }

    function _setStatus(msg) {
        $('#ai-cam-status').text(msg).toggle(!!msg);
        if (_currentCallbacks && _currentCallbacks.onStatus) {
            _currentCallbacks.onStatus(msg);
        }
    }

    function _clearStatus() {
        _setStatus("");
    }

})();
