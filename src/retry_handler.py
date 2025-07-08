from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional, Any
from models import Call, Contact, RetryAttempt, DatabaseManager
from config import config
import time
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger


class RetryHandler:

    def __init__(self, db_manager: DatabaseManager, call_manager):
        self.db_manager = db_manager
        self.call_manager = call_manager
        self.logger = logging.getLogger(__name__)
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self.retry_statuses = {'failed': config.retry.retry_on_failed,
            'no-answer': config.retry.retry_on_no_answer, 'busy': config.
            retry.retry_on_busy}

    def should_retry_call(self, call: Call) ->bool:
        if call.retry_count >= config.retry.max_attempts:
            self.logger.info(
                f'Call {call.id} has reached max retry attempts ({config.retry.max_attempts})'
                )
            return False
        if call.status not in self.retry_statuses:
            self.logger.info(
                f"Call {call.id} status '{call.status}' is not retry-eligible")
            return False
        if not self.retry_statuses.get(call.status, False):
            self.logger.info(f"Retry disabled for status '{call.status}'")
            return False
        return True

    def schedule_retry(self, call_id: int, delay_minutes: int=None) ->Dict[
        str, Any]:
        try:
            call = self.db_manager.get_call(call_id)
            if not call:
                return {'success': False, 'message': 'Call not found'}
            if not self.should_retry_call(call):
                return {'success': False, 'message':
                    'Call is not eligible for retry'}
            delay = delay_minutes or config.retry.retry_delay_minutes
            retry_time = datetime.now() + timedelta(minutes=delay)
            job_id = f'retry_call_{call_id}_{call.retry_count + 1}'
            self.scheduler.add_job(func=self._execute_retry, trigger=
                DateTrigger(run_date=retry_time), args=[call_id], id=job_id,
                replace_existing=True)
            retry_attempt = RetryAttempt(call_id=call_id, attempt_number=
                call.retry_count + 1, status='scheduled', attempted_at=
                retry_time, failure_reason=f'Retry scheduled for {call.status}'
                )
            self.db_manager.add_retry_attempt(retry_attempt)
            self.logger.info(
                f'Retry scheduled for call {call_id} at {retry_time}')
            return {'success': True, 'message':
                f"Retry scheduled for {retry_time.strftime('%Y-%m-%d %H:%M:%S')}"
                , 'retry_time': retry_time.isoformat(), 'job_id': job_id}
        except Exception as e:
            self.logger.error(
                f'Error scheduling retry for call {call_id}: {str(e)}')
            return {'success': False, 'message':
                f'Error scheduling retry: {str(e)}'}

    def _execute_retry(self, call_id: int):
        try:
            self.logger.info(f'Executing retry for call {call_id}')
            call = self.db_manager.get_call(call_id)
            if not call:
                self.logger.error(f'Call {call_id} not found for retry')
                return
            contact = self.db_manager.get_contact(call.contact_id)
            if not contact:
                self.logger.error(
                    f'Contact {call.contact_id} not found for retry')
                return
            call.retry_count += 1
            self.db_manager.update_call(call)
            result = self.call_manager.make_call(contact)
            retry_attempt = RetryAttempt(call_id=call_id, attempt_number=
                call.retry_count, status='completed' if result['success'] else
                'failed', attempted_at=datetime.now(), failure_reason=
                result.get('message', '') if not result['success'] else None)
            self.db_manager.add_retry_attempt(retry_attempt)
            if result['success']:
                self.logger.info(f'Retry successful for call {call_id}')
            else:
                self.logger.warning(
                    f"Retry failed for call {call_id}: {result['message']}")
                if self.should_retry_call(call):
                    self.schedule_retry(call_id)
        except Exception as e:
            self.logger.error(
                f'Error executing retry for call {call_id}: {str(e)}')

    def retry_failed_calls(self, status_filter: List[str]=None) ->Dict[str, Any
        ]:
        try:
            if status_filter:
                failed_calls = []
                for status in status_filter:
                    failed_calls.extend(self.db_manager.get_calls_by_status
                        (status))
            else:
                failed_calls = []
                for status in self.retry_statuses.keys():
                    if self.retry_statuses[status]:
                        failed_calls.extend(self.db_manager.
                            get_calls_by_status(status))
            eligible_calls = [call for call in failed_calls if self.
                should_retry_call(call)]
            if not eligible_calls:
                return {'success': True, 'message':
                    'No calls eligible for retry', 'retries_scheduled': 0}
            scheduled_count = 0
            for call in eligible_calls:
                result = self.schedule_retry(call.id)
                if result['success']:
                    scheduled_count += 1
            self.logger.info(
                f'Scheduled {scheduled_count} retries out of {len(eligible_calls)} eligible calls'
                )
            return {'success': True, 'message':
                f'Scheduled {scheduled_count} retries', 'retries_scheduled':
                scheduled_count, 'eligible_calls': len(eligible_calls)}
        except Exception as e:
            self.logger.error(f'Error retrying failed calls: {str(e)}')
            return {'success': False, 'message':
                f'Error retrying failed calls: {str(e)}',
                'retries_scheduled': 0}

    def cancel_retry(self, call_id: int) ->Dict[str, Any]:
        try:
            call = self.db_manager.get_call(call_id)
            if not call:
                return {'success': False, 'message': 'Call not found'}
            job_id = f'retry_call_{call_id}_{call.retry_count + 1}'
            try:
                self.scheduler.remove_job(job_id)
                self.logger.info(f'Canceled retry for call {call_id}')
                return {'success': True, 'message':
                    'Retry canceled successfully'}
            except Exception:
                return {'success': False, 'message':
                    'No scheduled retry found for this call'}
        except Exception as e:
            self.logger.error(f'Error canceling retry: {str(e)}')
            return {'success': False, 'message':
                f'Error canceling retry: {str(e)}'}

    def get_retry_status(self, call_id: int) ->Dict[str, Any]:
        try:
            call = self.db_manager.get_call(call_id)
            if not call:
                return {'call_found': False, 'message': 'Call not found'}
            job_id = f'retry_call_{call_id}_{call.retry_count + 1}'
            scheduled_job = None
            try:
                scheduled_job = self.scheduler.get_job(job_id)
            except Exception:
                pass
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM retry_attempts 
                WHERE call_id = ? 
                ORDER BY attempt_number DESC
            """
                , (call_id,))
            retry_rows = cursor.fetchall()
            conn.close()
            retry_attempts = []
            for row in retry_rows:
                retry_attempts.append({'attempt_number': row[
                    'attempt_number'], 'status': row['status'],
                    'attempted_at': row['attempted_at'], 'failure_reason':
                    row['failure_reason']})
            return {'call_found': True, 'call_id': call_id,
                'current_retry_count': call.retry_count, 'max_retries':
                config.retry.max_attempts, 'is_retry_eligible': self.
                should_retry_call(call), 'retry_scheduled': scheduled_job
                 is not None, 'next_retry_time': scheduled_job.
                next_run_time.isoformat() if scheduled_job else None,
                'retry_attempts': retry_attempts}
        except Exception as e:
            self.logger.error(f'Error getting retry status: {str(e)}')
            return {'call_found': False, 'message':
                f'Error getting retry status: {str(e)}'}

    def get_retry_summary(self) ->Dict[str, Any]:
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    COUNT(*) as total_retries,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_retries,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_retries,
                    COUNT(CASE WHEN status = 'scheduled' THEN 1 END) as scheduled_retries
                FROM retry_attempts
            """
                )
            stats = cursor.fetchone()
            cursor.execute(
                """
                SELECT COUNT(*) as eligible_calls
                FROM calls 
                WHERE status IN ('failed', 'no-answer', 'busy') 
                AND retry_count < ?
            """
                , (config.retry.max_attempts,))
            eligible = cursor.fetchone()
            scheduled_jobs = len([job for job in self.scheduler.get_jobs() if
                job.id.startswith('retry_call_')])
            conn.close()
            return {'total_retries': stats['total_retries'],
                'successful_retries': stats['successful_retries'],
                'failed_retries': stats['failed_retries'],
                'scheduled_retries': stats['scheduled_retries'],
                'eligible_for_retry': eligible['eligible_calls'],
                'currently_scheduled': scheduled_jobs, 'retry_config': {
                'max_attempts': config.retry.max_attempts, 'delay_minutes':
                config.retry.retry_delay_minutes, 'retry_on_busy': config.
                retry.retry_on_busy, 'retry_on_no_answer': config.retry.
                retry_on_no_answer, 'retry_on_failed': config.retry.
                retry_on_failed}}
        except Exception as e:
            self.logger.error(f'Error getting retry summary: {str(e)}')
            return {'error': f'Error getting retry summary: {str(e)}'}

    def update_retry_config(self, max_attempts: int=None, delay_minutes:
        int=None, retry_on_busy: bool=None, retry_on_no_answer: bool=None,
        retry_on_failed: bool=None) ->Dict[str, Any]:
        try:
            if max_attempts is not None:
                config.retry.max_attempts = max_attempts
            if delay_minutes is not None:
                config.retry.retry_delay_minutes = delay_minutes
            if retry_on_busy is not None:
                config.retry.retry_on_busy = retry_on_busy
                self.retry_statuses['busy'] = retry_on_busy
            if retry_on_no_answer is not None:
                config.retry.retry_on_no_answer = retry_on_no_answer
                self.retry_statuses['no-answer'] = retry_on_no_answer
            if retry_on_failed is not None:
                config.retry.retry_on_failed = retry_on_failed
                self.retry_statuses['failed'] = retry_on_failed
            self.logger.info('Retry configuration updated')
            return {'success': True, 'message':
                'Retry configuration updated successfully', 'config': {
                'max_attempts': config.retry.max_attempts, 'delay_minutes':
                config.retry.retry_delay_minutes, 'retry_on_busy': config.
                retry.retry_on_busy, 'retry_on_no_answer': config.retry.
                retry_on_no_answer, 'retry_on_failed': config.retry.
                retry_on_failed}}
        except Exception as e:
            self.logger.error(f'Error updating retry configuration: {str(e)}')
            return {'success': False, 'message':
                f'Error updating retry configuration: {str(e)}'}

    def shutdown(self):
        try:
            self.scheduler.shutdown()
            self.logger.info('Retry handler shutdown completed')
        except Exception as e:
            self.logger.error(f'Error shutting down retry handler: {str(e)}')
