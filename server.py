"""
Braintrust Analysis MCP Server

An MCP server built using FastMCP that provides tools for analyzing Braintrust conversation logs.
Claude performs all analysis, pattern recognition, and decision-making, while this server handles
data retrieval, statistical calculations, and report generation.
"""

import os
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from fastmcp import FastMCP

# Import business logic modules
from utils.btql_queries import (
    execute_btql_query,
    build_fetch_logs_query,
    format_log_records,
    PROJECT_NAME,
    PROJECT_ID
)

# Import prompts
from prompts.prompts import (
    get_btql_query_prompt,
    get_tolan_analysis_prompt
)

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("braintrust-analyzer")


# ==================== MCP Prompts ====================
@mcp.prompt()
def btql_query_prompt() -> str:
    """
    System prompt for querying Braintrust logs.
    """
    return get_btql_query_prompt()


@mcp.prompt()
def tolan_analysis_prompt() -> str:
    """
    System prompt for analyzing Tolan conversation data to identify assistant vs. friend behaviors.
    
    Returns the complete system prompt that guides Claude in analyzing Braintrust logs
    to identify when the AI behaves like an assistant instead of a best friend.
    """
    return get_tolan_analysis_prompt()


# ==================== MCP Tools ====================


@mcp.tool()
def fetch_logs(
    model_filter: Optional[str] = None,
    sample_size: int = 150,
    hours_back: int = 48,
    exclude_first_hours: int = 1,
    span_name_filter: str = "chat",
    additional_filters: Optional[Dict[str, Any]] = None,
    auto_save_to_file: bool = True,
    filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieve conversation logs from Braintrust project 'Chat' (ID: ec6cb39d-161d-4669-953f-444fd5c386f6).
    
    IMPORTANT: By default, logs are automatically saved to a file to prevent context overflow.
    The response only contains metadata, not the actual logs. Use read_logs_from_file() to analyze.
    
    Args:
        model_filter: Filter by model - "mini", "NOT mini", "gpt-5", or None for all models
        sample_size: Number of logs to retrieve (batched if > 250)
        hours_back: How far back to look for data (in hours)
        exclude_first_hours: Exclude most recent N hours (for incomplete streaming responses)
        span_name_filter: Filter by span name pattern
        additional_filters: Custom BTQL filter conditions as dict
        auto_save_to_file: If True, saves to file and returns only metadata (default: True)
        filename: Custom filename for saved logs (auto-generated if None)
        
    Returns:
        Dictionary containing:
        - file_path: Where logs were saved (if auto_save_to_file=True)
        - record_count: Number of logs fetched
        - sampling_info: Metadata about the query
        - message: Instructions on how to read the logs
    """
    # Handle pagination for large sample sizes
    if sample_size > 250:
        # For now, just limit to 250 and note in response
        # TODO: Implement proper cursor-based pagination
        actual_limit = 250
        pagination_note = f"Requested {sample_size} but limited to 250. Pagination not yet implemented."
    else:
        actual_limit = sample_size
        pagination_note = None
    
    # Build query
    query = build_fetch_logs_query(
        model_filter=model_filter,
        hours_back=hours_back,
        exclude_first_hours=exclude_first_hours,
        span_name_filter=span_name_filter,
        additional_filters=additional_filters,
        limit=actual_limit
    )
    
    # Execute query with retry for transient 500 errors
    max_retries = 3
    last_error = None
    
    for attempt in range(max_retries):
        try:
            response = execute_btql_query(query)
            records = response.get("data", [])
            formatted_records = format_log_records(records)
            
            # If auto-save is enabled, save to file and return minimal response
            if auto_save_to_file:
                import json
                from pathlib import Path
                from datetime import datetime
                
                # Generate filename if not provided
                if filename is None:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    model_str = model_filter if model_filter else "all"
                    filename = f"logs_{model_str}_{timestamp}.json"
                
                # Ensure .json extension
                if not filename.endswith(".json"):
                    filename += ".json"
                
                # Create full data structure
                full_data = {
                    "query_executed": query,
                    "sample_size": sample_size,
                    "total_available": len(records),
                    "records": formatted_records,
                    "sampling_info": {
                        "requested": sample_size,
                        "returned": len(formatted_records),
                        "date_range_hours": f"{hours_back} hours back, excluding first {exclude_first_hours} hour(s)",
                        "model_filter": model_filter,
                        "pagination_note": pagination_note,
                        "retries": attempt if attempt > 0 else None
                    }
                }
                
                # Save to file
                filepath = Path(filename)
                with open(filepath, "w") as f:
                    json.dump(full_data, f, indent=2)
                
                file_size = filepath.stat().st_size
                
                # Return minimal response with file info
                return {
                    "status": "success",
                    "file_path": str(filepath.absolute()),
                    "filename": filename,
                    "record_count": len(formatted_records),
                    "file_size_bytes": file_size,
                    "sampling_info": {
                        "requested": sample_size,
                        "returned": len(formatted_records),
                        "model_filter": model_filter,
                        "retries": attempt if attempt > 0 else None
                    },
                    "message": f"Saved {len(formatted_records)} logs to {filename}. Use read_logs_from_file('{filename}') to analyze."
                }
            
            # If auto-save disabled, return full data (NOT RECOMMENDED for >10 logs)
            else:
                return {
                    "query_executed": query,
                    "sample_size": sample_size,
                    "total_available": len(records),
                    "records": formatted_records,
                    "sampling_info": {
                        "requested": sample_size,
                        "returned": len(formatted_records),
                        "date_range_hours": f"{hours_back} hours back, excluding first {exclude_first_hours} hour(s)",
                        "model_filter": model_filter,
                        "pagination_note": pagination_note,
                        "retries": attempt if attempt > 0 else None
                    }
                }
        except Exception as e:
            last_error = str(e)
            # Retry on 500 errors (Braintrust server issues)
            if "500" in last_error and attempt < max_retries - 1:
                import time
                time.sleep(1)  # Wait 1 second before retry
                continue
            # Don't retry on other errors
            break
    
    # If we got here, all retries failed
    return {
        "error": last_error,
        "query_executed": query,
        "sample_size": sample_size,
        "records": [],
        "sampling_info": {
            "requested": sample_size,
            "returned": 0,
            "error": last_error,
            "retries_attempted": max_retries - 1
        }
    }


@mcp.tool()
def save_logs_to_file(
    logs_data: Dict[str, Any],
    filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    Save fetched logs to a JSON file to prevent context window overflow.
    
    NOTE: fetch_logs() and execute_custom_btql() now auto-save by default, so this tool
    is mainly useful for re-saving or transforming already-loaded data.
    
    Args:
        logs_data: The complete result from fetch_logs() or other data to save
        filename: Name for the output file (auto-generated if None)
        
    Returns:
        Dictionary containing:
        - status: "success" or "error"
        - file_path: Absolute path to saved file
        - record_count: Number of records saved
        - file_size_bytes: Size of the file
    """
    import json
    from pathlib import Path
    from datetime import datetime
    
    try:
        # Generate filename if not provided
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_filter = logs_data.get("sampling_info", {}).get("model_filter", "all")
            filename = f"logs_{model_filter}_{timestamp}.json"
        
        # Ensure .json extension
        if not filename.endswith(".json"):
            filename += ".json"
        
        # Save to current directory
        filepath = Path(filename)
        
        with open(filepath, "w") as f:
            json.dump(logs_data, f, indent=2)
        
        file_size = filepath.stat().st_size
        record_count = len(logs_data.get("records", []))
        
        return {
            "status": "success",
            "file_path": str(filepath.absolute()),
            "record_count": record_count,
            "file_size_bytes": file_size,
            "message": f"Saved {record_count} logs to {filename}"
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@mcp.tool()
def read_logs_from_file(
    filename: str,
    start_index: int = 0,
    count: int = 10
) -> Dict[str, Any]:
    """
    Read logs from a previously saved JSON file in batches.
    
    This allows you to analyze large datasets incrementally without context overflow.
    You can read 10-20 logs at a time, analyze them, then read the next batch.
    
    Args:
        filename: Name of the JSON file (e.g., "mini_logs.json")
        start_index: Which record to start from (0-based)
        count: How many records to return (max 50)
        
    Returns:
        Dictionary containing:
        - records: Batch of log records
        - batch_info: Information about this batch (start, count, total)
        - has_more: Whether there are more records after this batch
    """
    import json
    from pathlib import Path
    
    try:
        filepath = Path(filename)
        
        if not filepath.exists():
            return {
                "error": f"File not found: {filename}",
                "records": [],
                "batch_info": {}
            }
        
        with open(filepath, "r") as f:
            data = json.load(f)
        
        all_records = data.get("records", [])
        total_records = len(all_records)
        
        # Limit count to max 50
        count = min(count, 50)
        
        # Get the batch
        end_index = min(start_index + count, total_records)
        batch = all_records[start_index:end_index]
        
        has_more = end_index < total_records
        
        return {
            "records": batch,
            "batch_info": {
                "start_index": start_index,
                "end_index": end_index,
                "count_returned": len(batch),
                "total_records": total_records,
                "filename": filename
            },
            "has_more": has_more,
            "next_start_index": end_index if has_more else None
        }
    
    except Exception as e:
        return {
            "error": str(e),
            "records": [],
            "batch_info": {}
        }


@mcp.tool()
def execute_custom_btql(
    query: str,
    limit: int = 100,
    auto_save_to_file: bool = True,
    filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute a custom BTQL query for advanced use cases (project 'Chat': ec6cb39d-161d-4669-953f-444fd5c386f6).
    
    IMPORTANT: By default, results are automatically saved to a file to prevent context overflow.
    The response only contains metadata, not the actual records. Use read_logs_from_file() to analyze.
    
    Args:
        query: Full BTQL query string (will be modified to use project 'chat')
        limit: Maximum records to return
        auto_save_to_file: If True, saves to file and returns only metadata (default: True)
        filename: Custom filename for saved results (auto-generated if None)
        
    Returns:
        Dictionary containing:
        - file_path: Where results were saved (if auto_save_to_file=True)
        - query_executed: The actual query executed
        - record_count: Number of records returned
    """
    import json
    from pathlib import Path
    from datetime import datetime
    
    try:
        # Ensure query uses the correct project ID
        if "FROM:" in query or "from:" in query.lower():
            # Query already has FROM clause, ensure it uses correct project ID
            modified_query = query
        else:
            # Add FROM clause with project ID
            modified_query = f"{query}\nfrom: project_logs('{PROJECT_ID}')"
        
        # Add or update LIMIT
        if "LIMIT:" not in modified_query and "limit:" not in modified_query.lower():
            modified_query += f"\nlimit: {limit}"
        
        # Execute query
        response = execute_btql_query(modified_query)
        records = response.get("data", [])
        
        # If auto-save is enabled, save to file and return minimal response
        if auto_save_to_file:
            # Generate filename if not provided
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"btql_results_{timestamp}.json"
            
            # Ensure .json extension
            if not filename.endswith(".json"):
                filename += ".json"
            
            # Create full data structure
            full_data = {
                "query_executed": modified_query.strip(),
                "record_count": len(records),
                "records": records
            }
            
            # Save to file
            filepath = Path(filename)
            with open(filepath, "w") as f:
                json.dump(full_data, f, indent=2)
            
            file_size = filepath.stat().st_size
            
            # Return minimal response with file info
            return {
                "status": "success",
                "file_path": str(filepath.absolute()),
                "filename": filename,
                "query_executed": modified_query.strip(),
                "record_count": len(records),
                "file_size_bytes": file_size,
                "message": f"Saved {len(records)} records to {filename}. Use read_logs_from_file('{filename}') to analyze."
            }
        
        # If auto-save disabled, return full data (NOT RECOMMENDED for large result sets)
        else:
            return {
                "query_executed": modified_query.strip(),
                "records": records,
                "record_count": len(records)
            }
    
    except Exception as e:
        return {
            "error": str(e),
            "query_executed": query.strip() if 'modified_query' not in locals() else modified_query.strip(),
            "records": [] if not auto_save_to_file else None,
            "record_count": 0
        }


# ==================== Main ====================


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
