import asyncio
from typing import List
import google.auth
from google.genai import types
import sys, os
import json
from vertexai.generative_models import GenerativeModel, GenerationConfig
from docx import Document
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Add the root directory to the Python path
sys.path.append(os.path.abspath(os.path.join('..')))

# Env variables

SAFETY_SETTINGS = [types.SafetySetting(
      category="HARM_CATEGORY_HATE_SPEECH",
      threshold="OFF"
    ),types.SafetySetting(
      category="HARM_CATEGORY_DANGEROUS_CONTENT",
      threshold="OFF"
    ),types.SafetySetting(
      category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
      threshold="OFF"
    ),types.SafetySetting(
      category="HARM_CATEGORY_HARASSMENT",
      threshold="OFF"
    )
],

GEN_CONFIG = GenerationConfig(
    temperature = 0.1,
    top_p = 1,
    seed = 0,
    response_modalities = ["TEXT"],
    response_mime_type = "application/json",
)

# Helper functions

def docx_to_text(docx_path: str) -> str:
    """
    Extracts text from a .docx file.

    Args:
        docx_path: The path to the .docx file.

    Returns:
        The text content of the .docx file.
    """
    try:
        doc = Document(docx_path)
        return '\n'.join([paragraph.text for paragraph in doc.paragraphs])
    except Exception as e:
        print(f"Error reading docx file {docx_path}: {e}")
        return ""


# 1 - Generate taxonomy
async def generate_taxonomy(topic_domain):

    text1 =f"""**Role:** You are an Expert Knowledge Structuring Specialist and Taxonomy Designer. Your task is to create structured frameworks to guide research agents.

        **Objective:** Create a comprehensive glossary and structured taxonomy for analyzing and comparing entities within a specific domain. This taxonomy will guide a specialized deep research agent tasked with gathering consistent and relevant information.

        **Core Task:**
        Based on the user-provided inputs below, determine and define the most relevant categories and sub-categories for research. The structure should be logical and cover the key aspects needed to achieve the user's stated research goal and produce their desired output.

        1.  **Topic Domain:**
            *   **Description:** Specify the primary subject area, product category, technology, market segment, or field to be researched.
            *   **Example:** "<< e.g., 'Enterprise CRM Software', 'Quantum Computing Hardware Providers', 'Sustainable Packaging Materials', 'Generative AI Video Synthesis Tools', 'Cloud Security Posture Management (CSPM) Solutions' >>"
            *   **User Input:** {topic_domain}

        2.  **Research Goal and Outputs**: Perform a deep-dive comparative analysis of the leading platforms to identify key differentiators, strengths, and weaknesses, particularly from the perspective of Google Cloud Platform (GCP). 
        The goal is to enable the creation of detailed competitor battle cards for GCP's sales/technical teams and internal comparison reports.


        **Instructions for Taxonomy Generation:**

        1.  **Analyze Inputs:** Carefully consider the provided `[TOPIC_DOMAIN]` and `[RESEARCH_GOAL_AND_OUTPUT]`.
        2.  **Determine Key Categories:** Identify the essential high-level categories needed to structure the research effectively for the specified domain and goal. Think about common dimensions relevant to comparison and analysis, such as:
            *   **Overview/Identification:** Basic definition, branding, provider/origin.
            *   **Core Capabilities/Features:** What it does, key functionalities specific to the domain.
            *   **Technology/Architecture:** Underlying mechanisms, technical specifications.
            *   **Performance/Specifications:** Measurable characteristics, benchmarks (if applicable).
            *   **Target Audience/Use Cases:** Who is it for, what problems does it solve.
            *   **Pricing/Cost Structure:** How it's priced, TCO factors.
            *   **Ecosystem/Integrations:** How it connects with other tools/platforms.
            *   **Market Positioning:** Strengths, weaknesses, differentiators, market share/perception.
            *   **Implementation/Usability:** Ease of setup, deployment, usage factors.
            *   **Support/Documentation:** Availability and quality of help resources.
            *   **Recent Developments/Roadmap:** Latest updates and future direction.
            *   *(Adapt and select dimensions most relevant to the specific `[TOPIC_DOMAIN]` and `[RESEARCH_GOAL_AND_OUTPUT]`)*
        3.  **Define Structure:** Organize these into a logical structure with clear main categories and relevant sub-categories.
        4.  **Provide Definitions:** For *each* term, category, or sub-category, provide a brief, clear definition or description of the *specific information* the research agent should gather for that item. Ensure the descriptions are actionable for a research agent.
        5.  **Consider Goal Alignment:** Ensure the taxonomy directly supports the `[RESEARCH_GOAL_AND_OUTPUT]`. For instance, if battle cards are needed, explicitly include categories for Strengths, Weaknesses, and Differentiators. If a technical evaluation is the goal, emphasize capability and performance metrics.

        **Output Format:**
        Please present the taxonomy as a structured list or markdown document, suitable for configuring a research agent. Ensure each item has a clear label and a concise, actionable description of the information required.
        """

    model = GenerativeModel("gemini-2.5-pro-exp-03-25")

    max_retries = 3

    for attempt in range(max_retries):
        try:
            response_data = await model.generate_content_async([text1], generation_config=GEN_CONFIG, stream=False)

            # Save the raw response text to a file
            with open('research_prompt.txt', "w") as f:
                f.write(response_data.text)

            print(f"Taxonomy generated!")
            return

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: An unexpected error occurred: {e}")
            if attempt == max_retries - 1:
                raise  # Re-raise the exception if all retries failed
            else:
                print("Retrying...")
    return None


