from fastapi import FastAPI, Form , Request , WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
import google.generativeai as genai
from typing import Annotated
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
import re
import os
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key= os.getenv("GOOGLE_API_KEY"))

# Remove the global chat_history - we'll use sessions instead

model= genai.GenerativeModel('gemini-1.5-flash', system_instruction="you are a very usefull agent whihch \
                             has a lot of knowledge of the world and can help in everything including programming, fitness,\
                             cooking, health, education and every other important thing in the world. \
                             you are the one on which I can relay the most and you are the one who can help me in everything")
app= FastAPI()

# Add session middleware to persist chat across page refreshes only
app.add_middleware(SessionMiddleware, secret_key= os.getenv("GOOGLE_API_KEY"))

# In-memory storage for chat histories (will be cleared when app restarts)
chat_sessions = {}

template = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def chat_page(request: Request):
    # Create a session ID if one doesn't exist
    session_id = request.session.get('session_id')
    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())
        request.session['session_id'] = session_id
    
    # Get chat history from in-memory storage (will be cleared when app restarts)
    chat_history = chat_sessions.get(session_id, [])
    
    # Create display list for template - convert from Gemini format to display format
    display_responses = []
    for message in chat_history:
        if message['role'] == 'user':
            display_responses.append(message['parts'][0])  # User message
        elif message['role'] == 'model':
            display_responses.append(message['parts'][0])  # AI response
    
    return template.TemplateResponse("home.html", {
        "request": request, 
        "chat_responses": display_responses
    })

def format_ai_response(text):
    """
    Format AI response with proper bullets, headers, and structure
    """
    # Split text into lines
    lines = text.split('\n')
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            formatted_lines.append('<br>')
            continue
            
        # Format headers (text with ** or numbered sections)
        if line.startswith('**') and line.endswith('**'):
            header_text = line.replace('**', '')
            formatted_lines.append(f'<h4 class="response-header">{header_text}</h4>')
        
        # Format numbered points (1. 2. 3. etc.)
        elif re.match(r'^\d+\.\s', line):
            formatted_lines.append(f'<div class="numbered-point">{line}</div>')
        
        # Format bullet points (* or -)
        elif line.startswith('* ') or line.startswith('- '):
            bullet_text = line[2:]
            formatted_lines.append(f'<div class="bullet-point">• {bullet_text}</div>')
        
        # Format important notes (lines starting with specific keywords)
        elif any(line.lower().startswith(word) for word in ['note:', 'important:', 'remember:', 'warning:', 'tip:']):
            formatted_lines.append(f'<div class="important-note">{line}</div>')
        
        # Auto-create bullets for sentences that should be bullet points
        elif ':' in line and len(line) > 30:
            # Lines with colons that seem like definitions or explanations
            parts = line.split(':', 1)
            if len(parts) == 2:
                formatted_lines.append(f'<div class="bullet-point"><strong>{parts[0]}:</strong> {parts[1].strip()}</div>')
            else:
                formatted_lines.append(f'<div class="text-line">{line}</div>')
        
        # Regular text
        else:
            formatted_lines.append(f'<div class="text-line">{line}</div>')
    
    return '\n'.join(formatted_lines)

@app.post("/", response_class=HTMLResponse)
async def chat_endpoint(
    request: Request,
    user_input: Annotated[str, Form(description="User input for the chat")]
):
    # Get or create session ID
    session_id = request.session.get('session_id')
    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())
        request.session['session_id'] = session_id
    
    # Get chat history from in-memory storage
    chat_history = chat_sessions.get(session_id, [])

    try:
        chat = model.start_chat(history=chat_history)
        response = chat.send_message(user_input)
        
        # Format the AI response with bullets and structure
        formatted_response = format_ai_response(response.text)
        
        chat_history.append({'role': 'user', 'parts': [user_input]})
        chat_history.append({'role': 'model', 'parts': [formatted_response]})
        
        # Save updated chat history to in-memory storage
        chat_sessions[session_id] = chat_history
    
    except Exception as e:
        # Handle quota exceeded errors gracefully
        if "ResourceExhausted" in str(e) or "429" in str(e):
            error_message = '<div class="error-message">⚠️ API quota exceeded. Please try again in a few minutes.</div>'
        else:
            error_message = f'<div class="error-message">❌ Error: {str(e)}</div>'
            
        chat_history.append({'role': 'user', 'parts': [user_input]})
        chat_history.append({'role': 'model', 'parts': [error_message]})
        
        # Save updated chat history to in-memory storage
        chat_sessions[session_id] = chat_history
 
    # Create display list for template - convert from Gemini format to display format
    display_responses = []
    for message in chat_history:
        if message['role'] == 'user':
            display_responses.append(message['parts'][0])  # User message
        elif message['role'] == 'model':
            display_responses.append(message['parts'][0])  # AI response

    return template.TemplateResponse("home.html", {
        "request": request,
        "chat_responses": display_responses
    })

