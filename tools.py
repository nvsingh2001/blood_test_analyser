import re
import os
from typing import Dict, Optional, Any, Type
from langchain_community.document_loaders import PyPDFLoader
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import time

class ReadBloodReportInputSchema(BaseModel):
    file_path: str = Field(..., description="Path to the PDF file")

class ReadBloodReportTool(BaseTool):
    name: str = "read_blood_report_tool"
    description: str = "Reads a PDF blood test report and returns its full extracted text."
    args_schema: Type[BaseModel] = ReadBloodReportInputSchema

    def _run(self, file_path: str) -> str:
        # Convert to absolute path if not already
        file_path = os.path.abspath(file_path)
        
        # Retry logic for file access
        max_attempts = 3
        for attempt in range(max_attempts):
            if os.path.isfile(file_path):
                break
            # logger.warning(f"File not found on attempt {attempt + 1}: {file_path}")
            time.sleep(1)  # Wait before retrying
        else:
            raise FileNotFoundError(f"File not found after {max_attempts} attempts: {file_path}")
        
        if not file_path.lower().endswith('.pdf'):
            raise ValueError("File must be a PDF")
        
        try:
            loader = PyPDFLoader(file_path)
            docs = loader.load()
            full_text = "\n".join(doc.page_content for doc in docs)
            return full_text
        except Exception as e:
            raise ValueError(f"Error reading PDF file: {str(e)}")

    async def _arun(self, file_path: str) -> str:
        return self._run(file_path)

# -----------------------------
# Tool: Nutrition Analysis
# -----------------------------
class NutritionAnalysisInputSchema(BaseModel):
    blood_text: str = Field(..., description="Extracted text from a blood report")

class NutritionAnalysisTool(BaseTool):
    name: str = "nutrition_analysis"
    description: str = "Analyzes blood test metrics and provides personalized nutrition advice."
    args_schema: Type[BaseModel] = NutritionAnalysisInputSchema

    def _run(self, blood_text: str) -> str:
        reference_ranges: Dict[str, tuple] = {
            "Hemoglobin": (13.5, 17.5),  # g/dL
            "Cholesterol": (125, 200),   # mg/dL
        }

        findings = {}
        for marker, (low, high) in reference_ranges.items():
            pattern = rf"{marker}[:\s]*([\d\.]+)"
            match = re.search(pattern, blood_text, re.IGNORECASE)
            if match:
                findings[marker] = float(match.group(1))

        advice_lines = []
        for marker, value in findings.items():
            low, high = reference_ranges[marker]
            if value < low:
                advice_lines.append(
                    f"Your {marker} ({value}) is below the normal range ({low}-{high}).\n"
                    "Consider foods rich in iron and B12, such as lean red meat, spinach, and fortified cereals."
                )
            elif value > high:
                advice_lines.append(
                    f"Your {marker} ({value}) is above the normal range ({low}-{high}).\n"
                    "Limit saturated fats and processed foods; focus on fiber-rich fruits, vegetables, and whole grains."
                )
            else:
                advice_lines.append(f"Your {marker} ({value}) is within the normal range.")

        if not advice_lines:
            return "No recognizable markers found for nutrition analysis."
        return "\n\n".join(advice_lines)

    async def _arun(self, blood_text: str) -> str:
        return self._run(blood_text)

# -----------------------------
# Tool: Exercise Planning
# -----------------------------
class ExercisePlanningInputSchema(BaseModel):
    blood_text: str = Field(..., description="Extracted text from a blood report")

class ExercisePlanningTool(BaseTool):
    name: str = "exercise_planning"
    description: str = "Generates an exercise plan based on blood test findings."
    args_schema: Type[BaseModel] = ExercisePlanningInputSchema

    def _run(self, blood_text: str) -> str:
        plan = []

        chol_match = re.search(r"Cholesterol[:\s]*([\d\.]+)", blood_text, re.IGNORECASE)
        if chol_match and float(chol_match.group(1)) > 200:
            plan.append("High cholesterol detected: incorporate 30 minutes of moderate cardio (e.g., brisk walking) 5 days/week.")

        hemo_match = re.search(r"Hemoglobin[:\s]*([\d\.]+)", blood_text, re.IGNORECASE)
        if hemo_match and float(hemo_match.group(1)) < 13.5:
            plan.append("Low hemoglobin detected: start with light-intensity exercises like yoga or pilates 3 days/week, gradually increasing intensity.")

        if not plan:
            plan.append("No specific exercise adjustments needed based on provided metrics. Continue a balanced mix of cardio and strength training.")

        return "\n\n".join(plan)

    async def _arun(self, blood_text: str) -> str:
        return self._run(blood_text)

