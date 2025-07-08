import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import json


@dataclass
class Contact:
    id: Optional[int] = None
    phone_number: str = ""
    name: str = ""
    created_at: Optional[datetime] = None
    status: str = "active"


@dataclass
class Call:
    id: Optional[int] = None
    contact_id: int = 0
    call_sid: str = ""
    status: str = "pending"
    duration: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    retry_count: int = 0
    transcript_url: Optional[str] = None
    recording_url: Optional[str] = None


@dataclass
class RetryAttempt:
    id: Optional[int] = None
    call_id: int = 0
    attempt_number: int = 0
    status: str = ""
    attempted_at: Optional[datetime] = None
    failure_reason: Optional[str] = None


@dataclass
class Transcript:
    id: Optional[int] = None
    call_id: int = 0
    transcript_text: str = ""
    confidence_score: Optional[float] = None
    created_at: Optional[datetime] = None


class DatabaseManager:
    
    def __init__(self, db_path: str = "data/robo_calls.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE NOT NULL,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL,
                call_sid TEXT,
                status TEXT DEFAULT 'pending',
                duration INTEGER,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                retry_count INTEGER DEFAULT 0,
                transcript_url TEXT,
                recording_url TEXT,
                FOREIGN KEY (contact_id) REFERENCES contacts (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS retry_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id INTEGER NOT NULL,
                attempt_number INTEGER NOT NULL,
                status TEXT,
                attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                failure_reason TEXT,
                FOREIGN KEY (call_id) REFERENCES calls (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id INTEGER NOT NULL,
                transcript_text TEXT,
                confidence_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (call_id) REFERENCES calls (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_contact(self, contact: Contact) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO contacts (phone_number, name, status)
            VALUES (?, ?, ?)
        ''', (contact.phone_number, contact.name, contact.status))
        
        contact_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return contact_id
    
    def get_contact(self, contact_id: int) -> Optional[Contact]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM contacts WHERE id = ?', (contact_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return Contact(
                id=row['id'],
                phone_number=row['phone_number'],
                name=row['name'],
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                status=row['status']
            )
        return None
    
    def get_all_contacts(self) -> List[Contact]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM contacts ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        
        contacts = []
        for row in rows:
            contacts.append(Contact(
                id=row['id'],
                phone_number=row['phone_number'],
                name=row['name'],
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                status=row['status']
            ))
        return contacts
    
    def bulk_add_contacts(self, contacts: List[Contact]) -> List[int]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        contact_ids = []
        for contact in contacts:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO contacts (phone_number, name, status)
                    VALUES (?, ?, ?)
                ''', (contact.phone_number, contact.name, contact.status))
                
                if cursor.lastrowid:
                    contact_ids.append(cursor.lastrowid)
                else:
                    cursor.execute('SELECT id FROM contacts WHERE phone_number = ?', (contact.phone_number,))
                    existing_row = cursor.fetchone()
                    if existing_row:
                        contact_ids.append(existing_row['id'])
            except Exception as e:
                print(f"Error adding contact {contact.phone_number}: {e}")
        
        conn.commit()
        conn.close()
        return contact_ids
    
    def add_call(self, call: Call) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO calls (contact_id, call_sid, status, duration, start_time, end_time, retry_count, transcript_url, recording_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (call.contact_id, call.call_sid, call.status, call.duration, 
              call.start_time, call.end_time, call.retry_count, call.transcript_url, call.recording_url))
        
        call_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return call_id
    
    def update_call(self, call: Call):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE calls SET 
                call_sid = ?, status = ?, duration = ?, start_time = ?, end_time = ?, 
                retry_count = ?, transcript_url = ?, recording_url = ?
            WHERE id = ?
        ''', (call.call_sid, call.status, call.duration, call.start_time, call.end_time,
              call.retry_count, call.transcript_url, call.recording_url, call.id))
        
        conn.commit()
        conn.close()
    
    def get_call(self, call_id: int) -> Optional[Call]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM calls WHERE id = ?', (call_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return Call(
                id=row['id'],
                contact_id=row['contact_id'],
                call_sid=row['call_sid'],
                status=row['status'],
                duration=row['duration'],
                start_time=datetime.fromisoformat(row['start_time']) if row['start_time'] else None,
                end_time=datetime.fromisoformat(row['end_time']) if row['end_time'] else None,
                retry_count=row['retry_count'],
                transcript_url=row['transcript_url'],
                recording_url=row['recording_url']
            )
        return None
    
    def get_calls_by_status(self, status: str) -> List[Call]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM calls WHERE status = ? ORDER BY start_time DESC', (status,))
        rows = cursor.fetchall()
        conn.close()
        
        calls = []
        for row in rows:
            calls.append(Call(
                id=row['id'],
                contact_id=row['contact_id'],
                call_sid=row['call_sid'],
                status=row['status'],
                duration=row['duration'],
                start_time=datetime.fromisoformat(row['start_time']) if row['start_time'] else None,
                end_time=datetime.fromisoformat(row['end_time']) if row['end_time'] else None,
                retry_count=row['retry_count'],
                transcript_url=row['transcript_url'],
                recording_url=row['recording_url']
            ))
        return calls
    
    def get_all_calls(self) -> List[Call]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM calls ORDER BY start_time DESC')
        rows = cursor.fetchall()
        conn.close()
        
        calls = []
        for row in rows:
            calls.append(Call(
                id=row['id'],
                contact_id=row['contact_id'],
                call_sid=row['call_sid'],
                status=row['status'],
                duration=row['duration'],
                start_time=datetime.fromisoformat(row['start_time']) if row['start_time'] else None,
                end_time=datetime.fromisoformat(row['end_time']) if row['end_time'] else None,
                retry_count=row['retry_count'],
                transcript_url=row['transcript_url'],
                recording_url=row['recording_url']
            ))
        return calls
    
    def add_retry_attempt(self, retry: RetryAttempt) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO retry_attempts (call_id, attempt_number, status, failure_reason)
            VALUES (?, ?, ?, ?)
        ''', (retry.call_id, retry.attempt_number, retry.status, retry.failure_reason))
        
        retry_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return retry_id
    
    def add_transcript(self, transcript: Transcript) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO transcripts (call_id, transcript_text, confidence_score)
            VALUES (?, ?, ?)
        ''', (transcript.call_id, transcript.transcript_text, transcript.confidence_score))
        
        transcript_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return transcript_id
    
    def get_transcript_by_call_id(self, call_id: int) -> Optional[Transcript]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM transcripts WHERE call_id = ?', (call_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return Transcript(
                id=row['id'],
                call_id=row['call_id'],
                transcript_text=row['transcript_text'],
                confidence_score=row['confidence_score'],
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
            )
        return None
    
    def get_call_summary(self) -> Dict[str, Any]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT status, COUNT(*) as count 
            FROM calls 
            GROUP BY status
        ''')
        status_counts = dict(cursor.fetchall())
        
        cursor.execute('SELECT COUNT(*) as count FROM contacts')
        total_contacts = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM calls')
        total_calls = cursor.fetchone()['count']
        
        cursor.execute('SELECT AVG(duration) as avg_duration FROM calls WHERE duration IS NOT NULL')
        avg_duration = cursor.fetchone()['avg_duration']
        
        conn.close()
        
        return {
            'total_contacts': total_contacts,
            'total_calls': total_calls,
            'status_counts': status_counts,
            'average_duration': avg_duration
        }

