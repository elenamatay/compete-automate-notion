# Troubleshooting Guide: Common Student Issues

## Quick Diagnostic Commands

Before diving into specific issues, have students run these diagnostic commands:

```bash
# Check Python installation
python --version
python3 --version
which python
which python3

# Check virtual environment
echo $VIRTUAL_ENV  # Should show path if activated

# Check Google Cloud
gcloud auth list
gcloud config get-value project

# Check pip packages
pip list | grep -E "(google|notion|pandas|jupyter)"
```

---

## Python Installation Issues

### Issue: "python is not recognized" (Windows)
**Symptoms**: Command not found when typing `python`

**Solutions**:
1. **Add Python to PATH**:
   - Reinstall Python with "Add to PATH" checked
   - Or manually add: `C:\Users\YourName\AppData\Local\Programs\Python\Python312\`

2. **Use `py` command instead**:
   ```cmd
   py --version
   py -m pip install package
   ```

### Issue: "python3 command not found" (macOS)
**Solutions**:
1. **Install via Homebrew**:
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   brew install python@3.12
   ```

2. **Use python instead of python3**:
   ```bash
   python --version  # Should show 3.12.x
   ```

### Issue: Multiple Python versions conflict
**Solution**: Always use virtual environments
```bash
# Create with specific Python version
python3.12 -m venv compete-automate-venv
# Or on Windows:
py -3.12 -m venv compete-automate-venv
```

---

## Virtual Environment Issues

### Issue: Virtual environment not activating
**Symptoms**: No `(compete-automate-venv)` prefix in terminal

**Solutions**:
1. **Windows PowerShell execution policy**:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

2. **Use correct activation command**:
   ```bash
   # Windows Command Prompt
   compete-automate-venv\Scripts\activate.bat
   
   # Windows PowerShell
   compete-automate-venv\Scripts\Activate.ps1
   
   # macOS/Linux
   source compete-automate-venv/bin/activate
   ```

3. **Recreate environment**:
   ```bash
   rm -rf compete-automate-venv
   python -m venv compete-automate-venv
   ```

### Issue: "pip not found" in virtual environment
**Solution**:
```bash
python -m pip install --upgrade pip
```

---

## Package Installation Issues

### Issue: Requirements installation fails
**Common errors and solutions**:

1. **Network/proxy issues**:
   ```bash
   pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt
   ```

2. **Outdated pip**:
   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Individual package failures**:
   ```bash
   # Install packages one by one to identify the problem
   pip install google-cloud-aiplatform
   pip install notion-client
   pip install pandas
   ```

### Issue: "Microsoft Visual C++ required" (Windows)
**Solution**: Install Visual Studio Build Tools
- Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
- Install "C++ build tools" workload

### Issue: "Failed building wheel" errors
**Solutions**:
1. **Install build dependencies**:
   ```bash
   pip install wheel setuptools
   ```

2. **Use pre-compiled wheels**:
   ```bash
   pip install --only-binary=all package_name
   ```

---

## Google Cloud Issues

### Issue: "gcloud not found"
**Solutions**:
1. **Restart terminal** after installation
2. **Add to PATH manually**:
   ```bash
   # macOS/Linux
   export PATH=$PATH:/path/to/google-cloud-sdk/bin
   
   # Windows - add to system PATH:
   # C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin
   ```

### Issue: Authentication failures
**Symptoms**: "Default credentials not found" or "Authentication failed"

**Solutions**:
1. **Re-authenticate**:
   ```bash
   gcloud auth application-default revoke
   gcloud auth application-default login
   ```

2. **Check project setting**:
   ```bash
   gcloud config list
   gcloud config set project YOUR_PROJECT_ID
   ```

3. **Verify APIs are enabled**:
   - Go to Google Cloud Console
   - APIs & Services → Library
   - Enable "Vertex AI API" and "Generative AI API"

### Issue: "Project not found" or "Permission denied"
**Solutions**:
1. **Verify project ID**:
   ```bash
   gcloud projects list
   ```

2. **Set correct project**:
   ```bash
   gcloud config set project correct-project-id
   ```

3. **Check billing**:
   - Ensure billing is enabled for the project
   - Free tier should be sufficient for class

### Issue: API quota exceeded
**Symptoms**: "Quota exceeded" errors during notebook execution

**Solutions**:
1. **Check quotas**: Google Cloud Console → IAM & Admin → Quotas
2. **Request quota increase** if needed
3. **Use instructor's project** as backup

---

## Notion Integration Issues

### Issue: "Invalid token" errors
**Solutions**:
1. **Verify token format**:
   - Should start with `secret_`
   - Should be exactly 50+ characters
   - No extra spaces or quotes in `.env` file

2. **Regenerate token**:
   - Go to https://www.notion.so/my-integrations
   - Click your integration → "Internal Integration Token"
   - Generate new secret

