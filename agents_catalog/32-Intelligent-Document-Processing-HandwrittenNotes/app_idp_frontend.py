"""
Enhanced IDP Frontend Application
Provides a comprehensive UI for:
1. Document extraction
2. Visualization of extracted data
3. Human-in-the-loop validation
4. DynamoDB persistence
5. Document Q&A
"""

import json
import os
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

import boto3
import streamlit as st
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError
from botocore.config import Config

# Page configuration
st.set_page_config(
    page_title="IDP Document Processing",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
    <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: bold;
            color: #FF6B6B;
            text-align: center;
            margin-bottom: 2rem;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 2px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding: 10px 20px;
            background-color: #f0f2f6;
            border-radius: 4px 4px 0 0;
        }
        .stTabs [aria-selected="true"] {
            background-color: #FF6B6B;
            color: white;
        }
        .field-card {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 1rem;
            margin: 0.5rem 0;
            border-left: 4px solid #FF6B6B;
        }
        .confidence-high {
            color: #28a745;
            font-weight: bold;
        }
        .confidence-medium {
            color: #ffc107;
            font-weight: bold;
        }
        .confidence-low {
            color: #dc3545;
            font-weight: bold;
        }
        .validated-badge {
            background-color: #28a745;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.8rem;
        }
        .unvalidated-badge {
            background-color: #ffc107;
            color: black;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.8rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# AWS Configuration
S3_INPUT_BUCKET = "idp-wwso-input-files"
S3_INPUT_PREFIX = "input-pdfs/"
S3_OUTPUT_BUCKET = "idp-wwso-output"
S3_OUTPUT_PREFIX = "extracted-data/"
DYNAMODB_TABLE_NAME = "IDP_Agent"
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Initialize AWS clients
@st.cache_resource
def get_aws_clients():
    """Initialize and cache AWS clients with extended timeouts"""
    # Extended timeout config for long-running agent operations
    config = Config(
        read_timeout=300,  # 5 minutes for agent processing
        connect_timeout=60,
        retries={'max_attempts': 3}
    )
    
    return {
        's3': boto3.client('s3', region_name=AWS_REGION),
        'dynamodb': boto3.resource('dynamodb', region_name=AWS_REGION),
        'bedrock_agentcore': boto3.client('bedrock-agentcore', region_name=AWS_REGION, config=config),
        'bedrock_agentcore_control': boto3.client('bedrock-agentcore-control', region_name=AWS_REGION)
    }


def decimal_to_native(obj):
    """Convert DynamoDB Decimal types to native Python types"""
    if isinstance(obj, list):
        return [decimal_to_native(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: decimal_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj) if obj % 1 != 0 else int(obj)
    else:
        return obj


def convert_floats_to_decimal(obj):
    """Convert float values to Decimal for DynamoDB compatibility"""
    if isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: convert_floats_to_decimal(value) for key, value in obj.items()}
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj


def fetch_agent_runtimes(region: str = "us-east-1") -> List[Dict]:
    """Fetch available agent runtimes"""
    try:
        clients = get_aws_clients()
        response = clients['bedrock_agentcore_control'].list_agent_runtimes(maxResults=100)
        ready_agents = [
            agent for agent in response.get("agentRuntimes", [])
            if agent.get("status") == "READY"
        ]
        ready_agents.sort(key=lambda x: x.get("lastUpdatedAt", ""), reverse=True)
        return ready_agents
    except Exception as e:
        st.error(f"Error fetching agent runtimes: {e}")
        return []


def get_documents_from_dynamodb() -> List[Dict]:
    """Retrieve all documents from DynamoDB"""
    try:
        clients = get_aws_clients()
        table = clients['dynamodb'].Table(DYNAMODB_TABLE_NAME)
        response = table.scan()
        items = response.get('Items', [])
        
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))
        
        return decimal_to_native(items)
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            st.warning(f"⚠️ DynamoDB table '{DYNAMODB_TABLE_NAME}' not found. Please run extraction first.")
        else:
            st.error(f"Error accessing DynamoDB: {e}")
        return []
    except Exception as e:
        st.error(f"Error retrieving documents: {e}")
        return []


