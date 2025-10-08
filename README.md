# Java2NodeAI

An AI-assisted Python tool that analyzes Java codebases and converts them to Node.js (Express) applications, with intelligent code analysis and transformation capabilities.

## Features

- **Intelligent Code Analysis**
  - AST-based Java parsing
  - Cyclomatic complexity calculation
  - Dependency tracking
  - Optional LLM-enhanced code understanding

- **Smart Conversion**
  - Spring MVC to Express.js routes
  - Service layer abstraction
  - DAO pattern implementation
  - Automatic Express app scaffolding
  - Spring annotation parsing
  - Request/Response DTO handling
  - Automatic parameter binding
  - Service dependency injection
  - Type conversion

- **Multiple LLM Providers**
  - Google Gemini (default)
  - OpenAI
  - Anthropic
  - Local fallback mode

- **Comprehensive Reporting**
  - Modern HTML and TXT reports
  - Detailed token usage tracking
  - Performance metrics and timings
  - Project structure visualization
  - Knowledge extraction results
  - Class dependency graphs
  - Method complexity metrics
  - Code structure comparisons

- **Robust Logging**
  - Configurable log levels
  - File-based logging
  - Secure LLM call tracking
  - Performance monitoring
  - Debug capabilities

## Installation

### Prerequisites
- Python 3.11+
- Java source code (compilable)
- (Optional) LLM API keys

### Quick Start

1. Create and activate a virtual environment:
```bash
# Windows
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

4. Run the converter:
```bash
python -m ai2node.main /path/to/java/project --out ./Output
```

For detailed setup instructions, see:
- [Windows Installation](INSTALL_WINDOWS.md)
- [Linux Installation](INSTALL_LINUX.md)

## Knowledge Extraction

### Complexity Analysis
- Cyclomatic complexity scoring per method
- Complexity labels (Low/Medium/High)
- Decision point tracking (if/for/while/switch/try-catch)
- Boolean operation analysis

### Dependency Mapping
- Internal class reference tracking
- Type usage analysis
- Method parameter type mapping
- Return type collection

### Code Structure Analysis
- Class categorization (Controller/Service/DAO)
- Method signature extraction
- Field type analysis
- Package structure understanding

## Configuration

### LLM Settings
```yaml
# In .env or config file
LLM_PROVIDER=gemini  # gemini|openai|anthropic|local
MAX_TOKENS_PER_CALL=2000
CHUNK_TOKENS_TARGET=1200
CHUNK_OVERLAP_TOKENS=200

# Logging configuration
AI2NODE_LOG_LEVEL=INFO  # DEBUG|INFO|WARN|ERROR
AI2NODE_LOG_FILE=Output/Reports/app.log
```

Override with environment variables:
- `AI2NODE_LLM_PROVIDER`
- `AI2NODE_LLM_MODEL`
- `AI2NODE_LLM_MAX_INPUT_TOKENS`
- `AI2NODE_LLM_MAX_OUTPUT_TOKENS`
- `AI2NODE_LLM_TEMPERATURE`

### File Filtering
```yaml
EXCLUDED_DIRS=.git,node_modules,build,target,.idea,.vscode,.mvn
ALLOWED_FILE_EXT=.java,.xml,.properties,.yml,.yaml,.gradle,.md
```

## Token Management

### Smart Chunking
- Character-based token approximation
- Batch processing for multiple files
- Configurable chunk sizes
- Overlap control for context preservation

### Usage Control
- Per-request token caps
- Input/output token tracking, which helps in cost control measures
- Usage reporting

### Optimization Tips
- Adjust token limits for cost/quality balance
- Configure exclusion patterns
- Set appropriate file size limits
- Fine-tune batch processing

## Output Structure

```
Output/
├── Converted/          # Generated Node.js code
│   ├── controllers/
│   ├── services/
│   └── daos/
├── Knowledge/          # Extracted information
│   ├── knowledge.json
│   └── files.json
└── Reports/           # Analysis results
    ├── conversion_report.html
    └── conversion_report.txt
```

## Advanced Usage

### Command Line Options
```bash
python -m ai2node.main [OPTIONS] CODEBASE_PATH
Options:
  --config PATH         Custom config file
  --llm-provider NAME   Override LLM provider
  --exclude PATTERN     Additional exclude patterns
  --out DIR            Output directory
  --max-file-size-kb N File size limit
  --categories LIST    Override detection categories
```

### Custom Configuration
- Environment variable overrides
- CLI parameter precedence
- Flexible provider settings