# 2 - Research and generate companies info asynchronously

# Generate one single battlecard
async def generate_battlecard_content(google_report_path, competitor_report_path, output_folder, competitor_name):

    output_file_path = f"{output_folder}/{competitor_name}.json"

    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

    text1 =f"""**Role:** You are an expert Competitive Intelligence Analyst working internally for Google Cloud Platform (GCP). Your goal is to equip GCP sales and technical teams with actionable insights to win against competitors.

        **Objective:** Generate a competitor battle card for **${competitor_name}** specifically from the perspective of Google Cloud Platform (GCP).

        **Input Context:**
        You are provided with two detailed research reports:
        1.  The deep research report for **Google Cloud Platform (GCP)**:"""

    # Extract text from docx files
    google_report_text = docx_to_text(google_report_path)
    competitor_report_text = docx_to_text(competitor_report_path)

    text2 = f"""2. The deep research report for **${competitor_name}**:"""

    text3 = f"""Both reports are based on a comprehensive taxonomy covering platform overview, data/AI capabilities, unification, pricing, ecosystem, strengths, weaknesses, and recent developments.

        **Core Task:**
        Analyze BOTH provided reports to create a battle card focused on **${competitor_name}**. Your analysis *must* be from the **GCP perspective**. This means:
        *   Identify **${competitor_name}'s** key strengths and weaknesses *as they relate to GCP's position*.
        *   Explicitly highlight **GCP's advantages and differentiators** when compared directly to **${competitor_name}**.
        *   Provide concrete, actionable **\"How to Win\" strategies and talking points** for GCP teams engaging with customers considering **${competitor_name}**.
        *   Extract relevant factual information about the competitor's offerings for quick reference.

        **Output Format Instructions:**
        Generate the output **ONLY** as a single, valid JSON object adhering strictly to the schema defined below. Do **NOT** include any explanatory text, markdown formatting, or comments before or after the JSON object.
    """

    text4_json_schema = """**JSON Output Schema:**

        {
         \"battleCardTitle\": \"GCP vs. [competitor_name \"string\"]: Unified Data & AI Battle Card\",
         \"competitorName\": \"string\", // e.g., \"AWS\", \"Microsoft Azure\", \"Databricks\", \"NVIDIA\"
         \"competitorPlatformName\": \"string\", // e.g., \"AWS Cloud\", \"Microsoft Azure\", \"Databricks Lakehouse Platform\", \"NVIDIA AI Enterprise / DGX Cloud\"
         \"competitorValueProposition\": \"string\", // Summarized value prop of the competitor
         \"competitorTargetAudience\": \"string\", // Primary audience/industries for the competitor
         \"competitorStrengths\": [ // List key competitor strengths (Max ~3-4)
           {
             \"strength\": \"string\", // Description of the competitor's strength
             \"gcp_awareness_note\": \"string\" // Brief note on why this strength matters or how GCP should perceive it (e.g., \"Significant market share, be prepared for customer familiarity\", \"Strong in enterprise X, less so in Y\")
           }
         ],
         \"competitorWeaknesses\": [ // List key competitor weaknesses (Max ~3-4)
           {
             \"weakness\": \"string\", // Description of the competitor's weakness or challenge
             \"gcp_opportunity_note\": \"string\" // Brief note on the opportunity this creates for GCP (e.g., \"Opens door for GCP's simpler pricing\", \"Highlight GCP's better integration here\")
           }
         ],
         \"gcpAdvantagesVsCompetitor\": [ // List specific GCP advantages over THIS competitor (Max ~4-5)
           {
             \"gcp_advantage_theme\": \"string\", // Theme of the advantage (e.g., \"Superior AI/ML Integration\", \"Open Source Commitment\", \"Better TCO for Serverless Data\")
             \"gcp_specific_feature_service\": \"string\", // Specific GCP product/feature demonstrating the advantage (e.g., \"Vertex AI Platform\", \"BigQuery Omni\", \"Dataplex Unified Governance\")
             \"competitor_comparison_point\": \"string\" // How it contrasts with the competitor (e.g., \"vs. Competitor's siloed services\", \"vs. Competitor's vendor lock-in\", \"vs. Competitor's complex pricing tiers\")
           }
         ],
         \"howToWinForGcp\": [ // Actionable tactics for GCP teams (Combine themes, talking points, objection handling)
           {
             \"win_theme\": \"string\", // Overall strategic theme (e.g., \"Lead with Unified Data & AI Story\", \"Focus on Openness & Flexibility\", \"Challenge TCO Assumptions\")
             \"talking_point_or_question\": \"string\", // Specific thing to say or ask the customer (e.g., \"Highlight how Vertex AI integrates seamlessly with BigQuery...\", \"Ask about their challenges with [Competitor Weakness]...\")
             \"potential_objection\": \"string\", // Potential customer objection related to competitor strength or GCP perceived weakness
             \"gcp_response_counter\": \"string\" // How GCP should respond (e.g., \"Acknowledge [Competitor Strength] but pivot to GCP's advantage in...\", \"Clarify GCP's position on [Topic] with evidence...\")
           }
         ],
         \"keyCompetitorDataServices\": [ // List key competitor data products mentioned in their report
           \"string\" // e.g., \"S3\", \"Redshift\", \"Glue\"
         ],
         \"keyCompetitorAiMlServices\": [ // List key competitor AI/ML products mentioned in their report
           \"string\" // e.g., \"SageMaker Studio\", \"Bedrock\", \"Rekognition\"
         ],
         \"pricingComparisonNotes\": \"string\", // Brief GCP perspective on pricing comparison (e.g., \"Competitor known for complex egress fees, contrast with GCP's predictable pricing...\", \"While competitor has low entry cost for X, highlight GCP's better TCO for Y...\")
         \"recentCompetitorDevelopments\": \"string\", // Note 1-2 significant recent competitor announcements impacting the comparison.
         \"report_metadata\": { // Essential info about the source data
             \"report_date\": \"YYYY-MM-DD\", // Date the source reports were generated/refreshed
             \"gcp_report_version\": \"string\", // Identifier for the GCP report used
             \"competitor_report_version\": \"string\" // Identifier for the Competitor report used
         }
        }
    """

    text5 = f"""
        **Constraint Reminder:** Base ALL generated content *strictly* on the information contained within the provided GCP and **${competitor_name}** reports. Do not invent information or use external knowledge beyond interpreting the provided text through the GCP lens. Ensure the output is only the JSON object.
    """

    model = GenerativeModel("gemini-2.5-pro-exp-03-25")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response_data = await model.generate_content_async(
                [
                    text1,
                    google_report_text,
                    text2,
                    competitor_report_text,
                    text3,
                    text4_json_schema,
                    text5,
                ],
                generation_config=GEN_CONFIG,
                stream=False
            )

            response_text = response_data.text

            # Save the raw response text to a file
            with open(output_file_path, "w") as f:
                f.write(response_text)

            print(f"Raw battle card content for {competitor_name} saved to {output_file_path}")
            return response_text  # Return the raw text

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: An unexpected error occurred: {e}")
            if attempt == max_retries - 1:
                raise  # Re-raise the exception if all retries failed
            else:
                print("Retrying...")
    return None