def update_field_in_dynamodb(document_id: str, field_name: str, new_value: str, validated: bool = True) -> bool:
    """Update a field value in DynamoDB"""
    try:
        clients = get_aws_clients()
        table = clients['dynamodb'].Table(DYNAMODB_TABLE_NAME)
        
        response = table.get_item(Key={'document_id': document_id})
        item = response.get('Item')
        
        if not item:
            st.error(f"Document {document_id} not found")
            return False
        
        extracted_fields = item.get('extracted_fields', {})
        
        # Handle nested field paths (e.g., "patient_information.gender")
        field_parts = field_name.split('.')
        
        # Navigate to the correct nested location
        current_level = extracted_fields
        for i, part in enumerate(field_parts[:-1]):
            if part not in current_level:
                current_level[part] = {}
            current_level = current_level[part]
        
        # Update the final field
        final_key = field_parts[-1]
        
        if final_key not in current_level or not isinstance(current_level[final_key], dict):
            # Create new field structure
            current_level[final_key] = {
                'value': new_value,
                'confidence': 1.0,
                'validated': True
            }
        else:
            # Update existing field
            if 'value' in current_level[final_key]:
                # It's a proper field with value/confidence structure
                current_level[final_key]['value'] = new_value
                current_level[final_key]['validated'] = validated
                if validated:
                    current_level[final_key]['confidence'] = 1.0
            else:
                # It's nested structure, create field structure
                current_level[final_key] = {
                    'value': new_value,
                    'confidence': 1.0,
                    'validated': True
                }
        
        extracted_fields = convert_floats_to_decimal(extracted_fields)
        
        table.update_item(
            Key={'document_id': document_id},
            UpdateExpression='SET extracted_fields = :fields, last_updated = :timestamp',
            ExpressionAttributeValues={
                ':fields': extracted_fields,
                ':timestamp': datetime.utcnow().isoformat()
            }
        )
        
        return True
    except Exception as e:
        st.error(f"Error updating field: {e}")
        return False


def upload_to_s3(file_obj, bucket: str, key: str) -> bool:
    """Upload a file to S3"""
    try:
        clients = get_aws_clients()
        clients['s3'].upload_fileobj(file_obj, bucket, key)
        return True
    except Exception as e:
        st.error(f"Error uploading to S3: {e}")
        return False


def invoke_agent(agent_arn: str, prompt: str, session_id: str) -> str:
    """Invoke a Bedrock agent and return the response"""
    try:
        clients = get_aws_clients()
        response = clients['bedrock_agentcore'].invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            qualifier="DEFAULT",
            runtimeSessionId=session_id,
            payload=json.dumps({"prompt": prompt}),
        )
        
        # Handle response
        content_type = response.get('contentType', '')
        response_obj = response.get('response')
        
        if hasattr(response_obj, 'read'):
            content = response_obj.read()
            if isinstance(content, bytes):
                content = content.decode('utf-8')
            
            # Check if content is in SSE (Server-Sent Events) format
            if content.startswith('data: ') or '\ndata: ' in content:
                # Parse SSE format
                lines = content.split('\n')
                parsed_content = []
                for line in lines:
                    if line.startswith('data: '):
                        # Extract the data after "data: " prefix
                        data_str = line[6:]  # Remove "data: " prefix
                        try:
                            # Try to parse as JSON
                            data_json = json.loads(data_str)
                            parsed_content.append(data_json)
                        except:
                            # If not JSON, just use the string
                            parsed_content.append(data_str)
                
                # Join all content pieces
                result = ''.join(str(item) for item in parsed_content)
                return result.strip()
            
            # Try to parse as JSON
            try:
                data = json.loads(content)
                if isinstance(data, dict) and 'result' in data:
                    data = data['result']
                if 'role' in data and 'content' in data:
                    content_list = data['content']
                    if isinstance(content_list, list) and len(content_list) > 0:
                        return content_list[0].get('text', str(content_list[0]))
                return str(data)
            except:
                return content
        
        return str(response_obj)
    except Exception as e:
        return f"Error invoking agent: {str(e)}"


