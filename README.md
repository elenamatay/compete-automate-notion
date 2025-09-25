# Competitor Research Automation

Automated competitor research using AI (Google Vertex AI) with results stored in Notion databases.

## What This Does

1. **AI Research**: Uses Google's Vertex AI to automatically research competitors from the web
2. **Structured Data**: Extracts 50+ data points per competitor (pricing, features, market position, etc.)
3. **Notion Integration**: Creates and populates a Notion database with all research results
4. **Automatic Updates**: Discovers new competitors and updates existing research

## Quick Start

### 1. Prerequisites
- Python 3.12+
- Google Cloud account (free tier works)
- Notion account

### 2. Setup (First Time)
```bash
# Clone and enter directory
cd competitor-research-automation

# Create virtual environment
python -m venv compete-automate-venv
source compete-automate-venv/bin/activate  # Windows: compete-automate-venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup Google Cloud authentication
gcloud auth application-default login
```

### 3. Configuration

**Create `.env` file** (copy from `env_template.txt`):
```
NOTION_API_TOKEN=secret_your_integration_token_here
NOTION_PARENT_PAGE_ID=your_page_id_here
NOTION_DATABASE_ID=  # Leave empty - will be created automatically
```

**Edit `config.json`**:
- Update `company_context` with your company info
- Customize research fields if needed

**Edit `competitors.csv`**:
- Add your competitors (one per line)

### 4. Run the Analysis

Open `compete.ipynb` in Jupyter/VS Code and run cells step by step:

1. **Cell 1-2**: Load configuration and verify setup
2. **Cell 3-4**: Run AI research on competitors (takes 5-15 minutes)
3. **Cell 5-7**: Create Notion database 
4. **Cell 8-9**: Populate database with research results
5. **Cell 10-11**: Update existing research (optional)

## File Structure

```
├── compete.ipynb           # Main notebook - run this step by step
├── config.json            # Company context and research schema
├── competitors.csv         # List of competitors to research
├── .env                   # API tokens and IDs (create from template)
├── requirements.txt       # Python dependencies
├── utils.py              # Core research and Notion functions
├── update_competitor_research.py  # Standalone update script
└── competitor_research_json/      # Generated research files (JSON)
```

## Setup Help

**Need detailed setup instructions?** See `STUDENT_SETUP_GUIDE.md`

**Having issues?** Check `TROUBLESHOOTING_GUIDE.md`

## Key Features

- **Comprehensive Research**: 50+ data points per competitor including pricing, features, market position
- **AI-Powered**: Uses Google's latest Vertex AI with web search capabilities  
- **Notion Integration**: Automatically creates and maintains structured databases
- **Update Mechanism**: Tracks changes and discovers new competitors over time
- **Customizable**: Easy to adapt for different industries and research needs

## Example Output

Each competitor gets researched across categories like:
- Company basics (size, funding, location)
- Product features and AI capabilities  
- Pricing and business model
- Market position and reviews
- Competitive analysis specific to your company

Results are saved as JSON files and automatically formatted in Notion.

## Requirements

- **Google Cloud**: Free tier sufficient, needs Vertex AI API enabled
- **Notion**: Free account, requires integration token
- **Internet**: Stable connection for API calls
- **Time**: Initial research takes 5-15 minutes depending on competitor count

## Costs

- **Google Cloud**: ~$0.01-0.05 per competitor researched
- **Notion**: Free for personal use
- **Total**: Typically under $1 for 10-20 competitors

---

*For educational/workshop use: Students just need to configure the `.env` and `config.json` files, then run the notebook step by step.*
