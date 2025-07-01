import asyncio
import os
from typing import Dict, Any

from crewai import Task
from tools import ReadBloodReportTool, NutritionAnalysisTool, ExercisePlanningTool
from crewai_tools import SerperDevTool
from agents import doctor, verifier, nutritionist, exercise_specialist

# Instantiate tools
blood_tool = ReadBloodReportTool()
search_tool = SerperDevTool()
nutrition_tool = NutritionAnalysisTool()
exercise_tool = ExercisePlanningTool()

# Task 1: Blood Report Verification and Analysis
verification = Task(
    description="""
    Carefully analyze the uploaded document located at {file_path} using the ReadBloodReportTool to verify if it's a valid blood test report.
    
    Your responsibilities:
    1. Use the ReadBloodReportTool with the file path {file_path} to extract the text from the PDF.
    2. Confirm the document is actually a blood test report based on the extracted text.
    3. Extract key biomarkers and their values.
    4. Identify any values outside normal reference ranges.
    5. Provide a structured summary of findings.
    
    User query: {query}
    
    Important: Only analyze actual blood test data. Do not make assumptions or fabricate information.
    Always include appropriate medical disclaimers about consulting healthcare professionals.
    """,
    expected_output="""
    Provide a structured analysis including:
    - Document verification status (confirmed blood report: yes/no)
    - List of detected biomarkers with values and reference ranges
    - Identification of any abnormal values (high/low/critical)
    - Brief explanation of what abnormal values might indicate
    - Clear disclaimer about consulting healthcare professionals
    - Recommendation for follow-up if any critical values are found
    """,
    agent=verifier,
    tools=[blood_tool],
    async_execution=False,
)

# Task 2: Medical Analysis and Interpretation
help_patients = Task(
    description="""
    Based on the verified blood report data from {file_path}, provide a comprehensive medical analysis.
    
    Your responsibilities:
    1. Use the ReadBloodReportTool with the file path {file_path} to access the blood test data.
    2. Interpret the clinical significance of abnormal values.
    3. Look for patterns that might suggest specific conditions.
    4. Research current medical literature for context.
    5. Provide evidence-based explanations.
    
    User query: {query}
    
    Guidelines:
    - Base analysis only on verified blood test data extracted using ReadBloodReportTool.
    - Use peer-reviewed medical sources for interpretations.
    - Clearly distinguish between different levels of concern.
    - Always emphasize the need for professional medical consultation.
    """,
    expected_output="""
    Comprehensive medical analysis including:
    - Clinical interpretation of each abnormal biomarker
    - Potential medical conditions associated with the pattern of results
    - Risk stratification (low/moderate/high concern)
    - Recommended follow-up tests or consultations
    - References to reputable medical sources
    - Strong emphasis on consulting healthcare professionals for diagnosis
    """,
    agent=doctor,
    tools=[blood_tool, search_tool],
    async_execution=False,
)

# Task 3: Nutritional Recommendations
nutrition_analysis = Task(
    description="""
    Based on the blood test results from {file_path}, provide evidence-based nutritional recommendations.
    
    Your responsibilities:
    1. Use the ReadBloodReportTool with the file path {file_path} to access blood metrics.
    2. Identify nutritional deficiencies or excesses indicated by blood markers.
    3. Research nutritional interventions supported by scientific evidence.
    4. Provide practical dietary recommendations.
    5. Suggest appropriate supplements only when clinically indicated.
    
    User query: {query}
    
    Focus areas:
    - Vitamin and mineral levels (B12, D, Iron, etc.)
    - Lipid profile implications for diet
    - Blood sugar control through nutrition
    - Anti-inflammatory dietary approaches if indicated
    """,
    expected_output="""
    Evidence-based nutritional guidance including:
    - Specific nutrient deficiencies identified from blood work
    - Dietary recommendations with scientific rationale
    - Food sources for needed nutrients
    - Supplement recommendations only when appropriate with dosages
    - Meal planning suggestions if relevant
    - Timeline for re-testing to monitor improvements
    - References to nutritional research and guidelines
    """,
    agent=nutritionist,
    tools=[blood_tool, nutrition_tool, search_tool],
    async_execution=False,
)

# Task 4: Exercise and Lifestyle Recommendations
exercise_planning = Task(
    description="""
    Create safe, personalized exercise recommendations based on blood test findings from {file_path}.
    
    Your responsibilities:
    1. Use the ReadBloodReportTool with the file path {file_path} to access blood metrics.
    2. Assess cardiovascular risk factors from blood work.
    3. Consider any metabolic indicators that affect exercise capacity.
    4. Provide graduated exercise recommendations.
    5. Address any contraindications or precautions.
    
    User query: {query}
    
    Safety considerations:
    - Account for cardiovascular risk markers
    - Consider inflammatory markers
    - Adapt intensity based on metabolic health
    - Include recovery and monitoring recommendations
    """,
    expected_output="""
    Personalized exercise plan including:
    - Assessment of exercise readiness based on blood markers
    - Cardiovascular exercise recommendations with intensity guidelines
    - Strength training suggestions appropriate for health status
    - Flexibility and recovery protocols
    - Monitoring parameters (heart rate, symptoms to watch)
    - Progressive plan with milestones
    - When to seek medical clearance before starting
    - Modifications based on specific health markers
    """,
    agent=exercise_specialist,
    tools=[blood_tool, exercise_tool, search_tool],
    async_execution=False,
)