#!/usr/bin/env python3

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from models import DatabaseManager, Contact
from config import config

def main():
    
    print("=" * 60)
    print("Robo Calling AI Agent - Simple Demo")
    print("=" * 60)
    
    print("\n1. Checking Configuration...")
    print("Configuration module loaded")
    
    print("\n2. Initializing Database...")
    try:
        db_manager = DatabaseManager()
        print("Database initialized")
    except Exception as e:
        print(f"Error initializing database: {e}")
        return
    
    print("\n3. Adding Demo Contact...")
    demo_contact = Contact(
        phone_number="+16507147952",
        name="Demo Contact",
        status="active"
    )
    
    try:
        contact_id = db_manager.add_contact(demo_contact)
        print(f"Demo contact added with ID: {contact_id}")
    except Exception as e:
        print(f"Contact already exists or error: {e}")
        contacts = db_manager.get_all_contacts()
        if contacts:
            contact_id = contacts[0].id
            print(f"Using existing contact with ID: {contact_id}")
        else:
            return
    
    print("\n4. Contact Information:")
    contact = db_manager.get_contact(contact_id)
    print(f"   Phone: {contact.phone_number}")
    print(f"   Name: {contact.name}")
    print(f"   Created: {contact.created_at}")
    
    print("\n5. System Status:")
    summary = db_manager.get_call_summary()
    print(f"   Total Contacts: {summary['total_contacts']}")
    print(f"   Total Calls: {summary['total_calls']}")
    
    print("\n" + "=" * 60)
    print("Simple demo completed successfully!")
    print("Core functionality is working!")
    print("=" * 60)

if __name__ == "__main__":
    main()

