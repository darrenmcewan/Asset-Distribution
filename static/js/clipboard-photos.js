(function () {
    function clipboardFileName(file, index) {
        var extensionByType = {
            'image/gif': 'gif',
            'image/jpeg': 'jpg',
            'image/png': 'png',
            'image/webp': 'webp',
        };
        var extension = extensionByType[file.type] || 'png';
        var timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        return 'clipboard-image-' + timestamp + '-' + (index + 1) + '.' + extension;
    }

    function renamedClipboardFile(file, index) {
        if (typeof File !== 'function') {
            return file;
        }
        return new File([file], clipboardFileName(file, index), {
            type: file.type,
            lastModified: Date.now(),
        });
    }

    function filesFromClipboard(event) {
        var clipboardData = event.clipboardData || window.clipboardData;
        if (!clipboardData || !clipboardData.items) {
            return [];
        }

        return Array.from(clipboardData.items)
            .filter(function (item) {
                return item.kind === 'file' && item.type.indexOf('image/') === 0;
            })
            .map(function (item) {
                return item.getAsFile();
            })
            .filter(Boolean)
            .map(renamedClipboardFile);
    }

    function currentFiles(input) {
        return Array.from(input.files || []);
    }

    function setInputFiles(input, files) {
        var dataTransfer = new DataTransfer();
        files.forEach(function (file) {
            dataTransfer.items.add(file);
        });
        input.files = dataTransfer.files;
    }

    function initUploader(uploader) {
        var input = uploader.querySelector('[data-photo-input]');
        var dropzone = uploader.querySelector('[data-photo-dropzone]');
        var preview = uploader.querySelector('[data-photo-preview]');
        var status = uploader.querySelector('[data-photo-status]');
        var form = input && input.form;
        var previewUrls = [];

        if (!input || !dropzone || !preview || !status) {
            return;
        }

        function clearPreviewUrls() {
            previewUrls.forEach(function (url) {
                URL.revokeObjectURL(url);
            });
            previewUrls = [];
        }

        function renderPreview() {
            var files = currentFiles(input);
            clearPreviewUrls();
            preview.innerHTML = '';
            preview.hidden = files.length === 0;
            dropzone.classList.toggle('has-files', files.length > 0);
            status.textContent = files.length
                ? files.length + ' photo' + (files.length === 1 ? '' : 's') + ' ready to upload.'
                : 'You can select multiple photos at once.';

            files.forEach(function (file, index) {
                var item = document.createElement('div');
                item.className = 'clipboard-photo-preview-item';

                var image = document.createElement('img');
                image.alt = '';
                if (file.type.indexOf('image/') === 0) {
                    var url = URL.createObjectURL(file);
                    previewUrls.push(url);
                    image.src = url;
                }

                var name = document.createElement('span');
                name.className = 'clipboard-photo-preview-name';
                name.textContent = file.name;

                var remove = document.createElement('button');
                remove.type = 'button';
                remove.className = 'clipboard-photo-remove';
                remove.dataset.removeIndex = index;
                remove.setAttribute('aria-label', 'Remove ' + file.name);
                remove.textContent = 'x';

                item.appendChild(image);
                item.appendChild(name);
                item.appendChild(remove);
                preview.appendChild(item);
            });
        }

        function addFiles(files) {
            if (!files.length || typeof DataTransfer !== 'function') {
                return;
            }
            setInputFiles(input, currentFiles(input).concat(files));
            renderPreview();
        }

        function handlePaste(event) {
            var pastedImages = filesFromClipboard(event);
            if (!pastedImages.length) {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            addFiles(pastedImages);
            status.textContent = 'Added ' + pastedImages.length + ' pasted image' + (pastedImages.length === 1 ? '.' : 's.');
        }

        input.addEventListener('change', renderPreview);
        dropzone.addEventListener('paste', handlePaste);
        if (form) {
            form.addEventListener('paste', handlePaste);
        }
        preview.addEventListener('click', function (event) {
            var button = event.target.closest('[data-remove-index]');
            if (!button || typeof DataTransfer !== 'function') {
                return;
            }
            var removeIndex = Number(button.dataset.removeIndex);
            var files = currentFiles(input).filter(function (_, index) {
                return index !== removeIndex;
            });
            setInputFiles(input, files);
            renderPreview();
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('[data-clipboard-photo-uploader]').forEach(initUploader);
    });
})();