# Generate parallel battlecards (one per competitor) and store them in an output folder
async def research_competitors_async(companies: List[str], output_folder_path: str):
    """
    Processes each competitor battlecard generation in parallel and saves each report to a file.
    """
    tasks = []
    
    # Create the directory if it doesn't exist
    os.makedirs(output_folder_path, exist_ok=True)

    for competitor in companies:
        print(competitor)
        tasks.append(generate_battlecard_content("company_reports/GCP.docx", f"company_reports/{competitor}.docx", output_folder_path, competitor))

    report_filenames = await asyncio.gather(*tasks)
    return report_filenames




# Update Slides based on battlecards
def update_presentation_from_battlecard(battlecard_path, new_presentation_name, template_presentation_id, author_ldap):
    """
    Updates a Google Slides presentation with data from a battlecard JSON file.
    Authentication is handled via Application Default Credentials (ADC).

    Args:
        battlecard_path (str): The local path to the battlecard JSON file.
        new_presentation_name (str): The desired name for the new presentation.
        template_presentation_id (str): The ID of the template presentation to copy.
        author_ldap (str): The author's LDAP to be inserted in the presentation.
    """

    # --- 1. Validate Inputs ---
    if not os.path.exists(battlecard_path):
        raise FileNotFoundError(f"Battlecard file not found: {battlecard_path}")
    if not new_presentation_name:
        raise ValueError("New presentation name cannot be empty.")
    if not template_presentation_id:
        raise ValueError("Template presentation ID cannot be empty.")
    if not author_ldap:
        raise ValueError("Author LDAP cannot be empty.")

    # --- 1.5. Initialize Google Services with ADC ---
    try:
        # Automatically find credentials (ADC, environment variables, etc.)
        # This looks for credentials from 'gcloud auth application-default login'
        creds, project_id = google.auth.default(scopes=['https://www.googleapis.com/auth/presentations', 'https://www.googleapis.com/auth/drive'])
        print(f"Successfully obtained ADC credentials. Using project: {project_id or 'Default'}")

        # Build the service objects using the obtained credentials
        slides_service = build('slides', 'v1', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)
        print("Successfully built Slides and Drive API service clients.")

    except google.auth.exceptions.DefaultCredentialsError as e:
        print("ERROR: Could not find Application Default Credentials.")
        print("Please run 'gcloud auth application-default login' in your terminal.")
        print(f"Details: {e}")
        exit()
    except Exception as e:
        print(f"An unexpected error occurred during authentication or service building: {e}")
        exit()

    # --- 2. Load Battle Card JSON Data ---
    try:
        with open(battlecard_path, 'r') as f:
            battleCardJson = json.load(f)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format in battlecard file: {battlecard_path}")

    # --- 3. Copy the Template Presentation ---
    copy_request_body = {
        'name': new_presentation_name
    }
    try:
        copied_file = drive_service.files().copy(
            fileId=template_presentation_id, body=copy_request_body).execute()
        new_presentation_id = copied_file.get('id')
    except Exception as e:
        raise RuntimeError(f"Error copying template presentation: {e}")

    # --- 4. Prepare Replacement Requests ---
    requests = []

    # Function to format lists into bullet points (now fully generic)
    def format_list_for_slides(items):
        lines = []
        if not isinstance(items, list):
            return ""  # Return empty string if not a list

        for item in items:
            line_start = "• "  # Bullet point
            item_formatted = ""

            if isinstance(item, dict):
                # Concatenate all values from the dictionary
                item_formatted = " ".join(str(value) for value in item.values())
            elif isinstance(item, (str, int, float)):
                item_formatted = str(item)
            else:
                item_formatted = str(item)

            lines.append(line_start + item_formatted)

        # Use newline character for bullet points in Slides
        return "\n".join(lines) if lines else ""

    # --- Generic Replacement Logic ---
    for key, value in battleCardJson.items():
        placeholder = "{{" + key + "}}"
        if isinstance(value, list):
            # Format lists
            formatted_list = format_list_for_slides(value)
            requests.append({
                'replaceAllText': {
                    'containsText': {'text': placeholder, 'matchCase': True},
                    'replaceText': formatted_list
                }
            })
        elif isinstance(value, dict):
            # Handle nested dictionaries (e.g., report_metadata.report_date)
            for nested_key, nested_value in value.items():
                nested_placeholder = "{{" + key + "." + nested_key + "}}"
                requests.append({
                    'replaceAllText': {
                        'containsText': {'text': nested_placeholder, 'matchCase': True},
                        'replaceText': str(nested_value)
                    }
                })
        else:
            # Simple text replacement
            requests.append({
                'replaceAllText': {
                    'containsText': {'text': placeholder, 'matchCase': True},
                    'replaceText': str(value)
                }
            })

    # --- Author placeholder ---
    requests.append({
        'replaceAllText': {
            'containsText': {'text': '{{author}}', 'matchCase': True},
            'replaceText': author_ldap
        }
    })

    # --- 5. Execute Batch Update ---
    if requests:
        body = {'requests': requests}
        try:
            response = slides_service.presentations().batchUpdate(
                presentationId=new_presentation_id, body=body).execute()
            print(f"Successfully updated presentation. Response: {response}")
            return f"https://docs.google.com/presentation/d/{new_presentation_id}"
        except Exception as e:
            raise RuntimeError(f"Error updating presentation: {e}")
    else:
        print("No replacement requests generated.")
        return None


