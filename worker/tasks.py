"""
Celery tasks — the async execution layer.
Tasks invoke the agent engine, store results, and trigger handoffs.
The supervisor task routes work to the right specialist agent.
"""

import uuid
import yaml
import httpx
from pathlib import Path
from celery import Task
from openai import OpenAI

from worker.celery_app import celery_app
from config import get_settings
from logging_config import get_logger

settings = get_settings()
log = get_logger("worker")

# Synchronous HTTP client for calling our own Control API from the worker
CONTROL_API = "http://control-api:8000"


# ─── Agent Registry ──────────────────────────────────────────────────────────

def load_agent(agent_name: str) -> dict:
    """Load agent YAML definition from the agents directory."""
    agents_dir = Path(settings.agents_dir)
    agent_file = agents_dir / f"{agent_name}.yaml"
    if not agent_file.exists():
        raise FileNotFoundError(f"Agent definition not found: {agent_file}")
    with open(agent_file) as f:
        return yaml.safe_load(f)


def build_system_prompt(agent_def: dict) -> str:
    """Render the agent's system prompt from its YAML definition."""
    return agent_def["system_prompt"]


# ─── LiteLLM Client ──────────────────────────────────────────────────────────

def get_llm_client() -> OpenAI:
    """OpenAI-compatible client pointed at LiteLLM proxy."""
    return OpenAI(
        base_url=f"{settings.litellm_base_url}/v1",
        api_key=settings.litellm_api_key,
    )


# ─── Core Agent Execution ────────────────────────────────────────────────────

@celery_app.task(bind=True, name="worker.tasks.run_agent", max_retries=2)
def run_agent(self: Task, run_id: str, agent_name: str, input_payload: dict) -> dict:
    """
    Execute a single agent run:
    1. Load agent definition + system prompt
    2. Call LiteLLM with the agent's model alias
    3. Parse JSON output
    4. POST result to /runs/{run_id}/complete
    5. If recommended_next_agent is set, create a handoff
    """
    log.info("agent_task_started", run_id=run_id, agent=agent_name)

    try:
        agent_def = load_agent(agent_name)
        system_prompt = build_system_prompt(agent_def)
        model_alias = agent_def.get("model_alias", "standard_worker")

        client = get_llm_client()

        user_message = (
            f"Input payload:\n\n```json\n{input_payload}\n```\n\n"
            "Return valid JSON only, matching the output schema in your instructions."
        )

        response = client.chat.completions.create(
            model=model_alias,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        raw_output = response.choices[0].message.content
        import json
        output = json.loads(raw_output)

        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }

        # POST completion to Control API
        with httpx.Client() as http:
            http.post(
                f"{CONTROL_API}/runs/{run_id}/complete",
                json={
                    "result_status": "success",
                    "output_payload": output,
                    "model_used": response.model,
                    "token_usage": token_usage,
                },
                timeout=30,
            )

            # Create handoff if next agent recommended
            next_agent = output.get("recommended_next_agent")
            if next_agent:
                # Look up the run's DB ID from run_id
                run_resp = http.get(f"{CONTROL_API}/runs/{run_id}", timeout=10)
                run_data = run_resp.json()
                http.post(
                    f"{CONTROL_API}/handoffs/create",
                    json={
                        "from_run_id": run_data["id"],
                        "to_agent": next_agent,
                        "payload_json": output,
                    },
                    timeout=10,
                )

        log.info("agent_task_completed", run_id=run_id, agent=agent_name, next=next_agent)
        return {"status": "success", "run_id": run_id, "next_agent": next_agent}

    except Exception as exc:
        log.error("agent_task_failed", run_id=run_id, agent=agent_name, error=str(exc))

        # Record failure in Control API
        try:
            with httpx.Client() as http:
                http.post(
                    f"{CONTROL_API}/runs/{run_id}/complete",
                    json={
                        "result_status": "failure",
                        "output_payload": {
                            "summary": f"Agent execution failed: {str(exc)}",
                            "assumptions": [],
                            "work_completed": [],
                            "deliverables": [],
                            "open_questions": ["Why did the agent fail?"],
                            "risks": [{"level": "high", "issue": str(exc), "mitigation": "Retry or escalate"}],
                            "recommended_next_agent": None,
                            "approval_needed": False,
                        },
                        "error_code": type(exc).__name__,
                        "error_message": str(exc),
                    },
                    timeout=30,
                )
        except Exception:
            pass

        raise self.retry(exc=exc, countdown=30)


# ─── Supervisor Routing ───────────────────────────────────────────────────────

@celery_app.task(bind=True, name="worker.tasks.run_supervisor_routing", max_retries=1)
def run_supervisor_routing(self: Task, project_id: str, trigger: str, context: dict) -> dict:
    """
    Supervisor routing task: open a supervisor run, get a routing decision,
    then dispatch the first specialist agent.
    """
    log.info("supervisor_routing_started", project_id=project_id, trigger=trigger)

    with httpx.Client() as http:
        # Create supervisor run
        run_resp = http.post(
            f"{CONTROL_API}/runs/create",
            json={
                "project_id": project_id,
                "agent_name": "supervisor",
                "model_alias": "reasoning_premium",
                "input_payload": {"trigger": trigger, "context": context},
            },
            timeout=30,
        )
        run = run_resp.json()
        run_id = run["run_id"]

    # Execute supervisor agent
    run_agent.apply_async(
        args=[run_id, "supervisor", {"trigger": trigger, "context": context}],
        queue="agent_runs",
    )

    return {"supervisor_run_id": run_id}


# ─── Lead Intake Workflow ─────────────────────────────────────────────────────

@celery_app.task(bind=True, name="worker.tasks.run_intake_workflow", max_retries=1)
def run_intake_workflow(self: Task, lead_id: str) -> dict:
    """
    Entry point for new lead intake.
    Triggers: lead_created -> supervisor routing -> intake agent -> sales agent
    """
    log.info("intake_workflow_started", lead_id=lead_id)

    with httpx.Client() as http:
        lead_resp = http.get(f"{CONTROL_API}/leads/{lead_id}", timeout=10)
        lead = lead_resp.json()

    result = run_supervisor_routing.apply_async(
        args=[None, "new_lead", {"lead": lead}],
        queue="default",
    )

    return {"lead_id": lead_id, "supervisor_task_id": result.id}
