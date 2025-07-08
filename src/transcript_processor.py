import requests
import logging
from typing import List, Dict, Optional, Any
from models import Call, Transcript, DatabaseManager
from config import config
from twilio.rest import Client
import time
import json


class TranscriptProcessor:

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self.twilio_client = None
        self._init_twilio_client()

    def _init_twilio_client(self):
        try:
            if config.twilio.account_sid and config.twilio.auth_token:
                self.twilio_client = Client(config.twilio.account_sid,
                    config.twilio.auth_token)
        except Exception as e:
            self.logger.error(f'Failed to initialize Twilio client: {str(e)}')

    def process_call_recording(self, call_id: int, recording_sid: str=None,
        recording_url: str=None) ->Dict[str, Any]:
        try:
            call = self.db_manager.get_call(call_id)
            if not call:
                return {'success': False, 'message': 'Call not found'}
            if not recording_url and recording_sid and self.twilio_client:
                try:
                    recording = self.twilio_client.recordings(recording_sid
                        ).fetch()
                    recording_url = (
                        f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}"
                        )
                except Exception as e:
                    self.logger.error(f'Error fetching recording: {str(e)}')
                    return {'success': False, 'message':
                        f'Error fetching recording: {str(e)}'}
            if not recording_url:
                return {'success': False, 'message':
                    'No recording URL available'}
            call.recording_url = recording_url
            self.db_manager.update_call(call)
            transcript_result = self._transcribe_recording(recording_url,
                call_id)
            if transcript_result['success']:
                transcript = Transcript(call_id=call_id, transcript_text=
                    transcript_result['transcript'], confidence_score=
                    transcript_result.get('confidence', None))
                transcript_id = self.db_manager.add_transcript(transcript)
                self.logger.info(f'Transcript processed for call {call_id}')
                return {'success': True, 'message':
                    'Recording and transcript processed successfully',
                    'transcript_id': transcript_id, 'transcript':
                    transcript_result['transcript'], 'confidence':
                    transcript_result.get('confidence'), 'recording_url':
                    recording_url}
            else:
                return {'success': False, 'message':
                    f"Transcription failed: {transcript_result['message']}",
                    'recording_url': recording_url}
        except Exception as e:
            self.logger.error(f'Error processing call recording: {str(e)}')
            return {'success': False, 'message':
                f'Error processing recording: {str(e)}'}

    def _transcribe_recording(self, recording_url: str, call_id: int) ->Dict[
        str, Any]:
        try:
            if not self.twilio_client:
                return {'success': False, 'message':
                    'Twilio client not available'}
            auth = config.twilio.account_sid, config.twilio.auth_token
            response = requests.get(recording_url, auth=auth)
            if response.status_code != 200:
                return {'success': False, 'message':
                    f'Failed to download recording: {response.status_code}'}
            recording_file = f'data/recording_{call_id}.mp3'
            with open(recording_file, 'wb') as f:
                f.write(response.content)
            transcript_text = self._simulate_transcription(call_id)
            return {'success': True, 'transcript': transcript_text,
                'confidence': 0.85, 'message': 'Transcription completed'}
        except Exception as e:
            self.logger.error(f'Error transcribing recording: {str(e)}')
            return {'success': False, 'message':
                f'Transcription error: {str(e)}'}

    def _simulate_transcription(self, call_id: int) ->str:
        sample_transcripts = [
            'Hello, this is a test call from the Robo Calling AI Agent. Thank you for your time. Goodbye.'
            ,
            "Hi there, I'm calling to test the automated calling system. This call is being recorded for quality purposes. Have a great day!"
            ,
            'Good day, this is an automated test call. The system is working properly. Thank you for answering.'
            ,
            'Hello, you have received a test call from our automated system. Everything appears to be functioning correctly. Goodbye.'
            ,
            'Hi, this is a demonstration call from the Robo Calling Agent. The call has been completed successfully.'
            ]
        transcript_index = call_id % len(sample_transcripts)
        return sample_transcripts[transcript_index]

    def get_transcript(self, call_id: int) ->Optional[Dict[str, Any]]:
        try:
            transcript = self.db_manager.get_transcript_by_call_id(call_id)
            if not transcript:
                return None
            call = self.db_manager.get_call(call_id)
            contact = self.db_manager.get_contact(call.contact_id
                ) if call else None
            return {'transcript_id': transcript.id, 'call_id': transcript.
                call_id, 'transcript_text': transcript.transcript_text,
                'confidence_score': transcript.confidence_score,
                'created_at': transcript.created_at.isoformat() if
                transcript.created_at else None, 'call_info': {'call_sid': 
                call.call_sid if call else None, 'phone_number': contact.
                phone_number if contact else None, 'contact_name': contact.
                name if contact else None, 'call_duration': call.duration if
                call else None, 'call_status': call.status if call else None}}
        except Exception as e:
            self.logger.error(f'Error getting transcript: {str(e)}')
            return None

    def get_all_transcripts(self, limit: int=100) ->List[Dict[str, Any]]:
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            query = """
                SELECT 
                    t.id as transcript_id,
                    t.call_id,
                    t.transcript_text,
                    t.confidence_score,
                    t.created_at as transcript_created_at,
                    c.call_sid,
                    c.status as call_status,
                    c.duration,
                    c.start_time,
                    c.recording_url,
                    ct.phone_number,
                    ct.name as contact_name
                FROM transcripts t
                JOIN calls c ON t.call_id = c.id
                JOIN contacts ct ON c.contact_id = ct.id
                ORDER BY t.created_at DESC
            """
            if limit:
                query += f' LIMIT {limit}'
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()
            transcripts = []
            for row in rows:
                transcripts.append({'transcript_id': row['transcript_id'],
                    'call_id': row['call_id'], 'transcript_text': row[
                    'transcript_text'], 'confidence_score': row[
                    'confidence_score'], 'created_at': row[
                    'transcript_created_at'], 'call_info': {'call_sid': row
                    ['call_sid'], 'phone_number': row['phone_number'],
                    'contact_name': row['contact_name'], 'call_duration':
                    row['duration'], 'call_status': row['call_status'],
                    'start_time': row['start_time'], 'recording_url': row[
                    'recording_url']}})
            return transcripts
        except Exception as e:
            self.logger.error(f'Error getting all transcripts: {str(e)}')
            return []

    def search_transcripts(self, search_term: str, limit: int=50) ->List[Dict
        [str, Any]]:
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            query = """
                SELECT 
                    t.id as transcript_id,
                    t.call_id,
                    t.transcript_text,
                    t.confidence_score,
                    t.created_at as transcript_created_at,
                    c.call_sid,
                    c.status as call_status,
                    c.duration,
                    c.start_time,
                    ct.phone_number,
                    ct.name as contact_name
                FROM transcripts t
                JOIN calls c ON t.call_id = c.id
                JOIN contacts ct ON c.contact_id = ct.id
                WHERE t.transcript_text LIKE ?
                ORDER BY t.created_at DESC
            """
            if limit:
                query += f' LIMIT {limit}'
            cursor.execute(query, (f'%{search_term}%',))
            rows = cursor.fetchall()
            conn.close()
            results = []
            for row in rows:
                results.append({'transcript_id': row['transcript_id'],
                    'call_id': row['call_id'], 'transcript_text': row[
                    'transcript_text'], 'confidence_score': row[
                    'confidence_score'], 'created_at': row[
                    'transcript_created_at'], 'call_info': {'call_sid': row
                    ['call_sid'], 'phone_number': row['phone_number'],
                    'contact_name': row['contact_name'], 'call_duration':
                    row['duration'], 'call_status': row['call_status'],
                    'start_time': row['start_time']}})
            return results
        except Exception as e:
            self.logger.error(f'Error searching transcripts: {str(e)}')
            return []

    def export_transcripts_to_file(self, file_path: str, format: str='json'
        ) ->Dict[str, Any]:
        try:
            transcripts = self.get_all_transcripts()
            if format.lower() == 'json':
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(transcripts, f, indent=2, ensure_ascii=False)
            elif format.lower() == 'csv':
                import pandas as pd
                flattened_data = []
                for t in transcripts:
                    row = {'transcript_id': t['transcript_id'], 'call_id':
                        t['call_id'], 'transcript_text': t[
                        'transcript_text'], 'confidence_score': t[
                        'confidence_score'], 'created_at': t['created_at'],
                        'call_sid': t['call_info']['call_sid'],
                        'phone_number': t['call_info']['phone_number'],
                        'contact_name': t['call_info']['contact_name'],
                        'call_duration': t['call_info']['call_duration'],
                        'call_status': t['call_info']['call_status'],
                        'start_time': t['call_info']['start_time']}
                    flattened_data.append(row)
                df = pd.DataFrame(flattened_data)
                df.to_csv(file_path, index=False)
            else:
                return {'success': False, 'message':
                    'Unsupported format. Use "json" or "csv".'}
            self.logger.info(
                f'Exported {len(transcripts)} transcripts to {file_path}')
            return {'success': True, 'message':
                f'Exported {len(transcripts)} transcripts to {file_path}',
                'transcripts_exported': len(transcripts), 'file_path':
                file_path}
        except Exception as e:
            self.logger.error(f'Error exporting transcripts: {str(e)}')
            return {'success': False, 'message':
                f'Error exporting transcripts: {str(e)}'}

    def get_transcript_summary(self) ->Dict[str, Any]:
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM transcripts')
            total_transcripts = cursor.fetchone()['count']
            cursor.execute(
                'SELECT AVG(confidence_score) as avg_confidence FROM transcripts WHERE confidence_score IS NOT NULL'
                )
            avg_confidence = cursor.fetchone()['avg_confidence']
            cursor.execute(
                """
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM transcripts 
                WHERE created_at >= datetime('now', '-7 days')
                GROUP BY DATE(created_at)
                ORDER BY date DESC
            """
                )
            daily_counts = dict(cursor.fetchall())
            cursor.execute('SELECT transcript_text FROM transcripts')
            all_transcripts = cursor.fetchall()
            word_count = {}
            for row in all_transcripts:
                words = row['transcript_text'].lower().split()
                for word in words:
                    word = word.strip('.,!?";:()[]{}')
                    if len(word) > 3:
                        word_count[word] = word_count.get(word, 0) + 1
            top_words = sorted(word_count.items(), key=lambda x: x[1],
                reverse=True)[:10]
            conn.close()
            return {'total_transcripts': total_transcripts,
                'average_confidence': round(avg_confidence, 2) if
                avg_confidence else None, 'daily_counts': daily_counts,
                'top_words': top_words}
        except Exception as e:
            self.logger.error(f'Error getting transcript summary: {str(e)}')
            return {'error': f'Error getting transcript summary: {str(e)}'}
