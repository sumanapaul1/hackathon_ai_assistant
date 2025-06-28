import os
import json
import base64
import asyncio
import websockets
import re
from datetime import datetime
from fastapi import FastAPI, WebSocket, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import VoiceResponse, Connect, Say, Stream, Start, Transcription
from dotenv import load_dotenv
from twilio.rest import Client

# Import httpx for HTTP requests
try:
    import httpx
    print("httpx successfully imported")
except ImportError as e:
    print(f"Failed to import httpx: {e}")

# Explicitly import python-multipart to ensure it's available
try:
    import multipart
    print("python-multipart successfully imported")
except ImportError as e:
    print(f"Failed to import python-multipart: {e}")

load_dotenv()

with open("knowledge_base.json", "r") as file:
    knowledge_base = json.load(file)

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PORT = int(os.getenv('PORT', 5050))
RAILS_SERVER_URL = os.getenv('RAILS_SERVER_URL', 'http://localhost:3000')  # Your Rails server URL

# Lead extraction patterns
EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
PHONE_PATTERN = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b|\b\(\d{3}\)\s?\d{3}[-.]?\d{4}\b'
NAME_PATTERNS = [
    r'(?:my name is|i\'m|i am|this is|call me)\s+([a-zA-Z\s]+?)(?:\s|$|[.,!?])',
    r'(?:name)\s*[:=]\s*([a-zA-Z\s]+?)(?:\s|$|[.,!?])',
    r'(?:i\'m|i am)\s+([a-zA-Z\s]+?)(?:\s|$|[.,!?])'
]
SYSTEM_MESSAGE = """
You are a friendly and professional AI voice assistant for STONE Creek Apartment and Homes, located at 2700 Trimmier Rd, Killeen, TX 76542. Your role is to assist potential tenants by providing accurate information about apartment floor plans, vacancies, amenities, and appointment scheduling based solely on the provided JSON knowledge base. You are designed for voice interactions, so your responses should be concise, natural, and suitable for spoken communication. 

**Knowledge Base Summary**:
- **Property**: STONE Creek Apartment and Homes, 2700 Trimmier Rd, Killeen, TX 76542.
- **Amenities**: Swimming pool, fitness center, pet-friendly environment, gated community, clubhouse, on-site parking, washer/dryer connections.
- **Floor Plans**:
  - **A1**: 1BHK, 575 sqft, $1,095/month, 2 occupants, ground floor, features: walk-in closet, stainless steel appliances, balcony.
  - **A2**: 1BHK, 597 sqft, $1,130/month, 2 occupants, second floor, features: open kitchen, hardwood floors, large windows.
  - **B1**: 2BHK, 850 sqft, $1,500/month, 4 occupants, ground floor, features: two bathrooms, private patio, in-unit laundry.
- **Vacancies**:
  - Unit A101 (1BHK, A1): $1,100/month, appointment slots: June 25, 2025, at 4:00 PM; June 26, 2025, at 2:00 PM.
  - Unit A201 (1BHK, A2): $1,140/month, appointment slot: June 25, 2025, at 10:00 AM.
  - Unit B102 (2BHK, B1): $1,520/month, appointment slot: June 27, 2025, at 3:00 PM.

**Guidelines**:
1. **Tone and Style**: Use a warm, welcoming, and professional tone, like a helpful leasing agent. Keep responses short (1-2 sentences when possible) for voice clarity.
2. **Name**: Use the name "Tina" in the conversation.
3. **Property Name**: Use the name "STONE Creek Apartment and Homes" in the conversation.
4. **Lead Name**: Collect the name from user and use it in the conversation.
5. **Lead Phone Number**: Collect the phone number from user.
2. **Accuracy**: Answer queries using only the provided JSON data. Do not invent or speculate beyond the knowledge base.
3. **Query Handling**:
   - **Floor Plans**: For queries about floor plans (e.g., "What 1BHK apartments are available?"), mention the class (A1, A2, B1), type (1BHK, 2BHK), size, price, occupancy, level, and key features (limit to 3 features for brevity).
   - **Vacancies**: For queries about availability (e.g., "What units are available?"), provide unit number, type, class, price, and appointment slots (formatted as, e.g., "June 25 at 4:00 PM").
   - **Amenities**: For queries about amenities (e.g., "What amenities do you offer?"), list up to 5 amenities and offer to provide more details if asked.
   - **Bookings**: For booking requests (e.g., "Book a tour for A101 on June 25"), confirm the unit and slot if available, or prompt for clarification (e.g., "Please specify the unit or date"), and collect the name, email and phone number of the lead. Format dates as "Month Day at Time" (e.g., "June 25 at 4:00 PM").
   - **Specific Units**: If a unit (e.g., "A101") is mentioned, provide its details (type, class, price, slots) or say it's unavailable if not in the JSON.
   - **Price Queries**: If asked about units under a price (e.g., "Units under $1,200"), filter vacancies by price and list matches.
4. **Unclear Queries**: If the query is unclear or not covered by the JSON (e.g., "What's the weather like?"), respond politely: "I'm sorry, I don't have that information. Can I help with floor plans, vacancies, amenities, or tours?"
5. **Interruptions**: If interrupted (e.g., detected by speech activity), stop speaking immediately and process the new query.
6. **Engagement**: Occasionally include a light, professional dad joke or owl-themed joke to keep the conversation engaging, but only when appropriate (e.g., after a successful query response). Examples:
   - "Why did the owl move in? It wanted a 'hoot' of a deal!"
   - "Why did the apartment go to therapy? It had too many 'deep-rooted' issues!"
7. **Voice Interaction**: Avoid complex terms or long lists in responses. Use conversational phrases like "We have a lovely 1BHK A1 unit" or "Let me check that for you."
8. **Fallback**: If audio transcription fails, respond: "Sorry, I didn't catch that. Could you repeat it?"

**Example Interactions**:
- **User**: "What 1BHK apartments are available?"
  **AI**: "We have two 1BHK options: the A1, 575 square feet at $1,095/month on the ground floor with a walk-in closet, and the A2, 597 square feet at $1,130/month on the second floor with hardwood floors. Want to hear about available units? By the way, why did the owl pick the A1? It loved the balcony view!"
- **User**: "What amenities do you offer?"
  **AI**: "STONE Creek offers a swimming pool, fitness center, pet-friendly environment, gated community, and clubhouse. Interested in specific details?"
- **User**: "Can I book a tour for unit A101 on June 25?"
  **AI**: "Yes, unit A101, a 1BHK A1 at $1,100/month, has a tour slot on June 25 at 4:00 PM. Shall I confirm it?"
- **User**: "What's the price of unit A201?"
  **AI**: "Unit A201 is a 1BHK A2, priced at $1,140/month, with a tour slot on June 25 at 10:00 AM. Want to book it?"
- **User**: "Tell me about the weather."
  **AI**: "I'm sorry, I don't have weather info. Can I help with floor plans, vacancies, amenities, or tours?"

**Initial Greeting**:
When a call starts, greet the user with: "Hello there! I'm Tina AI assitant, Welcome to STONE Creek Apartment and Homes! how can I help you today?"

**Constraints**:
- Do not access external data or APIs beyond the JSON.
- Keep responses under 30 seconds when spoken (about 50-60 words).
- Handle interruptions gracefully by stopping and addressing the new query.
- Use the exact appointment slot times from the JSON, formatted for clarity.
"""
VOICE = 'alloy'
LOG_EVENT_TYPES = [
    'error', 'response.content.done', 'rate_limits.updated',
    'response.done', 'input_audio_buffer.committed',
    'input_audio_buffer.speech_stopped', 'input_audio_buffer.speech_started',
    'session.created'
]
SHOW_TIMING_MATH = False

