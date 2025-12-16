from langgraph.graph import StateGraph, START, END
from process import (
    State, 
    input_handler, 
    extraction_handler, 
    comparison_handler, 
    generation_handler
)
from voice_input import voice_input_handler
import os 

workflow = StateGraph(State)

workflow.add_node("voice_input", voice_input_handler)
workflow.add_node("input_node", input_handler)
workflow.add_node("extraction_node", extraction_handler)
workflow.add_node("comparison_node", comparison_handler)
workflow.add_node("generation_node", generation_handler)



workflow.add_edge(START, "voice_input")

def route_after_voice(state):
    return "end" if state.get("error_message") else "input_node"

workflow.add_conditional_edges(
    "voice_input",
    route_after_voice,
    {
        "input_node": "input_node",
        "end": END
    }
)
workflow.add_edge("input_node", "extraction_node")
workflow.add_edge("extraction_node", "comparison_node")
workflow.add_edge("comparison_node", "generation_node")
workflow.add_edge("generation_node", END)

app = workflow.compile()

if __name__ == "__main__":
    print("=== Resume vs Job Description Analyzer ===\n")

    # 1. Ask for Job Description
    print("Please paste the Job Description (press Enter twice when done):\n")
    jd_lines = []
    while True:
        line = input()
        if line == "" and len(jd_lines) > 0 and jd_lines[-1] == "":
            break
        jd_lines.append(line)
    jd_text = "\n".join(jd_lines).strip()

    if not jd_text:
        print("Error: Job Description cannot be empty.")
        exit(1)

    # 2. Ask for Resume file path
    while True:
        resume_path = input("\nEnter the full path to your resume file (PDF or DOCX): ").strip().strip('"\'')
        if os.path.exists(resume_path):
            break
        else:
            print("File not found. Please enter a valid path.")

    # 3. Initialize state
    initial_state = {
        "jd_text": jd_text,
        "resume_file_path": resume_path,
        "resume_text": "",
        "user_voice_transcript": "",
        "jd_terms": [],
        "resume_terms": [],
        "missing_terms": [],
        "generated_points": [],
        "error_message": None,
    }

    print("\n" + "="*60)
    print("Starting analysis...")
    print("When ready, speak your additional instructions (e.g., 'Focus on cloud skills', 'Ignore Redis')")
    print("Press Ctrl+C when you finish speaking.")
    print("="*60 + "\n")

    # Run the full pipeline
    result = app.invoke(initial_state)

    # Display results
    print("\n" + "="*80)
    if result.get("error_message"):
        print("ERROR:", result["error_message"])
    else:
        voice_inst = result.get("user_voice_transcript", "").strip()
        if voice_inst:
            print("YOUR VOICE INSTRUCTIONS:")
            print(voice_inst)
        else:
            print("NO VOICE INSTRUCTIONS PROVIDED")

        print("\nMISSING SKILLS/TERMS FROM RESUME:")
        missing = result.get("missing_terms", [])
        if missing:
            for term in missing:
                print(f"  • {term}")
        else:
            print("  All required skills are present!")

        print("\nSUGGESTED RESUME POINTS TO ADD:")
        points = result.get("generated_points", [])
        if points and points != ["All required skills are present in the resume!"]:
            for point in points:
                print(point)
        else:
            print("  Great! Your resume already covers all key requirements.")
    print("="*80)
