# Student Setup Guide: Competitor Research Automation

## Pre-Class Preparation (Complete Before Class)

### System Requirements
- **Operating System**: Windows 10/11, macOS 10.15+, or Linux
- **RAM**: Minimum 4GB, recommended 8GB+
- **Storage**: At least 2GB free space
- **Internet**: Stable broadband connection (required for API calls)

---

## Step 1: Install IDE (Choose One)

### Option A: Cursor
1. Go to https://cursor.sh/
2. Download and install Cursor
3. Python and Jupyter extensions come pre-installed

### Option B: Visual Studio Code
1. Go to https://code.visualstudio.com/
2. Download and install VS Code
3. Install Python extension:
   - Open VS Code
   - Click Extensions icon (left sidebar)
   - Search "Python" 
   - Install the Microsoft Python extension
   - Install "Jupyter" extension for notebook support

### About Terminal/Command Line
Throughout this guide, you'll see commands in code blocks like this:
```bash
python --version
```

These need to be typed in the **terminal** inside your IDE:
- Open your IDE (VS Code or Cursor)
- Go to View menu → Terminal (or press the shortcut, which might be either Ctrl + \` or Cmd + \`)
- Type the command exactly as shown, then press Enter

---

## Step 2: Install Python 3.12

### Windows:
1. Go to https://www.python.org/downloads/windows/
2. Download Python 3.12.x (latest version)
3. **IMPORTANT**: During installation, check "Add Python to PATH"
4. Choose "Install for all users" if prompted
5. Verify installation: Open Command Prompt and type:
   ```
   python --version
   ```
   Should show Python 3.12.x

### macOS:
1. Go to https://www.python.org/downloads/macos/
2. Download Python 3.12.x for macOS
3. Install the downloaded package
4. Verify installation: Open Terminal and type:
   ```
   python3 --version
   ```
   Should show Python 3.12.x

### Linux (Ubuntu/Debian):
```bash
sudo apt update
sudo apt install python3.12 python3.12-pip python3.12-venv
```

---

## Step 3: Install Google Cloud CLI

### Windows:
1. Go to https://cloud.google.com/sdk/docs/install
2. Download the Google Cloud CLI installer
3. Run the installer and follow prompts
4. Restart your command prompt

### macOS:
```bash
# Install using Homebrew (if you have it)
brew install --cask google-cloud-sdk

# OR download installer from:
# https://cloud.google.com/sdk/docs/install
```

### Linux:
```bash
# Ubuntu/Debian
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
echo "deb https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
sudo apt update
sudo apt install google-cloud-cli
```

### Verify Installation:
Open terminal/command prompt and type:
```
gcloud --version
```

---

## Step 4: Set Up Google Cloud Authentication

1. **Create Google Cloud Account** (if you don't have one):
   - Go to https://cloud.google.com/
   - Sign up with your Google account
   - You'll get $300 in free credits

2. **Create a New Project**:
   - Go to https://console.cloud.google.com/
   - Click "Select a project" → "New Project"
   - Name it: "competitor-research-class"
   - Note your Project ID

3. **Authenticate locally**:
   ```bash
   gcloud auth application-default login
   ```
   - This will open a browser
   - Sign in with your Google account
   - Grant permissions

4. **Set your project**:
   ```bash
   gcloud config set project YOUR_PROJECT_ID
   ```

---

## Step 5: Set Up Notion Integration

1. **Create Notion Account** (if you don't have one):
   - Go to https://notion.so and sign up

2. **Create Parent Page**:
   - In Notion, create a new page called "Competitor Analysis"
   - Share this page with your integration:
     - Click "Share" → "Add people"
     - Search for your integration name
     - Give it "Full access"
   - **SAVE THE PAGE URL** - you'll need the ID from it

3. **Create Integration**:
   - Go to https://www.notion.so/my-integrations
   - Click "New integration"
   - Name: "Competitor Research Bot"
   - Type: "Internal"
   - Capabilities: Read, Update and Insert content; No user information.
   - In the Access tab, select your new page
   - Click "Submit"
   - **SAVE THE SECRET TOKEN** - you'll need it later

---

## Step 6: Clone the repo

1. **Open the IDE and its terminal** again 
2. (If not done) **Create a new folder for your code projects**: 
   ```bash
   mkdir Code
   ```
3. **Move into the new folder**:
   ```bash
   cd Code
   ```
4. Once in the new folder, **clone the repo**: 
   ```bash
   git clone https://github.com/elenamatay/compete-automate-notion.git
   ```
   You'll see the repo being copied automatically, and since now you'll be able to open and interact with the repo files -your local version of it- in the left bar.

---

## Step 7: Set Up Python Environment

1. **Open terminal/command prompt** in your project folder (called `compete-automate-notion`)
2. **Create virtual environment**:
   ```bash
   # Windows
   python -m venv compete-automate-venv
   compete-automate-venv\Scripts\activate

   # macOS/Linux
   python3 -m venv compete-automate-venv
   source compete-automate-venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## Step 8: Configure Environment Files

1. **Copy the template**:
   - Copy `env_template.txt` to `.env`

2. **Edit `.env` file** with your information:
   ```
   NOTION_API_TOKEN=secret_YOUR_INTEGRATION_TOKEN_HERE
   NOTION_PARENT_PAGE_ID=YOUR_PAGE_ID_HERE
   NOTION_DATABASE_ID=  # Leave empty - will be created automatically
   ```

3. **Get your Notion Page ID**:
   - From your Notion page URL: `https://notion.so/Your-Page-NAME-HERE-abc123def456...`
   - The Page ID is the last 32 characters (after the last dash)
   - Example: if URL is `https://notion.so/My-Page-abc123def456789`, the ID is `abc123def456789`

4. **Edit `config.json`** if needed:
   - Update company context for your use case
   - Modify competitor list in `competitors.csv`

---

## Step 9: Test Your Setup

1. **Activate your virtual environment** (if not already active):
   ```bash
   # Windows
   compete-automate-venv\Scripts\activate
   
   # macOS/Linux
   source compete-automate-venv/bin/activate
   ```

2. **Test Google Cloud connection**:
   ```bash
   gcloud auth list
   ```
   Should show your authenticated account

3. **Open the notebook**:
   - In VS Code: Open `compete.ipynb`
   - In Cursor: Open `compete.ipynb`

4. **Run the first cell** to test imports
   - If you see errors, check the troubleshooting section below

---

## Troubleshooting Common Issues

For detailed troubleshooting help with common setup problems, see `TROUBLESHOOTING_GUIDE.md`.

---

## Need Help?

If you encounter issues during setup:
1. Check the troubleshooting section above
2. Search the error message online

**Important**: Please complete this setup BEFORE class. We'll have limited time for troubleshooting during the session.
