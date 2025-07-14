# 🤖 SMART_API_QA — LLM-based API Test Script Generator

**SMART_API_QA** is a Streamlit app that generates Pytest test scripts from a Swagger (OpenAPI) specification and human-readable validation rules. It uses an LLM (like DeepSeek or Mistral via OpenRouter) to output test code instantly — no setup, no coding required.

---

## 🚀 Features

- 📤 Upload Swagger/OpenAPI spec (YAML or JSON)
- 📝 Provide validation rules (manual or file upload)
- 🔄 Supports multi-endpoint flows and dependency chaining
- 🤖 Generates **Pytest test scripts** via LLM
- ⬇️ View & download test scripts instantly
- 🖼️ Minimal UI using Streamlit

---

## 🧠 How It Works

1. You upload a **Swagger file** and optionally a **rules text file**
2. The app extracts endpoint data & rules
3. It builds a natural language **context prompt**
4. That prompt is sent to an **LLM via OpenRouter**
5. A full **Pytest test script** is generated and shown/downloadable

---

## 💻 Running the App Locally

```bash
# Clone the repo
git clone https://github.com/your-username/smart_api_qa.git
cd smart_api_qa

# Install dependencies
pip install -r requirements.txt

# Start the app
streamlit run app.py

Built with ❤️ using Streamlit + OpenAPI + OpenRouter LLMs