def parse_transcription_file(file_path="transcription.json"):
    """Parse the transcription.json file and extract conversation data."""
    conversations = {}
    
    try:
        with open(file_path, 'r') as file:
            content = file.read().strip()
            if not content:
                return conversations
                
            # Split by lines and parse each JSON object (each line is a separate JSON object)
            lines = content.split('\n')
            print(f"📄 Found {len(lines)} lines in transcription file")
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if line and len(line) > 5:  # Skip very short lines
                    # Clean up common JSON formatting issues
                    if line.startswith('{') and not line.endswith('}'):
                        # Try to find the next complete JSON object
                        continue
                    
                    try:
                        data = json.loads(line)
                        sid = data.get('TranscriptionSid')
                        print(f"   Line {line_num}: SID={sid}, Status={data.get('TranscriptionStatus')}")
                        
                        if sid:
                            if sid not in conversations:
                                conversations[sid] = {
                                    'customer_messages': [],
                                    'ai_messages': [],
                                    'all_messages': []
                                }
                            
                            transcript_data = data.get('TranscriptionData')
                            if transcript_data:
                                try:
                                    # Parse the nested JSON string
                                    transcript_json = json.loads(transcript_data)
                                    transcript = transcript_json.get('transcript', '').strip()
                                    confidence = transcript_json.get('confidence', 0)
                                    status = data.get('TranscriptionStatus')
                                    
                                    print(f"     Transcript: '{transcript}' (confidence: {confidence})")
                                    
                                    if transcript and confidence > 0.3:  # Lowered confidence threshold
                                        message = {
                                            'text': transcript,
                                            'confidence': confidence,
                                            'timestamp': datetime.now().isoformat()
                                        }
                                        
                                        conversations[sid]['all_messages'].append(message)
                                        
                                        if status == 'inbound_track':  # Customer speaking
                                            conversations[sid]['customer_messages'].append(message)
                                        elif status == 'outbound_track':  # AI speaking
                                            conversations[sid]['ai_messages'].append(message)
                                except json.JSONDecodeError as nested_e:
                                    print(f"     Nested JSON decode error: {nested_e}")
                                        
                    except json.JSONDecodeError as e:
                        print(f"   Line {line_num}: JSON decode error - {e}")
                        print(f"     Problematic line: {line[:100]}...")
                        continue
                        
    except FileNotFoundError:
        print(f"Transcription file {file_path} not found")
        
    print(f"🎯 Parsed {len(conversations)} conversations")
    return conversations

