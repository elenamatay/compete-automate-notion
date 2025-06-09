import asyncio
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Import utility functions and constants
from utils import (
    update_single_competitor_async,
    generate_top_changes_summary_async,
    populate_notion_db_from_folder,
    append_text_to_notion_page_async,
    discover_new_competitors_async,
    SEIDO_CONTEXT_SUMMARY
)
from notion_client import AsyncClient
from vertexai.generative_models import GenerationConfig

# --- Config parameters ---
NOTION_API_TOKEN = os.getenv("NOTION_API_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_SUMMARY_PAGE_ID = os.getenv("NOTION_PARENT_PAGE_ID")

OUTPUT_FOLDER = "competitor_research_json"
DISCOVERY_LOOKBACK_DAYS = 30

async def main_update():
    """
    Main orchestration function to update competitor research, discover new ones,
    update the Notion DB, and post a summary of changes.
    """
    # --- 1. Verify Configuration ---
    if not all([NOTION_API_TOKEN, NOTION_DATABASE_ID, NOTION_SUMMARY_PAGE_ID]):
        print("Error: Missing critical environment variables.")
        print("Please ensure NOTION_API_TOKEN, NOTION_DATABASE_ID, and NOTION_SUMMARY_PAGE_ID are set in your .env file.")
        return

    if not os.path.exists(OUTPUT_FOLDER):
        print(f"Error: Output folder '{OUTPUT_FOLDER}' not found. Please run the initial research first.")
        return

    # --- 2. Gather Existing Competitors and Launch Parallel Tasks ---
    json_files = [os.path.join(OUTPUT_FOLDER, f) for f in os.listdir(OUTPUT_FOLDER) if f.endswith('.json')]
    existing_competitor_names = [f.replace('.json', '').replace('_', ' ') for f in os.listdir(OUTPUT_FOLDER) if f.endswith('.json')]

    if not json_files:
        print(f"No JSON files found in '{OUTPUT_FOLDER}'. Only running new competitor discovery.")

    print(f"Found {len(json_files)} competitors to check for updates...")

    # Create a list of all tasks to run in parallel
    update_tasks = []
    for json_file in json_files:
        update_tasks.append(
            update_single_competitor_async(
                json_file_path=json_file,
                seido_context=SEIDO_CONTEXT_SUMMARY
            )
        )

    discovery_task = asyncio.create_task(
        discover_new_competitors_async(
            days_ago=DISCOVERY_LOOKBACK_DAYS,
            seido_context=SEIDO_CONTEXT_SUMMARY,
            existing_competitors=existing_competitor_names
        )
    )

    # Run all update tasks and gather results
    update_results = await asyncio.gather(*update_tasks)
    newly_discovered_competitors = await discovery_task

    # --- 3. Process Update Results ---
    successful_updates = [res for res in update_results if res is not None]
    change_summaries = [summary for _, summary in successful_updates] if successful_updates else []

    # --- 4. Generate Top 10 Summary ---
    top_changes_summary = "No significant competitor updates found in this run."
    if change_summaries:
        print("\nGenerating final executive summary of top changes...")
        top_changes_summary = await generate_top_changes_summary_async(
            all_changes=change_summaries,
            seido_context=SEIDO_CONTEXT_SUMMARY
        )

    print("\n--- EXECUTIVE SUMMARY ---")
    print(top_changes_summary)
    print("-------------------------\n")

    # --- 5. Update Notion Database (if any updates were successful) ---
    if successful_updates:
        print("Updating Notion database with the latest information...")
        await populate_notion_db_from_folder(
            output_folder=OUTPUT_FOLDER,
            database_id=NOTION_DATABASE_ID,
            notion_token=NOTION_API_TOKEN,
            title_field_name="Competitor Name"
        )
    else:
        print("No successful updates, skipping Notion database population.")

    # --- 6. Append Summaries to Notion Page ---
    print("Appending summaries to the Notion page...")
    notion_client = AsyncClient(auth=NOTION_API_TOKEN)

    update_summary_title = f"Competitor Intelligence Update - {datetime.now().strftime('%B %d, %Y')}"
    await append_text_to_notion_page_async(
        notion_client=notion_client,
        page_id=NOTION_SUMMARY_PAGE_ID,
        title=update_summary_title,
        content=top_changes_summary
    )

    if newly_discovered_competitors:
        discovery_summary_title = "Potential New Competitors Discovered"
        discovery_content = (
            "The following potential new competitors were identified and should be reviewed. "
            "If relevant, add them to the 'competitors.csv' file for the next full research run:\n\n- " +
            "\n- ".join(newly_discovered_competitors)
        )
        await append_text_to_notion_page_async(
            notion_client=notion_client,
            page_id=NOTION_SUMMARY_PAGE_ID,
            title=discovery_summary_title,
            content=discovery_content
        )
        print(f"Appended {len(newly_discovered_competitors)} new potential competitors to the Notion page.")
    else:
        print("No new competitors were discovered in this run.")

    print("\nUpdate and Discovery process complete!")


if __name__ == "__main__":
    asyncio.run(main_update())