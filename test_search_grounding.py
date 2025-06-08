import asyncio
from utils import research_competitors_async

async def main():
    # Test with two competitors that should benefit from web search grounding
    test_competitors = [
        "Woz AI",  # Should find info about the AI startup
        "Rocketable"  # Should find info about the no-code automation platform
    ]
    
    print("Starting test with competitors:", test_competitors)
    
    results = await research_competitors_async(
        competitors_list=test_competitors,
        topic_domain="AI/ML automation solutions",
        research_goal="Find information about their AI capabilities and automation features",
        output_folder_path="test_results"
    )
    
    print("\nTest completed!")
    print(f"Successfully processed {len(results)} out of {len(test_competitors)} competitors")
    print("\nOutput files:")
    for file_path in results:
        print(f" - {file_path}")

if __name__ == "__main__":
    asyncio.run(main()) 