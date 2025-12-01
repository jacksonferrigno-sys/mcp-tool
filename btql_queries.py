"""
BTQL Query Construction and Execution

Handles all Braintrust Query Language operations.
"""

import os
from typing import Dict, List, Optional, Any
import requests

# Constants
PROJECT_NAME = "Chat"  # Project name (for display)
PROJECT_ID = "ec6cb39d-161d-4669-953f-444fd5c386f6"  # Project UUID (for queries)
BRAINTRUST_API_KEY = os.getenv("BRAINTRUST_API_KEY")
BRAINTRUST_API_URL = os.getenv("BRAINTRUST_API_URL", "https://api.braintrust.dev")
DEBUG = os.getenv("DEBUG", "0") == "1"


def execute_btql_query(query: str) -> Dict[str, Any]:
    """
    Execute a BTQL query against the Braintrust API.
    
    Args:
        query: BTQL query string
        
    Returns:
        API response as dictionary
        
    Raises:
        Exception: If API call fails
    """
    if not BRAINTRUST_API_KEY:
        raise ValueError("BRAINTRUST_API_KEY environment variable not set")
    
    headers = {
        "Authorization": f"Bearer {BRAINTRUST_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "query": query,
        "fmt": "json"
    }
    
    if DEBUG:
        print(f"Executing BTQL query:\n{query}")
    
    response = requests.post(
        f"{BRAINTRUST_API_URL}/btql",  # Fixed: removed /v1
        headers=headers,
        json=payload,
        timeout=30
    )
    
    if response.status_code != 200:
        # Don't dump HTML in error messages
        error_preview = response.text[:200] if len(response.text) > 200 else response.text
        raise Exception(
            f"BTQL query failed: {response.status_code} - {error_preview}..."
        )
    
    # Check if response is JSON
    content_type = response.headers.get('Content-Type', '')
    if 'application/json' not in content_type:
        raise Exception(
            f"Expected JSON response but got {content_type}. "
            f"Response preview: {response.text[:200]}..."
        )
    
    return response.json()


def build_model_filter(model_filter: Optional[str]) -> str:
    """
    Translate model filter string into BTQL clause.
    
    Args:
        model_filter: One of "mini", "NOT mini", "gpt-5", or None
        
    Returns:
        BTQL filter clause string (without leading AND)
    """
    if model_filter is None:
        return ""
    
    if model_filter == "mini":
        return "metadata.model LIKE '%mini%'"
    elif model_filter == "NOT mini":
        # Return both conditions - they'll be joined with AND by the caller
        return "metadata.model NOT LIKE '%mini%' AND metadata.model IS NOT NULL"
    elif model_filter == "gpt-5":
        return "metadata.model LIKE '%gpt-5%'"
    else:
        # Allow custom model filters
        return f"metadata.model LIKE '%{model_filter}%'"


def build_additional_filters(additional_filters: Optional[Dict[str, Any]]) -> str:
    """
    Build BTQL filter clauses from additional filter dictionary.
    
    Args:
        additional_filters: Dictionary of field: value pairs
        
    Returns:
        BTQL filter clause string (without leading AND)
    """
    if not additional_filters:
        return ""
    
    clauses = []
    for field, value in additional_filters.items():
        if isinstance(value, str):
            clauses.append(f"{field} = '{value}'")
        else:
            clauses.append(f"{field} = {value}")
    
    return " AND ".join(clauses)


def build_fetch_logs_query(
    model_filter: Optional[str],
    hours_back: int,
    exclude_first_hours: int,
    span_name_filter: str,
    additional_filters: Optional[Dict[str, Any]],
    limit: int
) -> str:
    """
    Build a complete BTQL query for fetching logs.
    
    Args:
        model_filter: Model filter string
        hours_back: Hours to look back
        exclude_first_hours: Hours to exclude from recent
        span_name_filter: Span name pattern
        additional_filters: Additional filter conditions
        limit: Maximum number of records
        
    Returns:
        Complete BTQL query string
    """
    select_clause = "input, output, metadata.model, metadata.userID, created, id, span_attributes.name"
    
    filter_parts = [
        f"span_attributes.name LIKE '%{span_name_filter}%'",
        f"created < now() - interval {exclude_first_hours} hour",
        f"created > now() - interval {hours_back} hour",
        "output IS NOT NULL",
        "output != ''",
        "metadata.userID IS NOT NULL"
    ]
    
    # Add model filter
    model_filter_clause = build_model_filter(model_filter)
    if model_filter_clause:
        filter_parts.append(model_filter_clause)
    
    # Add additional filters
    additional_filter_clause = build_additional_filters(additional_filters)
    if additional_filter_clause:
        filter_parts.append(additional_filter_clause)
    
    filter_clause = " AND ".join(filter_parts)
    
    # BTQL uses lowercase keywords: from, select, filter, limit
    # Use PROJECT_ID (UUID) not PROJECT_NAME
    query = f"""from: project_logs('{PROJECT_ID}')
select: {select_clause}
filter: {filter_clause}
limit: {limit}"""
    
    return query


def format_log_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Format raw API log records into consistent structure.
    Filters out system messages from input to reduce size.
    
    Args:
        records: Raw records from Braintrust API
        
    Returns:
        List of formatted record dictionaries
    """
    formatted_records = []
    
    for record in records:
        # Get input and filter out system messages
        raw_input = record.get("input")
        filtered_input = raw_input
        
        if isinstance(raw_input, list):
            # Filter out system messages, keep only user/assistant
            filtered_input = [
                msg for msg in raw_input 
                if isinstance(msg, dict) and msg.get("role") != "system"
            ]
        
        # Extract userID - BTQL returns it at top level when you select metadata.userID
        user_id = record.get("userID")
        if user_id is None and isinstance(record.get("metadata"), dict):
            user_id = record.get("metadata", {}).get("userID")
        
        formatted_records.append({
            "id": record.get("id"),
            "user_id": user_id,
            "input": filtered_input,
            "output": record.get("output"),
            "model": record.get("metadata", {}).get("model") if isinstance(record.get("metadata"), dict) else record.get("model"),
            "created": record.get("created"),
            "span_name": record.get("span_attributes", {}).get("name") if isinstance(record.get("span_attributes"), dict) else None,
            "metadata": record.get("metadata", {})
        })
    
    return formatted_records

