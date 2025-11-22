import streamlit as st
import os
from dotenv import load_dotenv
from src.utils.database import init_db, create_session, get_sessions, save_message, get_chat_history
from src.clients.hevy_client import HevyClient
from src.clients.fitbit_client import FitbitClient
from src.graph.agent import fitness_agent
from langchain_core.messages import HumanMessage, AIMessage

# Load Environment
load_dotenv()

# Initialize DB
init_db()

# Page Config
st.set_page_config(page_title="Fitness Bridge AI", page_icon="💪", layout="wide")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔌 Connections")
    
    # Check Hevy
    hevy_key = os.getenv("HEVY_API_KEY")
    if hevy_key and HevyClient(hevy_key).check_connection():
        st.success("Hevy Connected")
    else:
        st.error("Hevy Disconnected")
        
    # Check Fitbit
    fitbit_token = os.getenv("FITBIT_ACCESS_TOKEN")
    if fitbit_token and FitbitClient(fitbit_token).get_profile():
        st.success("Fitbit Connected")
    else:
        st.warning("Fitbit Token Invalid/Expired")

    st.divider()
    
    st.header("🗄️ History")
    # Session Management
    sessions = get_sessions()
    session_options = {s[0]: s[1] for s in sessions}
    
    if st.button("➕ New Chat"):
        new_id = create_session()
        st.session_state.active_session = new_id
        st.rerun()
        
    selected_session_id = st.selectbox(
        "Past Conversations", 
        options=list(session_options.keys()), 
        format_func=lambda x: session_options[x],
        index=0 if sessions else None
    )
    
    if selected_session_id:
        st.session_state.active_session = selected_session_id

# --- MAIN CHAT INTERFACE ---
st.title("🏋️ Fitness Bridge AI")

if "active_session" not in st.session_state:
    # Create default session if none exists
    st.session_state.active_session = create_session()

# Load Chat History from DB
history = get_chat_history(st.session_state.active_session)

# Display Messages
for msg in history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat Input
if prompt := st.chat_input("Ask about your workouts, recovery, or routine updates..."):
    # 1. Display User Message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 2. Save to DB
    save_message(st.session_state.active_session, "user", prompt)
    
    # 3. LangGraph Processing
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.text("Thinking...")
        
        # Construct LangChain message history for the graph
        # We reload full history from DB to ensure context window is accurate
        lc_messages = []
        for h in history:
            if h["role"] == "user":
                lc_messages.append(HumanMessage(content=h["content"]))
            else:
                lc_messages.append(AIMessage(content=h["content"]))
        lc_messages.append(HumanMessage(content=prompt))
        
        # Invoke Agent
        try:
            response = fitness_agent.invoke({"messages": lc_messages, "user_id": "user"})
            ai_response = response["messages"][-1].content
            
            message_placeholder.markdown(ai_response)
            
            # 4. Save AI Response to DB
            save_message(st.session_state.active_session, "assistant", ai_response)
            
        except Exception as e:
            message_placeholder.error(f"Error: {str(e)}")