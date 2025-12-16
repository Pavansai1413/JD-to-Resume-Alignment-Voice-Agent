from typing import TypedDict, Annotated, List, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langchain_community.document_loaders import UnstructuredWordDocumentLoader, UnstructuredPDFLoader
from voice_input import voice_input_handler
import os 
from dotenv import load_dotenv
load_dotenv()

class State(TypedDict):
    jd_text : str
    resume_file_path : str
    resume_text : str
    user_voice_transcript : str
    jd_terms : Annotated[List[str], "Terms extracted from Job Description"]
    resume_terms : Annotated[List[str], "Terms extracted from Resume"]
    missing_terms : Annotated[List[str], "Missing Key Terms from Resume"]
    generated_points : Annotated[List[str], "Generated Points on missing terms from Resume"]


# Model initialization
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)



# Input Handling Node
def input_handler(state: State) -> Dict[str, Any]:
    jd_text = state.get("jd_text", "").strip()
    resume_file_path = state.get("resume_file_path", "").strip()

    if not jd_text:
        raise ValueError("Job Description text is missing.")
    
    if not resume_file_path:
        raise ValueError("Resume file path is missing.")

    file_extension = os.path.splitext(resume_file_path)[1].lower()
    
    try:
        if file_extension == ".pdf":
            loader = UnstructuredPDFLoader(resume_file_path)
        elif file_extension in [".docx", ".doc"]:
            loader = UnstructuredWordDocumentLoader(resume_file_path)
        else:
            raise ValueError("Unsupported file format. Please provide a PDF or Word document.")
        
        documents = loader.load()
        resume_text = "\n\n".join([doc.page_content for doc in documents])
    except Exception as e:
        raise ValueError(f"Error loading resume file: {e}")
    return {
        "jd_text": jd_text,
        "resume_text": resume_text,
    }



# Term Extraction Node
def extraction_handler(state: State) -> Dict[str, Any]:
    # Prompt for term extraction
    extraction_prompt = ChatPromptTemplate.from_template(
        """ You are an expert at extracting the key programming languages, technical terms, skills, technologies, frameworks, libraries related to role from the following text.
        Extract only the technical terms. do not extract soft skills or non-technical terms.
        User instructions: "{user_voice_transcript}"
        Text: {text}
        Output a comma separated list of unique terms (no duplicates).
        """
    )

    # Extracting terms from job description
    jd_chain = extraction_prompt | llm
    jd_response = jd_chain.invoke({"text": state["jd_text"], "user_voice_transcript": state.get("user_voice_transcript", "")})

    # Extracting terms from resume
    resume_chain = extraction_prompt | llm
    resume_response = resume_chain.invoke({"text": state["resume_text"], "user_voice_transcript": state.get("user_voice_transcript", "")})

    voice = state.get("user_voice_transcript", "")

    jd_terms = [term.strip() for term in jd_response.content.split(",") if term.strip()]
    resume_terms = [term.strip() for term in resume_response.content.split(",") if term.strip()]
    
    return {
        "jd_terms": jd_terms,
        "resume_terms": resume_terms,
    }



# Comparison Node
def comparison_handler(state: State) -> Dict[str, Any]:
    comparison_prompt = ChatPromptTemplate.from_template(
        """ You are an expert at comparing. 
        Compare the following lists:
        JD Terms: {jd_terms}
        Resume Terms: {resume_terms}
        User Instructions: "{user_voice_transcript}"

        identify the terms that are present in the JD terms but NOT in resume terms (case insensitive match).
        Output comma separated list of missing terms.
        if no terms are missing, output 'None'.
        """
    )
    comparison_chain = comparison_prompt | llm
    response = comparison_chain.invoke({
        "jd_terms": state["jd_terms"],
        "resume_terms": state["resume_terms"],
        "user_voice_transcript": state.get("user_voice_transcript", "")
    })

    raw = response.content.strip()
    if raw.lower() == "none":
        missing_terms = []
    else:
        missing_terms = [t.strip() for t in raw.split(",") if t.strip() and t.strip().lower() != "none"]
    return {
        "missing_terms": missing_terms
    }


# Point Generation Node
def generation_handler(state: State) -> Dict[str, Any]:
    missing = state.get("missing_terms", [])
    if not missing:
        return {
            "generated_points": ["All terms match!"]
        }
    
    generation_prompt = ChatPromptTemplate.from_template(
        """ You are an expert resume writer specializing in creating high-impact, ATS-friendly technical resume bullet points.
        For each missing technical term provided, generate exactly 2 concise, actionable resume bullet points.

        Requirements:
        Tailor each bullet point to the company related usecase, data and related work and project context taken from the user’s resume.
        Do not hardcode company name in the bullet points.
        Ensure the bullets are technically accurate, results-oriented, and aligned with existing resume content.
        Use strong action verbs, relevant tools/technologies, and measurable impact where applicable.
        The generated points should seamlessly integrate with the rest of the resume to demonstrate the missing skill effectively.
        If missing terms are only domain names and role names, generate some basic skills related points for those terms.
        If user has given any voice instructions, take those into account while generating the points.
        
        User Instructions: "{user_voice_transcript}"
        missing terms: {missing_terms}
        resume text: {resume_text}
        

        Output Rules:
        Follow only the output format provided below.
        Do not include explanations, headings, or extra text.
        Do not repeat existing resume points.
        
        
        Output format (strictly follow this):

        **missing term Name**
        - Bullet point 1 about this term
        - Bullet point 2 about this term

        **Next missing term**
        - Bullet point 1...
        - Bullet point 2...
        """
    )
    generation_chain = generation_prompt | llm
    response = generation_chain.invoke({
        "missing_terms": state["missing_terms"],
        "resume_text": state["resume_text"],
        "user_voice_transcript": state.get("user_voice_transcript", "")
    })

    formatted_lines = [line.rstrip() for line in response.content.splitlines() if line.strip()]
    return {"generated_points": formatted_lines}