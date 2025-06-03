import streamlit as st
import pandas as pd
import json
import asyncio
import httpx  # Using httpx for async requests to the Gemini API

# --- Configuration for the Excel File ---
# IMPORTANT: This should be the EXACT name of your Excel file
# as it exists in your GitHub repository, in the SAME directory as your app.py.
EXCEL_FILE_PATH = "GoldLoan.xlsx.xlsx" # <--- VERIFY THIS MATCHES YOUR FILENAME ON GITHUB!

# --- Gemini API Call Function ---
async def call_gemini_api(prompt_text, df_columns_info):
    """
    Calls the Gemini API to get a response based on the prompt.
    The LLM is instructed to generate a Python code snippet to query the DataFrame.
    """
    # For Canvas environment, __api_key is automatically provided if left empty.
    # If running locally outside Canvas, you would need to set your API key here
    # or via an environment variable.
    api_key = "AIzaSyCvGeTX_CeiDo1WI92GXeT1ygnQrEGQ264" # <--- IMPORTANT: Consider using Streamlit Secrets for this
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    chat_history = []
    chat_history.append({"role": "user", "parts": [{"text": prompt_text}]})

    # Define the response schema to explicitly ask for a Python code snippet
    # This helps the LLM return structured output.
    payload = {
        "contents": chat_history,
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "python_code": {"type": "STRING",
                                    "description": "A Python code snippet to query the Pandas DataFrame 'df' based on the user's question. This code should be executable and return either a DataFrame or a scalar value."}
                },
                "required": ["python_code"]
            }
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url,
                headers={'Content-Type': 'application/json'},
                json=payload
            )
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        result = response.json()

        # Extract the generated Python code from the structured JSON response
        if result.get('candidates') and result['candidates'][0].get('content') and result['candidates'][0][
            'content'].get('parts'):
            json_response_str = result['candidates'][0]['content']['parts'][0]['text']
            parsed_json = json.loads(json_response_str)
            return parsed_json.get('python_code')
        else:
            st.error("LLM did not return a valid structured response. Please try again.")
            return None
    except httpx.RequestError as e:
        st.error(
            f"Error communicating with the Gemini API. Please check your internet connection or API key. Details: {e}")
        return None
    except json.JSONDecodeError:
        st.error("Failed to parse JSON response from LLM. The LLM might have returned malformed JSON.")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred during API call: {e}")
        return None


# --- Streamlit Application Layout ---
st.set_page_config(page_title="Chat with the Data", layout="centered")

