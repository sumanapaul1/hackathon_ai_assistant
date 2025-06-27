import os
import json
import base64
import asyncio
import websockets
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import VoiceResponse, Connect, Say, Stream, Start, Transcription
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

with open("knowledge_base.json", "r") as file:
    knowledge_base = json.load(file)

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PORT = int(os.getenv('PORT', 5050))
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

app = FastAPI()

if not OPENAI_API_KEY:
    raise ValueError('Missing the OpenAI API key. Please set it in the .env file.')

@app.get("/", response_class=JSONResponse)
async def index_page():
    return {"message": "Twilio Media Stream Server is running!"}

@app.api_route("/transcript-callback", methods=["POST"])
async def transcript_callback(request: Request):
    # Extract transcription details from the webhook
    print("****Comming here*******")
    form_data = await request.form()
    form_data = dict(form_data)
    print(f" Test Form data {form_data}")
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
        json.dump(transcription, f, indent=4)
        f.write('\n')
    # Return empty response (Twilio expects 200 or 204 for status callbacks)
    return {"status": "200"}

@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """Handle incoming call and return TwiML response to connect to Media Stream."""
    response = VoiceResponse()
    start = Start()
    start.transcription(
    status_callback_url='ngrok-free.app/transcript-callback',
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