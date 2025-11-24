import json
import time
import uuid
from typing import Dict, Iterator, List

import boto3
import streamlit as st
from streamlit.logger import get_logger
from botocore.config import Config

logger = get_logger(__name__)
logger.setLevel("INFO")

# Page config
st.set_page_config(
    page_title="IDP Agent Orchestrator",
    page_icon="static/gen-ai-dark.svg",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Remove Streamlit deployment components
st.markdown(
    """
      <style>
        .stAppDeployButton {display:none;}
        #MainMenu {visibility: hidden;}
      </style>
    """,
    unsafe_allow_html=True,
)

HUMAN_AVATAR = "static/user-profile.svg"
AI_AVATAR = "static/gen-ai-dark.svg"


def clean_response_text(text: str) -> str:
    """Clean and format response text for better presentation"""
    if not text:
        return text
    
    # Handle the consecutive quoted chunks pattern
    text = text.replace('"\n"', '\n').replace('" "', ' ')
    text = text.replace('\\n', '\n').replace('\\t', '\t')
    
    # Clean up multiple spaces and newlines
    import re
    text = re.sub(r' {3,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


def invoke_agent_streaming(
    agent_arn: str,
    prompt: str,
    runtime_session_id: str,
    region: str = "us-east-1",
) -> Iterator[str]:
    """Invoke agent and yield streaming response chunks"""
    try:
        config = Config(
            read_timeout=300,
            connect_timeout=60,
            retries={'max_attempts': 3}
        )
        agentcore_client = boto3.client("bedrock-agentcore", region_name=region, config=config)

        boto3_response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            qualifier="DEFAULT",
            runtimeSessionId=runtime_session_id,
            payload=json.dumps({"prompt": prompt}),
        )

        if "text/event-stream" in boto3_response.get("contentType", ""):
            for line in boto3_response["response"].iter_lines(chunk_size=1):
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        line = line[6:]
                        try:
                            data = json.loads(line)
                            if isinstance(data, dict) and "content" in data:
                                content = data["content"]
                                if isinstance(content, list) and len(content) > 0:
                                    if isinstance(content[0], dict) and "text" in content[0]:
                                        yield content[0]["text"]
                        except:
                            yield line
        else:
            # Handle non-streaming response
            response_obj = boto3_response.get("response")
            if hasattr(response_obj, "read"):
                content = response_obj.read()
                if isinstance(content, bytes):
                    content = content.decode("utf-8")
                try:
                    response_data = json.loads(content)
                    if isinstance(response_data, dict):
                        actual_data = response_data.get("result", response_data)
                        if "content" in actual_data:
                            content_list = actual_data["content"]
                            if isinstance(content_list, list) and len(content_list) > 0:
                                if isinstance(content_list[0], dict) and "text" in content_list[0]:
                                    yield content_list[0]["text"]
                except:
                    yield content

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error invoking agent: {e}\n{error_details}")
        yield f"Error invoking agent: {e}"


def main():
    st.logo("static/agentcore-service-icon.png", size="large")
    st.title("🤖 IDP Agent Orchestrator")
    st.markdown("### Three-Agent Document Processing Workflow")

    # Sidebar for settings
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Region selection
        region = st.selectbox(
            "AWS Region",
            ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
            index=0,
        )

        st.divider()
        
        # Agent ARNs configuration
        st.subheader("Agent ARNs")
        
        extractor_arn = st.text_input(
            "1️⃣ Extractor Agent ARN",
            value=st.session_state.get("extractor_arn", ""),
            help="ARN for the Extractor Agent",
            key="extractor_arn_input"
        )
        
        database_arn = st.text_input(
            "2️⃣ Database Agent ARN",
            value=st.session_state.get("database_arn", ""),
            help="ARN for the Database Agent",
            key="database_arn_input"
        )
        
        quality_check_arn = st.text_input(
            "3️⃣ Quality Check Agent ARN",
            value=st.session_state.get("quality_check_arn", ""),
            help="ARN for the Quality Check Agent",
            key="quality_check_arn_input"
        )
        
        # Save ARNs to session state
        if extractor_arn:
            st.session_state.extractor_arn = extractor_arn
        if database_arn:
            st.session_state.database_arn = database_arn
        if quality_check_arn:
            st.session_state.quality_check_arn = quality_check_arn
        
        st.divider()
        
        # Session Configuration
        st.subheader("Session Configuration")
        if "runtime_session_id" not in st.session_state:
            st.session_state.runtime_session_id = str(uuid.uuid4())

        runtime_session_id = st.text_input(
            "Runtime Session ID",
            value=st.session_state.runtime_session_id,
            help="Unique identifier for this runtime session",
        )

        if st.button("🔄 New Session", help="Generate new session ID and clear history"):
            st.session_state.runtime_session_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.rerun()

        st.divider()
        
        # Connection status
        agents_configured = all([
            st.session_state.get("extractor_arn"),
            st.session_state.get("database_arn"),
            st.session_state.get("quality_check_arn")
        ])
        
        if agents_configured:
            st.success("✅ All agents configured")
        else:
            st.warning("⚠️ Configure all agent ARNs")

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Main content area with tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔄 Sequential Processing", 
        "1️⃣ Extractor Agent", 
        "2️⃣ Database Agent", 
        "3️⃣ Quality Check Agent"
    ])

    # Tab 1: Sequential Processing
    with tab1:
        st.markdown("""
        ### 🔄 Sequential Processing Workflow
        
        This tab runs all three agents in sequence automatically:
        1. **Extractor Agent** - Processes PDFs and saves JSON to S3
        2. **Database Agent** - Imports JSON data into DynamoDB
        3. **Quality Check Agent** - Ready for queries and validation
        """)
        
        if st.button("▶️ Run Complete Workflow", type="primary", use_container_width=True):
            if not agents_configured:
                st.error("❌ Please configure all agent ARNs in the sidebar first")
            else:
                workflow_container = st.container()
                
                with workflow_container:
                    # Step 1: Extractor Agent
                    st.markdown("### Step 1: Document Extraction")
                    progress_placeholder = st.empty()
                    output_placeholder = st.empty()
                    
                    chunk_buffer = ""
                    for chunk in invoke_agent_streaming(
                        st.session_state.extractor_arn,
                        "Start extraction",
                        st.session_state.runtime_session_id,
                        region
                    ):
                        chunk_buffer += chunk
                        output_placeholder.text(chunk_buffer)
                        time.sleep(0.01)
                    
                    st.success("✅ Step 1 Complete: Documents extracted")
                    
                    # Small delay between steps
                    time.sleep(2)
                    
                    # Step 2: Database Agent
                    st.markdown("### Step 2: Database Import")
                    progress_placeholder2 = st.empty()
                    output_placeholder2 = st.empty()
                    
                    chunk_buffer = ""
                    for chunk in invoke_agent_streaming(
                        st.session_state.database_arn,
                        "Import data",
                        st.session_state.runtime_session_id,
                        region
                    ):
                        chunk_buffer += chunk
                        output_placeholder2.text(chunk_buffer)
                        time.sleep(0.01)
                    
                    st.success("✅ Step 2 Complete: Data imported to DynamoDB")
                    
                    st.markdown("### Step 3: Quality Check Agent")
                    st.info("✅ Quality Check Agent is ready. Use Tab 4 to query and validate data.")

    # Tab 2: Extractor Agent
    with tab2:
        st.markdown("""
        ### 1️⃣ Extractor Agent
        
        Processes PDF documents from S3 using BDA MCP and saves structured JSON output.
        
        **Input:** `s3://idp-wwso-input-files/input-pdfs/`  
        **Output:** `s3://idp-wwso-output/extracted-data/`
        """)
        
        if st.button("▶️ Run Extractor Agent", key="run_extractor", use_container_width=True):
            if not st.session_state.get("extractor_arn"):
                st.error("❌ Please configure Extractor Agent ARN in the sidebar")
            else:
                output_container = st.container()
                with output_container:
                    message_placeholder = st.empty()
                    chunk_buffer = ""
                    
                    for chunk in invoke_agent_streaming(
                        st.session_state.extractor_arn,
                        "Start extraction",
                        st.session_state.runtime_session_id,
                        region
                    ):
                        chunk_buffer += chunk
                        message_placeholder.text(chunk_buffer)
                        time.sleep(0.01)
                    
                    st.success("✅ Extraction complete!")

    # Tab 3: Database Agent
    with tab3:
        st.markdown("""
        ### 2️⃣ Database Agent
        
        Imports extracted JSON data from S3 into DynamoDB.
        
        **Input:** `s3://idp-wwso-output/extracted-data/`  
        **Output:** DynamoDB Table `IDP_Agent`
        """)
        
        if st.button("▶️ Run Database Agent", key="run_database", use_container_width=True):
            if not st.session_state.get("database_arn"):
                st.error("❌ Please configure Database Agent ARN in the sidebar")
            else:
                output_container = st.container()
                with output_container:
                    message_placeholder = st.empty()
                    chunk_buffer = ""
                    
                    for chunk in invoke_agent_streaming(
                        st.session_state.database_arn,
                        "Import data",
                        st.session_state.runtime_session_id,
                        region
                    ):
                        chunk_buffer += chunk
                        message_placeholder.text(chunk_buffer)
                        time.sleep(0.01)
                    
                    st.success("✅ Database import complete!")

    # Tab 4: Quality Check Agent (Interactive)
    with tab4:
        st.markdown("""
        ### 3️⃣ Quality Check Agent
        
        Query extracted data, validate fields, and update incorrect extractions.
        
        **Commands:**
        - Ask questions: "What is the patient name?"
        - Validate: "validate phone for document abc-123"
        - Update: "update phone to 555-9999 for document abc-123"
        """)
        
        # Display chat history for Quality Check Agent
        for message in st.session_state.messages:
            with st.chat_message(message["role"], avatar=message.get("avatar")):
                st.markdown(message["content"])
        
        # Chat input for Quality Check Agent
        if prompt := st.chat_input("Ask a question, validate, or update a field..."):
            if not st.session_state.get("quality_check_arn"):
                st.error("❌ Please configure Quality Check Agent ARN in the sidebar")
            else:
                # Add user message
                st.session_state.messages.append(
                    {"role": "user", "content": prompt, "avatar": HUMAN_AVATAR}
                )
                with st.chat_message("user", avatar=HUMAN_AVATAR):
                    st.markdown(prompt)
                
                # Generate assistant response
                with st.chat_message("assistant", avatar=AI_AVATAR):
                    message_placeholder = st.empty()
                    chunk_buffer = ""
                    
                    for chunk in invoke_agent_streaming(
                        st.session_state.quality_check_arn,
                        prompt,
                        st.session_state.runtime_session_id,
                        region
                    ):
                        chunk_buffer += chunk
                        cleaned = clean_response_text(chunk_buffer)
                        message_placeholder.markdown(cleaned + " ▌")
                        time.sleep(0.01)
                    
                    full_response = clean_response_text(chunk_buffer)
                    message_placeholder.markdown(full_response)
                
                # Add assistant response to history
                st.session_state.messages.append(
                    {"role": "assistant", "content": full_response, "avatar": AI_AVATAR}
                )


if __name__ == "__main__":
    main()