@app.post("/chat", response_class=JSONResponse)
async def chat_ajax(
    request: Request,
    user_input: Annotated[str, Form(description="User input for the chat")]
):
    # Get or create session ID
    session_id = request.session.get('session_id')
    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())
        request.session['session_id'] = session_id
    
    # Get chat history from in-memory storage
    chat_history = chat_sessions.get(session_id, [])

    try:
        chat = model.start_chat(history=chat_history)
        response = chat.send_message(user_input)
        
        # Format the AI response with bullets and structure
        formatted_response = format_ai_response(response.text)
        
        chat_history.append({'role': 'user', 'parts': [user_input]})
        chat_history.append({'role': 'model', 'parts': [formatted_response]})
        
        # Save updated chat history to in-memory storage
        chat_sessions[session_id] = chat_history
        
        return {
            "status": "success",
            "response": formatted_response
        }
    
    except Exception as e:
        if "ResourceExhausted" in str(e) or "429" in str(e):
            error_message = '<div class="error-message">⚠️ API quota exceeded. Please try again in a few minutes.</div>'
        else:
            error_message = f'<div class="error-message">❌ Error: {str(e)}</div>'
            
        chat_history.append({'role': 'user', 'parts': [user_input]})
        chat_history.append({'role': 'model', 'parts': [error_message]})
        
        # Save updated chat history to in-memory storage
        chat_sessions[session_id] = chat_history
        
        return {
            "status": "error", 
            "response": error_message
        }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print(f"🔌 WebSocket connection established")
    
    # For WebSocket, we'll maintain separate chat history per connection
    # since WebSocket doesn't have access to HTTP sessions
    websocket_chat_history = []
    
    try:
        while True:
            # Receive message from client
            user_input = await websocket.receive_text()
            print(f"👤 Received: {user_input}")
            
            try:
                # Process with Gemini
                chat = model.start_chat(history=websocket_chat_history)
                response = chat.send_message(user_input)
                
                # Format the AI response with bullets and structure (same as AJAX)
                formatted_response = format_ai_response(response.text)
                
                # Update WebSocket chat history
                websocket_chat_history.append({'role': 'user', 'parts': [user_input]})
                websocket_chat_history.append({'role': 'model', 'parts': [formatted_response]})
                
                # Send formatted response back to client
                await websocket.send_text(formatted_response)
                print(f"🤖 Sent: {formatted_response[:50]}...")
                
            except Exception as e:
                # Handle errors gracefully in WebSocket
                if "ResourceExhausted" in str(e) or "429" in str(e):
                    error_message = '<div class="error-message">⚠️ API quota exceeded. Please try again in a few minutes.</div>'
                else:
                    error_message = f'<div class="error-message">❌ Error: {str(e)}</div>'
                
                # Send error message to client
                await websocket.send_text(error_message)
                print(f"❌ Error sent: {str(e)}")
            
    except WebSocketDisconnect:
        print(f"🔌 WebSocket connection closed")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        try:
            await websocket.close()
        except:
            pass

@app.get("/favicon.ico")
async def favicon():
    """Return empty response for favicon to prevent 404 errors"""
    from fastapi.responses import Response
    return Response(content="", media_type="image/x-icon")

@app.get("/animation/gZahP0SpFC.json")
async def get_animation():
    """Serve the Lottie animation JSON file"""
    import json
    try:
        with open("animation/gZahP0SpFC.json", "r") as f:
            animation_data = json.load(f)
        return animation_data
    except FileNotFoundError:
        return {"error": "Animation file not found"}

@app.post("/clear-chat")
async def clear_chat(request: Request):
    """Clear chat history for the current session"""
    session_id = request.session.get('session_id')
    if session_id and session_id in chat_sessions:
        del chat_sessions[session_id]
    return {"status": "success", "message": "Chat history cleared"}

@app.get("/debug-session")
async def debug_session(request: Request):
    """Debug endpoint to see session contents"""
    session_id = request.session.get('session_id', 'No session ID')
    chat_history = chat_sessions.get(session_id, []) if session_id != 'No session ID' else []
    return {
        "session_id": session_id,
        "total_sessions": len(chat_sessions),
        "chat_history_length": len(chat_history),
        "chat_history": chat_history[:5]  # Show first 5 messages for debugging
    }