# Tab 1: Document Upload & Extraction
def tab_document_extraction():
    """Document upload and extraction interface"""
    st.header("📄 Document Upload & Extraction")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Upload Documents")
        uploaded_files = st.file_uploader(
            "Upload PDF documents for extraction",
            type=['pdf'],
            accept_multiple_files=True,
            help="Upload one or more PDF files to extract information"
        )
        
        if uploaded_files:
            st.success(f"✅ {len(uploaded_files)} file(s) ready for upload")
            
            for file in uploaded_files:
                st.text(f"📎 {file.name} ({file.size / 1024:.2f} KB)")
    
    with col2:
        st.subheader("Extraction Settings")
        
        # Get available agents
        agents = fetch_agent_runtimes(AWS_REGION)
        extractor_agents = [a for a in agents if 'extractor' in a.get('agentRuntimeName', '').lower()]
        
        if extractor_agents:
            agent_options = {a.get('agentRuntimeName'): a.get('agentRuntimeArn') for a in extractor_agents}
            selected_agent = st.selectbox("Select Extractor Agent", options=list(agent_options.keys()))
            agent_arn = agent_options.get(selected_agent)
        else:
            st.warning("No extractor agents found")
            agent_arn = st.text_input("Agent ARN", help="Enter extractor agent ARN manually")
    
    st.divider()
    
    # Upload and extract button
    if st.button("🚀 Upload & Extract", type="primary", disabled=not uploaded_files):
        with st.spinner("Uploading files to S3..."):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            uploaded_count = 0
            for idx, file in enumerate(uploaded_files):
                file_key = f"{S3_INPUT_PREFIX}{file.name}"
                if upload_to_s3(file, S3_INPUT_BUCKET, file_key):
                    uploaded_count += 1
                status_text.text(f"Uploading: {idx + 1}/{len(uploaded_files)}")
                progress_bar.progress((idx + 1) / len(uploaded_files))
            
            progress_bar.empty()
            status_text.empty()
            
            if uploaded_count == len(uploaded_files):
                st.success(f"✅ Successfully uploaded {uploaded_count} file(s) to S3")
                
                # Trigger extraction
                if agent_arn:
                    st.info("🔄 Starting extraction process...")
                    session_id = str(uuid.uuid4())
                    
                    # Create a list of uploaded filenames to pass to the agent
                    uploaded_filenames = [file.name for file in uploaded_files]
                    extraction_prompt = f"Extract only these specific documents from the input bucket: {', '.join(uploaded_filenames)}"
                    
                    # Timer display
                    import time
                    start_time = time.time()
                    timer_placeholder = st.empty()
                    
                    with st.expander("View Extraction Log", expanded=True):
                        # Show initial timer
                        timer_placeholder.info(f"⏱️ Extraction in progress... 0s elapsed")
                        
                        result = invoke_agent(
                            agent_arn,
                            extraction_prompt,
                            session_id
                        )
                        st.code(result)
                    
                    # Calculate and display final time
                    elapsed_time = time.time() - start_time
                    timer_placeholder.success(f"✅ Extraction completed in {elapsed_time:.1f} seconds!")
                    
                    # Automatically invoke database agent to load data into DynamoDB
                    st.info("💾 Loading extracted data into DynamoDB...")
                    
                    # Find database agent
                    database_agents = [a for a in agents if 'database' in a.get('agentRuntimeName', '').lower()]
                    
                    if database_agents:
                        db_agent_arn = database_agents[0].get('agentRuntimeArn')
                        db_session_id = str(uuid.uuid4())
                        
                        with st.expander("View Database Import Log", expanded=False):
                            db_result = invoke_agent(
                                db_agent_arn,
                                "Import all extracted data from S3 to DynamoDB",
                                db_session_id
                            )
                            st.code(db_result)
                        
                        st.success("✅ Data loaded into DynamoDB! Go to the Validation tab to review results.")
                    else:
                        st.warning("⚠️ Database agent not found. Data extracted but not loaded into DynamoDB yet.")
                        st.info("💡 Please run the database agent manually to load data.")
                else:
                    st.warning("⚠️ No agent ARN selected. Files uploaded but extraction not started.")
            else:
                st.error(f"❌ Upload failed. Only {uploaded_count}/{len(uploaded_files)} files uploaded.")


