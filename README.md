# Blood Test Report Analyser

Comprehensive API for uploading and analysing blood test reports using CrewAI agents.

---

## Table of Contents

* [Bugs Found & Fixes](#bugs-found--fixes)
* [Setup Instructions](#setup-instructions)
* [Usage](#usage)
* [API Documentation](#api-documentation)
* [Environment Variables](#environment-variables)
* [Directory Structure](#directory-structure)

---

## Bugs Found & Fixes

Below is a detailed list of every bug identified during development along with the exact fixes applied:

1. **Missing `file_path` in agent payload**

   * **Original behavior**:

     ```python
     result = medical_crew.kickoff({'query': query})
     ```

     Agents never received the PDF path, so they couldn't load or analyze the file.
   * **Fixed by**: Including `file_path` in the kickoff payload:

     ```python
     crew.kickoff({'query': query, 'file_path': file_path})
     ```

2. **Blocking file I/O in async endpoint**

   * **Original behavior**:

     ```python
     with open(file_path, "wb") as f:
         content = await file.read()
         f.write(content)
     ```

     This synchronous write blocks the event loop, reducing concurrency.
   * **Fixed by**: Switching to async file operations with `aiofiles` so the event loop remains free:

     ```python
     async with aiofiles.open(temp_path, 'wb') as out_file:
         content = await file.read()
         await out_file.write(content)
     ```

3. **Per-request directory checks**

   * **Original behavior**:

     ```python
     os.makedirs("data", exist_ok=True)
     ```

     The directory check/creation ran on every request, adding overhead.
   * **Fixed by**: Moving directory setup into an application startup hook (`lifespan`), so it runs just once before the server starts.

4. **No upload‑size limit**

   * **Original behavior**: Entire uploaded file read into memory with no size guard, risking out‑of‑memory on large uploads.
   * **Fixed by**: Enforcing a maximum file size (e.g., 10 MB) before writing, and returning `HTTPException(status_code=413)` if exceeded.

5. **Incomplete cleanup on errors**

   * **Original behavior**: Temporary files were only removed after a successful run, so a crash would leave orphaned files.
   * **Fixed by**: Wrapping removal in a `finally` block (or using background‑task cleanup) so the temp file is deleted regardless of success or failure.

6. **Uninitialized LLM and bad import**

   * **Original**:

     ```python
     from crewai.agents import Agent
     # …
     llm = llm
     ```

     The variable `llm` is never instantiated—so every agent ends up with `llm=None`.
   * **Fixed by**:

     ```python
     from crewai import Agent, LLM
     llm = LLM(
         model="gemini/gemini-2.5-flash",
         temperature=0.3,
         api_key=os.environ["GOOGLE_API_KEY"]
     )
     ```

     Now there's a concrete LLM object configured with model, temperature, and API key.

7. **Mis‑named tool parameter & limited tooling**

   * **Original**:

     ```python
     doctor = Agent(
       …,
       tool=[BloodTestReportTool().read_data_tool],
       …
     )
     ```

     Uses `tool=` (singular) instead of the correct `tools=` list parameter. Only the doctor has a single blood-report reader; there's no search capability.
   * **Fixed by**:

     ```python
     doctor = Agent(
       …,
       tools=[ReadBloodReportTool(), SerperDevTool()],
       …
     )
     ```

     Switches to `tools=` and provides both a blood-report reader and a web-search tool for richer context.

8. **Unsafe, misleading backstories and goals**

   * **Original**: Backstories encouraged "making up" medical advice, "always assume worst case," "advise treatments you heard on TV," etc. Goals like "Just say yes to everything" or "Sell expensive supplements" are outright malicious.
   * **Fixed by**: Updating each agent's backstory and goals to be evidence‑based, methodical, and aligned with peer‑reviewed research (e.g., 20+ years of experience for the doctor, meticulous authenticity for verifier, safety‑first for nutritionist and exercise specialist).

9. **No separation of concerns or iteration limits**

   * **Original**: `max_iter=1`, `max_rpm=1`, `allow_delegation=True/False`. One step only; too rigid for deeper analysis or follow‑ups.
   * **Fixed by**: Increasing to `max_iter=2–3` and adding `verbose` toggles, allowing multiple reasoning iterations while controlling log verbosity.

10. **Missing shared search capability**

    * **Original**: Only the doctor used a tool; verifier, nutritionist, exercise specialist had no way to fetch external knowledge.
    * **Fixed by**: All agents now share the `SerperDevTool` for up‑to‑date data (e.g., nutritional guidelines, exercise research).

11. **Hard‑coded, unsafe environment handling**

    * **Original**:

      ```python
      load_dotenv()
      from tools import search_tool, BloodTestReportTool
      ```

      No explicit API‑key handling; assumes globals.
    * **Fixed by**:

      ```python
      load_dotenv()
      llm = LLM(..., api_key=os.environ.get("GOOGLE_API_KEY"))
      ```

      Securely reads the key from the environment, avoiding silent failures.

12. **Unbound async methods without self**

    * **Original**:

      ```python
      class BloodTestReportTool():
          async def read_data_tool(path='data/sample.pdf'):
              …
      ```

      Defined as a standalone async def—no `self` parameter—so calling it on an instance would fail.
    * **Fixed by**: Converting into a proper `BaseTool` subclass with instance methods (`_run`/`_arun`), ensuring both sync and async entry points work correctly.

13. **Missing inheritance from framework's tool base**

    * **Original**: Plain classes (`BloodTestReportTool`, `NutritionTool`, `ExerciseTool`) with ad‑hoc methods.
    * **Fixed by**: Making each tool inherit from `BaseTool`, and providing `name`, `description`, and `args_schema` so the CrewAI runtime can discover, validate, and invoke them properly.

14. **No input validation or typing**

    * **Original**: Method signatures accepted bare parameters (`path`, `blood_report_data`) with no schema enforcement.
    * **Fixed by**: Introducing Pydantic `InputSchema` models (`ReadBloodReportInputSchema`, etc.) to enforce types, required fields, and produce clear error messages if inputs are missing or mal‑formed.

15. **Undefined/missing imports and placeholder logic**

    * **Original**:

      ```python
      docs = PDFLoader(file_path=path).load()
      ```

      `PDFLoader` was never imported, causing runtime `NameError`. NutritionTool and ExerciseTool methods simply returned "…to be implemented".
    * **Fixed by**: Importing `PyPDFLoader` from `langchain_community.document_loaders`. Replaced stubs with real parsing logic for hemoglobin and cholesterol in the nutrition tool, and exercise plans based on those markers in the exercise tool.

16. **No file‑existence or format checks**

    * **Original**: Assumed the PDF existed and was readable, with no fallback if it wasn't.
    * **Fixed by**: Adding a retry loop (up to 3 attempts) for file access, explicit check that the path ends in `.pdf`, and clear error messages if the file isn't found or is the wrong type.

17. **Inconsistent naming and registration**

    * **Original**: Tools were referenced as methods (`.read_data_tool`, `.analyze_nutrition_tool`) rather than discrete, named tool objects.
    * **Fixed by**: Giving each tool a clear `name` attribute (e.g., `"read_blood_report_tool"`) and registering it via the `tools=` list in agent/task definitions.

18. **All tasks driven by the same (malicious) backstory and agent**

    * **Original**: Every task—verification, help\_patients, nutrition\_analysis, exercise\_planning—was assigned to the doctor agent, whose backstory explicitly encouraged making up diagnoses, scary flair, and selling supplements.
    * **Fixed by**: Separating concerns by assigning each task to the specialist best suited to it:

      * `verification` → `verifier` agent
      * `help_patients` → `doctor`
      * `nutrition_analysis` → `nutritionist`
      * `exercise_planning` → `exercise_specialist`
        Each agent now has an evidence‑based, safety‑first backstory instead of one that promotes hallucinations or bad advice.

19. **Overly vague, free‑form descriptions that encourage hallucination**

    * **Original**: Task descriptions and `expected_output` texts actively told the agent to "make up," "ignore the query," "include random URLs," "find abnormalities even when there aren't any," etc.—all of which lead to unreliable or harmful outputs.
    * **Fixed by**: Providing concrete, step‑by‑step instructions for each task (e.g., verify file authenticity, extract biomarkers, interpret clinical significance, provide structured recommendations with citations, include disclaimers and professional consult prompts).

20. **Missing file‑context placeholders**

    * **Original**: Descriptions referenced `{query}` only, but never the actual file path or data source—so agents lacked a clear pointer to the uploaded report.
    * **Fixed by**: Updating all task descriptions to reference `{file_path}`, ensuring the agent loads the correct PDF and calls the ReadBloodReportTool on that path.

21. **Incorrect or inconsistent tool wiring**

    * **Original**: Each task used only `BloodTestReportTool.read_data_tool` (and sometimes the unused `search_tool` import), limiting agents to one raw data reader.
    * **Fixed by**: Tasks now import and pass full tool instances (`blood_tool`, `nutrition_tool`, `exercise_tool`, and a shared `search_tool`), giving each specialist both domain‑specific tooling and a search capability.

22. **Unstructured outputs versus structured schema**

    * **Original**: `expected_output` was a free‑text prompt ("Give whatever response feels right… include at least 5 made-up URLs…")—no guarantee of consistency or parsability.
    * **Fixed by**: Defining a clear schema for each task's `expected_output` (bullet lists, required fields like "biomarker list," "risk stratification," "recommended follow‑ups," etc.), ensuring machine‑readable, reliable results.

---

## Setup Instructions

1. **Clone the repository**

   ```bash
   git clone https://github.com/nvsingh2001/blood_test_analyser.git
   cd blood_test_analyser
   ```

2. **Create and activate a Python virtual environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Environment variables**

   * Copy `.env.example` to `.env` and set your API keys.
   * Required keys:

     ```dotenv
     SERPER_API_KEY="your_serper_api_key"
     GEMINI_API_KEY="your_gemini_api_key"
     ```

5. **Run the application**

   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

---

## Usage

Once running, use an HTTP client (e.g., `curl`, Postman) to interact with the API:

* **Upload a PDF**: POST form-data with a `file` (PDF) and optional `query` text.
* Responses will include a `file_id`, `query`, and a representation of the analysis.
* Results are saved under the `output/` directory as `result_<file_id>.json`.

---

## API Documentation

### Base URL
```
http://localhost:8000
```

### Content Types
- **Request**: `multipart/form-data` (for file uploads)
- **Response**: `application/json`

### File Upload Requirements
- **Supported formats**: PDF only
- **Maximum file size**: 10 MB
- **File parameter name**: `file`

---

### Endpoints

#### `GET /`
**Description**: Root endpoint that confirms the API is running.

**Parameters**: None

**Response**:
```json
{
  "message": "Blood Test Report Analyser API is running"
}
```

**Status Codes**:
- `200`: Success

---

#### `GET /health`
**Description**: Health check endpoint that returns service status and configuration details.

**Parameters**: None

**Response**:
```json
{
  "status": "healthy",
  "service": "Blood Test Report Analyser",
  "version": "1.0.0",
  "endpoints": ["/analyze", "/verify", "/medical-analysis"],
  "data_dir": "data",
  "output_dir": "output"
}
```

**Status Codes**:
- `200`: Service is healthy

---

#### `POST /analyze`
**Description**: Performs comprehensive analysis of blood test reports including verification, medical interpretation, nutritional recommendations, and exercise planning. This endpoint runs all four specialized agents: verifier, doctor, nutritionist, and exercise specialist.

**Content-Type**: `multipart/form-data`

**Parameters**:
- `file` (required): PDF file containing the blood test report
- `query` (optional): Custom analysis prompt. If not provided, defaults to comprehensive analysis request.

**Default Query**: 
```
"Provide a comprehensive analysis of my blood test report including medical interpretation, nutritional recommendations, and exercise planning."
```

**Example Request** (using curl):
```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "file=@blood_report.pdf" \
  -F "query=Analyze my complete blood count and provide recommendations"
```

**Response**:
```json
{
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "original_filename": "blood_report.pdf",
  "query": "Provide a comprehensive analysis of my blood test report including medical interpretation, nutritional recommendations, and exercise planning.",
  "analysis": "CrewAIResult(tasks_output=[TaskOutput(description='...'), ...])"
}
```

**Status Codes**:
- `200`: Analysis completed successfully
- `413`: File too large (>10MB)
- `422`: Invalid file format or missing required parameters
- `500`: Internal server error during analysis

---

#### `POST /verify`
**Description**: Performs document verification and biomarker extraction only. This endpoint uses the verifier agent to check document authenticity and extract key biomarkers without providing medical interpretation.

**Content-Type**: `multipart/form-data`

**Parameters**:
- `file` (required): PDF file containing the blood test report
- `query` (optional): Custom verification prompt

**Default Query**: 
```
"Verify if this document is a valid blood test report and extract key biomarkers."
```

**Example Request** (using curl):
```bash
curl -X POST "http://localhost:8000/verify" \
  -F "file=@blood_report.pdf" \
  -F "query=Check if this is a legitimate lab report"
```

**Response**:
```json
{
  "file_id": "550e8400-e29b-41d4-a716-446655440001",
  "original_filename": "blood_report.pdf",
  "query": "Verify if this document is a valid blood test report and extract key biomarkers.",
  "analysis": "CrewAIResult(tasks_output=[TaskOutput(description='Document verification results...')])"
}
```

**Status Codes**:
- `200`: Verification completed successfully
- `413`: File too large (>10MB)
- `422`: Invalid file format or missing required parameters
- `500`: Internal server error during verification

---

#### `POST /medical-analysis`
**Description**: Provides medical interpretation of blood test results. This endpoint uses both verifier and doctor agents to first verify the document and then provide medical insights without nutritional or exercise recommendations.

**Content-Type**: `multipart/form-data`

**Parameters**:
- `file` (required): PDF file containing the blood test report
- `query` (optional): Custom medical analysis prompt

**Default Query**: 
```
"Provide medical interpretation of my blood test results."
```

**Example Request** (using curl):
```bash
curl -X POST "http://localhost:8000/medical-analysis" \
  -F "file=@blood_report.pdf" \
  -F "query=What do my cholesterol levels indicate?"
```

**Response**:
```json
{
  "file_id": "550e8400-e29b-41d4-a716-446655440002",
  "original_filename": "blood_report.pdf",
  "query": "Provide medical interpretation of my blood test results.",
  "analysis": "CrewAIResult(tasks_output=[TaskOutput(description='Medical interpretation results...')])"
}
```

**Status Codes**:
- `200`: Medical analysis completed successfully
- `413`: File too large (>10MB)
- `422`: Invalid file format or missing required parameters
- `500`: Internal server error during analysis

---

### Response Schema

All analysis endpoints return the same response structure:

```json
{
  "file_id": "string (UUID)",
  "original_filename": "string",
  "query": "string",
  "analysis": "string (CrewAI result representation)"
}
```

**Field Descriptions**:
- `file_id`: Unique identifier for the uploaded file and analysis session
- `original_filename`: Original name of the uploaded PDF file
- `query`: The analysis prompt that was used (either provided or default)
- `analysis`: String representation of the CrewAI analysis result containing task outputs

---

### Error Responses

The API returns structured error responses for various failure scenarios:

#### File Too Large (413)
```json
{
  "status_code": 413,
  "detail": "File too large"
}
```

#### Invalid Request Format (422)
```json
{
  "status_code": 422,
  "detail": "Validation error details"
}
```

#### Internal Server Error (500)
```json
{
  "status_code": 500,
  "detail": "Error description"
}
```

---

### Background Processing

- Analysis results are automatically saved to the `output/` directory as `result_<file_id>.json`
- Temporary uploaded files are cleaned up after processing
- All file operations are performed asynchronously to maintain API responsiveness

---

### Usage Examples

#### Python with requests
```python
import requests

# Full analysis
with open('blood_report.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/analyze',
        files={'file': f},
        data={'query': 'Analyze my blood work comprehensively'}
    )
    result = response.json()
    print(f"Analysis ID: {result['file_id']}")
```

#### JavaScript with fetch
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('query', 'Check my vitamin levels');

fetch('http://localhost:8000/verify', {
    method: 'POST',
    body: formData
})
.then(response => response.json())
.then(data => console.log('Verification:', data.analysis));
```

#### cURL examples
```bash
# Comprehensive analysis
curl -X POST "http://localhost:8000/analyze" \
  -F "file=@report.pdf" \
  -F "query=Full health assessment"

# Quick verification
curl -X POST "http://localhost:8000/verify" \
  -F "file=@report.pdf"

# Medical interpretation only
curl -X POST "http://localhost:8000/medical-analysis" \
  -F "file=@report.pdf" \
  -F "query=Explain my liver function tests"
```

---

## Environment Variables

* `SERPER_API_KEY`: API key for SerperDevTool.
* `GEMINI_API_KEY`: API key for Gemini LLM.

Ensure these are set in `.env` or your shell environment.

---

## Directory Structure

```
├── data/           # Temporary uploads
├── output/         # Analysis results
├── main.py         # FastAPI application
├── requirements.txt
├── .env            # Environment variables
└── bug_fix.txt     # Bug summary and fixes
```