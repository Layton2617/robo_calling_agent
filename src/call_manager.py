from twilio.rest import Client
from twilio.base.exceptions import TwilioException
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional, Any
from models import Call, Contact, DatabaseManager
from config import config
import time
import threading


class CallManager:

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self.twilio_client = None
        self.active_calls = {}
        self.call_queue = []
        self.is_calling = False
        self._init_twilio_client()

    def _init_twilio_client(self):
        try:
            if not config.twilio.account_sid or not config.twilio.auth_token:
                self.logger.error('Twilio credentials not configured')
                return
            self.twilio_client = Client(config.twilio.account_sid, config.
                twilio.auth_token)
            account = self.twilio_client.api.accounts(config.twilio.account_sid
                ).fetch()
            self.logger.info(
                f'Twilio client initialized successfully. Account: {account.friendly_name}'
                )
        except Exception as e:
            self.logger.error(f'Failed to initialize Twilio client: {str(e)}')
            self.twilio_client = None

    def make_call(self, contact: Contact, call_script: str=None) ->Dict[str,
        Any]:
        if not self.twilio_client:
            return {'success': False, 'message':
                'Twilio client not initialized', 'call_id': None}
        if not config.twilio.phone_number:
            return {'success': False, 'message':
                'Twilio phone number not configured', 'call_id': None}
        script = call_script or config.call.call_script
        try:
            call = Call(contact_id=contact.id, status='pending', start_time
                =datetime.now(), retry_count=0)
            call_id = self.db_manager.add_call(call)
            call.id = call_id
            twiml_url = f'{config.twilio.webhook_url}/twiml/{call_id}'
            twilio_call = self.twilio_client.calls.create(to=contact.
                phone_number, from_=config.twilio.phone_number, url=
                twiml_url, timeout=config.call.call_timeout_seconds, record
                =config.call.record_calls, status_callback=
                f'{config.twilio.webhook_url}/status/{call_id}',
                status_callback_event=['initiated', 'ringing', 'answered',
                'completed'])
            call.call_sid = twilio_call.sid
            call.status = 'initiated'
            self.db_manager.update_call(call)
            self.active_calls[call_id] = {'call': call, 'contact': contact,
                'twilio_call': twilio_call, 'script': script}
            self.logger.info(
                f'Call initiated to {contact.phone_number} (Call ID: {call_id}, SID: {twilio_call.sid})'
                )
            return {'success': True, 'message':
                'Call initiated successfully', 'call_id': call_id,
                'call_sid': twilio_call.sid}
        except TwilioException as e:
            self.logger.error(
                f'Twilio error making call to {contact.phone_number}: {str(e)}'
                )
            if 'call' in locals():
                call.status = 'failed'
                call.end_time = datetime.now()
                self.db_manager.update_call(call)
            return {'success': False, 'message': f'Twilio error: {str(e)}',
                'call_id': call_id if 'call_id' in locals() else None}
        except Exception as e:
            self.logger.error(
                f'Error making call to {contact.phone_number}: {str(e)}')
            if 'call' in locals():
                call.status = 'failed'
                call.end_time = datetime.now()
                self.db_manager.update_call(call)
            return {'success': False, 'message': f'Error: {str(e)}',
                'call_id': call_id if 'call_id' in locals() else None}

    def make_bulk_calls(self, contact_ids: List[int], call_script: str=None,
        delay_seconds: int=2) ->Dict[str, Any]:
        if self.is_calling:
            return {'success': False, 'message':
                'Another calling session is already in progress', 'results': []
                }
        self.is_calling = True
        results = []
        successful_calls = 0
        failed_calls = 0
        try:
            for contact_id in contact_ids:
                contact = self.db_manager.get_contact(contact_id)
                if not contact:
                    results.append({'contact_id': contact_id, 'success': 
                        False, 'message': 'Contact not found'})
                    failed_calls += 1
                    continue
                result = self.make_call(contact, call_script)
                result['contact_id'] = contact_id
                result['phone_number'] = contact.phone_number
                result['name'] = contact.name
                results.append(result)
                if result['success']:
                    successful_calls += 1
                else:
                    failed_calls += 1
                if delay_seconds > 0:
                    time.sleep(delay_seconds)
            self.logger.info(
                f'Bulk calling completed: {successful_calls} successful, {failed_calls} failed'
                )
            return {'success': True, 'message':
                f'Bulk calling completed: {successful_calls} successful, {failed_calls} failed'
                , 'total_calls': len(contact_ids), 'successful_calls':
                successful_calls, 'failed_calls': failed_calls, 'results':
                results}
        except Exception as e:
            self.logger.error(f'Error in bulk calling: {str(e)}')
            return {'success': False, 'message':
                f'Error in bulk calling: {str(e)}', 'results': results}
        finally:
            self.is_calling = False

    def update_call_status(self, call_id: int, status: str, call_sid: str=
        None, duration: int=None) ->bool:
        try:
            call = self.db_manager.get_call(call_id)
            if not call:
                self.logger.error(f'Call not found: {call_id}')
                return False
            call.status = status
            if call_sid:
                call.call_sid = call_sid
            if duration is not None:
                call.duration = duration
            if status in ['completed', 'failed', 'no-answer', 'busy',
                'canceled']:
                call.end_time = datetime.now()
                if call_id in self.active_calls:
                    del self.active_calls[call_id]
            self.db_manager.update_call(call)
            self.logger.info(f'Updated call {call_id} status to {status}')
            return True
        except Exception as e:
            self.logger.error(f'Error updating call status: {str(e)}')
            return False

    def get_call_status(self, call_id: int) ->Optional[Dict[str, Any]]:
        try:
            call = self.db_manager.get_call(call_id)
            if not call:
                return None
            contact = self.db_manager.get_contact(call.contact_id)
            twilio_info = None
            if call.call_sid and self.twilio_client:
                try:
                    twilio_call = self.twilio_client.calls(call.call_sid
                        ).fetch()
                    twilio_info = {'status': twilio_call.status,
                        'direction': twilio_call.direction, 'duration':
                        twilio_call.duration, 'price': twilio_call.price,
                        'price_unit': twilio_call.price_unit}
                except Exception as e:
                    self.logger.warning(
                        f'Could not fetch Twilio call info: {str(e)}')
            return {'call_id': call.id, 'contact_id': call.contact_id,
                'contact_name': contact.name if contact else '',
                'phone_number': contact.phone_number if contact else '',
                'call_sid': call.call_sid, 'status': call.status,
                'duration': call.duration, 'start_time': call.start_time.
                isoformat() if call.start_time else None, 'end_time': call.
                end_time.isoformat() if call.end_time else None,
                'retry_count': call.retry_count, 'recording_url': call.
                recording_url, 'transcript_url': call.transcript_url,
                'twilio_info': twilio_info}
        except Exception as e:
            self.logger.error(f'Error getting call status: {str(e)}')
            return None

    def get_active_calls(self) ->List[Dict[str, Any]]:
        active_call_info = []
        for call_id, call_data in self.active_calls.items():
            call_info = self.get_call_status(call_id)
            if call_info:
                active_call_info.append(call_info)
        return active_call_info

    def get_call_history(self, limit: int=100) ->List[Dict[str, Any]]:
        try:
            calls = self.db_manager.get_all_calls()
            if limit:
                calls = calls[:limit]
            call_history = []
            for call in calls:
                contact = self.db_manager.get_contact(call.contact_id)
                call_info = {'call_id': call.id, 'contact_id': call.
                    contact_id, 'contact_name': contact.name if contact else
                    '', 'phone_number': contact.phone_number if contact else
                    '', 'call_sid': call.call_sid, 'status': call.status,
                    'duration': call.duration, 'start_time': call.
                    start_time.isoformat() if call.start_time else None,
                    'end_time': call.end_time.isoformat() if call.end_time else
                    None, 'retry_count': call.retry_count, 'recording_url':
                    call.recording_url, 'transcript_url': call.transcript_url}
                call_history.append(call_info)
            return call_history
        except Exception as e:
            self.logger.error(f'Error getting call history: {str(e)}')
            return []

    def cancel_call(self, call_id: int) ->Dict[str, Any]:
        try:
            call = self.db_manager.get_call(call_id)
            if not call:
                return {'success': False, 'message': 'Call not found'}
            if call.call_sid and self.twilio_client:
                twilio_call = self.twilio_client.calls(call.call_sid).update(
                    status='canceled')
                call.status = 'canceled'
                call.end_time = datetime.now()
                self.db_manager.update_call(call)
                if call_id in self.active_calls:
                    del self.active_calls[call_id]
                self.logger.info(f'Call {call_id} canceled successfully')
                return {'success': True, 'message':
                    'Call canceled successfully'}
            else:
                return {'success': False, 'message':
                    'Call cannot be canceled (no Twilio SID or client not available)'
                    }
        except Exception as e:
            self.logger.error(f'Error canceling call: {str(e)}')
            return {'success': False, 'message':
                f'Error canceling call: {str(e)}'}

    def get_twiml_response(self, call_id: int) ->str:
        try:
            if call_id in self.active_calls:
                script = self.active_calls[call_id]['script']
            else:
                script = config.call.call_script
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">{script}</Say>
    <Pause length="2"/>
    <Say voice="alice">Thank you for your time. Goodbye.</Say>
</Response>"""
            return twiml
        except Exception as e:
            self.logger.error(f'Error generating TwiML: {str(e)}')
            return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Hello, this is a test call. Thank you for your time.</Say>
</Response>"""
