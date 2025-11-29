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
    let currentMarkdown = '';
    let currentFileName = '';
    let currentChunks = null;

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
            handleFile(e.dataTransfer.files[0]);
        }
    });

    // Click to upload
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    // File input change
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            handleFile(fileInput.files[0]);
        }
    });

    function handleFile(file) {
        selectedFile = file;

        // Update UI - hide drop zone, show preview
        dropZone.style.display = 'none';
        if (filePreview) {
            filePreview.classList.remove('hidden');
        }
        if (fileName) {
            fileName.textContent = file.name;
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

    function resetForm() {
        selectedFile = null;
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
    }

    // Close result button
    if (closeResult) {
        closeResult.addEventListener('click', () => {
            resetForm();
        });
    }

    // Convert button click - now uses API to get content
    convertBtn.addEventListener('click', async () => {
        if (!selectedFile) {
            showMessage('Please select a file first.', 'error');
            return;
        }

        // Check honeypot
        if (honeypot && honeypot.value) {
            showMessage('Invalid request.', 'error');
            return;
        }

        // Prepare form data - always convert to markdown first
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('csrf_token', window.CSRF_TOKEN);
        formData.append('output_format', 'markdown');

        // Update UI
        convertBtn.disabled = true;
        const btnText = convertBtn.querySelector('.btn-text');
        const btnLoading = convertBtn.querySelector('.btn-loading');
        if (btnText) btnText.hidden = true;
        if (btnLoading) {
            btnLoading.hidden = false;
            btnLoading.textContent = 'Preparing...';
        }
        showMessage('Converting your document...', 'success');

        // Simulated progress
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += Math.random() * 10;
            if (progress > 90) progress = 90;
            if (btnLoading) btnLoading.textContent = `Converting... ${Math.round(progress)}%`;
        }, 200);

        try {
            const response = await fetch('/api/convert', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRF-Token': window.CSRF_TOKEN
                }
            });

            clearInterval(progressInterval);
            if (btnLoading) btnLoading.textContent = 'Finalizing...';

            const data = await response.json();

            if (response.ok && data.success) {
                currentMarkdown = data.content;
                currentFileName = data.filename.replace('.md', '');

                // Show result section
                showResultSection();
                hideMessage();

            } else {
                showMessage(data.error || 'Conversion failed. Please try again.', 'error');
            }

        } catch (error) {
            clearInterval(progressInterval);
            console.error('Conversion error:', error);
            showMessage('Network error. Please check your connection.', 'error');
        }

        // Reset button
        convertBtn.disabled = false;
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
});