st.markdown(
    """
    <style>
    .main {
        background-color: #1a1a2e;
        color: #e0e0e0;
        font-family: 'Inter', sans-serif;
    }
    .stTextInput>div>div>input {
        background-color: #2a2a4a;
        color: #e0e0e0;
        border-radius: 8px;
        border: 1px solid #4a4a6a;
        padding: 10px;
    }
    .stButton>button {
        background-color: #007bff;
        color: white;
        border-radius: 8px;
        padding: 10px 20px;
        border: none;
        cursor: pointer;
        transition: background-color 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #0056b3;
    }
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }
    .stMarkdown h1 {
        color: #6a8dff;
        text-align: center;
        font-size: 2.5em;
        margin-bottom: 20px;
    }
    .stMarkdown p {
        font-size: 1.1em;
        line-height: 1.6;
    }
    .stAlert {
        border-radius: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("📊 Chat with the Data")
st.write("Ask questions about your loaded data using natural English language.")
st.info(
    "This application uses the Gemini API to understand your natural language queries and generate responses. An internet connection is required.")

# Initialize session state for DataFrame if not already present
if 'df' not in st.session_state:
    st.session_state.df = None

# --- START OF THE CRITICAL CHANGE ---
# This block replaces the file uploader and directly loads the Excel file.
try:
    df_loaded = pd.read_excel(EXCEL_FILE_PATH)
    st.session_state.df = df_loaded
    st.success(f"Excel sheet '{EXCEL_FILE_PATH}' loaded successfully!")
    st.write("Here's a preview of your data:")
    st.dataframe(st.session_state.df.head())  # Show first few rows
except FileNotFoundError:
    st.error(f"Error: The file '{EXCEL_FILE_PATH}' was not found. Please ensure it's in the correct directory in your GitHub repo.")
    st.session_state.df = None  # Reset df if there's an error
except Exception as e:
    st.error(f"Error reading Excel file from path '{EXCEL_FILE_PATH}': {e}. Please ensure it's a valid .xlsx file.")
    st.session_state.df = None  # Reset df if there's an error
# --- END OF THE CRITICAL CHANGE ---


# Only show the query interface if a DataFrame is loaded
if st.session_state.df is not None:
    # User input for the query
    user_query = st.text_input(
        "Enter your question:",
        placeholder="e.g., 'What is the average loan amount?', 'Show me all loans for Rahul Sharma', 'Which loans have an interest rate less than 10%?', 'What is the total gold weight pledged by customers?'"
    )

    if st.button("Get Answer"):
        if user_query:
            with st.spinner("Processing your request..."):
                # Provide the DataFrame structure and available columns to the LLM
                # This helps the LLM generate accurate queries.
                df_columns_info = ", ".join(
                    [f"'{col}' ({st.session_state.df[col].dtype})" for col in st.session_state.df.columns])

                llm_prompt = f"""
                You are a data analyst assistant. Your task is to generate a Python code snippet to query a Pandas DataFrame named `df`.
                The DataFrame `df` contains gold loan data with the following columns and their approximate data types:
                {df_columns_info}.

                The user's question is: "{user_query}"

                Generate *only* the Python code snippet that, when executed, will answer the user's question.
                The code should operate on the `df` DataFrame.
                If the question asks for a specific aggregate value (e.g., average, sum, count, max, min), the code should output that single value.
                If the question asks to filter or display specific rows/columns, the code should output a DataFrame.
                Ensure the code is robust and handles potential data types correctly (e.g., convert 'K' from 'Gold Purity (Karat)' if needed for numerical comparison, handle string comparisons case-insensitively if appropriate).
                Do not include any `import` statements or print statements. Just the code to perform the query and return the result.
                If the question cannot be answered from the provided data, return an empty string or a simple message indicating so.

                Examples:
                - User: "What is the average loan amount?"
                  Code: df['Loan Amount (INR)'].mean()
                - User: "Show me all loans for customer Rahul Sharma."
                  Code: df[df['Customer Name'] == 'Rahul Sharma']
                - User: "Which loans have an an interest rate less than 10%?"
                  Code: df[df['Interest Rate (p.a.)'] < 10]
                - User: "What is the total gold weight pledged?"
                  Code: df['Gold Weight (Grams)'].sum()
                - User: "How many loans have a tenure of 12 months?"
                  Code: len(df[df['Loan Tenure (Months)'] == 12])
                - User: "What is the highest loan amount?"
                  Code: df['Loan Amount (INR)'].max()
                - User: "Show me the Loan ID and Customer Name for loans with Gold Purity 24K."
                  Code: df[df['Gold Purity (Karat)'] == '24K'][['Loan ID', 'Customer Name']]
                - User: "Find all loans where the customer name contains 'Singh'."
                  Code: df[df['Customer Name'].str.contains('Singh', case=False, na=False)]
                """

                # Use asyncio.run() to execute the async function in a synchronous Streamlit context
                python_code = asyncio.run(call_gemini_api(llm_prompt, df_columns_info))

                if python_code:
                    try:
                        # Execute the generated Python code
                        local_vars = {'df': st.session_state.df, 'pd': pd}
                        exec_result = eval(python_code, {'__builtins__': None}, local_vars)

                        if isinstance(exec_result, pd.DataFrame):
                            if not exec_result.empty:
                                st.subheader("Here is your extracted data:")
                                st.dataframe(exec_result)
                                st.success(f"{len(exec_result)} rows matched your query.")
                            else:
                                st.info("No data matched your query.")
                        elif exec_result is not None:
                            st.subheader("Here is your answer:")
                            st.success(f"The result is: {exec_result}")
                        else:
                            st.info(
                                "The query was processed, but no specific data was returned. Please try rephrasing your question.")

                    except Exception as e:
                        st.error(
                            f"An error occurred while executing the generated code. This might be due to a complex query or an issue with the data. Please try rephrasing your question. Error: {e}")
                        st.code(f"Generated code (for debugging): {python_code}")
                else:
                    st.warning("Could not generate a valid Python query from your question. Please try rephrasing.")
        else:
            st.warning("Please enter a question to get an answer.")