### Issue: "Page not found" or "Permission denied"
**Solutions**:
1. **Verify page ID**:
   - From URL: `https://notion.so/Page-Name-abc123def456...`
   - ID is the last 32 characters after final dash
   - Remove any query parameters (`?v=...`)

2. **Check page sharing**:
   - Page must be shared with your integration
   - Click "Share" → Add your integration
   - Give "Full access" permissions

3. **Test with simple page**:
   - Create a new, simple page
   - Share it with integration
   - Use that page ID for testing

### Issue: Database creation fails
**Solutions**:
1. **Check parent page permissions**:
   - Integration needs "Full access" to parent page
   - Parent page must exist and be accessible

2. **Clear database ID**:
   ```bash
   # In .env file, ensure this line is empty:
   NOTION_DATABASE_ID=
   ```

---

## IDE and Jupyter Issues

### Issue: Jupyter kernel not found
**Symptoms**: "No kernel" or "Kernel not found" in notebook

**Solutions**:
1. **Install ipykernel in virtual environment**:
   ```bash
   pip install ipykernel
   python -m ipykernel install --user --name=compete-automate-venv
   ```

2. **Select correct kernel**:
   - VS Code: Click kernel selector, choose your venv
   - Cursor: Select Python interpreter from your venv

### Issue: Python interpreter not found in IDE
**Solutions**:
1. **VS Code**:
   - Ctrl+Shift+P → "Python: Select Interpreter"
   - Choose interpreter from your virtual environment

2. **Cursor**:
   - Similar to VS Code - select Python interpreter
   - Should show path to your venv

### Issue: Extensions not working
**Solutions**:
1. **Install required extensions**:
   - VS Code: Python, Jupyter
   - Cursor: Usually pre-installed

2. **Reload window**:
   - Ctrl+Shift+P → "Developer: Reload Window"

---

## Notebook Execution Issues

### Issue: "Module not found" errors
**Solutions**:
1. **Verify virtual environment is active**:
   ```python
   import sys
   print(sys.executable)
   # Should show path to your venv
   ```

2. **Reinstall packages**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Check kernel**:
   - Make sure notebook is using correct Python kernel

### Issue: API call failures
**Common errors**:

1. **"Authentication failed"**:
   - Re-run `gcloud auth application-default login`
   - Check project is set correctly

2. **"API not enabled"**:
   - Enable Vertex AI API in Google Cloud Console
   - Wait a few minutes for propagation

3. **"Quota exceeded"**:
   - Check API quotas in Google Cloud Console
   - Use smaller competitor lists for testing

### Issue: Slow notebook execution
**Solutions**:
1. **Reduce competitor list** for testing:
   ```python
   COMPETITORS = ["AppFolio"]  # Test with one competitor first
   ```

2. **Check internet connection**:
   - API calls require stable internet
   - Consider mobile hotspot if WiFi is slow

---

## File and Configuration Issues

### Issue: ".env file not found"
**Solutions**:
1. **Verify file location**:
   ```bash
   ls -la | grep env  # Should show .env file
   ```

2. **Create from template**:
   ```bash
   cp env_template.txt .env
   ```

3. **Check file permissions**:
   ```bash
   chmod 644 .env
   ```

### Issue: "config.json not found"
**Solution**: Ensure `config.json` is in the same directory as the notebook

### Issue: CSV file not found
**Solution**: Ensure `competitors.csv` exists and has proper format:
```csv
Competitor
AppFolio
Buildium
Avail
```

---

## Network and Firewall Issues

### Issue: Corporate firewall blocking APIs
**Solutions**:
1. **Use mobile hotspot** for class
2. **Configure proxy settings**:
   ```bash
   pip install --proxy http://proxy:port package
   gcloud config set proxy/type http
   gcloud config set proxy/address proxy_address
   gcloud config set proxy/port proxy_port
   ```

### Issue: SSL certificate errors
**Solutions**:
```bash
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org package
```

---

## Emergency Solutions for Class

### If Student Setup Completely Fails:
1. **Pair programming**: Have them work with someone who has working setup
2. **Google Colab backup**: Upload notebook to Colab (pre-configured)
3. **Screen sharing**: Let them follow along with your screen
4. **Demo mode**: Show results without them running code

### If APIs Are Down:
1. **Use pre-generated results**: Show example JSON files
2. **Simulate API responses**: Mock the data for learning purposes
3. **Focus on Notion part**: Use existing data to populate database

### Quick Fixes During Class:
```bash
# Reset everything quickly
rm -rf compete-automate-venv
python -m venv compete-automate-venv
source compete-automate-venv/bin/activate  # or Scripts\activate
pip install -r requirements.txt
gcloud auth application-default login
```

---

## Prevention Tips for Next Class

1. **Send setup guide 1 week before class**
2. **Offer "setup office hours" 2 days before**
3. **Test with actual students before class**
4. **Prepare backup Google Cloud project**
5. **Have pre-configured environments ready**
6. **Create troubleshooting FAQ from this session**

Remember: Stay calm, be patient, and have backup plans ready!
