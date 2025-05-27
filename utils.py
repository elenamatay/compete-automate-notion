import asyncio
from typing import List, Dict, Any
import google.auth # type: ignore
from google.genai import types as genai_types # type: ignore
import sys, os
import json
from vertexai.generative_models import GenerativeModel, GenerationConfig # type: ignore
from notion_client import AsyncClient, Client # type: ignore
from notion_client.helpers import get_id # type: ignore

# Define the new CSV Schema
CSV_SCHEMA = [
    # I. Basic Competitor Information
    "CompetitorID", "Competitor Name", "DateAdded", "LastUpdated", "WebsiteURL",
    "HQ_Location", "CompanySize_Employees", "YearFounded", "CompanyStatus", "Source_Data",
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

# Add the root directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Env variables & LLM Config
SAFETY_SETTINGS = [
    genai_types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
    genai_types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
    genai_types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
    genai_types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
]

GEN_CONFIG_JSON_OUTPUT = GenerationConfig(
    temperature=0.1,
    top_p=1.0,
    response_mime_type="application/json",
)

# --- LLM Based Competitor Research ---

async def research_competitor_to_json(
    competitor_name: str,
    topic_domain: str,
    research_goal: str,
    output_folder: str
) -> str | None:
    """
    Researches a single competitor using an LLM and outputs data as a JSON object
    matching the global CSV_SCHEMA. Saves the JSON to a file.
    Returns the file path if successful, None otherwise.
    """
    output_file_path = os.path.join(output_folder, f"{competitor_name.replace(' ', '_').replace('/', '_')}.json")
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

    prompt = f"""**Role:** You are an expert Market Research Analyst specializing in the tech industry.

            **Objective:** Conduct thorough research on the company '{competitor_name}' and provide detailed information for each of the requested fields.

            **Context:**
            *   **Topic Domain:** {topic_domain}
            *   **Research Goal:** {research_goal}

            **Task:**
            For the competitor '{competitor_name}', gather information for all the fields listed below.
            Present your findings STRICTLY as a single, valid JSON object.
            The keys in the JSON object MUST EXACTLY match the field names provided in the 'Fields to Research' list.
            If specific information for a field cannot be found after diligent research, use "N/A" as the value for that field. Do not omit any fields.

            **Fields to Research (JSON Keys):**
            {json.dumps(CSV_SCHEMA, indent=2)}

            **Output Format Instructions:**
            *   The output MUST be a single, valid JSON object.
            *   Do NOT include any explanatory text, markdown formatting (like ```json ... ```), or comments before or after the JSON object.
            *   Ensure all requested fields are present as keys in the JSON.
            *   For fields representing lists (e.g., 'Reported_Strengths'), provide the information as a JSON array of strings. For other fields, provide a string or number where appropriate.
            """

    model = GenerativeModel("gemini-2.5-flash-preview-05-20")
    max_retries = 3

    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1} to research {competitor_name}...")
            response_data = await model.generate_content_async(
                [prompt],
                generation_config=GEN_CONFIG_JSON_OUTPUT,
                safety_settings=SAFETY_SETTINGS,
                stream=False
            )
            
            response_text = response_data.text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            try:
                json.loads(response_text) # Try to parse
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

            with open(output_file_path, "w") as f:
                f.write(response_text)
            print(f"Successfully researched and saved data for {competitor_name} to {output_file_path}")
            return output_file_path
        
        except Exception as e:
            print(f"Attempt {attempt + 1} for {competitor_name} failed: An unexpected error occurred: {e}")
            if attempt == max_retries - 1:
                with open(output_file_path + ".fatal.txt", "w") as f_err:
                    f_err.write(f"Fatal error during research: {e}")
                print(f"Max retries reached for {competitor_name}. Skipping. Fatal error log saved.")
                return None
            print("Retrying...")
            await asyncio.sleep(5 * (attempt + 1))
    return None

async def research_competitors_async(
    competitors_list: List[str],
    topic_domain: str,
    research_goal: str,
    output_folder_path: str
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
                output_folder_path
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
            else:
                properties[field] = {"rich_text": [{"text": {"content": ""}}]}
            continue

        if field == title_field_name:
            properties[field] = {"title": [{"text": {"content": str(value)}}]}
        elif field == "WebsiteURL" or (isinstance(value, str) and (value.startswith("http://") or value.startswith("https://"))):
            properties[field] = {"url": str(value) if value else None}
        elif isinstance(value, list):
            content = "\\n".join([f"• {str(item)}" for item in value])
            properties[field] = {"rich_text": [{"text": {"content": content}}]}
        else:
            properties[field] = {"rich_text": [{"text": {"content": str(value)}}]}
            
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
                existing_pages = await notion_async_client.databases.query(database_id=database_id, filter=api_query_filter)
                if existing_pages and existing_pages.get("results"):
                    existing_page_id = existing_pages["results"][0]["id"]
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
    if not notion_sync_client.auth:
        print("Error: Notion client is not authenticated. Please provide a token for the synchronous client.")
        return None
    
    # Validate parent_page_id format (basic check for 32 hex chars or 36 with hyphens)
    # Notion IDs are typically 32 characters long (hexadecimal) when hyphens are removed.
    normalized_parent_page_id = parent_page_id.replace("-", "")
    if not (len(normalized_parent_page_id) == 32 and all(c in '0123456789abcdefABCDEF' for c in normalized_parent_page_id)):
        print(f"Error: Invalid NOTION_PARENT_PAGE_ID format: '{parent_page_id}'. It should be a 32-character hex string (hyphens optional).")
        return None


    for field_name in CSV_SCHEMA:
        if field_name == title_property_name:
            properties[field_name] = {"title": {}}
        elif field_name == "WebsiteURL":
             properties[field_name] = {"url": {}}
        # Add elif for other specific Notion types for columns (Date, Number, Select etc.)
        # elif field_name == "DateAdded": properties[field_name] = {"date": {}}
        # elif field_name == "CompanySize_Employees": properties[field_name] = {"number": {"format": "number"}}
        else: 
            properties[field_name] = {"rich_text": {}}

    try:
        print(f"Creating Notion database '{db_title}' under page ID {parent_page_id}...")
        db_title_payload = [{"type": "text", "text": {"content": db_title}}]
        
        response = notion_sync_client.databases.create(
            parent={"type": "page_id", "page_id": parent_page_id}, # Corrected parent type
            title=db_title_payload,
            properties=properties,
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