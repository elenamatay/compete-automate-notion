import asyncio
from typing import List, Dict, Any
import google.auth # type: ignore
import google.genai as genai # type: ignore
import sys, os
import json
import uuid
from datetime import datetime
import vertexai.generative_models as generative_models
from vertexai.generative_models import Tool, GenerationConfig
from notion_client import AsyncClient, Client # type: ignore
from notion_client.helpers import get_id # type: ignore
from google.genai.types import GoogleSearch, GenerateContentConfig

# Define the new CSV Schema
CSV_SCHEMA = [
    # I. Basic Competitor Information
    "CompetitorID", "Competitor Name", "WebsiteURL", "Debrief", "Type", 
    "DateAdded", "LastUpdated", "HQ_Location", "CompanySize_Employees", 
    "YearFounded", "CompanyStatus", "Source_Data", "Research_Sources",
    # II. Offering & Technology
    "CoreOffering_Summary", "Product_Categories", "KeyFeatures_AI_Automation", "KeyFeatures_NoCode",
    "Automation_Scope", "Underlying_Technology", "Integration_Capabilities", "Customization_Level",
    # III. Target Market & Positioning
    "TargetAudience_Primary", "TargetAudience_PersonasMatch_Seido", "ValueProposition_USP",
    "Positioning_Statement", "MarketSegment_Focus",
    # IV. Business Model & Pricing
    "BusinessModel", "Pricing_Tiers_Summary", "Pricing_LowestPaidTier_USD",
    "Pricing_KeyTier_USD", "FreeTrial_Offered", "Freemium_Offered",
    # V. Market Performance & Strategy
    "MarketShare_Estimate", "CustomerBase_Size_Estimate", "Funding_Total_USD", "Key_Investors",
    "Recent_News_KeyDevelopments", "Reported_Strengths", "Reported_Weaknesses",
    # VI. Marketing & Sales Channels
    "Marketing_Channels_Primary", "Sales_Approach", "Geographic_Presence",
    # VII. Customer Perception (from Reviews)
    "ReviewSites_Presence", "Average_Rating_Overall", "Total_Reviews_Count",
    "Review_CommonThemes_Positive", "Review_CommonThemes_Negative",
    # VIII. Seido-Specific Competitive Assessment
    "Competitor_Type_Relative_To_Seido", "Relevance_To_NonTechnicalFounders",
    "AI_As_Technical_Cofounder_Analogy", "Agent_Reusability_Platform_NetworkEffects",
    "EaseOfUse_For_SeidoPersonas", "Seido_Differentiation_Points", "Threat_Level_To_Seido",
    "Opportunity_For_Seido", "Notes_QualitativeInsights"
]

# Define valid competitor types
COMPETITOR_TYPES = [
    "Legacy Business Automator",
    "No-Code App Builder",
    "AI Agent Framework",
    "Vertical AI Tool",
    "Enterprise iPaaS"
]

# Add the root directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# --- LLM Based Competitor Research ---

async def research_competitor_to_json(
    competitor_name: str, 
    topic_domain: str, 
    research_goal: str, 
    output_folder: str,
    request_args: Dict[str, Any] = None
) -> str | None:
    """
    Researches a single competitor using an LLM and outputs data as a JSON object
    matching the global CSV_SCHEMA. Saves the JSON to a file.
    Returns the file path if successful, None otherwise.
    """
    output_file_path = os.path.join(output_folder, f"{competitor_name.replace(' ', '_').replace('/', '_')}.json")
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

    # Generate a UUID for the competitor and current date
    competitor_id = str(uuid.uuid4())
    current_date = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""**Role:** You are an expert Market Research Analyst specializing in the tech industry.

**Objective:** Conduct thorough research on the company '{competitor_name}' and provide detailed information for each of the requested fields.

**Context:**
* **Topic Domain:** {topic_domain}
* **Research Goal:** {research_goal}

