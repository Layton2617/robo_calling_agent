import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class TwilioConfig:
    account_sid: str
    auth_token: str
    phone_number: str
    webhook_url: Optional[str] = None


@dataclass
class RetryConfig:
    max_attempts: int = 3
    retry_delay_minutes: int = 5
    retry_on_busy: bool = True
    retry_on_no_answer: bool = True
    retry_on_failed: bool = True


@dataclass
class CallConfig:
    call_timeout_seconds: int = 30
    record_calls: bool = True
    transcribe_calls: bool = True
    call_script: str = "Hello, this is a test call from the Robo Calling AI Agent. Thank you for your time."


class Config:
    
    def __init__(self):
        self.twilio = TwilioConfig(
            account_sid=os.getenv('TWILIO_ACCOUNT_SID', ''),
            auth_token=os.getenv('TWILIO_AUTH_TOKEN', ''),
            phone_number=os.getenv('TWILIO_PHONE_NUMBER', ''),
            webhook_url=os.getenv('TWILIO_WEBHOOK_URL', 'http://localhost:5000/webhook')
        )
        
        self.retry = RetryConfig()
        self.call = CallConfig()
        
        self.database_url = os.getenv('DATABASE_URL', 'sqlite:///robo_calls.db')
        
        self.flask_host = os.getenv('FLASK_HOST', '0.0.0.0')
        self.flask_port = int(os.getenv('FLASK_PORT', '5000'))
        self.flask_debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
        
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.log_file = os.getenv('LOG_FILE', 'logs/robo_calls.log')
    
    def validate(self) -> bool:
        if not self.twilio.account_sid:
            print("Error: TWILIO_ACCOUNT_SID not set")
            return False
        
        if not self.twilio.auth_token:
            print("Error: TWILIO_AUTH_TOKEN not set")
            return False
        
        if not self.twilio.phone_number:
            print("Error: TWILIO_PHONE_NUMBER not set")
            return False
        
        return True
    
    def update_call_script(self, script: str):
        self.call.call_script = script
    
    def update_retry_config(self, max_attempts: int = None, delay_minutes: int = None):
        if max_attempts is not None:
            self.retry.max_attempts = max_attempts
        if delay_minutes is not None:
            self.retry.retry_delay_minutes = delay_minutes


config = Config()

