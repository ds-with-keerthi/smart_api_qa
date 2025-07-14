import streamlit as st
import yaml
import json
from openapi3 import OpenAPI
import re
import requests

OPENROUTER_API_KEY = "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"  # openroter token

# Simulated LLM function to generate test scripts (replace with actual LLM API call in production)
def generate_test_script(context):
    """
    Simulates LLM generating a Pytest script based on the provided context.
    In production, this would call an LLM API with the context.
    """
    swagger_info = context["swagger"]
    rules = context["rules"]
    endpoints = swagger_info["endpoints"]

    # Initialize the script
    script = "import pytest\nimport requests\n\n"
    
    # Handle multiple endpoints
    for endpoint in endpoints:
        path = endpoint["path"]
        method = endpoint["method"]
        response_schema = endpoint["response_schema"]
        endpoint_rules = [rule for rule in rules if rule["endpoint"] == path]

        # Generate test function for each endpoint
        test_name = f"test_{method.lower()}_{path.replace('/', '_').strip('_')}"
        script += f"def {test_name}():\n"
        script += f"    response = requests.{method.lower()}('https://api.example.com{path}')\n"
        script += f"    assert response.status_code == 200, 'Expected 200 OK'\n"
        script += f"    data = response.json()\n\n"

        # Add validations based on rules
        for rule in endpoint_rules:
            if "parentId" in rule["rule"]:
                script += f"    # Validate {rule['rule']}\n"
                script += f"    assert 'parentId' in data and data['parentId'] is not None, 'parentId is missing or null'\n"
                script += f"    assert isinstance(data['parentId'], int) and data['parentId'] > 0, 'parentId must be a positive integer'\n"
            if "field order" in rule["rule"]:
                script += f"    # Validate field order\n"
                script += f"    keys = list(data.keys())\n"
                script += f"    assert keys.index('parentId') < keys.index('childId'), 'parentId must appear before childId'\n"
            if "name" in rule["rule"]:
                script += f"    # Validate name\n"
                script += f"    assert 'name' in data and isinstance(data['name'], str) and len(data['name']) > 0, 'name must be a non-empty string'\n"
        
        # Handle dependencies (e.g., use output from one call in another)
        if endpoint.get("depends_on"):
            dep_path = endpoint["depends_on"]["path"]
            dep_field = endpoint["depends_on"]["field"]
            script += f"\n    # Use {dep_field} from previous call\n"
            script += f"    response_dep = requests.get('https://api.example.com{dep_path}'.format({dep_field}=data['{dep_field}']))\n"
            script += f"    assert response_dep.status_code == 200, 'Dependent call failed'\n"
            script += f"    dep_data = response_dep.json()\n"
            script += f"    assert dep_data['id'] == data['{dep_field}'], 'Dependent data does not match'\n"
        
        script += "\n"
    
    return script

# Function to parse Swagger spec
def parse_swagger(file_content, file_type):
    try:
        if file_type == "yaml":
            spec_dict = yaml.safe_load(file_content)
        else:  # json
            spec_dict = json.loads(file_content)
        
        spec = OpenAPI(spec_dict)
        endpoints = []
        for path, path_item in spec.paths.items():
            for method in ["get", "post", "put", "delete"]:
                operation = getattr(path_item, method, None)
                if operation:
                    response_schema = None
                    if "200" in operation.responses:
                        content = operation.responses["200"].content
                        if content and "application/json" in content:
                            response_schema = content["application/json"].schema
                    endpoints.append({
                        "path": path,
                        "method": method.upper(),
                        "response_schema": response_schema
                    })
        return endpoints
    except Exception as e:
        st.error(f"Error parsing Swagger spec: {str(e)}")
        return []

# Function to parse validation rules
def parse_validation_rules(rules_text):
    rules = []
    lines = rules_text.strip().split("\n")
    current_endpoint = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("Endpoint:"):
            current_endpoint = line.replace("Endpoint:", "").strip()
        elif line.startswith("-"):
            rule = line.lstrip("- ").strip()
            rules.append({"endpoint": current_endpoint, "rule": rule})
    
    return rules

# Function to create context for LLM
def create_context(swagger_endpoints, rules):
    return {
        "swagger": {"endpoints": swagger_endpoints},
        "rules": rules,
        "task": "Generate a Pytest script to validate the API responses."
    }

