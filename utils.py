import asyncio
from typing import List, Dict, Any
import google.auth # type: ignore
import sys, os
import json
import uuid
from datetime import datetime
from typing import Tuple
import vertexai
import vertexai.generative_models as generative_models
from vertexai.generative_models import Tool, GenerationConfig
from notion_client import AsyncClient, Client # type: ignore
from notion_client.errors import APIResponseError
from tenacity import retry, wait_random_exponential



# Derive the list of types from the dictionary keys for validation
COMPETITOR_TYPES = list(COMPETITOR_TYPE_DEFINITIONS.keys())

# Attempt to override schema and type definitions from config.json (initial_research section)
try:
    repo_root = os.path.abspath(os.path.dirname(__file__))
    config_path = os.path.join(repo_root, 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as _f:
            _cfg = json.load(_f)
        initial_research_cfg = _cfg.get('initial_research', {})
        # csv_schema override
        if isinstance(initial_research_cfg.get('csv_schema'), list) and initial_research_cfg['csv_schema']:
            CSV_SCHEMA = initial_research_cfg['csv_schema']
        # competitor_type_definitions override
        if isinstance(initial_research_cfg.get('competitor_type_definitions'), dict) and initial_research_cfg['competitor_type_definitions']:
            COMPETITOR_TYPE_DEFINITIONS = initial_research_cfg['competitor_type_definitions']
        # Recompute dependent constants
        COMPETITOR_TYPES = list(COMPETITOR_TYPE_DEFINITIONS.keys())
except Exception as _e:
    # Non-fatal: if config.json is malformed, continue with built-ins
    print(f"Warning: could not load initial_research config from config.json: {_e}")


# Add the root directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# --- LLM Based Competitor Research ---

@retry(wait=wait_random_exponential(multiplier=1, max=120))
async def research_competitor_to_json(
    competitor_name: str, 
    output_folder: str,
    company_context: str,
    request_args: Dict[str, Any] = None
) -> str | None:
    """
    Researches a single competitor using an LLM and outputs data as a JSON object
    matching the global CSV_SCHEMA. Saves the JSON to a file.
    Returns the file path if successful, None otherwise.
    """
    # Initialize Vertex AI for this async call (following article pattern)
    vertexai.init(project=os.getenv("GOOGLE_CLOUD_PROJECT"), location="us-central1")
    
    output_file_path = os.path.join(output_folder, f"{competitor_name.replace(' ', '_').replace('/', '_')}.json")
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

    # Generate a UUID for the competitor and current date
    competitor_id = str(uuid.uuid4())
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Format the definitions for inclusion in the prompt
    definitions_text = "\n".join(f"- **{name}:** {desc}" for name, desc in COMPETITOR_TYPE_DEFINITIONS.items())
    prompt = f"""**Role:** You are a Senior Market Research Analyst and expert detective working for a startup. You are skilled at using web searches to uncover hard-to-find details about competitor companies.

    **Your Company's Context:**
    {company_context}

    **Primary Objective:**
    Conduct a deep-dive analysis of the competitor '{competitor_name}'. Your goal is to fill out EVERY field in the requested JSON schema with accurate, well-researched information. You must also provide a critical competitive assessment from your company's strategic perspective.

    **IMPORTANT: Research Methodology & Instructions**

    1.  **Be a Detective, Not Just a Reporter:** Your primary directive is to avoid using "N/A". If information like pricing, funding, or specific features isn't obvious, your job is to find it. Use advanced search queries. Look in press releases, news articles, customer review sites (like Capterra), and funding announcements. If an exact number is unavailable, provide a well-reasoned estimate (e.g., "Estimated 11-50 employees based on LinkedIn data") and cite your reasoning.

    2.  **Use the Search Tool Extensively:** You must use the provided search tool to find up-to-date information on the competitor's website, recent news, product reviews, pricing, and AI features.

    3.  **Analyze from Your Company's Perspective:** For all company-specific fields (Section VIII in the schema), you MUST use the 'Your Company's Context' provided above. This is the most critical part of the task.
        *   `Focus_On_Business_Owner_ROI`: Does their marketing, messaging, and product focus on delivering tangible ROI to the business owner, or is it more about operational features for the day-to-day user?
        *   `Automation_Depth`: Analyze the depth of their automation. Is it basic (automating simple, reactive tasks) or deep (automating complex, multi-step processes)? How does it compare to your company's approach?
        *   `Company_Differentiation_Points`: Based on your company's differentiators mentioned in the context, what makes your company strategically different from this competitor? Be specific.
        *   `Threat_Level_To_Company`: How directly do they compete for your company's target customer profile? (High, Medium, Low). Justify your answer based on the company context.
        *   `Opportunity_For_Company`: What strategic gaps in product, marketing, or target audience does this competitor leave that your company can exploit?

    **CRITICAL STEP 1: Competitor Type Classification**
    Before generating the JSON, you must first classify the competitor. Analyze '{competitor_name}' based on its primary product, target audience (firm owners vs. managers), and how it uses technology (especially AI). Using the definitions below, select the SINGLE most accurate category.

    **Category Definitions:**
    {definitions_text}

    **CRITICAL STEP 2: JSON Output Generation**
    For the competitor '{competitor_name}', gather information for all the fields listed below. Present your findings STRICTLY as a single, valid JSON object. The keys MUST EXACTLY match the field names provided.

    *   **Source Citation:** For every piece of data, you MUST add the source URL to the `Research_Sources` field. Create a comprehensive list.
        ```
        [
            {{"url": "https://source-url.com", "description": "Brief description of what was found at this source"}}
        ]
        ```
    *   **Completeness:** Do not omit any fields. If, after exhaustive work, you cannot find information for a field, use "N/A".
    *   **Debrief Field:** Provide a single, concise sentence summarizing the company's core offering from the perspective of a potential customer.

    **Fields to Research (JSON Keys):**
    {json.dumps(CSV_SCHEMA, indent=2)}

    **Final Output Format Instructions:**
    *   The output MUST be a single, valid JSON object.
    *   Do NOT include any explanatory text or markdown formatting before or after the JSON object.
    *   Ensure all keys from the schema are present.
    *   For the "Type" field, use EXACTLY one of the predefined competitor types.

    Now, begin your research for '{competitor_name}' and generate the complete JSON object.
    """

    model = generative_models.GenerativeModel("gemini-2.5-flash")

    if request_args is None:
        # Configure default request args if none provided
        # Using standard Google AI SDK format for tool configuration
        search_tool = Tool.from_dict({
            "google_search": {}  # Basic configuration without unsupported parameters
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
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Attempt {attempt + 1} to research {competitor_name}...")
            
            response_data = await model.generate_content_async(
                [prompt],
                **request_args
            )
            
            # Correctly handle multipart responses by concatenating text parts
            response_text = "".join(part.text for part in response_data.candidates[0].content.parts).strip()
            
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
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully researched and saved data for {competitor_name} to {output_file_path}")
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
    output_folder_path: str,
    company_context: str,
    request_args: Dict[str, Any] = None
) -> List[str]:
    """
    Processes research for each competitor in parallel using global CSV_SCHEMA.
    Returns a list of file paths for successfully processed competitors.
    """
    tasks = []
    os.makedirs(output_folder_path, exist_ok=True)

    for competitor_name in competitors_list:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Queueing research for: {competitor_name}")
        tasks.append(
            research_competitor_to_json(
                competitor_name,
                output_folder_path,
                company_context=company_context,
                request_args=request_args
            )
        )
    
    results_paths = await asyncio.gather(*tasks)
    successful_paths = [path for path in results_paths if path is not None]
    print(f"Finished researching all competitors. {len(successful_paths)} successful out of {len(competitors_list)}.")
    return successful_paths

# --- Notion Database Population ---

# Single source of truth for the Notion database Title property
TITLE_FIELD_NAME = "Competitor Name"

def map_data_to_notion_properties(competitor_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Maps the competitor data (from JSON) to Notion's property format using global CSV_SCHEMA.
    The Title property name is fixed by TITLE_FIELD_NAME.
    """
    properties = {}
    for field in CSV_SCHEMA:
        value = competitor_data.get(field)

        if field == "CompetitorID" and value is not None:
            value = str(value)
        
        if value is None or value == "N/A":
            if field == TITLE_FIELD_NAME:
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

        if field == TITLE_FIELD_NAME:
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
    competitor_json_path: str
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

    competitor_name_for_log = competitor_data.get(TITLE_FIELD_NAME, os.path.basename(competitor_json_path).replace('.json',''))
    
    try:
        notion_properties = map_data_to_notion_properties(competitor_data)
        
        api_query_filter = None
        if competitor_data.get(TITLE_FIELD_NAME): # Check if title field has a value to filter on
             api_query_filter = {"property": TITLE_FIELD_NAME, "title": {"equals": competitor_data.get(TITLE_FIELD_NAME)}}
        
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
    notion_token: str
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
        tasks.append(add_json_to_notion_db(notion_client, database_id, json_file_path))
    
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
    db_title: str
) -> str | None:
    """
    Creates a new Notion database under parent_page_id using global CSV_SCHEMA.
    Returns the new database ID or None on failure.
    """
    properties: Dict[str, Any] = {}

    if TITLE_FIELD_NAME not in CSV_SCHEMA:
        print(f"Error: Title property '{TITLE_FIELD_NAME}' not in CSV_SCHEMA.")
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
        
        # First create the database with all properties
        for field_name in CSV_SCHEMA:
            if field_name == TITLE_FIELD_NAME:
                properties[field_name] = {"title": {}}
            elif field_name == "WebsiteURL":
                properties[field_name] = {"url": {}}
            elif field_name == "Type":
                properties[field_name] = {
                    "select": {
                        "options": [{"name": t} for t in COMPETITOR_TYPES]
                    }
                }
            elif field_name == "Research_Sources":
                properties[field_name] = {"rich_text": {}}  # Will store as formatted text with clickable links
            elif field_name in ["DateAdded", "LastUpdated"]:
                properties[field_name] = {"date": {}}
            elif field_name in ["CompanySize_Employees", "YearFounded", "Pricing_LowestPaidTier_USD", 
                              "Pricing_KeyTier_USD", "Funding_Total_USD", "Total_Reviews_Count",
                              "Average_Rating_Overall"]:
                properties[field_name] = {"number": {}}
            else:
                properties[field_name] = {"rich_text": {}}
        
        response = notion_sync_client.databases.create(
            parent={"type": "page_id", "page_id": parent_page_id},
            title=[{"type": "text", "text": {"content": db_title}}],
            properties=properties,
            is_inline=False 
        )
        
        db_id = response.get("id")
        if db_id:
            # Now update the database to set property order
            try:
                notion_sync_client.databases.update(
                    database_id=db_id,
                    properties=properties,
                    property_items=[{"name": field_name} for field_name in CSV_SCHEMA]
                )
                print(f"Successfully set property order for database {db_id}")
            except Exception as order_e:
                print(f"Warning: Could not set property order: {order_e}")
                print("Properties will remain in alphabetical order.")
            
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
        
        new_db_id = await create_notion_db_from_schema(
            notion_sync_client=sync_notion_client,
            parent_page_id=parent_page_id,
            db_title=database_name
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
    

# --- Competitor Research Update ---

async def update_single_competitor_async(
    json_file_path: str,
    company_context: str
) -> Tuple[str, str] | None:
    """
    Reads existing competitor data, performs a new full research,
    and uses an LLM to generate an updated JSON and a summary of changes.
    """
    try:
        with open(json_file_path, 'r') as f:
            old_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading or parsing existing JSON {json_file_path}: {e}")
        return None

    competitor_name = old_data.get("Competitor Name", "Unknown Competitor")
    print(f"Performing full re-research for '{competitor_name}'...")

    # Simplified prompt for a full re-research and comparison.
    prompt = f"""**Role:** You are a Senior Market Research Analyst for a company with this context: `{company_context}`.

    **Objective:**
    Perform a fresh, deep-dive research on '{competitor_name}'. Then, compare your new findings against the `PREVIOUS_RESEARCH_DATA` provided below to identify any changes.

    **Methodology:**
    1.  **Full Research:** Use the Google Search tool to find all current information about '{competitor_name}'.
    2.  **Compare and Synthesize:** Compare your new findings with the `PREVIOUS_RESEARCH_DATA`.
    3.  **Generate Two Outputs:** Produce a single JSON object with two keys: `updated_competitor_data` and `change_summary`.

    **PREVIOUS_RESEARCH_DATA:**
    ```json
    {json.dumps(old_data, indent=2)}
    ```

    **Output Instructions:**
    Your entire response MUST be a single, valid JSON object with the structure:
    {{
        "updated_competitor_data": {{
            // A COMPLETE and UPDATED JSON object for the competitor based on your new research.
            // It MUST contain ALL keys from the original schema.
        }},
        "change_summary": "A concise, one-paragraph summary of the most significant changes found when comparing your new research to the old data. If no significant changes were found, state that."
    }}
    """

    # Create a simple, generic search tool configuration inside the function.
    search_tool = Tool.from_dict({"google_search": {}})

    request_args = {
        "generation_config": GenerationConfig(temperature=0.2, top_p=1.0),
        "tools": [search_tool]
    }

    model = generative_models.GenerativeModel("gemini-2.5-flash")
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = await model.generate_content_async([prompt], **request_args)
            response_text = "".join(part.text for part in response.candidates[0].content.parts).strip()

            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()

            parsed_response = json.loads(response_text)
            updated_data = parsed_response.get("updated_competitor_data")
            change_summary = parsed_response.get("change_summary")

            if not updated_data or not change_summary:
                raise ValueError("LLM response missing 'updated_competitor_data' or 'change_summary'.")

            updated_data["LastUpdated"] = datetime.now().strftime("%Y-%m-%d")
            with open(json_file_path, 'w') as f:
                json.dump(updated_data, f, indent=2)

            print(f"Successfully updated research for '{competitor_name}'.")
            return (json_file_path, f"**{competitor_name}:** {change_summary}")

        except (json.JSONDecodeError, ValueError, Exception) as e:
            print(f"Attempt {attempt + 1} failed for '{competitor_name}': {e}")
            if attempt == max_retries - 1:
                print(f"Skipping update for '{competitor_name}' after multiple failures.")
                return None
            await asyncio.sleep(5)
    return None


async def generate_top_changes_summary_async(
    all_changes: List[str],
    company_context: str
) -> str:
    """
    Takes a list of individual competitor change summaries and synthesizes them
    into a top-10 executive briefing for the company's founders.
    """
    if not all_changes:
        return "No significant competitor updates found in this run."

    # Create a simple request_args without a search tool, as it's not needed.
    request_args = {"generation_config": GenerationConfig(temperature=0.2, top_p=1.0)}

    combined_changes_text = "\n\n".join(all_changes)
    prompt = f"""**Role:** You are a Chief Strategy Officer reporting directly to your company's founders.

    **Your Company's Context:**
    {company_context}

    **Task:**
    You have received the following intelligence briefings on recent competitor activities. Your job is to synthesize this information into a high-level executive summary. Identify the **top 10 most strategically important changes** that your company's founders must be aware of.

    **Intelligence Briefings:**
    ---
    {combined_changes_text}
    ---

    **Instructions:**
    - Analyze the updates through the lens of your company's strategy.
    - Prioritize changes that represent a direct threat or a significant opportunity.
    - Format the output as a clean, markdown-formatted, numbered list.
    - Do NOT include a headline - start directly with the numbered list.
    - Each list item should be concise and clearly state the competitor, the change, and the strategic implication for your company (the 'so what?').
    """
    model = generative_models.GenerativeModel("gemini-2.5-flash")
    try:
        response = await model.generate_content_async([prompt], **request_args)
        return response.text
    except Exception as e:
        print(f"Error generating top changes summary: {e}")
        return "Error: Could not generate the final summary."



async def append_text_to_notion_page_async(
    notion_client: AsyncClient,
    page_id: str,
    title: str,
    content: str
):
    """Appends a title and a block of text to a Notion page."""
    print(f"Appending summary to Notion page: {page_id}")
    try:
        # Add minimal spacing between numbered items and convert **text** to bold
        import re
        
        # First, convert **text** to bold formatting for Notion
        def parse_bold_text(text):
            """Parse text with **bold** markdown into Notion rich_text format"""
            parts = []
            # Split by **text** patterns while preserving the delimiters
            bold_pattern = r'(\*\*.*?\*\*)'
            segments = re.split(bold_pattern, text)
            
            for segment in segments:
                if segment.startswith('**') and segment.endswith('**'):
                    # Bold text (remove the **)
                    bold_text = segment[2:-2]
                    if bold_text:
                        parts.append({"type": "text", "text": {"content": bold_text}, "annotations": {"bold": True}})
                elif segment:
                    # Regular text
                    parts.append({"type": "text", "text": {"content": segment}})
            return parts
        
        # Split content by numbered items (1., 2., etc.) and add minimal spacing
        numbered_pattern = r'(\d+\.\s)'
        parts = re.split(numbered_pattern, content)
        
        if len(parts) > 1:
            # Reconstruct with single line spacing between items
            spaced_content = parts[0]  # Any content before first number
            for i in range(1, len(parts), 2):
                if i + 1 < len(parts):
                    spaced_content += parts[i] + parts[i + 1] + "\n"
            content = spaced_content.rstrip()
        
        # Parse content into rich text with bold formatting
        rich_text_parts = parse_bold_text(content)

        blocks_to_append = [
            {
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [{"type": "text", "text": {"content": title}}]
                }
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "Top 10 Strategic Competitor Updates"}}]
                }
            }
        ]
        
        # Create a single paragraph block with rich text formatting
        if rich_text_parts:
            # Split rich text parts into chunks to respect Notion's limits
            current_chunk = []
            current_length = 0
            
            for part in rich_text_parts:
                part_length = len(part["text"]["content"])
                if current_length + part_length > 2000 and current_chunk:
                    # Add current chunk as a paragraph
                    blocks_to_append.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": current_chunk}
                    })
                    current_chunk = [part]
                    current_length = part_length
                else:
                    current_chunk.append(part)
                    current_length += part_length
            
            # Add remaining chunk
            if current_chunk:
                blocks_to_append.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": current_chunk}
                })

        await notion_client.blocks.children.append(
            block_id=page_id,
            children=blocks_to_append
        )
        print("Successfully appended summary to Notion page.")
    except APIResponseError as e:
        print(f"Error appending to Notion page: {e.body}")
    except Exception as e:
        print(f"An unexpected error occurred while appending to Notion: {e}")


def dedupe_sources_preserve_order(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return sources deduplicated by URL, preserving original order."""
    seen: set[str] = set()
    unique: List[Dict[str, Any]] = []
    for src in sources or []:
        if isinstance(src, dict):
            url = src.get("url")
            if url and url not in seen:
                seen.add(url)
                unique.append(src)
    return unique


def build_inline_source_refs(unique_sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build Notion rich_text parts like [1] [2] ... each linked to its source URL."""
    parts: List[Dict[str, Any]] = []
    for idx, src in enumerate(unique_sources, start=1):
        url = src.get("url")
        if not url:
            continue
        parts.append({
            "type": "text",
            "text": {"content": f"[{idx}] ", "link": {"url": url}}
        })
    return parts



async def discover_new_competitors_async(
    days_ago: int,
    existing_competitors: List[str],
    company_context: str
) -> List[str]:
    """
    Scans for new potential competitors that have emerged recently.
    """
    print(f"\nSearching for new competitors...")

    # Create a simple, generic search tool configuration inside the function.
    search_tool = Tool.from_dict({"google_search": {}})

    request_args = {
        "generation_config": GenerationConfig(temperature=0.5, top_p=1.0),
        "tools": [search_tool]
    }

    # The prompt still uses `days_ago` as a helpful guideline for the model.
    prompt = f"""**Role:** You are a Market Intelligence Analyst. Your task is to identify emerging startups that could be potential competitors to your company.

    **Your Company's Context:**
    {company_context}

    **Objective:**
    Identify new companies, startups, or open-source projects that have been announced, funded, or gained traction recently (e.g., in the last {days_ago} days). These new entities must be relevant to your company's mission and target market.

    **Search Focus Areas:**
    Based on your company's context, search for relevant terms related to:
    - Your company's industry and technology stack
    - Competitors targeting similar customer segments
    - New funding announcements in your space
    - Emerging solutions addressing similar problems
    - Industry-specific accelerator programs and batches

    **CRITICAL Instructions:**
    1.  **Analyze Relevance:** A new company is relevant if it targets your company's customer base, aims to solve similar problems (especially with similar technology approaches), and addresses the same business challenges mentioned in your company context.
    2.  **Exclude Known Competitors:** Do NOT include any of the following known companies in your response: {', '.join(existing_competitors)}
    3.  **Output Format:** Your response MUST be a single, valid JSON object containing a single key "new_competitors", which is a list of strings (company names).
    4.  **No Hallucinations:** If you cannot find any new, relevant competitors after a thorough search, return an empty list.

    **Example Output:**
    ```
    {{
      "new_competitors": ["PropManagify AI", "FincaTech Solutions"]
    }}
    ```
    """

    model = generative_models.GenerativeModel("gemini-2.5-flash")
    try:
        response = await model.generate_content_async([prompt], **request_args)
        response_text = "".join(part.text for part in response.candidates[0].content.parts).strip()

        if response_text.startswith("```json"):
            response_text = response_text[7:-3].strip()

        parsed_response = json.loads(response_text)
        new_competitors = parsed_response.get("new_competitors", [])

        if not isinstance(new_competitors, list):
            print("Warning: 'new_competitors' field was not a list. Returning empty list.")
            return []
            
        print(f"Discovery complete. Found {len(new_competitors)} potential new competitors.")
        return new_competitors

    except (json.JSONDecodeError, Exception) as e:
        print(f"An error occurred during new competitor discovery: {e}")
        return []