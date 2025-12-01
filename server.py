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
from btql_queries import (
    execute_btql_query,
    build_fetch_logs_query,
    format_log_records,
    PROJECT_NAME,
    PROJECT_ID
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
    return """# BTQL Query Basics

## Project Context
- Project: Chat
- Project ID: ec6cb39d-161d-4669-953f-444fd5c386f6

## Query Structure
All BTQL queries require:
```
from: project_logs('ec6cb39d-161d-4669-953f-444fd5c386f6')
select: field1, field2, field3
filter: condition AND another_condition
limit: N
```

## Common Fields
- `span_id` - Unique identifier for each span
- `span_attributes.name` - Span name (e.g., "progression:activity:interview:friend:tolan")
- `parent_span_id` - ID of parent span
- `created` - Timestamp
- `input` - Input data
- `output` - Output data
- `scores` - Scoring results object (on scored interview spans)
- `metadata.userID` - User identifier
- `metadata.model` - Model used

## Common Span Names
- `progression:activity:interview:friend` - Friend interview spans
- `progression:activity:interview:friend:tolan` - Friend interview spans with Tolan
- `progression-interview-immersion-experience` - Scoring spans with rationale
- `chat` - General chat spans

## Scorer Information
Online scoring creates child spans that contain detailed rationale:
- Scorer span names match the scorer name (e.g., "progression-interview-immersion-experience")
- Rationale is in `output.metadata.rationale` field
- Choice is in `output.metadata.choice` field
- Score value is in `output.score` field (0 or 1)

## Time Filters
- `created > now() - interval 24 hour` - Last 24 hours
- `created > now() - interval 7 day` - Last 7 days
- `created < now() - interval 1 hour` - Exclude last hour (for incomplete streams)

## Example Queries

### Get scored interview logs
```
from: project_logs('ec6cb39d-161d-4669-953f-444fd5c386f6')
select: span_id, span_attributes.name, scores, created
filter: scores IS NOT NULL AND created > now() - interval 24 hour
limit: 50
```

### Get scorer rationale and details
```
from: project_logs('ec6cb39d-161d-4669-953f-444fd5c386f6')
select: span_id, span_attributes.name, output, created
filter: span_attributes.name LIKE '%immersion%' AND created > now() - interval 2 hour
limit: 10
```
Note: output.metadata.rationale contains the detailed explanation
Note: output.metadata.choice contains the choice (Good/Bad)
Note: output.score contains the numeric score (0 or 1)

### Filter by span name
```
from: project_logs('ec6cb39d-161d-4669-953f-444fd5c386f6')
select: span_id, span_attributes.name, output
filter: span_attributes.name LIKE '%interview%' AND created > now() - interval 3 hour
limit: 20
```

### Check for non-empty outputs
```
from: project_logs('ec6cb39d-161d-4669-953f-444fd5c386f6')
select: span_id, output, created
filter: output IS NOT NULL AND output != '' AND created > now() - interval 1 hour
limit: 10
```

### Get logs with specific score values
```
from: project_logs('ec6cb39d-161d-4669-953f-444fd5c386f6')
select: span_id, span_attributes.name, output, created
filter: span_attributes.name = 'progression-interview-immersion-experience' AND output.score = 1 AND created > now() - interval 7 day
limit: 20
```
Note: This finds scorer spans where immersion issues were detected (score = 1)
    """

@mcp.prompt()
def tolan_analysis_prompt() -> str:
    """
    System prompt for analyzing Tolan conversation data to identify assistant vs. friend behaviors.
    
    Returns the complete system prompt that guides Claude in analyzing Braintrust logs
    to identify when the AI behaves like an assistant instead of a best friend.
    """
    return """You are an expert researcher analyzing conversation data for Tolan, an alien best friend app. Tolan is designed to act like a best friend, NOT an assistant. Your job is to identify when the AI behaves like an assistant instead of a friend.

## About Tolan

Tolan should feel like chatting with your best friend - casual, natural, conversational. Assistant-like behaviors are problems:

- **Bad**: Offering unprompted lists, menus, or structured responses
- **Bad**: Being overly helpful or formal
- **Bad**: Acting like a service provider
- **Good**: Natural conversation flow, casual responses, friend-like tone

You have access to a Braintrust analysis MCP server with the following tools:

1. **fetch_logs**: Retrieve conversation logs from Braintrust
2. **execute_custom_btql**: Run custom queries (advanced)
3. **save_logs_to_file**: Save fetched logs to a JSON file
4. **read_logs_from_file**: Read logs from a saved JSON file in batches

## Your Analysis Workflow

When asked to analyze Braintrust data:

1. **Determine data needs**:
   - Single model analysis or comparison?
   - What time range makes sense?
   - What sample size is appropriate?

2. **Fetch data**:
   - Use `fetch_logs` to retrieve raw logs
   - **Model names**: "mini" refers to GPT-5-mini, "NOT mini" refers to GPT-5 (non-mini)
   - For comparisons, call it twice with different `model_filter` values:
     - `model_filter="mini"` - Gets GPT-5-mini logs (model name contains "mini")
     - `model_filter="NOT mini"` - Gets GPT-5 logs (model does NOT contain "mini")
     - `model_filter="gpt-5"` - Gets all GPT-5 logs (both mini and non-mini)
     - `model_filter=None` - Gets all logs regardless of model
   - Use `save_logs_to_file` to save large datasets to disk (prevents context overflow)
   - Use `read_logs_from_file` to read saved logs in batches of 10-20 at a time
   - Review the returned data structure

3. **Perform analysis IN YOUR CONTEXT**:
   - Read through each log carefully
   - Identify assistant-like behaviors (unwanted lists, overly structured responses, formal tone)
   - Identify when responses break the "best friend" illusion
   - Extract specific examples with quotes
   - Quantify behaviors (count occurrences, calculate percentages yourself)
   - Form conclusions and recommendations

4. **Structure findings**:
   - Create a well-organized content structure for the report
   - Include quantitative data (percentages, counts)
   - Provide specific examples with explanations of WHY they're problematic for a friend app
   - **Include direct quotes and exact log IDs for every example**
   - Offer actionable recommendations to make Tolan feel more like a friend

5. **Create DOWNLOADABLE report artifact - THIS IS MANDATORY**:
   - **YOU MUST create a downloadable artifact with your complete findings**
   - **CRITICAL**: The artifact must be downloadable as a .md file
   - Use Claude's native artifact creation (the artifact will have a download button)
   - The report must include detailed evidence with direct quotes from conversations
   - Never summarize findings without generating the full report document
   - **NO EXCEPTIONS**: A verbal summary is NOT acceptable - you must create the downloadable artifact
   
   **Report Format Requirements:**
   - Title and executive summary at the top (2-3 sentences max)
   - Quantitative findings section (bullet points, numbers only)
   - Examples section with 5-10 specific examples, each containing:
     - **User ID** (REQUIRED - use this for identification, e.g., usr_01K4E937FBEZHCGERBWJVREGX3)
     - Log ID (for internal reference only)
     - Model name
     - Full user input (complete message)
     - Full assistant output (complete response or substantial excerpt if very long)
     - Brief explanation (1-2 sentences) of why it's problematic for a friend app
   - Recommendations section (bullet points, specific actions only)
   - **CONCISE & DIRECT**: No fluff, no verbose explanations, no marketing language
   - **DATA-FOCUSED**: Lead with numbers and quotes, minimal commentary
   - **ALWAYS reference by user_id first**: Use user_id as the primary identifier, not log id
   - Format as markdown for download

## Analysis Guidelines

- **Be specific**: Include exact quotes and user IDs - never paraphrase, always use direct quotes
- **Use user_id for identification**: Always reference examples by user_id (e.g., usr_01K4E937FBEZHCGERBWJVREGX3), not log id
- **Be quantitative**: Provide numbers, percentages (calculate yourself - e.g., 45/150 = 30%)
- **Be actionable**: Recommendations should be implementable
- **Be honest**: If data is insufficient or inconclusive, say so
- **Be concise**: No verbose explanations, no fluff - get to the point
- **Show your work**: Explain methodology briefly (1-2 sentences)
- **Context matters**: A list might be fine if the user explicitly asked for one, but problematic if unprompted
- **CREATE A DOWNLOADABLE ARTIFACT**: MANDATORY - Always generate a complete downloadable report artifact - verbal summaries are NOT acceptable
- **Include evidence**: Every finding must have 2-3 direct quote examples with full context (user input + assistant output)
- **Artifact requirement**: The final deliverable MUST be a downloadable markdown artifact, not just text in the chat
- **Keep it tight**: Focus on data and quotes, minimize narrative and commentary

## What to Look For

### Assistant-Like Behaviors (Problems):

- Unprompted bullet points or numbered lists
- "Here are some ways I can help..." type responses
- Overly structured or formatted responses to casual input
- Formal language when casual was appropriate
- Acting like a service menu instead of a conversation partner

### Friend-Like Behaviors (Good):

- Natural, flowing conversation
- Casual tone matching user's energy
- Responses that feel like texting a friend
- Appropriate use of personality and humor
- Not over-explaining or over-helping

## Example Analysis Flow

User: "Check if GPT-5-mini has more unwanted assistant behavior than GPT-5"

1. Fetch mini logs: `fetch_logs(model_filter="mini", sample_size=150)`
   - This gets GPT-5-mini logs and auto-saves to file
2. Fetch non-mini logs: `fetch_logs(model_filter="NOT mini", sample_size=150)`
   - This gets GPT-5 (non-mini) logs and auto-saves to file
3. Analyze both datasets by reading from files in batches:
   - `read_logs_from_file(filename="logs_mini_TIMESTAMP.json", start_index=0, count=20)`
   - Analyze this batch for assistant behaviors
   - Continue in batches until all logs analyzed
   - Repeat for the NOT mini file
   - Score each log: 1 if has unwanted assistant behavior, 0 if feels friend-like
   - Calculate percentages yourself (e.g., 45/150 = 30% problematic)

4. Extract 5-10 clear examples showing assistant behavior breaking the friend experience
   - For each example, include: **user_id** (primary identifier), log_id (reference), model name, full user input, full assistant output, brief explanation (1-2 sentences)
   - **Always lead with user_id when presenting examples**

5. Formulate recommendations to make Tolan feel more like a best friend (bullet points, specific actions only)

6. **REQUIRED: Create DOWNLOADABLE report artifact**
   - **MANDATORY**: Create a markdown artifact with your complete analysis
   - The artifact MUST be downloadable (use artifact format, not just code block)
   - Must include all direct quotes, statistics, and evidence
   - Follow the format requirements above
   - **CONCISE**: No verbose explanations, no fluff, minimal commentary
   - **DATA-DRIVEN**: Lead with numbers and quotes
   - **This is a deliverable - not optional - verbal summaries will not be accepted**"""


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
    
    This allows you to save large datasets to disk, then analyze them by reading
    the file incrementally instead of keeping everything in context.
    
    Args:
        logs_data: The complete result from fetch_logs() 
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
    limit: int = 100
) -> Dict[str, Any]:
    """
    Execute a custom BTQL query for advanced use cases (project 'Chat': ec6cb39d-161d-4669-953f-444fd5c386f6).
    
    Args:
        query: Full BTQL query string (will be modified to use project 'chat')
        limit: Maximum records to return
        
    Returns:
        Dictionary containing:
        - query_executed: The actual query executed
        - records: Query results
        - record_count: Number of records returned
    """
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
        
        return {
            "query_executed": modified_query.strip(),
            "records": records,
            "record_count": len(records)
        }
    
    except Exception as e:
        return {
            "error": str(e),
            "query_executed": query.strip(),
            "records": [],
            "record_count": 0
        }


# ==================== Main ====================


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
