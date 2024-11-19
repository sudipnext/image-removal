from flask import Flask, request, render_template, jsonify
from celery import Celery
from rembg import remove
from PIL import Image
import os
import redis
import uuid
from werkzeug.utils import secure_filename

# Flask app configuration
app = Flask(__name__)
app.config.update(
    UPLOAD_FOLDER='static/uploads',
    RESULT_FOLDER='static/results',
    MAX_CONTENT_LENGTH=10 * 1024 * 1024,  # 10MB max file size
    CELERY_BROKER_URL='redis://localhost:6379/0',
    CELERY_RESULT_BACKEND='redis://localhost:6379/0',
    REDIS_URL='redis://localhost:6379/1'
)

# Initialize Redis for status tracking
redis_client = redis.Redis.from_url(app.config['REDIS_URL'])

# Initialize Celery with the correct name
celery = Celery(
    'app',  # Change from 'tasks' to 'app'
    broker=app.config['CELERY_BROKER_URL'],
    backend=app.config['CELERY_RESULT_BACKEND']
)

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULT_FOLDER'], exist_ok=True)

@celery.task(name='app.process_image_task')  # Remove bind=True
def process_image_task(input_path, output_path, task_id):
    try:
        # Update task status
        redis_client.set(f"task_{task_id}", "processing")
        
        # Process image
        input_image = Image.open(input_path)
        
        # Convert to RGB if necessary
        if input_image.mode in ('RGBA', 'LA') or (input_image.mode == 'P' and 'transparency' in input_image.info):
            # Create white background
            background = Image.new('RGB', input_image.size, (255, 255, 255))
            if input_image.mode == 'RGBA':
                background.paste(input_image, mask=input_image.split()[3])
            else:
                background.paste(input_image)
            input_image = background
        elif input_image.mode != 'RGB':
            input_image = input_image.convert('RGB')
        
        # Optimize large images
        max_size = 1500
        if max(input_image.size) > max_size:
            ratio = max_size / max(input_image.size)
            new_size = tuple([int(x * ratio) for x in input_image.size])
            input_image = input_image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Remove background
        output_image = remove(input_image)
        
        # Determine output format based on file extension
        output_format = os.path.splitext(output_path)[1].lower()
        if output_format == '.jpg' or output_format == '.jpeg':
            # Convert to RGB for JPEG
            output_image = output_image.convert('RGB')
            output_image.save(output_path, 'JPEG', quality=95, optimize=True)
        else:
            # Save as PNG for transparency support
            output_path = os.path.splitext(output_path)[0] + '.png'
            output_image.save(output_path, 'PNG', optimize=True)
        
        # Cleanup
        input_image.close()
        output_image.close()
        
        # Update status
        redis_client.set(f"task_{task_id}", "completed")
        redis_client.expire(f"task_{task_id}", 3600)  # Expire in 1 hour
        
        return {
            'status': 'success',
            'output_path': output_path
        }
        
    except Exception as e:
        redis_client.set(f"task_{task_id}", f"error:{str(e)}")
        redis_client.expire(f"task_{task_id}", 3600)
        return {'status': 'error', 'message': str(e)}
    finally:
        # Cleanup input file
        if os.path.exists(input_path):
            os.remove(input_path)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        try:
            # Generate unique IDs
            task_id = str(uuid.uuid4())
            filename = f"{task_id}_{secure_filename(file.filename)}"
            
            # Setup paths
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            output_path = os.path.join(app.config['RESULT_FOLDER'], f'processed_{filename}')
            
            # Save uploaded file
            file.save(input_path)
            
            # Start celery task
            task = process_image_task.delay(input_path, output_path, task_id)
            
            return jsonify({
                'task_id': task_id,
                'result_path': f'/static/results/processed_{filename}'
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/status/<task_id>')
def get_status(task_id):
    try:
        status = redis_client.get(f"task_{task_id}")
        if status:
            return jsonify({
                'status': status.decode(),
                'task_id': task_id
            })
        return jsonify({'status': 'not_found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500



if __name__ == '__main__':
    app.run(debug=True) 