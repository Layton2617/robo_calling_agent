import pandas as pd
import re
from typing import List, Dict, Tuple, Optional
from models import Contact, DatabaseManager
import logging


class PhoneListManager:

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)

    def validate_phone_number(self, phone: str) ->Tuple[bool, str]:
        if not phone:
            return False, ''
        digits_only = re.sub('\\D', '', str(phone))
        if len(digits_only) == 10:
            formatted = f'+1{digits_only}'
            return True, formatted
        elif len(digits_only) == 11 and digits_only.startswith('1'):
            formatted = f'+{digits_only}'
            return True, formatted
        elif len(digits_only) > 11:
            formatted = f'+{digits_only}'
            return True, formatted
        else:
            return False, digits_only

    def parse_csv_file(self, file_path: str) ->Tuple[List[Contact], List[str]]:
        contacts = []
        errors = []
        try:
            encodings = ['utf-8', 'latin-1', 'cp1252']
            df = None
            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if df is None:
                errors.append(
                    'Could not read CSV file with any supported encoding')
                return contacts, errors
            df.columns = df.columns.str.lower().str.strip()
            phone_col = None
            name_col = None
            phone_patterns = ['phone', 'number', 'mobile', 'cell',
                'telephone', 'tel']
            for col in df.columns:
                if any(pattern in col for pattern in phone_patterns):
                    phone_col = col
                    break
            name_patterns = ['name', 'first', 'last', 'full', 'contact']
            for col in df.columns:
                if any(pattern in col for pattern in name_patterns):
                    name_col = col
                    break
            if phone_col is None and len(df.columns) > 0:
                phone_col = df.columns[0]
            if name_col is None and len(df.columns) > 1:
                name_col = df.columns[1]
            if phone_col is None:
                errors.append('No phone number column found in CSV')
                return contacts, errors
            for index, row in df.iterrows():
                try:
                    phone = str(row[phone_col]).strip()
                    name = str(row[name_col]).strip() if name_col and pd.notna(
                        row[name_col]) else ''
                    if not phone or phone.lower() in ['nan', 'none', '']:
                        continue
                    is_valid, formatted_phone = self.validate_phone_number(
                        phone)
                    if is_valid:
                        contact = Contact(phone_number=formatted_phone,
                            name=name, status='active')
                        contacts.append(contact)
                    else:
                        errors.append(
                            f"Row {index + 2}: Invalid phone number '{phone}'")
                except Exception as e:
                    errors.append(
                        f'Row {index + 2}: Error processing row - {str(e)}')
        except Exception as e:
            errors.append(f'Error reading CSV file: {str(e)}')
        return contacts, errors

    def parse_excel_file(self, file_path: str) ->Tuple[List[Contact], List[str]
        ]:
        contacts = []
        errors = []
        try:
            df = pd.read_excel(file_path)
            df.columns = df.columns.str.lower().str.strip()
            phone_col = None
            name_col = None
            phone_patterns = ['phone', 'number', 'mobile', 'cell',
                'telephone', 'tel']
            for col in df.columns:
                if any(pattern in col for pattern in phone_patterns):
                    phone_col = col
                    break
            name_patterns = ['name', 'first', 'last', 'full', 'contact']
            for col in df.columns:
                if any(pattern in col for pattern in name_patterns):
                    name_col = col
                    break
            if phone_col is None and len(df.columns) > 0:
                phone_col = df.columns[0]
            if name_col is None and len(df.columns) > 1:
                name_col = df.columns[1]
            if phone_col is None:
                errors.append('No phone number column found in Excel file')
                return contacts, errors
            for index, row in df.iterrows():
                try:
                    phone = str(row[phone_col]).strip()
                    name = str(row[name_col]).strip() if name_col and pd.notna(
                        row[name_col]) else ''
                    if not phone or phone.lower() in ['nan', 'none', '']:
                        continue
                    is_valid, formatted_phone = self.validate_phone_number(
                        phone)
                    if is_valid:
                        contact = Contact(phone_number=formatted_phone,
                            name=name, status='active')
                        contacts.append(contact)
                    else:
                        errors.append(
                            f"Row {index + 2}: Invalid phone number '{phone}'")
                except Exception as e:
                    errors.append(
                        f'Row {index + 2}: Error processing row - {str(e)}')
        except Exception as e:
            errors.append(f'Error reading Excel file: {str(e)}')
        return contacts, errors

    def upload_contacts_from_file(self, file_path: str) ->Dict[str, any]:
        file_extension = file_path.lower().split('.')[-1]
        if file_extension == 'csv':
            contacts, errors = self.parse_csv_file(file_path)
        elif file_extension in ['xlsx', 'xls']:
            contacts, errors = self.parse_excel_file(file_path)
        else:
            return {'success': False, 'message':
                'Unsupported file format. Please use CSV or Excel files.',
                'contacts_added': 0, 'errors': []}
        if not contacts and errors:
            return {'success': False, 'message':
                'No valid contacts found in file.', 'contacts_added': 0,
                'errors': errors}
        try:
            contact_ids = self.db_manager.bulk_add_contacts(contacts)
            self.logger.info(
                f'Successfully uploaded {len(contact_ids)} contacts from {file_path}'
                )
            return {'success': True, 'message':
                f'Successfully uploaded {len(contact_ids)} contacts.',
                'contacts_added': len(contact_ids), 'errors': errors,
                'contact_ids': contact_ids}
        except Exception as e:
            self.logger.error(f'Error uploading contacts: {str(e)}')
            return {'success': False, 'message':
                f'Error uploading contacts: {str(e)}', 'contacts_added': 0,
                'errors': errors}

    def add_single_contact(self, phone: str, name: str='') ->Dict[str, any]:
        is_valid, formatted_phone = self.validate_phone_number(phone)
        if not is_valid:
            return {'success': False, 'message':
                f'Invalid phone number: {phone}', 'contact_id': None}
        try:
            contact = Contact(phone_number=formatted_phone, name=name.strip
                (), status='active')
            contact_id = self.db_manager.add_contact(contact)
            self.logger.info(f'Successfully added contact: {formatted_phone}')
            return {'success': True, 'message':
                'Contact added successfully.', 'contact_id': contact_id}
        except Exception as e:
            self.logger.error(f'Error adding contact: {str(e)}')
            return {'success': False, 'message':
                f'Error adding contact: {str(e)}', 'contact_id': None}

    def get_contacts_summary(self) ->Dict[str, any]:
        try:
            contacts = self.db_manager.get_all_contacts()
            status_counts = {}
            for contact in contacts:
                status = contact.status
                status_counts[status] = status_counts.get(status, 0) + 1
            return {'total_contacts': len(contacts), 'status_counts':
                status_counts, 'contacts': [{'id': c.id, 'phone_number': c.
                phone_number, 'name': c.name, 'status': c.status,
                'created_at': c.created_at.isoformat() if c.created_at else
                None} for c in contacts]}
        except Exception as e:
            self.logger.error(f'Error getting contacts summary: {str(e)}')
            return {'total_contacts': 0, 'status_counts': {}, 'contacts': []}

    def export_contacts_to_csv(self, file_path: str) ->bool:
        try:
            contacts = self.db_manager.get_all_contacts()
            data = []
            for contact in contacts:
                data.append({'ID': contact.id, 'Phone Number': contact.
                    phone_number, 'Name': contact.name, 'Status': contact.
                    status, 'Created At': contact.created_at.isoformat() if
                    contact.created_at else ''})
            df = pd.DataFrame(data)
            df.to_csv(file_path, index=False)
            self.logger.info(
                f'Exported {len(contacts)} contacts to {file_path}')
            return True
        except Exception as e:
            self.logger.error(f'Error exporting contacts: {str(e)}')
            return False