def update_presentations_from_battlecards_folder(battlecards_folder_path, template_presentation_id, author_ldap):
    """
    Updates multiple Google Slides presentations from battlecard JSON files in a folder (sequentially).

    Args:
        battlecards_folder_path (str): The path to the folder containing the battlecard JSON files.
        template_presentation_id (str): The ID of the template presentation to copy.
        author_ldap (str): The author's LDAP.

    Returns:
        list: A list of links to the newly created presentations.
    """
    if not os.path.exists(battlecards_folder_path):
        raise FileNotFoundError(f"Battlecards folder not found: {battlecards_folder_path}")

    presentation_links = []
    for filename in os.listdir(battlecards_folder_path):
        if filename.endswith(".json"):
            competitor = filename[:-5]  # Remove ".json"
            new_presentation_name = f"GCP vs {competitor} Battle Card"
            battlecard_path = os.path.join(battlecards_folder_path, filename)
            try:
                link = update_presentation_from_battlecard(
                    battlecard_path,
                    new_presentation_name,
                    template_presentation_id,
                    author_ldap
                )
                if link:
                    presentation_links.append(link)
            except Exception as e:
                print(f"Error processing battlecard {filename}: {e}")

    return presentation_links


def create_merged_battlecard_presentation(
    battlecards_folder_path,
    template_presentation_id,
    author_ldap,
    merged_presentation_name="Merged Battle Cards"
    ):
    """
    Creates a single Google Slides presentation, populates interleaved slides,
    and then reorders them into competitor groups at the end.

    Args:
        battlecards_folder_path: Path to folder containing JSON files.
        template_presentation_id: ID of the Google Slides template (multi-slide).
        author_ldap: Author's LDAP/name.
        merged_presentation_name: Name for the final merged file.

    Returns:
        str: Link to the merged presentation, or None.
    """
    # --- Steps 1, 2, 3 (Init, Copy Template, Get Initial IDs) ---
    if not os.path.exists(battlecards_folder_path): print(f"ERROR: Folder not found: {battlecards_folder_path}"); return None
    try:
        creds, project_id = google.auth.default(scopes=['https://www.googleapis.com/auth/presentations', 'https://www.googleapis.com/auth/drive'])
        slides_service = build('slides', 'v1', credentials=creds); drive_service = build('drive', 'v3', credentials=creds)
        print("Services built.")
    except Exception as e: print(f"ERROR: Init services: {e}"); return None
    try:
        merged_presentation_file = drive_service.files().copy(fileId=template_presentation_id, body={'name': merged_presentation_name}).execute()
        merged_presentation_id = merged_presentation_file.get('id'); assert merged_presentation_id
        print(f"Created merged presentation: {merged_presentation_id}")
    except Exception as e: print(f"ERROR: Copy template: {e}"); return None
    initial_template_slide_ids = []
    try:
        presentation = slides_service.presentations().get(presentationId=merged_presentation_id).execute()
        slides = presentation.get('slides', []); assert slides
        initial_template_slide_ids = [s.get('objectId') for s in slides if s.get('objectId')]; assert initial_template_slide_ids
        num_template_slides = len(initial_template_slide_ids) # Store count M
        print(f"Identified {num_template_slides} initial template slide(s): {initial_template_slide_ids}")
    except Exception as e: print(f"ERROR: Get initial slides: {e}"); return None

    # Function to format lists
    def format_list_for_slides(items):
        lines = [];
        if not isinstance(items, list): return ""
        for item in items:
            line_start = "• "; item_formatted = ""
            if isinstance(item, dict): item_formatted = ": ".join(str(value) for value in item.values() if value)
            else: item_formatted = str(item)
            lines.append(line_start + item_formatted)
        return "\n".join(lines) if lines else ""

    # --- 4. Loop Through Competitors: Duplicate & Populate (NO MOVE YET) ---
    all_new_slide_ids_nested = [] # Store lists of IDs per competitor: [[A1,A2,A3], [B1,B2,B3], ...]
    processed_files_count = 0
    all_json_files = sorted([f for f in os.listdir(battlecards_folder_path) if f.endswith(".json")])

    for c, filename in enumerate(all_json_files): # Keep track of competitor index 'c'
        competitor = filename[:-5]; battlecard_path = os.path.join(battlecards_folder_path, filename)
        print(f"\nProcessing {filename} for {competitor}...")

        # --- 4a. Load JSON ---
        try:
            with open(battlecard_path, 'r') as f: battleCardJson = json.load(f)
        except Exception as e: print(f"  ERROR: Load/Parse JSON: {e}. Skipping."); continue

        # --- 4b. Duplicate slide set ---
        requests_duplicate_set = [{'duplicateObject': {'objectId': t_id, 'objectIds': {}}} for t_id in initial_template_slide_ids]
        if not requests_duplicate_set: continue

        current_competitor_new_slide_ids = []
        try:
            print(f"  Duplicating {len(requests_duplicate_set)} template slide(s)...")
            duplicate_response = slides_service.presentations().batchUpdate(
                presentationId=merged_presentation_id, body={'requests': requests_duplicate_set}).execute()
            replies = duplicate_response.get('replies', [])
            if len(replies) != len(requests_duplicate_set): raise ValueError("Mismatch duplicating")
            current_competitor_new_slide_ids = [r.get('duplicateObject', {}).get('objectId') for r in replies]
            if None in current_competitor_new_slide_ids: raise ValueError("Got None new slide ID")
            # Store this list of IDs for the final reorder step
            all_new_slide_ids_nested.append(current_competitor_new_slide_ids)
            print(f"  Created {len(current_competitor_new_slide_ids)} new slides: {current_competitor_new_slide_ids}")
        except Exception as e: print(f"  ERROR during duplication: {e}. Skipping."); continue

        # --- 4c. REMOVED MOVE STEP ---

        # --- 4d/4e. Prepare and Execute Replacement Requests ---
        # (Populate the slides wherever they were created)
        requests_replace = []
        try:
            for key, value in battleCardJson.items():
                placeholder = "{{" + key + "}}"; req_base={'replaceAllText': {'containsText': {'text': placeholder, 'matchCase': True}, 'pageObjectIds': current_competitor_new_slide_ids}}
                if isinstance(value, list): req_base['replaceAllText']['replaceText'] = format_list_for_slides(value); requests_replace.append(req_base)
                elif isinstance(value, dict):
                    for nk, nv in value.items(): requests_replace.append({'replaceAllText': {'containsText': {'text': "{{" + key + "." + nk + "}}", 'matchCase': True}, 'replaceText': str(nv), 'pageObjectIds': current_competitor_new_slide_ids}})
                else: req_base['replaceAllText']['replaceText'] = str(value); requests_replace.append(req_base)
            requests_replace.append({'replaceAllText': {'containsText': {'text': '{{author}}', 'matchCase': True}, 'replaceText': author_ldap, 'pageObjectIds': current_competitor_new_slide_ids}})

            if requests_replace:
                    body_replace = {'requests': requests_replace}; replace_response = slides_service.presentations().batchUpdate(presentationId=merged_presentation_id, body=body_replace).execute()
                    changes_made = sum(reply.get('replaceAllText',{}).get('occurrencesChanged', 0) for reply in replace_response.get('replies',[])); print(f"  Successfully applied {len(requests_replace)} replacements (occurrences changed: {changes_made}).")
                    processed_files_count += 1 # Indicate success for this competitor
            else: print("  Warning: No replacement requests generated.")
        except Exception as e: print(f"  ERROR during replacement: {e}. Slide content may be incomplete."); continue # Don't count as processed


    # --- END OF COMPETITOR LOOP ---


    # --- 5. ***Final Reordering Step *** ---
    print(f"\n--- Starting final slide reordering phase ---")
    if processed_files_count > 0 and len(all_new_slide_ids_nested) == processed_files_count:
        move_requests = []
        num_slides_per_competitor = len(initial_template_slide_ids) # M

        # Iterate through the *stored* slide IDs, grouped by competitor
        for c, competitor_slide_ids in enumerate(all_new_slide_ids_nested):
             # Double check we have the expected number of slides for this competitor
            if len(competitor_slide_ids) != num_slides_per_competitor:
                print(f"  Warning: Competitor {c} has unexpected number of slides ({len(competitor_slide_ids)} vs {num_slides_per_competitor}). Skipping its reorder.")
                continue

            for s, slide_id in enumerate(competitor_slide_ids):
                # Calculate FINAL target index: M (offset) + c*M (previous blocks) + s (position in block)
                target_index = num_template_slides + (c * num_slides_per_competitor) + s
                move_requests.append({
                    'updateSlidesPosition': {
                        'slideObjectIds': [slide_id], # Move one slide at a time
                        'insertionIndex': target_index
                    }
                })

        if move_requests:
            try:
                print(f"Preparing to move {len(move_requests)} slides into final grouped order...")
                move_body = {'requests': move_requests}
                slides_service.presentations().batchUpdate(
                    presentationId=merged_presentation_id, body=move_body).execute()
                print("Successfully submitted final reordering requests.")
            except HttpError as error:
                print(f"  ERROR: Could not execute final slide reordering batch.")
                print(f"  Details: {error}. Presentation slides may be out of order.")
            except Exception as e:
                print(f"  ERROR: An unexpected error occurred during final reordering: {e}.")
        else:
             print("No move requests were generated for reordering (perhaps no files processed?).")

    elif processed_files_count > 0:
        print("\nWarning: Number of processed competitors doesn't match stored slide ID groups. Skipping reordering.")
    else:
        print("\nNo competitors processed successfully. Skipping reordering phase.")

    # --- 6. Delete the original template slides ---
    if processed_files_count > 0 and initial_template_slide_ids:
        print(f"\nDeleting {len(initial_template_slide_ids)} original template slide(s)...")
        try:
            requests_delete = [{'deleteObject': {'objectId': s_id}} for s_id in initial_template_slide_ids]
            slides_service.presentations().batchUpdate(presentationId=merged_presentation_id, body={'requests': requests_delete}).execute()
            print("  Successfully deleted original template slides.")
        except Exception as e: print(f"  Warning: Could not delete template slides: {e}")
    # ... (rest of deletion logic) ...

    # --- 7. Return Link ---
    # ... (keep return logic the same) ...
    final_link = f"https://docs.google.com/presentation/d/{merged_presentation_id}/edit"
    print(f"\nMerged presentation processing complete: {final_link}")
    return final_link