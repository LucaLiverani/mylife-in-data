# DuckDB Data Exploration

Data exploration project using DuckDB, MinIO, and Jupyter notebooks.

## Setup

### 1. Clone and Setup Environment

\`\`\`bash
# Clone repository
git clone <your-repo>
cd duckdb-data-exploration

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt
\`\`\`

### 2. Configure Environment

\`\`\`bash
# Copy example env file
cp .env.example .env

# Edit .env with your MinIO credentials
\`\`\`

### 3. Open in VSCode

\`\`\`bash
code .
\`\`\`

### 4. Select Kernel

1. Open a notebook in `notebooks/`
2. Click "Select Kernel" (top-right)
3. Choose `.venv` environment

## Project Structure

\`\`\`
├── notebooks/          # Jupyter notebooks
├── src/               # Python modules
├── queries/           # SQL queries
├── tests/             # Unit tests
└── data/              # Local data files
\`\`\`

## Usage

### Quick Start

\`\`\`python
from src.duckdb_config import explore

# Query data
df = explore("SELECT * FROM read_parquet('s3://bucket/*.parquet')")
\`\`\`

### Running Tests

\`\`\`bash
pytest
\`\`\`

### Code Formatting

\`\`\`bash
black src/ tests/
isort src/ tests/
\`\`\`

## Documentation

- [DuckDB Docs](https://duckdb.org/docs/)
- [Project Wiki](link-to-wiki)
\`\`\`

---

## **Best Practices Checklist**

### **Environment Management**

- [ ] Always activate `.venv` before working
- [ ] Keep `requirements.txt` updated (`pip freeze > requirements.txt`)
- [ ] Use `.env` for sensitive credentials (never commit!)
- [ ] Document dependencies in README

### **Notebook Hygiene**

- [ ] Clear outputs before committing (`Cell → All Output → Clear`)
- [ ] Use descriptive cell comments
- [ ] Keep notebooks focused (one topic per notebook)
- [ ] Extract reusable code to `src/` modules
- [ ] Name notebooks with numbers: `01_exploration.ipynb`, `02_analysis.ipynb`

### **Code Quality**

- [ ] Format code with Black: `black .`
- [ ] Sort imports with isort: `isort .`
- [ ] Run tests before commits: `pytest`
- [ ] Use type hints where helpful
- [ ] Write docstrings for functions

### **Version Control**

- [ ] Commit frequently with clear messages
- [ ] Don't commit large data files
- [ ] Don't commit `.env` files
- [ ] Clear notebook outputs before committing
- [ ] Use `.gitignore` properly

### **DuckDB Specific**

- [ ] Use parameterized queries for safety
- [ ] Close connections when done (use context managers)
- [ ] Limit memory usage with `SET memory_limit`
- [ ] Use `EXPLAIN` to optimize slow queries
- [ ] Sample large datasets for exploration

---

## **Quick Start Commands**

```bash
# Complete setup from scratch
git init
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
code .

# Daily workflow
source .venv/bin/activate  # Activate environment
code .                      # Open VSCode
# Create/open notebook → Select .venv kernel → Start exploring!

# Before committing
black src/ tests/
isort src/ tests/
pytest
git add .
git commit -m "Your message"

## §(Optional) Install VsCode extensions
```bash
# Install all at once
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension ms-toolsai.jupyter
code --install-extension ms-toolsai.jupyter-keymap
code --install-extension ms-toolsai.jupyter-renderers
code --install-extension mtxr.sqltools
code --install-extension evidence-dev.sqltools-duckdb-driver
code --install-extension charliermarsh.ruff
code --install-extension ms-python.black-formatter
code --install-extension eamodio.gitlens
``` 