def extract_lead_info(conversation_data):
    """Extract lead information from conversation transcripts."""
    customer_text = ' '.join([msg['text'] for msg in conversation_data.get('customer_messages', [])])
    all_text = ' '.join([msg['text'] for msg in conversation_data.get('all_messages', [])])
    
    lead_info = {
        'name': None,
        'email': None,
        'phone': None,
        'interests': [],
        'appointment_requested': False,
        'conversation_summary': customer_text[:500],  # First 500 chars
        'message_count': len(conversation_data.get('all_messages', [])),
        'source': 'voice_call'
    }
    
    # Extract email
    email_match = re.search(EMAIL_PATTERN, customer_text, re.IGNORECASE)
    if email_match:
        lead_info['email'] = email_match.group()
    
    # Extract phone
    phone_match = re.search(PHONE_PATTERN, customer_text)
    if phone_match:
        lead_info['phone'] = phone_match.group()
    
    # Extract name
    for pattern in NAME_PATTERNS:
        name_match = re.search(pattern, customer_text, re.IGNORECASE)
        if name_match:
            candidate_name = name_match.group(1).strip().title()
            # Simple validation
            if len(candidate_name) > 1 and candidate_name not in ['Hello', 'Hi', 'Thanks']:
                lead_info['name'] = candidate_name
                break
    
    # Extract interests
    interests_keywords = {
        '1BHK': ['1bhk', 'one bedroom', '1 bedroom'],
        '2BHK': ['2bhk', 'two bedroom', '2 bedroom'],
        'Swimming Pool': ['pool', 'swimming'],
        'Fitness Center': ['gym', 'fitness'],
        'Pet Friendly': ['pet', 'dog', 'cat'],
        'Ground Floor': ['ground floor', 'first floor']
    }
    
    for interest, keywords in interests_keywords.items():
        if any(keyword in all_text.lower() for keyword in keywords):
            lead_info['interests'].append(interest)
    
    # Check for appointment requests
    appointment_keywords = ['tour', 'visit', 'appointment', 'schedule', 'book', 'see the place']
    if any(keyword in all_text.lower() for keyword in appointment_keywords):
        lead_info['appointment_requested'] = True
    
    return lead_info