# Tab 2: Extraction Visualization & Validation
def tab_validation():
    """Visualization and validation interface"""
    st.header("✅ Extraction Validation")
    
    # Add refresh button
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("🔄 Refresh", help="Reload documents from database"):
            st.rerun()
    
    # Fetch documents from DynamoDB
    documents = get_documents_from_dynamodb()
    
    if not documents:
        st.info("📭 No documents found. Please extract documents first.")
        return
    
    # Sort documents by extraction timestamp (newest first)
    documents.sort(key=lambda x: x.get('extraction_timestamp', ''), reverse=True)
    
    st.success(f"📊 Found {len(documents)} document(s)")
    
    # Document selector with better labeling
    doc_options = {}
    for idx, doc in enumerate(documents):
        source_file = os.path.basename(doc.get('source_file', 'Unknown'))
        doc_id = doc.get('document_id', '')[:8]
        timestamp = doc.get('extraction_timestamp', 'N/A')
        if timestamp != 'N/A':
            timestamp = timestamp[:19].replace('T', ' ')
        label = f"{source_file} | {timestamp} | ID: {doc_id}..."
        doc_options[label] = doc
    
    selected_doc_name = st.selectbox(
        "Select Document to Validate",
        options=list(doc_options.keys())
    )
    
    selected_doc = doc_options[selected_doc_name]
    
    st.divider()
    
    # Document info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Document ID", selected_doc.get('document_id', 'N/A')[:16] + "...")
    with col2:
        st.metric("Source File", os.path.basename(selected_doc.get('source_file', 'N/A')))
    with col3:
        extraction_time = selected_doc.get('extraction_timestamp', 'N/A')
        if extraction_time != 'N/A':
            extraction_time = extraction_time[:19].replace('T', ' ')
        st.metric("Extracted", extraction_time)
    
    st.divider()
    
    # Fields display and validation
    extracted_fields = selected_doc.get('extracted_fields', {})
    
    if not extracted_fields:
        st.warning("⚠️ No extracted fields found for this document.")
        return
    
    # Helper function to organize fields into groups
    def organize_fields_into_groups(fields_dict):
        """Organize fields into logical groups based on field names"""
        groups = {
            'Personal Information': [],
            'Contact Information': [],
            'Medical History': [],
            'Current Medications': [],
            'Allergies': [],
            'Insurance & Demographics': [],
            'Other Information': []
        }
        
        def flatten_and_categorize(fields, parent_key=''):
            """Flatten nested structure and categorize fields"""
            for key, value in fields.items():
                full_key = f"{parent_key}.{key}" if parent_key else key
                
                if isinstance(value, dict):
                    if 'value' in value and 'confidence' in value:
                        # This is a field with value/confidence
                        field_info = {
                            'name': full_key,
                            'value': value.get('value', ''),
                            'confidence': float(value.get('confidence', 0)),
                            'validated': value.get('validated', False)
                        }
                        
                        # Categorize based on field name (only add to ONE group)
                        key_lower = full_key.lower()
                        if any(term in key_lower for term in ['phone', 'email', 'address', 'emergency', 'contact']):
                            groups['Contact Information'].append(field_info)
                        elif any(term in key_lower for term in ['condition', 'disease', 'diagnosis', 'history', 'surgery', 'symptom']):
                            groups['Medical History'].append(field_info)
                        elif any(term in key_lower for term in ['medication', 'drug', 'prescription', 'dose']):
                            groups['Current Medications'].append(field_info)
                        elif any(term in key_lower for term in ['allergy', 'allergies', 'reaction']):
                            groups['Allergies'].append(field_info)
                        elif any(term in key_lower for term in ['insurance', 'policy', 'provider', 'ssn', 'member']):
                            groups['Insurance & Demographics'].append(field_info)
                        elif any(term in key_lower for term in ['name', 'age', 'gender', 'sex', 'birth', 'dob', 'patient']):
                            groups['Personal Information'].append(field_info)
                        else:
                            groups['Other Information'].append(field_info)
                    elif 'validated' in value and len(value) > 1:
                        # This is a section, recurse without the 'validated' key
                        flatten_and_categorize({k: v for k, v in value.items() if k != 'validated'}, full_key)
                    else:
                        # Generic nested structure
                        flatten_and_categorize(value, full_key)
                else:
                    # Scalar value, wrap and categorize
                    field_info = {
                        'name': full_key,
                        'value': str(value),
                        'confidence': 0.0,
                        'validated': False
                    }
                    groups['Other Information'].append(field_info)
        
        flatten_and_categorize(fields_dict)
        
        # Remove empty groups
        return {k: v for k, v in groups.items() if v}
    
    # Organize fields into groups
    grouped_fields = organize_fields_into_groups(extracted_fields)
    
    # Calculate statistics
    all_fields = [field for group in grouped_fields.values() for field in group]
    total_fields = len(all_fields)
    validated_fields = sum(1 for f in all_fields if f.get('validated', False))
    avg_confidence = sum(f.get('confidence', 0) for f in all_fields) / total_fields if total_fields > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Fields", total_fields)
    with col2:
        st.metric("Validated", f"{validated_fields}/{total_fields}")
    with col3:
        confidence_color = "🟢" if avg_confidence > 0.8 else "🟡" if avg_confidence > 0.5 else "🔴"
        st.metric("Avg Confidence", f"{confidence_color} {avg_confidence:.1%}")
    
    st.divider()
    
    # Display fields by group with data editor
    import pandas as pd
    
    for group_name, fields in grouped_fields.items():
        if not fields:
            continue
        
        with st.expander(f"📁 {group_name} ({len(fields)} fields)", expanded=True):
            # Create DataFrame for display
            df_data = []
            for field in fields:
                confidence = field.get('confidence', 0)
                validated = field.get('validated', False)
                
                # Confidence emoji
                if confidence > 0.8:
                    conf_display = f"🟢 {confidence:.0%}"
                elif confidence > 0.5:
                    conf_display = f"🟡 {confidence:.0%}"
                else:
                    conf_display = f"🔴 {confidence:.0%}"
                
                # Status emoji
                status_display = "✅ Validated" if validated else "⏳ Pending"
                
                df_data.append({
                    'Field': field['name'],
                    'Value': str(field['value']),
                    'Confidence': conf_display,
                    'Status': status_display
                })
            
            # Display as dataframe
            df = pd.DataFrame(df_data)
            
            # Show the table
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Field": st.column_config.TextColumn("Field Name", width="medium"),
                    "Value": st.column_config.TextColumn("Extracted Value", width="large"),
                    "Confidence": st.column_config.TextColumn("Confidence", width="small"),
                    "Status": st.column_config.TextColumn("Status", width="small")
                }
            )
            
            # Edit controls for this group
            st.markdown("**Edit & Validate:**")
            cols = st.columns(len(fields) if len(fields) <= 3 else 3)
            
            for idx, field in enumerate(fields):
                col_idx = idx % (len(fields) if len(fields) <= 3 else 3)
                with cols[col_idx]:
                    field_name = field['name']
                    current_value = field['value']
                    validated = field['validated']
                    
                    # Shorter display name for UI
                    display_name = field_name.split('.')[-1] if '.' in field_name else field_name
                    
                    # Use group_name + idx to ensure unique keys
                    unique_key = f"{group_name}_{idx}_{selected_doc.get('document_id')}_{field_name}"
                    
                    new_value = st.text_input(
                        display_name,
                        value=str(current_value),
                        key=f"edit_{unique_key}",
                        help=f"Full path: {field_name}"
                    )
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("💾 Save", key=f"save_{unique_key}", use_container_width=True):
                            if update_field_in_dynamodb(
                                selected_doc.get('document_id'),
                                field_name,
                                new_value,
                                validated=True
                            ):
                                st.success("✅ Saved")
                                st.rerun()
                    
                    with col_b:
                        if not validated:
                            if st.button("✓ OK", key=f"validate_{unique_key}", use_container_width=True):
                                if update_field_in_dynamodb(
                                    selected_doc.get('document_id'),
                                    field_name,
                                    current_value,
                                    validated=True
                                ):
                                    st.success("✅ Done")
                                    st.rerun()
            
            st.divider()
    
    # Bulk validation
    st.subheader("🎯 Bulk Actions")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✓ Validate All High Confidence (>80%)", type="primary"):
            count = 0
            for field_name, field_data in extracted_fields.items():
                if isinstance(field_data, dict):
                    confidence = float(field_data.get('confidence', 0))
                    if confidence > 0.8 and not field_data.get('validated', False):
                        if update_field_in_dynamodb(
                            selected_doc.get('document_id'),
                            field_name,
                            field_data.get('value', ''),
                            validated=True
                        ):
                            count += 1
            st.success(f"✅ Validated {count} field(s)")
            st.rerun()
    
    with col2:
        if st.button("📊 Export to JSON"):
            export_data = {
                'document_id': selected_doc.get('document_id'),
                'source_file': selected_doc.get('source_file'),
                'extraction_timestamp': selected_doc.get('extraction_timestamp'),
                'fields': extracted_fields
            }
            st.download_button(
                "⬇️ Download JSON",
                data=json.dumps(export_data, indent=2),
                file_name=f"validated_{selected_doc.get('document_id')[:8]}.json",
                mime="application/json"
            )