# Function to create the llm context prompt
def context_to_prompt(context):
    prompt_lines = []
    
    prompt_lines.append("Generate Pytest test cases for the following API endpoints based on the given validation rules:\n")
    
    for ep in context["swagger"]["endpoints"]:
        prompt_lines.append(f"Endpoint: {ep['method']} {ep['path']}")
        
        # Handle parameters
        if ep.get("parameters"):
            prompt_lines.append("Parameters:")
            for p in ep["parameters"]:
                schema_obj = p.get("schema")
                if schema_obj:
                    schema_type = getattr(schema_obj, "type", "unknown")
                else:
                    schema_type = "unknown"
                prompt_lines.append(f"- {p['name']} ({p['in']}): {schema_type}")
        
        # Handle request body
        if ep.get("request_body"):
            prompt_lines.append("Request Body Fields:")
            req_props = getattr(ep["request_body"], "properties", {}) or {}
            for field, details in req_props.items():
                field_type = getattr(details, "type", "unknown")
                prompt_lines.append(f"- {field}: {field_type}")
        
        # Handle response schema
        if ep.get("response_schema"):
            prompt_lines.append("Response Fields:")
            res_props = getattr(ep["response_schema"], "properties", {}) or {}
            for field, details in res_props.items():
                field_type = getattr(details, "type", "unknown")
                prompt_lines.append(f"- {field}: {field_type}")
        
        # Dependency info if any
        if ep.get("depends_on"):
            dep = ep["depends_on"]
            prompt_lines.append(f"This endpoint depends on {dep['path']} field {dep['field']}")
        
        prompt_lines.append("")  # Empty line for separation

    # Add validation rules
    prompt_lines.append("\nValidation Rules:")
    for rule in context["rules"]:
        prompt_lines.append(f"- [{rule['endpoint']}] {rule['rule']}")
    
    return "\n".join(prompt_lines)


    # Add validation rules
    prompt_lines.append("\nValidation Rules:")
    for rule in context["rules"]:
        prompt_lines.append(f"- [{rule['endpoint']}] {rule['rule']}")

    return "\n".join(prompt_lines)


# Actual LLM API call via openrouter to Deepseek-coder
def call_openrouter_llm(prompt, model="deepseek/deepseek-chat-v3-0324:free"):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 1024
    }
    resp = requests.post(url, headers=headers, json=body)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"]
    else:
        raise Exception(f"LLM call failed: {resp.status_code}\n{resp.text}")

# Streamlit UI
st.title("API Test Script Generator")
st.write("Upload a Swagger spec and validation rules to generate API test scripts.")

# File upload for Swagger spec
swagger_file = st.file_uploader("Upload Swagger Spec (YAML/JSON)", type=["yaml", "json"])
file_type = "yaml" if swagger_file and swagger_file.name.endswith(".yaml") else "json"

# Validation rules input
rules_input = st.radio("Provide Validation Rules", ["Enter Manually", "Upload File"])
rules_text = ""

if rules_input == "Enter Manually":
    rules_text = st.text_area(
        "Enter Validation Rules",
        placeholder="Example:\nEndpoint: /users/{id}\n- parentId must be a positive integer and not null\n- parentId must appear before childId\n- name must be a non-empty string\nEndpoint: /users\n- name must be a non-empty string"
    )
else:
    rules_file = st.file_uploader("Upload Validation Rules (Text)", type=["txt"])
    if rules_file:
        rules_text = rules_file.getvalue().decode("utf-8")
        st.write("✅ Rules file loaded:")
        st.text(rules_text[:1000])  # preview the first 1000 chars
    else:
        rules_text = ""

# Test framework selection
test_framework = st.selectbox("Select Test Framework", ["Pytest"])  # Add more frameworks as needed

# Generate button
if st.button("Generate Test Scripts"):
    if swagger_file and rules_text.strip():
        # Read Swagger file
        swagger_content = swagger_file.read().decode("utf-8")
        swagger_endpoints = parse_swagger(swagger_content, file_type)
        
        if swagger_endpoints:
            # Parse validation rules
            rules = parse_validation_rules(rules_text)
            
            # Handle multi-call scenario: infer dependencies from rules
            for rule in rules:
                if "depends on" in rule["rule"].lower():
                    match = re.search(r"depends on (\S+) (\S+)", rule["rule"], re.IGNORECASE)
                    if match:
                        dep_path, dep_field = match.groups()
                        for endpoint in swagger_endpoints:
                            if endpoint["path"] == rule["endpoint"]:
                                endpoint["depends_on"] = {"path": dep_path, "field": dep_field}
            
            # Create context for LLM
            context = create_context(swagger_endpoints, rules)
            
            # Generate test script
            try:
                #test_script = generate_test_script(context) # Generates dummy output for show in case for No-llm situations
                prompt = context_to_prompt(context)
                test_script = call_openrouter_llm(prompt)
                st.subheader("Generated Test Script")
                st.code(test_script, language="python")
                
                # Provide download option
                st.download_button(
                    label="Download Test Script",
                    data=test_script,
                    file_name="api_test.py",
                    mime="text/plain"
                )
            except Exception as e:
                st.error(f"Error generating test script: {str(e)}")
        else:
            st.error("No valid endpoints found in Swagger spec.")
    else:
        st.error("Please upload a Swagger spec and provide validation rules.")

# Instructions
st.markdown("""
### Instructions
1. Upload a Swagger spec in YAML or JSON format.
2. Provide validation rules either by entering them manually or uploading a text file.
   - Format for rules:
     ```
     Endpoint: /path
     - Rule 1
     - Rule 2
     Endpoint: /another/path
     - Rule 3
     ```
3. Select the test framework (currently supports Pytest).
4. Click "Generate Test Scripts" to create and download the test script.
""")