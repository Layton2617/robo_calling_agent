# Robo Calling AI Agent

A comprehensive Python-based automated calling system using Twilio API with retry mechanisms, call recording, transcript management, and web interface.

## Features

- **Automated Calling**: Make bulk calls using Twilio API
- **Contact Management**: Upload and manage phone number lists via CSV/Excel
- **Call Retry Logic**: Configurable retry attempts for failed calls
- **Call Recording**: Record calls and generate transcripts
- **Web Interface**: User-friendly dashboard for managing campaigns
- **Real-time Status**: Track call progress and status updates
- **Export Functionality**: Export call records and transcripts
- **Webhook Integration**: Handle Twilio webhooks for status updates

## System Requirements

- Python 3.11+
- Twilio Account with Phone Number
- SQLite (included with Python)
- Internet connection for Twilio API

## Installation

1. **Clone or extract the project**:
   ```bash
   cd robo_calling_agent
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` file with your Twilio credentials:
   ```
   TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
   TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
   TWILIO_PHONE_NUMBER=+1234567890
   TWILIO_WEBHOOK_URL=https://your-domain.com
   ```

4. **Create necessary directories**:
   ```bash
   mkdir -p data logs data/uploads
   ```

## Twilio Setup

1. **Create Twilio Account**: Sign up at [twilio.com](https://www.twilio.com)

2. **Get Credentials**:
   - Account SID: Found in Twilio Console Dashboard
   - Auth Token: Found in Twilio Console Dashboard
   - Phone Number: Purchase a phone number in Twilio Console

3. **Configure Webhooks**:
   - Set webhook URL for call status updates
   - For local development, use ngrok or similar tunneling service

## Usage

### Starting the Application

```bash
cd src
python app.py
```

The web interface will be available at `http://localhost:5000`

### Web Interface Features

1. **Dashboard**: Overview of contacts, calls, and statistics
2. **Contacts**: Upload CSV/Excel files with phone numbers
3. **Calls**: View call history and status
4. **Transcripts**: View and search call transcripts
5. **Settings**: Configure retry settings and call scripts

### API Endpoints

#### Contact Management
- `POST /api/contacts/upload` - Upload contact list
- `POST /api/contacts/add` - Add single contact
- `GET /api/contacts` - Get all contacts

#### Call Management
- `POST /api/calls/start` - Start calling campaign
- `GET /api/calls/status/<call_id>` - Get call status
- `GET /api/calls/history` - Get call history
- `GET /api/calls/active` - Get active calls

#### Retry Management
- `POST /api/retry/schedule/<call_id>` - Schedule retry
- `POST /api/retry/failed` - Retry all failed calls
- `GET /api/retry/status/<call_id>` - Get retry status

#### Transcripts
- `GET /api/transcripts` - Get all transcripts
- `GET /api/transcripts/<call_id>` - Get specific transcript

### Contact File Format

Upload CSV or Excel files with the following columns:
- **Phone Number** (required): Phone numbers in any format
- **Name** (optional): Contact name

Example CSV:
```csv
Phone Number,Name
+16507147952,Test Contact
650-714-7952,Another Contact
6507147952,Third Contact
```

### Configuration

#### Retry Settings
- `max_attempts`: Maximum retry attempts (default: 3)
- `retry_delay_minutes`: Delay between retries (default: 5)
- `retry_on_busy`: Retry on busy signal (default: true)
- `retry_on_no_answer`: Retry on no answer (default: true)
- `retry_on_failed`: Retry on failed calls (default: true)

#### Call Settings
- `call_timeout_seconds`: Call timeout (default: 30)
- `record_calls`: Enable call recording (default: true)
- `transcribe_calls`: Enable transcription (default: true)
- `call_script`: Default call script

## File Structure

```
robo_calling_agent/
├── src/
│   ├── app.py                 # Flask web application
│   ├── call_manager.py        # Twilio call management
│   ├── config.py              # Configuration management
│   ├── models.py              # Database models
│   ├── phone_list_manager.py  # Contact management
│   ├── retry_handler.py       # Retry logic
│   └── transcript_processor.py # Transcript handling
├── templates/
│   ├── base.html              # Base template
│   ├── dashboard.html         # Dashboard page
│   └── error.html             # Error page
├── data/                      # Database and uploads
├── logs/                      # Log files
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variables template
└── README.md                 # This file
```

## Demo Usage

1. **Set up Twilio credentials** in `.env` file
2. **Start the application**: `python src/app.py`
3. **Open web interface**: http://localhost:5000
4. **Upload contacts**: Use the dashboard to upload a CSV with phone numbers
5. **Start calling**: Click "Start Calling Campaign" to begin
6. **Monitor progress**: View call status and transcripts in real-time

## Testing with Your Phone Number

To test the system with the provided phone number (650-714-7952):

1. Create a CSV file with the phone number:
   ```csv
   Phone Number,Name
   +16507147952,Test Call
   ```

2. Upload the file through the web interface
3. Start a calling campaign
4. Monitor the call status and transcript

## Troubleshooting

### Common Issues

1. **Twilio Authentication Error**:
   - Verify Account SID and Auth Token
   - Check phone number format (+1XXXXXXXXXX)

2. **Webhook Errors**:
   - Ensure webhook URL is publicly accessible
   - Use ngrok for local development

3. **Database Errors**:
   - Ensure `data/` directory exists
   - Check file permissions

4. **Import Errors**:
   - Verify all dependencies are installed
   - Check Python version (3.11+ required)

### Logs

Check log files in `logs/robo_calls.log` for detailed error information.

## Production Deployment

For production deployment:

1. **Use a production WSGI server**:
   ```bash
   gunicorn -w 4 -b 0.0.0.0:5000 src.app:app
   ```

2. **Set up reverse proxy** (nginx/Apache)
3. **Configure SSL** for webhook security
4. **Use environment variables** for sensitive configuration
5. **Set up monitoring** and log rotation

## Security Considerations

- Keep Twilio credentials secure
- Use HTTPS for webhook URLs
- Implement rate limiting for API endpoints
- Regularly rotate authentication tokens
- Monitor call usage and costs

## License

This project is provided as-is for educational and demonstration purposes.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review Twilio documentation
3. Check application logs for error details

