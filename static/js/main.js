document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');
    const originalImage = document.getElementById('originalImage');
    const processedImage = document.getElementById('processedImage');
    const downloadBtn = document.getElementById('downloadBtn');

    // Handle file selection button
    uploadBtn.addEventListener('click', () => fileInput.click());

    // Handle file input change
    fileInput.addEventListener('change', handleFileSelect);

    // Handle drag and drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = '#2ecc71';
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = '#3498db';
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = '#3498db';
        const files = e.dataTransfer.files;
        handleFiles(files);
    });

    function handleFileSelect(e) {
        const files = e.target.files;
        handleFiles(files);
    }

    function handleFiles(files) {
        if (files.length > 0) {
            const file = files[0];
            if (file.type.startsWith('image/')) {
                uploadImage(file);
            } else {
                alert('Please upload an image file');
            }
        }
    }

    function uploadImage(file) {
        const formData = new FormData();
        formData.append('file', file);

        // Show loading spinner
        loading.style.display = 'block';
        results.style.display = 'none';

        // Display original image
        const reader = new FileReader();
        reader.onload = function(e) {
            originalImage.src = e.target.result;
        }
        reader.readAsDataURL(file);

        // Upload and process image
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Poll for processed image
            checkProcessedImage(data.result_path, data.task_id);
        })
        .catch(error => {
            alert('Error: ' + error.message);
            loading.style.display = 'none';
        });
    }

    function checkProcessedImage(path, taskId) {
        fetch(`/status/${taskId}`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'completed') {
                    // Image is ready, update UI
                    processedImage.src = path;
                    results.style.display = 'flex';
                    loading.style.display = 'none';
                    downloadBtn.href = path;
                    downloadBtn.download = 'processed_image.png';
                } else if (data.status === 'processing') {
                    // Still processing, check again in 1 second
                    setTimeout(() => checkProcessedImage(path, taskId), 1000);
                } else if (data.status.startsWith('error:')) {
                    // Handle error
                    loading.style.display = 'none';
                    alert('Error processing image: ' + data.status.split(':')[1]);
                }
            })
            .catch(error => {
                console.error('Error checking status:', error);
                loading.style.display = 'none';
                alert('Error checking image status');
            });
    }
}); 