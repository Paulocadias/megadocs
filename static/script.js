/**
 * Document Converter - Frontend JavaScript
 * Handles file upload, drag-drop, conversion, analysis, and chunking
 */

document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const filePreview = document.getElementById('filePreview');
    const fileName = document.getElementById('fileName');
    const removeFile = document.getElementById('removeFile');
    const convertBtn = document.getElementById('convertBtn');
    const message = document.getElementById('message');
    const honeypot = document.getElementById('honeypot');

    // Result section elements
    const resultSection = document.getElementById('resultSection');
    const closeResult = document.getElementById('closeResult');
    const markdownContent = document.getElementById('markdownContent');
    const renderedContent = document.getElementById('renderedContent');
    const viewRaw = document.getElementById('viewRaw');
    const viewRendered = document.getElementById('viewRendered');
    const rawView = document.getElementById('rawView');
    const renderedView = document.getElementById('renderedView');
    const fileInfoName = document.getElementById('fileInfoName');
    const fileInfoTokens = document.getElementById('fileInfoTokens');

    // Action buttons
    const downloadMd = document.getElementById('downloadMd');
    const downloadTxt = document.getElementById('downloadTxt');
    const copyContent = document.getElementById('copyContent');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const chunkBtn = document.getElementById('chunkBtn');

    // Modals
    const analysisModal = document.getElementById('analysisModal');
    const chunkModal = document.getElementById('chunkModal');
    const closeAnalysis = document.getElementById('closeAnalysis');
    const closeChunk = document.getElementById('closeChunk');
    const analysisContent = document.getElementById('analysisContent');
    const chunksContent = document.getElementById('chunksContent');
    const chunkStats = document.getElementById('chunkStats');
    const chunkSize = document.getElementById('chunkSize');
    const chunkOverlap = document.getElementById('chunkOverlap');
    const rechunkBtn = document.getElementById('rechunkBtn');
    const exportChunksBtn = document.getElementById('exportChunksBtn');

    let selectedFile = null;
    let selectedFiles = [];  // Queue for multiple file upload
    let currentMarkdown = '';
    let currentFileName = '';
    let currentChunks = null;
    let rateLimitCountdown = null;  // For rate limit timer

    // Exit early if elements don't exist (non-converter pages)
    if (!dropZone || !fileInput || !convertBtn) {
        return;
    }

    // Drag and drop handlers
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        if (e.dataTransfer.files.length) {
            if (e.dataTransfer.files.length === 1) {
                handleFile(e.dataTransfer.files[0]);
            } else {
                handleMultipleFiles(Array.from(e.dataTransfer.files));
            }
        }
    });

    // Click to upload
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    // File input change (support multiple files)
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            if (fileInput.files.length === 1) {
                handleFile(fileInput.files[0]);
            } else {
                // Multiple files selected - show all
                handleMultipleFiles(Array.from(fileInput.files));
            }
        }
    });

    function handleMultipleFiles(files) {
        if (files.length === 0) return;

        // Store all files for batch processing
        selectedFiles = files;
        selectedFile = files[0];  // Keep first file for compatibility

        // Update UI - hide drop zone, show preview
        dropZone.style.display = 'none';
        if (filePreview) {
            filePreview.classList.remove('hidden');
        }

        // Show list of all files
        if (fileName) {
            if (files.length === 1) {
                fileName.textContent = files[0].name;
            } else {
                fileName.innerHTML = `<strong>${files.length} files:</strong> ${files.map(f => f.name).join(', ')}`;
            }
        }

        convertBtn.disabled = false;
        if (files.length > 1) {
            showMessage(`${files.length} files selected. Click "Ingest Document" to process all.`, 'info');
        } else {
            hideMessage();
        }
    }

    function handleFile(file) {
        selectedFile = file;
        selectedFiles = [file];  // Single file as array

        // Check if file is an image
        const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp'];
        const fileExt = '.' + file.name.split('.').pop().toLowerCase();
        const isImage = imageExtensions.includes(fileExt);

        // Update UI - hide drop zone, show preview
        dropZone.style.display = 'none';
        if (filePreview) {
            filePreview.classList.remove('hidden');
        }
        if (fileName) {
            fileName.textContent = file.name;
        }

        // Show image preview if it's an image
        if (isImage && filePreview) {
            const reader = new FileReader();
            reader.onload = (e) => {
                // Create or update image preview
                let imgPreview = filePreview.querySelector('.image-preview');
                if (!imgPreview) {
                    imgPreview = document.createElement('div');
                    imgPreview.className = 'image-preview';
                    imgPreview.style.cssText = 'margin-top: 1rem; text-align: center;';
                    filePreview.appendChild(imgPreview);
                }
                imgPreview.innerHTML = `
                    <img src="${e.target.result}" alt="Preview" style="max-width: 300px; max-height: 200px; border-radius: 8px; border: 2px solid var(--border);">
                    <p style="margin-top: 0.5rem; font-size: 0.875rem; color: var(--text-light);">📸 Image will be analyzed by AI for RAG indexing</p>
                `;
            };
            reader.readAsDataURL(file);
        } else if (filePreview) {
            // Remove image preview if switching from image to document
            const imgPreview = filePreview.querySelector('.image-preview');
            if (imgPreview) {
                imgPreview.remove();
            }
        }

        convertBtn.disabled = false;
        hideMessage();
    }

    // Remove file button
    if (removeFile) {
        removeFile.addEventListener('click', (e) => {
            e.stopPropagation();
            resetForm();
        });
    }

    function showMessage(text, type) {
        if (!message) return;
        message.textContent = text;
        message.className = 'status-message ' + type;
        message.classList.remove('hidden');
    }

    function hideMessage() {
        if (!message) return;
        message.classList.add('hidden');
    }

    // Rate Limit Indicator functions
    function showRateLimitIndicator(retryAfter = 10) {
        const indicator = document.getElementById('rateLimitIndicator');
        const countdownEl = document.getElementById('countdownTimer');
        const light1 = document.getElementById('light1');
        const light2 = document.getElementById('light2');
        const light3 = document.getElementById('light3');

        if (!indicator) return;

        indicator.classList.add('visible');

        // Clear any existing countdown
        if (rateLimitCountdown) {
            clearInterval(rateLimitCountdown);
        }

        let remaining = retryAfter;

        // Update semaphore lights based on time
        function updateSemaphore() {
            // Reset all lights
            light1.className = 'semaphore-light';
            light2.className = 'semaphore-light';
            light3.className = 'semaphore-light';

            if (remaining > 6) {
                light1.classList.add('red');
            } else if (remaining > 3) {
                light1.classList.add('yellow');
                light2.classList.add('yellow');
            } else if (remaining > 0) {
                light1.classList.add('green');
                light2.classList.add('green');
                light3.classList.add('green');
            }
        }

        // Initial update
        countdownEl.textContent = remaining;
        updateSemaphore();

        // Countdown timer
        rateLimitCountdown = setInterval(() => {
            remaining--;
            countdownEl.textContent = remaining;
            updateSemaphore();

            if (remaining <= 0) {
                clearInterval(rateLimitCountdown);
                hideRateLimitIndicator();
                // Re-enable the convert button
                if (convertBtn) convertBtn.disabled = false;
            }
        }, 1000);
    }

    function hideRateLimitIndicator() {
        const indicator = document.getElementById('rateLimitIndicator');
        if (indicator) {
            indicator.classList.remove('visible');
        }
        if (rateLimitCountdown) {
            clearInterval(rateLimitCountdown);
            rateLimitCountdown = null;
        }
    }

    function resetForm() {
        selectedFile = null;
        selectedFiles = [];
        currentMarkdown = '';
        currentFileName = '';
        fileInput.value = '';

        // Show drop zone, hide preview
        dropZone.style.display = 'block';
        if (filePreview) {
            filePreview.classList.add('hidden');
        }
        if (fileName) {
            fileName.textContent = '';
        }

        // Hide result section
        if (resultSection) {
            resultSection.classList.add('hidden');
        }

        convertBtn.disabled = true;
        hideMessage();
        hideRateLimitIndicator();
    }

    // Close result button
    if (closeResult) {
        closeResult.addEventListener('click', () => {
            resetForm();
        });
    }

    // Helper function to process a single file
    async function processFile(file, options) {
        return new Promise((resolve, reject) => {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('csrf_token', window.CSRF_TOKEN);
            formData.append('output_format', options.outputFormat);
            if (options.removeMacros) formData.append('remove_macros', 'true');
            if (options.stripMetadata) formData.append('strip_metadata', 'true');
            if (options.redactEmails) formData.append('redact_emails', 'true');

            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/convert', true);
            xhr.setRequestHeader('X-CSRF-Token', window.CSRF_TOKEN);

            xhr.upload.onprogress = function(e) {
                if (e.lengthComputable && options.onProgress) {
                    options.onProgress((e.loaded / e.total) * 100);
                }
            };

            xhr.onload = function() {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        resolve(data);
                    } catch (e) {
                        reject(new Error('Invalid server response'));
                    }
                } else if (xhr.status === 429) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        reject(new Error(data.message || 'Rate limit exceeded. Please wait and try again.'));
                    } catch (e) {
                        reject(new Error('Rate limit exceeded'));
                    }
                } else {
                    reject(new Error('Server error: ' + xhr.status));
                }
            };

            xhr.onerror = function() {
                reject(new Error('Network error'));
            };

            xhr.send(formData);
        });
    }

    // Convert button click - supports batch processing
    convertBtn.addEventListener('click', async () => {
        if (selectedFiles.length === 0) {
            showMessage('Please select file(s) first.', 'error');
            return;
        }

        // Check honeypot
        if (honeypot && honeypot.value) {
            showMessage('Invalid request.', 'error');
            return;
        }

        // Get sanitization options
        const removeMacros = document.getElementById('removeMacros')?.checked || false;
        const stripMetadata = document.getElementById('stripMetadata')?.checked || false;
        const redactEmails = document.getElementById('redactEmails')?.checked || false;
        const outputFormat = document.getElementById('outputFormat')?.value || 'markdown';

        // Show validation indicator if any sanitization is enabled
        const validationIndicator = document.getElementById('validationIndicator');
        if (validationIndicator) {
            validationIndicator.style.display = (removeMacros || stripMetadata || redactEmails) ? 'block' : 'none';
        }

        // UI elements
        const btnText = convertBtn.querySelector('.btn-text');
        const btnLoading = convertBtn.querySelector('.btn-loading');
        const progressContainer = document.getElementById('uploadProgressContainer');
        const progressBar = document.getElementById('progressBar');
        const progressPercent = document.getElementById('progressPercent');
        const progressText = document.getElementById('progressText');

        // Disable button and show loading
        convertBtn.disabled = true;
        if (btnText) btnText.hidden = true;
        if (btnLoading) btnLoading.hidden = false;

        const totalFiles = selectedFiles.length;
        let successCount = 0;
        let errorCount = 0;
        let rateLimitHit = false;
        let lastErrorMessage = '';
        let lastSuccessData = null;

        // Process each file
        for (let i = 0; i < totalFiles; i++) {
            const file = selectedFiles[i];
            const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp'];
            const fileExt = '.' + file.name.split('.').pop().toLowerCase();
            const isImage = imageExtensions.includes(fileExt);

            // Update UI for current file
            if (btnLoading) {
                btnLoading.textContent = totalFiles > 1
                    ? `Processing ${i + 1}/${totalFiles}...`
                    : (isImage ? 'Analyzing Visual Data...' : 'Processing...');
            }
            showMessage(
                totalFiles > 1
                    ? `Processing file ${i + 1} of ${totalFiles}: ${file.name}`
                    : (isImage ? 'Analyzing image with AI vision model...' : 'Converting your document...'),
                'success'
            );

            if (progressContainer) {
                progressContainer.style.display = 'block';
                progressBar.style.width = '0%';
                progressPercent.textContent = '0%';
                progressText.textContent = totalFiles > 1 ? `File ${i + 1}/${totalFiles}` : 'Uploading...';
            }

            try {
                const data = await processFile(file, {
                    outputFormat,
                    removeMacros,
                    stripMetadata,
                    redactEmails,
                    onProgress: (percent) => {
                        if (progressBar) progressBar.style.width = percent + '%';
                        if (progressPercent) progressPercent.textContent = Math.round(percent) + '%';
                        if (percent >= 100 && progressText) {
                            progressText.textContent = 'Processing...';
                        }
                    }
                });

                if (data.success) {
                    successCount++;
                    lastSuccessData = data;
                    currentMarkdown = data.content;
                    currentFileName = data.filename.replace('.md', '');
                    localStorage.setItem('sourceType', data.source_type === 'image' ? 'image' : 'document');
                    updateMemoryStatus(data.memory_count || 0);
                } else {
                    errorCount++;
                    console.error(`Failed to process ${file.name}:`, data.error);
                }
            } catch (error) {
                errorCount++;
                lastErrorMessage = error.message;
                console.error(`Error processing ${file.name}:`, error.message);
                // Track rate limit errors
                if (error.message.toLowerCase().includes('rate limit') || error.message.includes('Queue Full')) {
                    rateLimitHit = true;
                    // Extract retry_after from error or use default of 10 seconds
                    let retryAfter = 10;
                    const retryMatch = error.message.match(/(\d+)\s*seconds?/i);
                    if (retryMatch) {
                        retryAfter = parseInt(retryMatch[1], 10);
                    }
                    // Show the semaphore indicator with countdown
                    showRateLimitIndicator(retryAfter);
                }
                // Show error but continue with other files
                if (totalFiles === 1) {
                    showMessage(error.message, 'error');
                }
            }

            // Small delay between files to avoid rate limiting
            if (i < totalFiles - 1) {
                await new Promise(r => setTimeout(r, 500));
            }
        }

        // Hide progress
        if (progressContainer) progressContainer.style.display = 'none';

        // Show final result
        if (successCount > 0) {
            showResultSection();
            if (totalFiles > 1) {
                showMessage(
                    errorCount > 0
                        ? `Processed ${successCount} of ${totalFiles} files. ${errorCount} failed.`
                        : `All ${totalFiles} files processed successfully!`,
                    errorCount > 0 ? 'info' : 'success'
                );
            } else {
                hideMessage();
            }
        } else {
            // Show user-friendly error message based on error type
            if (rateLimitHit) {
                showMessage('Service is busy. Please wait a few seconds and try again.', 'warning');
            } else {
                showMessage(lastErrorMessage || 'Processing failed. Please try again.', 'error');
            }
        }

        // Clear selection
        selectedFile = null;
        selectedFiles = [];
        if (fileInput) fileInput.value = '';
        if (filePreview) filePreview.classList.add('hidden');
        if (fileName) fileName.textContent = '';

        // Reset button
        convertBtn.disabled = true;
        if (btnText) btnText.hidden = false;
        if (btnLoading) btnLoading.hidden = true;
    });

    function showResultSection() {
        if (!resultSection) return;

        // Hide upload area
        dropZone.style.display = 'none';
        if (filePreview) filePreview.classList.add('hidden');

        // Show result section
        resultSection.classList.remove('hidden');

        // Display markdown content
        if (markdownContent) {
            markdownContent.textContent = currentMarkdown;
        }

        // Render markdown preview
        if (renderedContent) {
            renderedContent.innerHTML = renderMarkdown(currentMarkdown);
        }

        // Update file info
        if (fileInfoName) {
            fileInfoName.textContent = currentFileName;
        }

        // Get token count
        getTokenCount(currentMarkdown);

        // Reset view to raw
        if (viewRaw && viewRendered && rawView && renderedView) {
            viewRaw.classList.add('active');
            viewRendered.classList.remove('active');
            rawView.classList.remove('hidden');
            renderedView.classList.add('hidden');
        }
    }

    async function getTokenCount(text) {
        try {
            const response = await fetch('/api/token-count', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': window.CSRF_TOKEN
                },
                body: JSON.stringify({ content: text })
            });
            const data = await response.json();
            if (fileInfoTokens && data.token_count !== undefined) {
                fileInfoTokens.textContent = `${data.token_count.toLocaleString()} tokens`;
            }
        } catch (e) {
            if (fileInfoTokens) {
                fileInfoTokens.textContent = `~${Math.round(text.length / 4).toLocaleString()} tokens (est.)`;
            }
        }
    }

    // Simple markdown renderer
    function renderMarkdown(md) {
        let html = md
            // Headers
            .replace(/^### (.*$)/gim, '<h3>$1</h3>')
            .replace(/^## (.*$)/gim, '<h2>$1</h2>')
            .replace(/^# (.*$)/gim, '<h1>$1</h1>')
            // Bold and italic
            .replace(/\*\*\*(.*?)\*\*\*/gim, '<strong><em>$1</em></strong>')
            .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/gim, '<em>$1</em>')
            // Code blocks
            .replace(/```([\s\S]*?)```/gim, '<pre><code>$1</code></pre>')
            .replace(/`([^`]+)`/gim, '<code>$1</code>')
            // Links
            .replace(/\[([^\]]+)\]\(([^)]+)\)/gim, '<a href="$2" target="_blank">$1</a>')
            // Lists
            .replace(/^\s*-\s+(.*$)/gim, '<li>$1</li>')
            .replace(/^\s*\d+\.\s+(.*$)/gim, '<li>$1</li>')
            // Paragraphs
            .replace(/\n\n/gim, '</p><p>')
            // Line breaks
            .replace(/\n/gim, '<br>');

        return '<p>' + html + '</p>';
    }

    // View toggle
    if (viewRaw) {
        viewRaw.addEventListener('click', () => {
            viewRaw.classList.add('active');
            viewRendered.classList.remove('active');
            rawView.classList.remove('hidden');
            renderedView.classList.add('hidden');
        });
    }

    if (viewRendered) {
        viewRendered.addEventListener('click', () => {
            viewRendered.classList.add('active');
            viewRaw.classList.remove('active');
            renderedView.classList.remove('hidden');
            rawView.classList.add('hidden');
        });
    }

    // Download markdown
    if (downloadMd) {
        downloadMd.addEventListener('click', () => {
            downloadFile(currentMarkdown, currentFileName + '.md', 'text/markdown');
        });
    }

    // Download text
    if (downloadTxt) {
        downloadTxt.addEventListener('click', async () => {
            // Convert markdown to plain text (simple strip)
            const plainText = currentMarkdown
                .replace(/^#{1,6}\s+/gm, '')
                .replace(/\*\*([^*]+)\*\*/g, '$1')
                .replace(/\*([^*]+)\*/g, '$1')
                .replace(/`([^`]+)`/g, '$1')
                .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
                .replace(/```[\s\S]*?```/g, '');
            downloadFile(plainText, currentFileName + '.txt', 'text/plain');
        });
    }

    // Copy to clipboard
    if (copyContent) {
        copyContent.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(currentMarkdown);
                const originalText = copyContent.innerHTML;
                copyContent.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg> Copied!';
                setTimeout(() => {
                    copyContent.innerHTML = originalText;
                }, 2000);
            } catch (e) {
                showMessage('Failed to copy to clipboard', 'error');
            }
        });
    }

    // Analyze in RAG Chat
    // Memory status functions
    async function updateMemoryStatus(count) {
        const memoryStatus = document.getElementById('memoryStatus');
        const memoryCount = document.getElementById('memoryCount');
        const memoryItemsList = document.getElementById('memoryItemsList');
        const finishBtn = document.getElementById('finishBtn');
        
        if (memoryStatus && memoryCount) {
            if (count > 0) {
                memoryStatus.style.display = 'block';
                memoryCount.textContent = count;
                
                // Fetch memory items list
                try {
                    const response = await fetch('/api/memory/status');
                    const data = await response.json();
                    if (data.items && memoryItemsList) {
                        memoryItemsList.innerHTML = data.items.map(item => 
                            `<div style="padding: 0.25rem 0; border-bottom: 1px solid #e2e8f0;">
                                <span style="font-weight: 600;">${item.filename}</span>
                                <span style="color: var(--text-light); font-size: 0.8rem;"> (${item.type})</span>
                            </div>`
                        ).join('');
                    }
                } catch (error) {
                    console.error('Failed to fetch memory status:', error);
                }
                
                if (finishBtn) finishBtn.style.display = 'block';
            } else {
                memoryStatus.style.display = 'none';
                if (finishBtn) finishBtn.style.display = 'none';
            }
        }
    }

    // Reset memory button
    const resetMemoryBtn = document.getElementById('resetMemoryBtn');
    if (resetMemoryBtn) {
        resetMemoryBtn.addEventListener('click', async () => {
            if (!confirm('Are you sure you want to clear all memory? This will remove all uploaded files.')) {
                return;
            }
            
            try {
                const response = await fetch('/api/memory/reset', {
                    method: 'POST',
                    headers: {
                        'X-CSRF-Token': window.CSRF_TOKEN,
                        'Content-Type': 'application/json'
                    }
                });
                
                if (response.ok) {
                    updateMemoryStatus(0);
                    showMessage('Memory cleared', 'success');
                } else {
                    showMessage('Failed to clear memory', 'error');
                }
            } catch (error) {
                console.error('Reset memory error:', error);
                showMessage('Network error', 'error');
            }
        });
    }

    // Finish & Go to RAG button
    const finishBtn = document.getElementById('finishBtn');
    if (finishBtn) {
        finishBtn.addEventListener('click', () => {
            // Store RAG configuration
            const ragModelSelect = document.getElementById('ragModelSelect');
            const ragDomainSelect = document.getElementById('ragDomainSelect');
            if (ragModelSelect) {
                localStorage.setItem('ragModel', ragModelSelect.value);
            }
            if (ragDomainSelect) {
                localStorage.setItem('ragDomain', ragDomainSelect.value);
            }
            window.location.href = '/rag';
        });
    }

    // Load memory status on page load
    document.addEventListener('DOMContentLoaded', async () => {
        try {
            const response = await fetch('/api/memory/status');
            const data = await response.json();
            updateMemoryStatus(data.count || 0);
        } catch (error) {
            console.error('Failed to load memory status:', error);
        }
    });

    const analyzeInRAG = document.getElementById('analyzeInRAG');
    if (analyzeInRAG) {
        analyzeInRAG.addEventListener('click', () => {
            if (!currentMarkdown) {
                showMessage('No document to analyze. Please convert a document first.', 'error');
                return;
            }
            // Store converted markdown in localStorage
            localStorage.setItem('convertedDocument', currentMarkdown);
            localStorage.setItem('documentSource', 'conversion');
            // Redirect to RAG chat page
            window.location.href = '/rag';
        });
    }

    function downloadFile(content, filename, type) {
        const blob = new Blob([content], { type: type });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    // Analyze button
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', async () => {
            if (!currentMarkdown) return;

            analysisModal.classList.remove('hidden');
            analysisContent.innerHTML = '<div class="loading-spinner">Analyzing document...</div>';

            try {
                const response = await fetch('/api/analyze', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': window.CSRF_TOKEN
                    },
                    body: JSON.stringify({ content: currentMarkdown })
                });

                const data = await response.json();

                if (data.success && data.analysis) {
                    analysisContent.innerHTML = renderAnalysis(data.analysis);
                } else {
                    analysisContent.innerHTML = `<div class="error">${data.error || 'Analysis failed'}</div>`;
                }
            } catch (e) {
                analysisContent.innerHTML = '<div class="error">Failed to analyze document</div>';
            }
        });
    }

    function renderAnalysis(analysis) {
        const basic = analysis.basic_stats || {};
        const reading = analysis.reading_time || {};
        const structure = analysis.structure || {};
        const keywords = analysis.keywords || [];
        const readability = analysis.readability || {};
        const language = analysis.language || {};

        let html = `
            <div class="analysis-grid">
                <div class="analysis-card">
                    <h4>Words</h4>
                    <div class="value">${(basic.word_count || 0).toLocaleString()}</div>
                </div>
                <div class="analysis-card">
                    <h4>Characters</h4>
                    <div class="value">${(basic.character_count || 0).toLocaleString()}</div>
                </div>
                <div class="analysis-card">
                    <h4>Sentences</h4>
                    <div class="value">${(basic.sentence_count || 0).toLocaleString()}</div>
                </div>
                <div class="analysis-card">
                    <h4>Reading Time</h4>
                    <div class="value">${reading.display || 'N/A'}</div>
                </div>
            </div>
        `;

        // Language
        if (language.available && language.name) {
            html += `
                <div class="analysis-section">
                    <h4>Language Detected</h4>
                    <p><strong>${language.name}</strong> (${language.code})</p>
                </div>
            `;
        }

        // Keywords
        if (keywords.length > 0) {
            html += `
                <div class="analysis-section">
                    <h4>Top Keywords (TF-IDF)</h4>
                    <div class="keyword-list">
                        ${keywords.map(k => `<span class="keyword-tag">${k.keyword}</span>`).join('')}
                    </div>
                </div>
            `;
        }

        // Readability
        if (readability.available) {
            html += `
                <div class="analysis-section">
                    <h4>Readability</h4>
                    <div class="readability-score">
                        <div class="readability-gauge" style="--score: ${readability.flesch_reading_ease || 0}">
                            <span>${Math.round(readability.flesch_reading_ease || 0)}</span>
                        </div>
                        <div>
                            <strong>${readability.reading_level || 'N/A'}</strong>
                            <p style="font-size: 0.8rem; color: var(--text-light);">Flesch Reading Ease: ${readability.flesch_reading_ease || 'N/A'}</p>
                            <p style="font-size: 0.8rem; color: var(--text-light);">Grade Level: ${readability.flesch_kincaid_grade || 'N/A'}</p>
                        </div>
                    </div>
                </div>
            `;
        }

        // Structure
        if (structure.headers) {
            html += `
                <div class="analysis-section">
                    <h4>Document Structure</h4>
                    <div class="structure-list">
                        <div class="structure-item"><span>Headers</span><span class="count">${structure.headers.total || 0}</span></div>
                        <div class="structure-item"><span>Lists</span><span class="count">${structure.lists?.total_items || 0}</span></div>
                        <div class="structure-item"><span>Code Blocks</span><span class="count">${structure.code?.code_blocks || 0}</span></div>
                        <div class="structure-item"><span>Links</span><span class="count">${structure.links || 0}</span></div>
                        <div class="structure-item"><span>Images</span><span class="count">${structure.images || 0}</span></div>
                        <div class="structure-item"><span>Tables</span><span class="count">${structure.table_rows || 0}</span></div>
                    </div>
                </div>
            `;
        }

        return html;
    }

    // Close analysis modal
    if (closeAnalysis) {
        closeAnalysis.addEventListener('click', () => {
            analysisModal.classList.add('hidden');
        });
    }

    // Chunk button
    if (chunkBtn) {
        chunkBtn.addEventListener('click', () => {
            if (!currentMarkdown) return;
            chunkModal.classList.remove('hidden');
            performChunking();
        });
    }

    async function performChunking() {
        chunksContent.innerHTML = '<div class="loading-spinner">Chunking document...</div>';
        chunkStats.innerHTML = '';

        const size = chunkSize ? chunkSize.value : 512;
        const overlap = chunkOverlap ? chunkOverlap.value : 50;

        try {
            const response = await fetch('/api/chunk', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': window.CSRF_TOKEN
                },
                body: JSON.stringify({
                    content: currentMarkdown,
                    chunk_size: parseInt(size),
                    chunk_overlap: parseInt(overlap),
                    preserve_headers: true
                })
            });

            const data = await response.json();

            if (data.success) {
                currentChunks = data;
                renderChunks(data);
            } else {
                chunksContent.innerHTML = `<div class="error">${data.error || 'Chunking failed'}</div>`;
            }
        } catch (e) {
            chunksContent.innerHTML = '<div class="error">Failed to chunk document</div>';
        }
    }

    function renderChunks(data) {
        const chunks = data.chunks || [];
        const meta = data.metadata || {};

        // Stats
        chunkStats.innerHTML = `
            <span>Total Chunks: <strong>${meta.total_chunks || chunks.length}</strong></span>
            <span>Total Tokens: <strong>${(meta.total_tokens || 0).toLocaleString()}</strong></span>
            <span>Avg Tokens/Chunk: <strong>${meta.average_chunk_tokens || 'N/A'}</strong></span>
            <span>Strategy: <strong>${meta.strategy || 'token'}</strong></span>
        `;

        // Chunks
        let html = '';
        chunks.forEach((chunk, i) => {
            const section = chunk.metadata?.section || '';
            html += `
                <div class="chunk-item">
                    <div class="chunk-header">
                        <span class="chunk-index">Chunk ${chunk.index !== undefined ? chunk.index + 1 : i + 1}</span>
                        <span class="chunk-tokens">${chunk.token_count || '?'} tokens</span>
                    </div>
                    <div class="chunk-text">${escapeHtml(chunk.text)}</div>
                    ${section ? `<div class="chunk-section">Section: ${section}</div>` : ''}
                </div>
            `;
        });

        chunksContent.innerHTML = html || '<p>No chunks generated</p>';
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Re-chunk button
    if (rechunkBtn) {
        rechunkBtn.addEventListener('click', () => {
            performChunking();
        });
    }

    // Export chunks as JSON
    if (exportChunksBtn) {
        exportChunksBtn.addEventListener('click', () => {
            if (!currentChunks) return;
            const json = JSON.stringify(currentChunks, null, 2);
            downloadFile(json, currentFileName + '_chunks.json', 'application/json');
        });
    }

    // Close chunk modal
    if (closeChunk) {
        closeChunk.addEventListener('click', () => {
            chunkModal.classList.add('hidden');
        });
    }

    // Close modals on backdrop click
    if (analysisModal) {
        analysisModal.addEventListener('click', (e) => {
            if (e.target === analysisModal) {
                analysisModal.classList.add('hidden');
            }
        });
    }

    if (chunkModal) {
        chunkModal.addEventListener('click', (e) => {
            if (e.target === chunkModal) {
                chunkModal.classList.add('hidden');
            }
        });
    }

    // Close modals on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (analysisModal && !analysisModal.classList.contains('hidden')) {
                analysisModal.classList.add('hidden');
            }
            if (chunkModal && !chunkModal.classList.contains('hidden')) {
                chunkModal.classList.add('hidden');
            }
        }
    });

    // Update validation indicator when sanitization options change
    function updateValidationIndicator() {
        const removeMacros = document.getElementById('removeMacros')?.checked || false;
        const stripMetadata = document.getElementById('stripMetadata')?.checked || false;
        const redactEmails = document.getElementById('redactEmails')?.checked || false;
        const validationIndicator = document.getElementById('validationIndicator');
        
        if (validationIndicator) {
            if (removeMacros || stripMetadata || redactEmails) {
                validationIndicator.style.display = 'block';
            } else {
                validationIndicator.style.display = 'none';
            }
        }
    }

    // Add event listeners to sanitization checkboxes
    const removeMacrosCheckbox = document.getElementById('removeMacros');
    const stripMetadataCheckbox = document.getElementById('stripMetadata');
    const redactEmailsCheckbox = document.getElementById('redactEmails');
    
    if (removeMacrosCheckbox) {
        removeMacrosCheckbox.addEventListener('change', updateValidationIndicator);
    }
    if (stripMetadataCheckbox) {
        stripMetadataCheckbox.addEventListener('change', updateValidationIndicator);
    }
    if (redactEmailsCheckbox) {
        redactEmailsCheckbox.addEventListener('change', updateValidationIndicator);
    }
});
