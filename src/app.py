from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
import os
import logging
from datetime import datetime
import json
from models import DatabaseManager
from phone_list_manager import PhoneListManager
from call_manager import CallManager
from retry_handler import RetryHandler
from transcript_processor import TranscriptProcessor
from config import config
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')
UPLOAD_FOLDER = 'data/uploads'
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('data', exist_ok=True)
os.makedirs('logs', exist_ok=True)
logging.basicConfig(level=getattr(logging, config.log_level), format=
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=[
    logging.FileHandler(config.log_file), logging.StreamHandler()])
db_manager = DatabaseManager()
phone_manager = PhoneListManager(db_manager)
call_manager = CallManager(db_manager)
retry_handler = RetryHandler(db_manager, call_manager)
transcript_processor = TranscriptProcessor(db_manager)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower(
        ) in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    try:
        call_summary = db_manager.get_call_summary()
        contacts_summary = phone_manager.get_contacts_summary()
        retry_summary = retry_handler.get_retry_summary()
        transcript_summary = transcript_processor.get_transcript_summary()
        return render_template('dashboard.html', call_summary=call_summary,
            contacts_summary=contacts_summary, retry_summary=retry_summary,
            transcript_summary=transcript_summary)
    except Exception as e:
        app.logger.error(f'Error loading dashboard: {str(e)}')
        return render_template('error.html', error=str(e))


@app.route('/contacts')
def contacts():
    try:
        contacts_data = phone_manager.get_contacts_summary()
        return render_template('contacts.html', contacts=contacts_data[
            'contacts'])
    except Exception as e:
        app.logger.error(f'Error loading contacts: {str(e)}')
        return render_template('error.html', error=str(e))


@app.route('/calls')
def calls():
    try:
        call_history = call_manager.get_call_history(limit=100)
        return render_template('calls.html', calls=call_history)
    except Exception as e:
        app.logger.error(f'Error loading calls: {str(e)}')
        return render_template('error.html', error=str(e))


@app.route('/transcripts')
def transcripts():
    try:
        all_transcripts = transcript_processor.get_all_transcripts(limit=50)
        return render_template('transcripts.html', transcripts=all_transcripts)
    except Exception as e:
        app.logger.error(f'Error loading transcripts: {str(e)}')
        return render_template('error.html', error=str(e))


@app.route('/settings')
def settings():
    try:
        return render_template('settings.html', config=config)
    except Exception as e:
        app.logger.error(f'Error loading settings: {str(e)}')
        return render_template('error.html', error=str(e))


@app.route('/api/contacts/upload', methods=['POST'])
def upload_contacts():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file provided'}
                ), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}
                ), 400
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'{timestamp}_{filename}'
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            result = phone_manager.upload_contacts_from_file(file_path)
            try:
                os.remove(file_path)
            except:
                pass
            return jsonify(result)
        else:
            return jsonify({'success': False, 'message': 'Invalid file type'}
                ), 400
    except Exception as e:
        app.logger.error(f'Error uploading contacts: {str(e)}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/contacts/add', methods=['POST'])
def add_contact():
    try:
        data = request.get_json()
        phone = data.get('phone', '').strip()
        name = data.get('name', '').strip()
        if not phone:
            return jsonify({'success': False, 'message':
                'Phone number is required'}), 400
        result = phone_manager.add_single_contact(phone, name)
        return jsonify(result)
    except Exception as e:
        app.logger.error(f'Error adding contact: {str(e)}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/contacts', methods=['GET'])
def get_contacts():
    try:
        result = phone_manager.get_contacts_summary()
        return jsonify(result)
    except Exception as e:
        app.logger.error(f'Error getting contacts: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/calls/start', methods=['POST'])
def start_calls():
    try:
        data = request.get_json()
        contact_ids = data.get('contact_ids', [])
        call_script = data.get('call_script', '')
        delay_seconds = data.get('delay_seconds', 2)
        if not contact_ids:
            return jsonify({'success': False, 'message':
                'No contacts selected'}), 400
        if call_script:
            config.update_call_script(call_script)
        result = call_manager.make_bulk_calls(contact_ids, call_script,
            delay_seconds)
        return jsonify(result)
    except Exception as e:
        app.logger.error(f'Error starting calls: {str(e)}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/calls/status/<int:call_id>', methods=['GET'])
def get_call_status(call_id):
    try:
        result = call_manager.get_call_status(call_id)
        if result:
            return jsonify(result)
        else:
            return jsonify({'error': 'Call not found'}), 404
    except Exception as e:
        app.logger.error(f'Error getting call status: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/calls/history', methods=['GET'])
def get_call_history():
    try:
        limit = request.args.get('limit', 100, type=int)
        result = call_manager.get_call_history(limit)
        return jsonify(result)
    except Exception as e:
        app.logger.error(f'Error getting call history: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/calls/active', methods=['GET'])