# Tab 3: Document Q&A
def tab_qa():
    """Document Q&A interface"""
    st.header("💬 Document Q&A")
    
    st.info("Ask questions about the extracted documents. The system will search through all validated data to answer your questions.")
    
    # Get available agents
    agents = fetch_agent_runtimes(AWS_REGION)
    qa_agents = [a for a in agents if 'quality' in a.get('agentRuntimeName', '').lower() or 'qa' in a.get('agentRuntimeName', '').lower()]
    
    if qa_agents:
        agent_options = {a.get('agentRuntimeName'): a.get('agentRuntimeArn') for a in qa_agents}
        selected_agent = st.selectbox("Select Q&A Agent", options=list(agent_options.keys()))
        agent_arn = agent_options.get(selected_agent)
    else:
        st.warning("No Q&A agents found")
        agent_arn = st.text_input("Agent ARN", help="Enter Q&A agent ARN manually")
    
    # Display document summaries
    documents = get_documents_from_dynamodb()
    
    if documents:
        with st.expander(f"📚 Available Documents ({len(documents)})"):
            for doc in documents:
                st.markdown(f"**{os.path.basename(doc.get('source_file', 'Unknown'))}**")
                fields = doc.get('extracted_fields', {})
                validated = sum(1 for f in fields.values() if isinstance(f, dict) and f.get('validated', False))
                st.caption(f"Fields: {len(fields)} | Validated: {validated}")
    
    st.divider()
    
    # Initialize chat history
    if "qa_messages" not in st.session_state:
        st.session_state.qa_messages = []
    
    # Display chat history
    for message in st.session_state.qa_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if question := st.chat_input("Ask a question about the documents..."):
        if not agent_arn:
            st.error("❌ Please select a Q&A agent first")
            return
        
        # Add user message
        st.session_state.qa_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        
        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                session_id = str(uuid.uuid4())
                response = invoke_agent(agent_arn, question, session_id)
                st.markdown(response)
        
        # Add assistant message
        st.session_state.qa_messages.append({"role": "assistant", "content": response})
    
    # Clear chat button
    if st.button("🗑️ Clear Chat"):
        st.session_state.qa_messages = []
        st.rerun()
    
    # Example questions
    with st.expander("💡 Example Questions"):
        st.markdown("""
        - What information was extracted from the medical forms?
        - Which fields have low confidence scores?
        - Show me all patient contact information
        - What medical conditions were mentioned?
        - List all unvalidated fields
        - What is the average confidence score across all documents?
        """)


