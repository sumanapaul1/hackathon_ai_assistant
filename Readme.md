# 🏠 AI-Powered Apartment Leasing Assistant

An intelligent voice assistant built for apartment leasing and property management, designed to handle tenant inquiries, provide property information, and schedule tours through natural voice conversations.

## 🚀 Features

### 🗣️ Voice-First Interaction
- **Real-time voice conversations** using OpenAI's Realtime API
- **Twilio integration** for phone call handling
- **Natural language processing** for understanding tenant queries
- **Professional voice responses** with personality and occasional humor

### 🏢 Property Management
- **Dynamic knowledge base** with apartment floor plans, pricing, and availability
- **Real-time vacancy tracking** and appointment scheduling
- **Multi-property support** with configurable property information
- **Amenities and features information** delivery

### 🤖 AI Capabilities
- **Semantic search** through property data using sentence transformers
- **Contextual responses** based on tenant queries
- **Fallback handling** for unknown questions

### 🔧 Advanced Configuration
- **Flexible assistant personality** and behavior configuration
- **Template-based responses** for consistent communication
- **Multiple knowledge sources** (JSON files, databases, APIs)
- **Property management system integration** ready

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Phone Call    │────│  Twilio Media    │────│   FastAPI       │
│   (Tenant)      │    │     Stream       │    │   WebServer     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐                               ┌─────────────────┐
│   Knowledge     │───────────────────────────────│   OpenAI        │
│     Base        │                               │  Realtime API   │
│   (JSON/DB)     │                               │                 │
└─────────────────┘                               └─────────────────┘
```

## 🛠️ Technologies Used

- **Backend**: FastAPI, Python 3.8+
- **AI/ML**: OpenAI Realtime API
- **Voice**: Twilio Voice API, WebSocket connections
- **Data**: JSON knowledge base
- **Configuration**: Environment variables and direct code configuration

## 📋 Prerequisites

- Python 3.8 or higher
- OpenAI API key with Realtime API access
- Twilio account with phone number
- ngrok or similar tool for local development (optional)

## ⚡ Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd hackathon_ai_assistant
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the root directory:

```env
OPENAI_API_KEY=your_openai_api_key_here
PORT=5050
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
```

### 3. Configure Property Information

Edit `knowledge_base.json` with your property details:

```json
{
  "properties": [
    {
      "name": "Your Property Name",
      "address": "Property Address",
      "floorplans": [...],
      "amenities": [...],
      "vacancies": [...]
    }
  ]
}
```

### 4. Run the Application

```bash
python main.py
```

The server will start on `http://localhost:5050`

### 5. Setup Twilio Webhook

1. Use ngrok to expose your local server: `ngrok http 5050`
2. In Twilio Console, set your phone number's webhook URL to: `https://your-ngrok-url.ngrok.io/incoming-call`

## 🔧 Configuration

### Assistant Configuration

The AI assistant's personality and behavior are configured directly in the `main.py` file through the `SYSTEM_MESSAGE` variable. This includes:

- **Professional and friendly tone** with occasional humor
- **Concise responses** optimized for voice interaction  
- **Property-specific knowledge** about STONE Creek Apartments
- **Greeting behavior** with welcome message and light jokes
- **Appointment booking** with confirmation details

### Knowledge Base

The application uses a JSON-based knowledge system:

- **Single JSON file**: `knowledge_base.json` contains all property data
- **Real-time loading**: Knowledge base is loaded at application startup
- **Structured data**: Properties, floor plans, amenities, and vacancies
- **Easy updates**: Simply modify the JSON file and restart the application

## 📁 Project Structure

```
hackathon_ai_assistant/
├── main.py                 # FastAPI application and Twilio integration
├── test_app.py            # Comprehensive test suite
├── knowledge_base.json    # Property data and information
├── requirements.txt       # Python dependencies (includes test dependencies)
├── .env                   # Environment variables
└── README.md             # This file
```

## 🎯 Usage Examples

### Making a Test Call

1. Call your Twilio phone number
2. Wait for the greeting: "Hello! Welcome to [Property Name]!"
3. Try these sample queries:
   - "What 1-bedroom apartments do you have?"
   - "What amenities are available?"
   - "Can I schedule a tour for unit A101?"
   - "Show me apartments under $1200"

### API Endpoints

- `GET /` - Health check
- `POST /incoming-call` - Twilio webhook for incoming calls
- `WebSocket /media-stream` - Real-time audio streaming

### Sample Conversation Flow

```
Tenant: "Hi, what 1-bedroom apartments do you have available?"

AI: "We have several 1-bedroom options! The A1 floor plan is 575 square feet 
    starting at $1,095 per month with a walk-in closet. The A2 is 597 square 
    feet at $1,130 with hardwood floors. Would you like to schedule a tour?"

Tenant: "Yes, can I see unit A101 this weekend?"

AI: "Absolutely! Unit A101 has tour slots available on June 25th at 4:00 PM 
    and June 26th at 2:00 PM. Which works better for you?"
```

## 🧪 Development

### Running Tests

Install test dependencies:
```bash
pip install pytest pytest-asyncio httpx
```

Run the test suite:
```bash
python -m pytest test_app.py -v
```

Run specific test categories:
```bash
# Test API endpoints only
python -m pytest test_app.py::TestHealthEndpoint -v

# Test WebSocket functionality
python -m pytest test_app.py::TestWebSocketHandling -v

# Test integration scenarios
python -m pytest test_app.py::TestIntegrationScenarios -v
```

Run tests with coverage:
```bash
pip install pytest-cov
python -m pytest test_app.py --cov=main --cov-report=html
```

### Adding New Features

1. **New Knowledge Sources**: Modify `knowledge_base.json` structure
2. **Response Templates**: Update `SYSTEM_MESSAGE` in `main.py`
3. **Assistant Behavior**: Customize the assistant instructions in `main.py`

### Debugging

Enable detailed logging by setting environment variable:
```bash
LOG_LEVEL=DEBUG python main.py
```

## 🚀 Deployment

### Production Deployment

1. **Environment Setup**:
   ```bash
   pip install gunicorn
   gunicorn main:app --host 0.0.0.0 --port 5050
   ```

2. **Docker Deployment**:
   ```dockerfile
   FROM python:3.9
   COPY . /app
   WORKDIR /app
   RUN pip install -r requirements.txt
   CMD ["python", "main.py"]
   ```

3. **Cloud Deployment**: Compatible with AWS, GCP, Azure, and Heroku

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Open an issue on GitHub
- Check the configuration documentation
- Review the example configurations

## 🎉 Hackathon Notes

This project was built for a hackathon to demonstrate:
- **Real-time AI voice interactions** in property management
- **Seamless integration** between multiple APIs and services  
- **Scalable architecture** for handling multiple properties and tenants
- **Professional-grade voice assistant** with personality and humor

---

**Built with ❤️ for the future of property management**