def get_active_calls():
    try:
        result = call_manager.get_active_calls()
        return jsonify(result)
    except Exception as e:
        app.logger.error(f'Error getting active calls: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/retry/schedule/<int:call_id>', methods=['POST'])
def schedule_retry(call_id):
    try:
        data = request.get_json() or {}
        delay_minutes = data.get('delay_minutes')
        result = retry_handler.schedule_retry(call_id, delay_minutes)
        return jsonify(result)
    except Exception as e:
        app.logger.error(f'Error scheduling retry: {str(e)}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/retry/failed', methods=['POST'])
def retry_failed_calls():
    try:
        data = request.get_json() or {}
        status_filter = data.get('status_filter')
        result = retry_handler.retry_failed_calls(status_filter)
        return jsonify(result)
    except Exception as e:
        app.logger.error(f'Error retrying failed calls: {str(e)}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/retry/status/<int:call_id>', methods=['GET'])
def get_retry_status(call_id):
    try:
        result = retry_handler.get_retry_status(call_id)
        return jsonify(result)
    except Exception as e:
        app.logger.error(f'Error getting retry status: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/transcripts', methods=['GET'])
def get_transcripts():
    try:
        limit = request.args.get('limit', 50, type=int)
        search = request.args.get('search', '')
        if search:
            result = transcript_processor.search_transcripts(search, limit)
        else:
            result = transcript_processor.get_all_transcripts(limit)
        return jsonify(result)
    except Exception as e:
        app.logger.error(f'Error getting transcripts: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/transcripts/<int:call_id>', methods=['GET'])
def get_transcript(call_id):
    try:
        result = transcript_processor.get_transcript(call_id)
        if result:
            return jsonify(result)
        else:
            return jsonify({'error': 'Transcript not found'}), 404
    except Exception as e:
        app.logger.error(f'Error getting transcript: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/reports/export', methods=['POST'])
def export_data():
    try:
        data = request.get_json()
        export_type = data.get('type', 'transcripts')
        format_type = data.get('format', 'json')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if export_type == 'transcripts':
            filename = f'transcripts_export_{timestamp}.{format_type}'
            file_path = os.path.join('data', filename)
            result = transcript_processor.export_transcripts_to_file(file_path,
                format_type)
        elif export_type == 'contacts':
            filename = f'contacts_export_{timestamp}.csv'
            file_path = os.path.join('data', filename)
            result = {'success': phone_manager.export_contacts_to_csv(
                file_path)}
        else:
            return jsonify({'success': False, 'message': 'Invalid export type'}
                ), 400
        if result.get('success', False):
            return send_file(file_path, as_attachment=True, download_name=
                filename)
        else:
            return jsonify(result), 500
    except Exception as e:
        app.logger.error(f'Error exporting data: {str(e)}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/webhook/twiml/<int:call_id>', methods=['POST', 'GET'])
def twiml_response(call_id):
    try:
        twiml = call_manager.get_twiml_response(call_id)
        return twiml, 200, {'Content-Type': 'application/xml'}
    except Exception as e:
        app.logger.error(f'Error generating TwiML: {str(e)}')
        return (
            """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Hello, this is a test call. Thank you.</Say>
</Response>"""
            , 200, {'Content-Type': 'application/xml'})


@app.route('/webhook/status/<int:call_id>', methods=['POST'])
def call_status_webhook(call_id):
    try:
        call_status = request.form.get('CallStatus')
        call_sid = request.form.get('CallSid')
        call_duration = request.form.get('CallDuration')
        recording_url = request.form.get('RecordingUrl')
        duration = int(call_duration) if call_duration else None
        call_manager.update_call_status(call_id, call_status, call_sid,
            duration)
        if recording_url and config.call.transcribe_calls:
            transcript_processor.process_call_recording(call_id,
                recording_url=recording_url)
        if call_status in ['failed', 'no-answer', 'busy']:
            retry_handler.schedule_retry(call_id)
        return 'OK', 200
    except Exception as e:
        app.logger.error(f'Error handling status webhook: {str(e)}')
        return 'Error', 500


@app.route('/webhook/recording/<int:call_id>', methods=['POST'])
def recording_webhook(call_id):
    try:
        recording_sid = request.form.get('RecordingSid')
        recording_url = request.form.get('RecordingUrl')
        if recording_url and config.call.transcribe_calls:
            transcript_processor.process_call_recording(call_id,
                recording_sid, recording_url)
        return 'OK', 200
    except Exception as e:
        app.logger.error(f'Error handling recording webhook: {str(e)}')
        return 'Error', 500


@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error='Page not found'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error='Internal server error'), 500


if __name__ == '__main__':
    if not config.validate():
        print(
            'Configuration validation failed. Please check your environment variables.'
            )
        exit(1)
    print('Starting Robo Calling AI Agent...')
    print(
        f'Dashboard will be available at: http://{config.flask_host}:{config.flask_port}'
        )
    app.run(host=config.flask_host, port=config.flask_port, debug=config.
        flask_debug)