async def create_lead_in_rails(lead_info, transcription_sid):
    """Send lead information to Rails server to create a lead."""
    try:
        # Prepare payload for Rails API
        payload = {
            'lead': {
                'email': lead_info.get('email'),
                'payload': {
                    'source': 'voice_call_ai',
                    'transcription_sid': transcription_sid,
                    'contact_info': {
                        'name': lead_info.get('name'),
                        'phone': lead_info.get('phone'),
                        'email': lead_info.get('email')
                    },
                    'interests': lead_info.get('interests', []),
                    'appointments': {
                        'requested': lead_info.get('appointment_requested', False),
                        'status': 'requested' if lead_info.get('appointment_requested') else 'none'
                    },
                    'conversation_summary': {
                        'total_messages': lead_info.get('message_count', 0),
                        'summary': lead_info.get('conversation_summary', ''),
                        'source': 'voice_ai_assistant'
                    },
                    'lead_score': calculate_lead_score(lead_info),
                    'created_at': datetime.now().isoformat()
                }
            }
        }
        
        rails_url = f"{RAILS_SERVER_URL}/leads"
        print(f"🚀 Sending POST request to Rails: {rails_url}")
        print(f"📦 Payload: {json.dumps(payload, indent=2)}")
        
        # Ensure we're using httpx properly for POST request
        if 'httpx' not in globals():
            print("❌ httpx not available, falling back to requests")
            import requests
            response = requests.post(
                rails_url,
                json=payload,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                timeout=10.0
            )
            
            if response.status_code in [200, 201]:
                print(f"✅ Lead created successfully in Rails: {response.json()}")
                return True
            else:
                print(f"❌ Failed to create lead: {response.status_code} - {response.text}")
                return False
        else:
            async with httpx.AsyncClient() as client:
                print("📡 Making POST request with httpx...")
                response = await client.post(
                    rails_url,
                    json=payload,
                    headers={
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'User-Agent': 'FastAPI-Voice-Assistant/1.0'
                    },
                    timeout=10.0
                )
                
                print(f"📈 Response status: {response.status_code}")
                print(f"📄 Response headers: {dict(response.headers)}")
                
                if response.status_code in [200, 201]:
                    try:
                        response_data = response.json()
                        print(f"✅ Lead created successfully in Rails: {response_data}")
                        return True
                    except:
                        print(f"✅ Lead created successfully in Rails (non-JSON response): {response.text}")
                        return True
                else:
                    print(f"❌ Failed to create lead: {response.status_code}")
                    print(f"❌ Response text: {response.text}")
                    return False
                
    except Exception as e:
        print(f"❌ Error creating lead in Rails: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return False

def calculate_lead_score(lead_info):
    """Calculate lead score based on available information."""
    score = 0
    
    # Contact information
    if lead_info.get('email'): score += 30
    if lead_info.get('phone'): score += 25
    if lead_info.get('name'): score += 15
    
    # Engagement indicators
    if lead_info.get('appointment_requested'): score += 20
    if lead_info.get('interests'): score += 10
    if lead_info.get('message_count', 0) >= 5: score += 10
    
    return min(score, 100)  # Cap at 100

async def process_completed_transcriptions():
    """Process transcriptions and create leads for completed conversations."""
    print("🔍 Starting transcription processing...")
    conversations = parse_transcription_file()
    
    print(f"📊 Found {len(conversations)} conversations")
    
    for sid, conversation_data in conversations.items():
        print(f"📞 Processing conversation {sid}")
        print(f"   - Customer messages: {len(conversation_data.get('customer_messages', []))}")
        print(f"   - AI messages: {len(conversation_data.get('ai_messages', []))}")
        
        # Check if conversation has enough data to create a lead
        if len(conversation_data.get('customer_messages', [])) >= 1:  # Lowered threshold
            lead_info = extract_lead_info(conversation_data)
            print(f"   - Extracted lead info: {lead_info}")
            
            # Only create lead if we have meaningful information
            if (lead_info.get('email') or lead_info.get('phone') or 
                lead_info.get('appointment_requested') or lead_info.get('interests') or
                len(conversation_data.get('customer_messages', [])) >= 2):  # Or if enough conversation
                
                print(f"✅ Creating lead for conversation {sid}")
                result = await create_lead_in_rails(lead_info, sid)
                print(f"   - Lead creation result: {result}")
            else:
                print(f"⏭️  Skipping conversation {sid} - not enough meaningful data")
        else:
            print(f"⏭️  Skipping conversation {sid} - not enough messages")
    
    print("🏁 Transcription processing completed")

app = FastAPI()

if not OPENAI_API_KEY:
    raise ValueError('Missing the OpenAI API key. Please set it in the .env file.')

@app.get("/", response_class=JSONResponse)
async def index_page():
    return {"message": "Twilio Media Stream Server is running!"}

@app.get("/process-leads", response_class=JSONResponse)
async def process_leads_endpoint():
    """Manual endpoint to process transcriptions and create leads."""
    print("🔄 Processing transcriptions to create leads...")
    await process_completed_transcriptions()
    return {"message": "Lead processing completed", "status": "success"}

@app.get("/test-lead-creation", response_class=JSONResponse)
async def test_lead_creation():
    """Test endpoint to verify lead creation functionality."""
    # Test with sample data
    test_lead_info = {
        'name': 'John Doe',
        'email': 'john.doe@example.com',
        'phone': '555-123-4567',
        'interests': ['1BHK', 'Swimming Pool'],
        'appointment_requested': True,
        'conversation_summary': 'Customer interested in 1BHK apartment with pool access',
        'message_count': 8,
        'source': 'voice_call_test'
    }
    
    result = await create_lead_in_rails(test_lead_info, "TEST_SID_123")
    return {"message": "Test lead creation", "success": result}

@app.api_route("/transcript-callback", methods=["POST"])
async def transcript_callback(request: Request):
    # Extract transcription details from the webhook
    print("****Coming here*******")
    
    try:
        # Try to get form data first
        content_type = request.headers.get("content-type", "")
        
        if "application/x-www-form-urlencoded" in content_type:
            # Handle URL-encoded form data
            body = await request.body()
            from urllib.parse import parse_qs
            form_data = parse_qs(body.decode())
            # Convert list values to single values
            form_data = {k: v[0] if v else None for k, v in form_data.items()}
        elif "multipart/form-data" in content_type:
            # Handle multipart form data (requires python-multipart)
            form_data = await request.form()
            form_data = dict(form_data)
        else:
            # Try JSON if it's not form data
            try:
                form_data = await request.json()
            except:
                # Fallback to reading raw body
                body = await request.body()
                print(f"Raw body: {body}")
                form_data = {}
        
        print(f"Test Form data {form_data}")
        
        transcription = {
            'TranscriptionSid': form_data.get('TranscriptionSid'),
            'TranscriptionData': form_data.get('TranscriptionData'),
            'TranscriptionStatus': form_data.get('Track')
        }
        
        # Print or process the JSON transcription
        print("Transcription JSON:", transcription)
        
        # Optionally save to a file or database
        with open('transcription.json', 'a') as f:
            import json
            json.dump(transcription, f, separators=(',', ':'))  # Compact format, one line per object
            f.write('\n')
            
        # Check if conversation is complete and process lead automatically
        transcript_data = transcription.get('TranscriptionData')
        transcript_status = transcription.get('TranscriptionStatus')
        
        # Conversation is complete when both TranscriptionData and TranscriptionStatus are null
        if transcript_data is None and transcript_status is None:
            print("🏁 Conversation completed - processing lead automatically...")
            # Process leads asynchronously in background
            asyncio.create_task(process_completed_transcriptions())
        elif transcript_data:
            # Log the transcript for monitoring
            try:
                transcript_json = json.loads(transcript_data)
                transcript_text = transcript_json.get('transcript', '').strip()
                if transcript_text:
                    print(f"📝 Transcription: {transcript_text}")
            except json.JSONDecodeError:
                pass
            
    except Exception as e:
        print(f"Error processing transcript callback: {e}")
        return {"status": "error", "message": str(e)}
    
    # Return empty response (Twilio expects 200 or 204 for status callbacks)
    return {"status": "200"}

@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """Handle incoming call and return TwiML response to connect to Media Stream."""
    response = VoiceResponse()
    start = Start()
    start.transcription(
    status_callback_url='https://870b-2405-201-c404-40d6-4d67-efb6-b575-ec34.ngrok-free.app/transcript-callback',
    language_code='en-US',
    inbound_track_label='agent',
    outbound_track_label='customer'
    )
    response.append(start)
    response.say("Please wait while we connect your call to the A.I")
    response.pause(length=1)
    response.say("O.K. you can start talking!")
    host = request.url.hostname
    connect = Connect()
    connect.stream(url=f'wss://{host}/media-stream')
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")

@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connections between Twilio and OpenAI."""
    print("Client connected")
    await websocket.accept()

    async with websockets.connect(
        'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2025-06-03',
        additional_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1"
        }
    ) as openai_ws:
        await initialize_session(openai_ws)

        # Connection specific state
        stream_sid = None
        latest_media_timestamp = 0
        last_assistant_item = None
        mark_queue = []
        response_start_timestamp_twilio = None

        async def receive_from_twilio():
            """Receive audio data from Twilio and send it to the OpenAI Realtime API."""
            nonlocal stream_sid, latest_media_timestamp
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    if data['event'] == 'media':
                        latest_media_timestamp = int(data['media']['timestamp'])
                        audio_append = {
                            "type": "input_audio_buffer.append",
                            "audio": data['media']['payload']
                        }
                        await openai_ws.send(json.dumps(audio_append))
                    elif data['event'] == 'start':
                        stream_sid = data['start']['streamSid']
                        print(f"Incoming stream has started {stream_sid}")
                        response_start_timestamp_twilio = None
                        latest_media_timestamp = 0
                        last_assistant_item = None
                    elif data['event'] == 'mark':
                        if mark_queue:
                            mark_queue.pop(0)
            except WebSocketDisconnect:
                print("Client disconnected.")
                if openai_ws.open:
                    await openai_ws.close()

        async def send_to_twilio():
            """Receive events from the OpenAI Realtime API, send audio back to Twilio."""
            nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio
            try:
                async for openai_message in openai_ws:
                    response = json.loads(openai_message)
                    if response['type'] in LOG_EVENT_TYPES:
                        print(f"Received event: {response['type']}", response)

                    if response.get('type') == 'response.audio.delta' and 'delta' in response:
                        audio_payload = base64.b64encode(base64.b64decode(response['delta'])).decode('utf-8')
                        audio_delta = {
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {
                                "payload": audio_payload
                            }
                        }
                        await websocket.send_json(audio_delta)

                        if response_start_timestamp_twilio is None:
                            response_start_timestamp_twilio = latest_media_timestamp
                            if SHOW_TIMING_MATH:
                                print(f"Setting start timestamp for new response: {response_start_timestamp_twilio}ms")

                        # Update last_assistant_item safely
                        if response.get('item_id'):
                            last_assistant_item = response['item_id']

                        await send_mark(websocket, stream_sid)

                    # Trigger an interruption. Your use case might work better using `input_audio_buffer.speech_stopped`, or combining the two.
                    if response.get('type') == 'input_audio_buffer.speech_started':
                        print("Speech started detected.")
                        if last_assistant_item:
                            print(f"Interrupting response with id: {last_assistant_item}")
                            await handle_speech_started_event()
            except Exception as e:
                print(f"Error in send_to_twilio: {e}")

        async def handle_speech_started_event():
            """Handle interruption when the caller's speech starts."""
            nonlocal response_start_timestamp_twilio, last_assistant_item
            print("Handling speech started event.")
            if mark_queue and response_start_timestamp_twilio is not None:
                elapsed_time = latest_media_timestamp - response_start_timestamp_twilio
                if SHOW_TIMING_MATH:
                    print(f"Calculating elapsed time for truncation: {latest_media_timestamp} - {response_start_timestamp_twilio} = {elapsed_time}ms")

                if last_assistant_item:
                    if SHOW_TIMING_MATH:
                        print(f"Truncating item with ID: {last_assistant_item}, Truncated at: {elapsed_time}ms")

                    truncate_event = {
                        "type": "conversation.item.truncate",
                        "item_id": last_assistant_item,
                        "content_index": 0,
                        "audio_end_ms": elapsed_time
                    }
                    await openai_ws.send(json.dumps(truncate_event))

                await websocket.send_json({
                    "event": "clear",
                    "streamSid": stream_sid
                })

                mark_queue.clear()
                last_assistant_item = None
                response_start_timestamp_twilio = None

        async def send_mark(connection, stream_sid):
            if stream_sid:
                mark_event = {
                    "event": "mark",
                    "streamSid": stream_sid,
                    "mark": {"name": "responsePart"}
                }
                await connection.send_json(mark_event)
                mark_queue.append('responsePart')

        await asyncio.gather(receive_from_twilio(), send_to_twilio())

async def send_initial_conversation_item(openai_ws):
    """Send initial conversation item if AI talks first."""
    initial_conversation_item = {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "Greet the user with 'Hello there! I am an Tina,AI voice assistant for STONE Creek Apartment and Homes. How can I help you?'"
                }
            ]
        }
    }
    await openai_ws.send(json.dumps(initial_conversation_item))
    await openai_ws.send(json.dumps({"type": "response.create"}))


async def initialize_session(openai_ws):
    """Control initial session with OpenAI."""
    session_update = {
        "type": "session.update",
        "session": {
            "turn_detection": {"type": "server_vad"},
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": VOICE,
            "instructions": SYSTEM_MESSAGE,
            "modalities": ["text", "audio"],
            "temperature": 0.8,
        }
    }
    print('Sending session update:', json.dumps(session_update))
    await openai_ws.send(json.dumps(session_update))

    # Uncomment the next line to have the AI speak first
    # await send_initial_conversation_item(openai_ws)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)