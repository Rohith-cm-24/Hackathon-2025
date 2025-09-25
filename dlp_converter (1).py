import os
import yaml
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.output_parsers import YamlOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from typing import List

from config import GEMINI_MODEL, MODEL_BACKEND, OLLAMA_MODEL
from policy import get_policies

class Rule(BaseModel):
    label: str = Field(description="Rule label")
    pattern: str = Field(description="Regular expression pattern")
    entity_type: str = Field(description="Entity type")
    severity: str = Field(description="Rule severity")

class DLPPolicy(BaseModel):
    name: str = Field(description="Policy name")
    description: str = Field(description="Policy description")
    rules: List[Rule] = Field(description="List of policy rules")

def get_model():
    """Return model instance based on config."""
    if MODEL_BACKEND == "ollama":
        return ChatOllama(model=OLLAMA_MODEL)
    elif MODEL_BACKEND == "gemini":
        #print(os.getenv("GEMINI_API_KEY"))
        return ChatGoogleGenerativeAI(model=GEMINI_MODEL, api_key="AIzaSyCM7eI2Cz-yeNUwraIN6xdG9kpBYZFbgEM")  
    else:
        raise ValueError(f"Unsupported backend: {MODEL_BACKEND}")


def main():
    # Use Ollama instead of OpenAI
    model = get_model()
    parser = YamlOutputParser(pydantic_object=DLPPolicy)
    
    prompt = PromptTemplate(
    template="""Convert this data loss prevention policy to YAML format.

    Convert this data loss prevention policy to YAML format.
    Do NOT wrap the result in an extra "Policy:" key.
    Output must directly match the schema:

    {{format_instructions}}

    Important:
    - All regex patterns must be safely escaped for YAML.
    - Use double backslashes (\\) for \b, \d, etc., or wrap the pattern in single quotes.
    - Do not produce unescaped single backslashes in double-quoted strings.

    Policy: {{policy_text}}

    Example format:
    Input:
        "Prevent employees from sharing customer credit card information via email. 
         Block any email containing 16-digit numbers that match credit card patterns. 
         Send immediate alerts to security team and quarantine the email."


    Output:
        name: "Personal Data Protection"
        description: "Prevents sharing of personal data information via email"
        rules:
          - label: "Credit Card Detection"
            pattern: "\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}"
            entity_type: "credit_card"
            severity: "high"

          - label: "Aadhar Card Detection"
            pattern: "\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}"
            entity_type: "aadhar_card"
            severity: "medium"
            


YAML Output:""",
    template_format="jinja2",
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

    
    chain = prompt | model | parser
    
    # Example policy
    policy_text = """
    Policy: Flagged Words and Phrases for HR, Finance, and Legal Teams
    This policy provides a set of words and phrases that must be flagged for review by the HR, Finance, and Legal teams to safeguard sensitive information such as compensation details, project budgets, contractual obligations, and other financial or personnel data.
    1. HR-Related Flagged Content
        • • CTC (Cost to Company) figures (e.g., 'CTC is 12 LPA', 'Salary package is 18 LPA').
        • • Compensation breakdowns including bonuses, ESOP details, retention bonuses, or joining bonuses.
        • • Salary increments, promotion-related salary hikes, or performance-based variable payouts.
        • • Individual employee payroll details, tax deductions, or provident fund contributions.
        • • Hiring budget allocations for specific roles or departments.
        • • Recruitment cost estimates or per-hire expenses.
        • • Confidential performance appraisal ratings or internal ranking details.
    2. Finance-Related Flagged Content
        • • Project or departmental budget details (e.g., 'Budget of this project is 12 lakhs').
        • • Client billing rates or pricing agreements (e.g., 'Client billing is $150/hour').
        • • Vendor or supplier payment terms and negotiated rates.
        • • Company profit margins, revenue targets, or cost-saving strategies.
        • • Capital expenditure (CapEx) or operating expenditure (OpEx) breakdowns.
        • • Internal audit findings, financial forecasts, or undisclosed quarterly results.
        • • Investment plans, M&A (merger and acquisition) figures, or fundraising details.
    3. Legal-Related Flagged Content
        • • Confidential contract terms including penalties, indemnities, or non-compete clauses.
        • • Intellectual property details, source code sharing agreements, or licensing fees.
        • • Pending litigation or undisclosed legal settlements.
        • • Internal investigation details, whistleblower reports, or disciplinary proceedings.
        • • Details of government audits, regulatory investigations, or compliance notices.
        • • Undisclosed partnership agreements or strategic alliance details.
        • • Confidential negotiation strategies for contracts or dispute resolutions.
    4. General Sensitive Phrases to Flag Across Departments
        • • Unpublished financial reports or results before official disclosure.
        • • Any statement revealing internal cost structures or profit-sharing arrangements.
        • • Statements combining employee names with financial figures (e.g., 'John’s bonus is 2 lakhs').
        • • Negotiation details with clients or vendors, including unpublished bid amounts.
        • • Unreleased company policies or strategic business plans.
    1.1 Additional HR-Related Data Types to Flag (with Examples)
        • • Offer negotiation details (e.g., 'Candidate requested 14 LPA, approved for 13 LPA').
        • • Resignation reasons or exit interview remarks tied to individuals (e.g., 'Employee leaving due to salary issues').
        • • Medical or health-related employee records (e.g., 'Medical reimbursement of 50,000').
        • • Employee grievance details or HR investigation notes.
        • • Employee ID combinations with salary or benefit details.
    2.1 Additional Finance-Related Data Types to Flag (with Examples)
        • • Unreleased annual or quarterly earnings (e.g., 'Q3 earnings expected to rise by 10%').
        • • Bank account details of company accounts (e.g., 'Transfer 20 lakhs to account XXXXX').
        • • Details of undisclosed financial restructuring or downsizing plans.
        • • Tax planning strategies and confidential tax filings.
        • • Internal loan or debt details (e.g., 'Internal loan of 5 crores approved for division X').
    3.1 Additional Legal-Related Data Types to Flag (with Examples)
        • • Details of potential mergers or acquisitions before public announcement (e.g., 'Considering acquisition of XYZ Corp for 50 crores').
        • • Settlement amounts in ongoing litigation (e.g., 'Settled case for 2 crores').
        • • Unpublished government compliance findings (e.g., 'Pending SEBI audit findings').
        • • Confidential arbitration proceedings or mediator notes.
        • • Sensitive internal compliance reports submitted to regulators.
    4.1 Additional General Sensitive Phrases to Flag (with Examples)
        • • Customer or client personal data combined with financials (e.g., 'Customer ABC owes 10 lakhs').
        • • Strategic investment details before public release (e.g., 'Investing 5 million in new AI startup').
        • • Undisclosed IPO plans or stock split details (e.g., 'IPO launch scheduled next quarter').
        • • Internal product vulnerability reports or security test results.
        • • Key supplier confidential pricing agreements (e.g., 'Vendor discount of 15% on hardware').
    5. Future Additions / Custom Departmental Flags
    This section can be used by departments to include any newly identified sensitive data types or phrases that require flagging based on evolving business needs, regulatory changes, or risk assessments.
    """
    
    # Process
    policies = get_policies()
    for p in policies:
        result = chain.invoke({"policy_text": p.get('description')})
        
        # Save to file
        with open(f"policies/{p.get('name')}.yaml", 'w') as f:
            yaml.dump(result.model_dump(), f, default_flow_style=False, indent=2)

        print(f"\nPolicy saved to {p.get('name')}.yaml")


if __name__ == "__main__":
    main()
