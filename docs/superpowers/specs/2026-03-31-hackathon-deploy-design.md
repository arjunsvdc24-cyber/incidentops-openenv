# IncidentOps OpenEnv Hackathon Submission Spec

## Purpose
Adapt the `incidentops` RL environment to meet the specific automated validation and evaluation requirements of the OpenEnv hackathon. This involves integrating specific environment variables and exposing a dedicated inference script at the root level.

## Requirements Addressed
1. **Inference Script (`inference.py`)**: Must exist in the root directory and evaluate the agent.
2. **Environment Variables**: Use `API_BASE_URL`, `MODEL_NAME`, and `HF_TOKEN`.
3. **OpenAI Client Usage**: The baseline agent must use the OpenAI client configured with the above variables.
4. **Endpoints Validation**: The `/baseline` endpoint must function using the new environment variables rather than falling back to rule-based evaluation when `OPENAI_API_KEY` is missing.

## Architecture & Changes

### 1. `app/llm_baseline.py`
- Modify the `LLMBaselineAgent` initialization to read the new environment variables:
  ```python
  api_key = os.environ.get("HF_TOKEN")
  base_url = os.environ.get("API_BASE_URL")
  model = os.environ.get("MODEL_NAME", self.config.model)
  ```
- Instantiate the OpenAI client as:
  ```python
  self.client = OpenAI(api_key=api_key, base_url=base_url)
  ```
- Pass `model` from the environment dynamically into the `client.chat.completions.create` call.
- Update `check_openai_available()` to verify the presence of `HF_TOKEN`, `API_BASE_URL`, and `MODEL_NAME`.

### 2. `inference.py` (Root Script)
- Create a new script in the root directory.
- This script will act as the CLI entrypoint for the automated evaluator.
- It will verify that the required environment variables are set.
- It will import `run_llm_evaluation` from `app.llm_baseline` and execute it.
- It will print the final evaluation scores (Easy, Medium, Hard, and Total) to standard output.

### 3. `app/main.py`
- Update the `/baseline` endpoint to handle the new environment variable requirements.
- Instead of checking for `openai_api_key` in the request, it should check for `HF_TOKEN`, `API_BASE_URL`, and `MODEL_NAME`.
- Ensure it properly falls back to rule-based baseline ONLY if these variables are absent.

## Error Handling
- If `HF_TOKEN` or `API_BASE_URL` is missing during `inference.py` execution, the script will exit with a non-zero status code and print an informative error message.
- If the LLM call fails during evaluation, `LLMBaselineAgent` gracefully falls back to the rule-based approach, ensuring completion without crashing.

## Testing
- The Docker build process must be able to run `inference.py` or the `/baseline` endpoint seamlessly given the right environment variables.
- We will manually trigger a test run locally to ensure `inference.py` executes without errors and produces a 0.0-1.0 score range for all tasks.