**Competitor Type Classification:**
First, classify the competitor into ONE of these categories:
{json.dumps(COMPETITOR_TYPES, indent=2)}

**Task:**
For the competitor '{competitor_name}', gather information for all the fields listed below.
Present your findings STRICTLY as a single, valid JSON object.
The keys in the JSON object MUST EXACTLY match the field names provided in the 'Fields to Research' list.

For each piece of information you find, include its source URL in the "Research_Sources" field as an array of objects with this structure:
[
    {{"url": "https://source-url.com", "description": "Brief description of what was found at this source"}}
]

If specific information for a field cannot be found after diligent research, use "N/A" as the value for that field. Do not omit any fields.

**Fields to Research (JSON Keys):**
{json.dumps(CSV_SCHEMA, indent=2)}

**Output Format Instructions:**
* The output MUST be a single, valid JSON object.
* Do NOT include any explanatory text, markdown formatting (like ```json ... ```), or comments before or after the JSON object.
* Ensure all requested fields are present as keys in the JSON.
* For fields representing lists (e.g., 'Reported_Strengths'), provide the information as a JSON array of strings.
* For the "Type" field, use EXACTLY one of the predefined competitor types.
* For the "Debrief" field, provide a single, concise sentence summarizing the company's core offering and value proposition.
* For other fields, provide a string or number where appropriate.
"""

    model = generative_models.GenerativeModel("gemini-2.5-flash-preview-05-20")

    if request_args is None:
        # Configure default request args if none provided
        search_tool = Tool.from_dict({
            "Google Search": {}
        })
        
        config = GenerationConfig(
            temperature=0.1,
            top_p=1.0
        )
        
        request_args = {
            "generation_config": config,
            "tools": [search_tool],
            "stream": False
        }

    max_retries = 3

    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1} to research {competitor_name}...")
            response_data = await model.generate_content_async(
                [prompt],
                **request_args
            )
            
            # --- START of Change ---
            # Correctly handle multipart responses by concatenating text parts
            response_text = "".join(part.text for part in response_data.candidates[0].content.parts).strip()
            # --- END of Change ---
            
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            try:
                json_data = json.loads(response_text) # Try to parse
                
                # Add system-generated fields
                json_data["CompetitorID"] = competitor_id
                json_data["DateAdded"] = current_date
                json_data["LastUpdated"] = current_date
                
                # Validate competitor type
                if json_data.get("Type") not in COMPETITOR_TYPES:
                    print(f"Warning: Invalid competitor type '{json_data.get('Type')}' for {competitor_name}. Using 'N/A'.")
                    json_data["Type"] = "N/A"
                
                # Ensure Research_Sources is a list of objects with url and description
                sources = json_data.get("Research_Sources", [])
                if not isinstance(sources, list):
                    json_data["Research_Sources"] = []
                else:
                    # Validate each source has required fields
                    valid_sources = []
                    for source in sources:
                        if isinstance(source, dict) and "url" in source and "description" in source:
                            valid_sources.append(source)
                    json_data["Research_Sources"] = valid_sources
                
                # Write validated JSON
                with open(output_file_path, "w") as f:
                    json.dump(json_data, f, indent=2)
                
                print(f"Successfully researched and saved data for {competitor_name} to {output_file_path}")
                return output_file_path
                
            except json.JSONDecodeError as json_err:
                print(f"LLM response for {competitor_name} is not valid JSON: {json_err}")
                print(f"Raw response fragment: {response_text[:500]}...")
                if attempt == max_retries - 1:
                    with open(output_file_path + ".error.txt", "w") as f_err:
                        f_err.write(response_text)
                    print(f"LLM failed to produce valid JSON for {competitor_name} after {max_retries} attempts. Error log saved.")
                    return None
                print("Retrying due to invalid JSON...")
                await asyncio.sleep(5 * (attempt + 1))
                continue
        
        except Exception as e:
            print(f"Attempt {attempt + 1} for {competitor_name} failed: An unexpected error occurred: {e}")
            if attempt == max_retries - 1:
                with open(output_file_path + ".fatal.txt", "w") as f_err:
                    f_err.write(f"Fatal error during research: {e}\n\nFull Response:\n{response_data if 'response_data' in locals() else 'N/A'}")
                print(f"Max retries reached for {competitor_name}. Skipping. Fatal error log saved.")
                return None
            print("Retrying...")
            await asyncio.sleep(5 * (attempt + 1))
    return None

async def research_competitors_async(
    competitors_list: List[str],
    topic_domain: str,
    research_goal: str,
    output_folder_path: str,
    request_args: Dict[str, Any] = None
) -> List[str]:
    """
    Processes research for each competitor in parallel using global CSV_SCHEMA.
    Returns a list of file paths for successfully processed competitors.
    """
    tasks = []
    os.makedirs(output_folder_path, exist_ok=True)

    for competitor_name in competitors_list:
        print(f"Queueing research for: {competitor_name}")
        tasks.append(
            research_competitor_to_json(
                competitor_name,
                topic_domain,
                research_goal,
                output_folder_path,
                request_args
            )
        )
    
    results_paths = await asyncio.gather(*tasks)
    successful_paths = [path for path in results_paths if path is not None]
    print(f"Finished researching all competitors. {len(successful_paths)} successful out of {len(competitors_list)}.")
    return successful_paths

# --- Notion Database Population ---

def map_data_to_notion_properties(competitor_data: Dict[str, Any], title_field_name: str = "Competitor Name") -> Dict[str, Any]:
    """
    Maps the competitor data (from JSON) to Notion's property format using global CSV_SCHEMA.
    The title_field_name MUST match the name of the "Title" property in your Notion DB.
    """
    properties = {}
    for field in CSV_SCHEMA:
        value = competitor_data.get(field)

        if field == "CompetitorID" and value is not None:
            value = str(value)
        
        if value is None or value == "N/A":
            if field == title_field_name:
                 properties[field] = {"title": [{"text": {"content": "Untitled Competitor"}}]}
            elif field == "WebsiteURL":
                properties[field] = {"url": None}
            elif field == "Type":
                properties[field] = {"select": None}
            elif field in ["DateAdded", "LastUpdated"]:
                properties[field] = {"date": None}
            elif field in ["CompanySize_Employees", "YearFounded", "Pricing_LowestPaidTier_USD", 
                          "Pricing_KeyTier_USD", "Funding_Total_USD", "Total_Reviews_Count",
                          "Average_Rating_Overall"]:
                properties[field] = {"number": None}
            else:
                properties[field] = {"rich_text": [{"text": {"content": ""}}]}
            continue

        if field == title_field_name:
            properties[field] = {"title": [{"text": {"content": str(value)}}]}
        elif field == "WebsiteURL" or (isinstance(value, str) and (value.startswith("http://") or value.startswith("https://"))):
            properties[field] = {"url": str(value) if value else None}
        elif field == "Type":
            if value in COMPETITOR_TYPES:
                properties[field] = {"select": {"name": value}}
            else:
                properties[field] = {"select": None}
        
        # --- START of Change ---
        # Updated logic to handle Notion's 2000-character limit per rich text block.
        elif field == "Research_Sources":
            if isinstance(value, list) and value:
                rich_text_payload = []
                current_chunk = ""
                for i, source in enumerate(value, 1):
                    if isinstance(source, dict) and "url" in source and "description" in source:
                        # Format the source line with a newline character
                        source_line = f"{i}. [{source['description']}]({source['url']})\n"
                        
                        # Notion API limit is 2000 chars per rich text object.
                        # Check if adding the new line exceeds the limit.
                        if len(current_chunk) + len(source_line) > 2000:
                            # If the chunk is full, add it to the payload if it's not empty.
                            if current_chunk:
                                rich_text_payload.append({"text": {"content": current_chunk}})
                            # Start a new chunk. If the line itself is too long, it will be truncated by Notion.
                            current_chunk = source_line
                        else:
                            # Otherwise, add the line to the current chunk.
                            current_chunk += source_line
                
                # Add the last remaining chunk to the payload.
                if current_chunk:
                    rich_text_payload.append({"text": {"content": current_chunk}})
                
                properties[field] = {"rich_text": rich_text_payload}
            else:
                # Handle cases with no sources or invalid format.
                properties[field] = {"rich_text": [{"text": {"content": ""}}]}
        # --- END of Change ---
        
        elif field in ["DateAdded", "LastUpdated"]:
            try:
                # Try to parse the date string
                from datetime import datetime
                date_obj = datetime.strptime(str(value), "%Y-%m-%d")
                properties[field] = {"date": {"start": date_obj.strftime("%Y-%m-%d")}}
            except:
                properties[field] = {"date": None}
        elif field in ["CompanySize_Employees", "YearFounded", "Pricing_LowestPaidTier_USD", 
                      "Pricing_KeyTier_USD", "Funding_Total_USD", "Total_Reviews_Count",
                      "Average_Rating_Overall"]:
            try:
                # Try to convert to number
                num_value = float(str(value).replace("$", "").replace(",", ""))
                properties[field] = {"number": num_value}
            except:
                properties[field] = {"number": None}
        elif isinstance(value, list):
            # Also apply chunking for other potentially long list fields
            content_string = "\n".join([f"• {str(item)}" for item in value])
            rich_text_payload = []
            
            # Split the string into chunks of 2000 characters
            for i in range(0, len(content_string), 2000):
                chunk = content_string[i:i+2000]
                rich_text_payload.append({"text": {"content": chunk}})
                
            if not rich_text_payload:
                properties[field] = {"rich_text": [{"text": {"content": ""}}]}
            else:
                 properties[field] = {"rich_text": rich_text_payload}
        else:
            # Also apply chunking for any other potentially long text field
            content_string = str(value)
            rich_text_payload = []
            
            # Split the string into chunks of 2000 characters
            for i in range(0, len(content_string), 2000):
                chunk = content_string[i:i+2000]
                rich_text_payload.append({"text": {"content": chunk}})

            if not rich_text_payload:
                properties[field] = {"rich_text": [{"text": {"content": ""}}]}
            else:
                 properties[field] = {"rich_text": rich_text_payload}

    return properties

async def add_json_to_notion_db(
    notion_async_client: AsyncClient,
    database_id: str,
    competitor_json_path: str,
    title_field_name: str = "Competitor Name"
) -> bool:
    """
    Reads a competitor's JSON data and adds/updates it as a page in the Notion database.
    """
    try:
        with open(competitor_json_path, 'r') as f:
            competitor_data = json.load(f)
    except Exception as e:
        print(f"Error reading/parsing JSON file {competitor_json_path}: {e}")
        return False

    competitor_name_for_log = competitor_data.get(title_field_name, os.path.basename(competitor_json_path).replace('.json',''))
    
    try:
        notion_properties = map_data_to_notion_properties(competitor_data, title_field_name)
        
        api_query_filter = None
        if competitor_data.get(title_field_name): # Check if title field has a value to filter on
             api_query_filter = {"property": title_field_name, "title": {"equals": competitor_data.get(title_field_name)}}
        
        existing_page_id = None
        if api_query_filter:
            try:
                existing_pages_response = await notion_async_client.databases.query(database_id=database_id, filter=api_query_filter)
                if existing_pages_response and existing_pages_response.get("results"):
                    existing_page_id = existing_pages_response["results"][0]["id"]
            except Exception as query_e:
                print(f"Warning: Could not query for existing page for {competitor_name_for_log}: {query_e}. Will attempt to create.")

        if existing_page_id:
            print(f"Competitor '{competitor_name_for_log}' already exists (ID: {existing_page_id}). Updating.")
            await notion_async_client.pages.update(page_id=existing_page_id, properties=notion_properties)
            print(f"Successfully updated '{competitor_name_for_log}' in Notion.")
        else:
            print(f"Adding new competitor '{competitor_name_for_log}' to Notion database {database_id}.")
            await notion_async_client.pages.create(parent={"database_id": database_id}, properties=notion_properties)
            print(f"Successfully added '{competitor_name_for_log}' to Notion.")
        return True
    except Exception as e:
        error_message = str(e)
        if hasattr(e, 'body'): # Check if it's a Notion API error with a body
            try:
                error_detail = json.loads(e.body) # type: ignore
                error_message = f"{e} - Details: {error_detail.get('message', e.body)}" # type: ignore
            except:
                 pass # Keep original error_message if body isn't JSON
        print(f"Error adding/updating page for {competitor_name_for_log} in Notion: {error_message}")
        return False

async def populate_notion_db_from_folder(
    output_folder: str,
    database_id: str,
    notion_token: str,
    title_field_name: str = "Competitor Name"
) -> None:
    """
    Populates Notion database from all JSON files in the output_folder.
    """
    if not notion_token:
        print("Notion API token is not provided. Cannot populate database.")
        return
    if not database_id:
        print("Notion Database ID is not provided. Cannot populate database.")
        return

    notion_client = AsyncClient(auth=notion_token)
    tasks = []
    
    try:
        json_files = [f for f in os.listdir(output_folder) if f.endswith('.json')]
    except FileNotFoundError:
        print(f"Error: Output folder {output_folder} not found.")
        return
        
    if not json_files:
        print(f"No JSON files found in {output_folder}.")
        return

    for json_file_name in json_files:
        json_file_path = os.path.join(output_folder, json_file_name)
        tasks.append(add_json_to_notion_db(notion_client, database_id, json_file_path, title_field_name))
    
    results = await asyncio.gather(*tasks, return_exceptions=True) 
    
    successful_uploads = 0
    for i, res_or_exc in enumerate(results):
        if isinstance(res_or_exc, Exception):
            print(f"Error processing file {json_files[i]}: {res_or_exc}")
        elif res_or_exc is True:
            successful_uploads += 1
            
    print(f"Finished populating Notion database. {successful_uploads}/{len(json_files)} competitors processed successfully.")

# --- Notion Database Creation ---

async def create_notion_db_from_schema(
    notion_sync_client: Client, 
    parent_page_id: str,
    db_title: str,
    title_property_name: str = "Competitor Name" 
) -> str | None:
    """
    Creates a new Notion database under parent_page_id using global CSV_SCHEMA.
    Returns the new database ID or None on failure.
    """
    properties: Dict[str, Any] = {}

    if title_property_name not in CSV_SCHEMA:
        print(f"Error: Title property '{title_property_name}' not in CSV_SCHEMA.")
        return None
    if not parent_page_id:
        print("Error: Parent Page ID is required to create a Notion Database.")
        return None
    
    # Validate parent_page_id format (basic check for 32 hex chars or 36 with hyphens)
    normalized_parent_page_id = parent_page_id.replace("-", "")
    if not (len(normalized_parent_page_id) == 32 and all(c in '0123456789abcdefABCDEF' for c in normalized_parent_page_id)):
        print(f"Error: Invalid NOTION_PARENT_PAGE_ID format: '{parent_page_id}'. It should be a 32-character hex string (hyphens optional).")
        return None

    try:
        print(f"Creating Notion database '{db_title}' under page ID {parent_page_id}...")
        
        # Create property items in the order specified by CSV_SCHEMA
        property_items = []
        for field_name in CSV_SCHEMA:
            if field_name == title_property_name:
                property_items.append({"name": field_name, "type": "title"})
            elif field_name == "WebsiteURL":
                property_items.append({"name": field_name, "type": "url"})
            elif field_name == "Type":
                property_items.append({
                    "name": field_name,
                    "type": "select",
                    "select": {
                        "options": [{"name": t} for t in COMPETITOR_TYPES]
                    }
                })
            elif field_name == "Research_Sources":
                property_items.append({"name": field_name, "type": "rich_text"})
            elif field_name in ["DateAdded", "LastUpdated"]:
                property_items.append({"name": field_name, "type": "date"})
            elif field_name in ["CompanySize_Employees", "YearFounded", "Pricing_LowestPaidTier_USD", 
                              "Pricing_KeyTier_USD", "Funding_Total_USD", "Total_Reviews_Count",
                              "Average_Rating_Overall"]:
                property_items.append({"name": field_name, "type": "number"})
            else:
                property_items.append({"name": field_name, "type": "rich_text"})
        
        response = notion_sync_client.databases.create(
            parent={"type": "page_id", "page_id": parent_page_id},
            title=[{"type": "text", "text": {"content": db_title}}],
            properties=properties,
            property_items=property_items,  # Add property items to specify order
            is_inline=False 
        )
        db_id = response.get("id")
        if db_id:
            db_url = f"https://www.notion.so/{db_id.replace('-', '')}"
            print(f"Successfully created Notion database with ID: {db_id}")
            print(f"Link: {db_url}")
            return db_id
        else:
            error_message = "Failed to create Notion database. No ID returned."
            if hasattr(response, 'text'): error_message += f" Response: {response.text}"
            elif response: error_message += f" Response: {str(response)}"
            print(error_message)
            return None
    except Exception as e: 
        error_message = f"Failed to create Notion database: {e}"
        if hasattr(e, 'code') and hasattr(e, 'body'): # Notion specific error attributes
             error_message += f" (Code: {e.code}, Body: {e.body})" # type: ignore
        print(error_message)
        return None

async def setup_notion_database(
    notion_token: str,
    parent_page_id: str,
    database_name: str,
    database_id: str | None = None
) -> str | None:
    """
    Sets up a Notion database for competitor research.
    If database_id is provided, verifies it exists.
    If not, creates a new database under the specified parent page.
    
    Args:
        notion_token: Notion API token
        parent_page_id: ID of the parent page where to create the database
        database_name: Name for the new database
        database_id: Optional existing database ID
        
    Returns:
        str: Database ID if successful
        None: If setup fails
    """
    if database_id:
        print(f"Using existing Notion Database ID: {database_id}")
        return database_id
    
    if not notion_token:
        print("Error: Notion API token is not provided. Cannot create database.")
        return None
    if not parent_page_id:
        print("Error: Parent Page ID is not provided. Cannot create database.")
        return None

    print(f"Attempting to create Notion Database titled '{database_name}' under parent page ID: {parent_page_id}")
    
    try:
        sync_notion_client = Client(auth=notion_token)
        
        # Competitor Name is the designated title property in our CSV_SCHEMA
        title_property_name_in_schema = "Competitor Name"
        
        new_db_id = await create_notion_db_from_schema(
            notion_sync_client=sync_notion_client,
            parent_page_id=parent_page_id,
            db_title=database_name,
            title_property_name=title_property_name_in_schema
        )
        
        if new_db_id:
            print(f"Successfully created Notion Database. New ID: {new_db_id}")
            db_url = f"https://www.notion.so/{new_db_id.replace('-', '')}"
            print(f"Link: {db_url}")
        else:
            print("Failed to create Notion Database. Please check logs and Notion settings.")
            print("You may need to create the database manually in Notion and then provide its ID.")
        
        return new_db_id
    except Exception as e:
        print(f"Error creating Notion database: {str(e)}")
        print("Please check your Notion API token and permissions.")
        return None