# Main application
def main():
    """Main application entry point"""
    st.markdown('<h1 class="main-header">📝 Intelligent Document Processing</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        # Use absolute path for image
        import pathlib
        current_dir = pathlib.Path(__file__).parent
        image_path = current_dir / "static" / "gen-ai-dark.svg"
        
        if image_path.exists():
            st.image(str(image_path), width=100)
        else:
            st.markdown("### 🤖")
        
        st.title("IDP System")
        
        st.divider()
        
        st.subheader("📊 System Status")
        
        # Check AWS connectivity
        try:
            clients = get_aws_clients()
            
            # Get AWS Account ID
            try:
                sts_client = boto3.client('sts', region_name=AWS_REGION)
                account_id = sts_client.get_caller_identity()['Account']
                st.success(f"✅ AWS Connected")
                st.caption(f"Account: {account_id}")
            except Exception as e:
                st.success("✅ AWS Connected")
                st.caption("Account: Unable to retrieve")
            
            # Check S3 Input Bucket
            try:
                clients['s3'].head_bucket(Bucket=S3_INPUT_BUCKET)
                st.success(f"✅ S3 Input Bucket")
                st.caption(f"Bucket: {S3_INPUT_BUCKET}")
            except Exception as e:
                st.error(f"❌ S3 Input Bucket")
                st.caption(f"Bucket: {S3_INPUT_BUCKET}")
            
            # Check S3 Output Bucket
            try:
                clients['s3'].head_bucket(Bucket=S3_OUTPUT_BUCKET)
                st.success(f"✅ S3 Output Bucket")
                st.caption(f"Bucket: {S3_OUTPUT_BUCKET}")
            except Exception as e:
                st.error(f"❌ S3 Output Bucket")
                st.caption(f"Bucket: {S3_OUTPUT_BUCKET}")
            
            # Check DynamoDB table
            try:
                table = clients['dynamodb'].Table(DYNAMODB_TABLE_NAME)
                table.table_status
                st.success(f"✅ DynamoDB Table")
                st.caption(f"Table: {DYNAMODB_TABLE_NAME}")
            except Exception as e:
                st.warning(f"⚠️ DynamoDB Table")
                st.caption(f"Table: {DYNAMODB_TABLE_NAME}")
            
            # Display AWS Region
            st.info(f"🌍 AWS Region")
            st.caption(f"Region: {AWS_REGION}")
        except Exception as e:
            st.error(f"❌ AWS Connection Failed")
            st.caption(f"Error: {str(e)}")
        
        st.divider()
        
        st.subheader("ℹ️ About")
        st.caption("""
        This application provides an end-to-end document processing workflow:
        
        1. **Extract**: Upload and extract data from documents
        2. **Validate**: Review and validate extracted information
        3. **Query**: Ask questions about your documents
        """)
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs([
        "📤 Upload & Extract",
        "✅ Validate & Review",
        "💬 Q&A"
    ])
    
    with tab1:
        tab_document_extraction()
    
    with tab2:
        tab_validation()
    
    with tab3:
        tab_qa()


if __name__ == "__main__":
    main()
