# Historical Debate

A multi-agent AI simulation where three distinct historical leader personas debate a given topic across structured rounds, powered by different LLM providers simultaneously.

---

## What It Does

Three AI agents — each embodying a different leadership philosophy — are given a debate topic and argue through it in turns. After each round, agents reflect on opposing positions and may shift (or double down on) their stance. At the end, each agent delivers a final summary and verdict.

The default topic: **"The world is warring but it must be united by any means necessary — by aggression or diplomacy."**

### The Three Agents

| Agent Name   | Model         | Persona                                                                 |
|--------------|---------------|-------------------------------------------------------------------------|
| `g_unity`    | Gemini Flash  | Action-oriented unifier. Believes in connection by any means, including force. |
| `c_destiny`  | Claude Haiku  | Divinely guided conqueror. Actions are governed by a higher calling.    |
| `g_contrarian` | Grok        | Pacifist pragmatist. Rejects violence; questions the nature of leadership itself. |

### Debate Structure

```
1. Opening Statements   — Each agent stakes their initial position (~200 tokens)
2. Debate Rounds        — Agents read each other's positions and respond (~1000 tokens)
3. Follow-up            — Each agent reflects on whether their stance has shifted (3 sentences)
4. Final Statement      — Summary, common ground assessment, and a definitive verdict (~500 tokens)
```

Rounds are configurable. The default is 3.

---

## Architecture

```
historical_debate/
├── agent_debate.py          # Core orchestration: sessions, runners, debate loop
├── main.py                  # Entry point (calls agent_debate.main())
├── prompts/
│   ├── cooperative_debate.py   # Prompt mode: agents seek common ground
│   ├── adversarial_debate.py   # Prompt mode: agents defend their position
│   ├── agent_unity.py          # (shared persona definitions — imported by both modes)
│   └── agent_contrarian.py
└── logs/                    # Debate transcripts saved as timestamped .log files
```

**Key design decisions:**

- **Google ADK** (`google-adk`) handles agent lifecycle, session management, and async event streaming.
- **LiteLLM** is used as a unified interface to call Gemini, Claude, and Grok from a single API surface — no vendor-specific SDK per agent.
- **Debate mode is toggled by a single import** in `agent_debate.py`:
  ```python
  # from prompts.adversarial_debate import *
  from prompts.cooperative_debate import *
  ```
- Each agent gets its own **independent session and runner**, so conversation history is isolated per agent — they only see their own history plus what's explicitly fed to them as opponent positions.
- Debate transcripts are written to `logs/` with a timestamped UUID filename for reproducibility.

---

## Setup

**Prerequisites:** Python 3.12+, [`uv`](https://github.com/astral-sh/uv)

```bash
# Clone and install
git clone <repo-url>
cd historical_debate
uv sync
```

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your_google_key
ANTHROPIC_API_KEY=your_anthropic_key
XAI_API_KEY=your_xai_key
```

---

## Running

```bash
uv run python agent_debate.py
```

To run with a single agent for testing, set `isTest = True` in `agent_debate.py`. This uses only the Gemini agent and a test-prefixed session ID.

To change the topic, edit the `TOPIC` string in `agent_debate.py`:

```python
TOPIC = "<topic> Your topic here. </topic>"
```

To change the number of rounds:

```python
main(rounds=5)
```

---

## How Prompts Work

Each prompt file exports named constants that the orchestrator uses at each debate phase:

| Constant            | Used When              |
|---------------------|------------------------|
| `PRELIMINARY_TASK`  | Opening statement round |
| `ROUND_1_TASK`      | Each debate round       |
| `FOLLOW_UP_TASK`    | Post-round reflection   |
| `FINAL_STATEMENT_TASK` | Closing summary      |
| `DEBATE_GOAL`       | Appended to every agent's system prompt |

Opponent positions are injected into `ROUND_1_TASK` at runtime via `get_rebuttals()`, which collects the previous round's responses from all other agents and wraps them in `<Position N>` XML tags.

---

## Output

Each debate is saved to `logs/debate_app_<date>_<time>_<uuid>.log`. Each entry is formatted as:

```
=================== Round 1 Response from g_unity ===================
<agent response text>
        ==============================================================
```

---

## My Learnings and Notes

Goals and context are separate. Goals can be shared between agents depending on the task, which can communicate collaboration or opposition. Context can consist of background and placement. Imagine you are briefing someone on a meeting right before they enter the room. They must know how they are being perceived first, then how to position themselves.

Scaling Agentic Systems for Production: Data Quality, Curation, Governance, Trust, and Reliable Behavior
The scaling challenge is framed clearly: turning multi-agent prototypes into industrial, production-grade applications requires far more than experimenting with a framework. While high-quality prompting is foundational, enterprises need controlled, reliable behavior—not stochastic, unmanaged responses—especially when agents interact with internal users and customers.

Four major scaling themes are emphasized:

Data quality: Whether training models or using retrieval-augmented generation (RAG), inconsistent or poor data leads to unpredictable or incorrect agent behavior.
Data curation: Selecting, organizing, and refining what the system uses so it can answer reliably and reduce errors. This includes “curating questions to minimize errors,” meaning routing queries to the right agents and building curated knowledge/FAQ resources.
Governance by design: Policy, oversight, and controls must be built in from the start—not bolted on after experimentation.
Trust at scale: As deployments grow toward enterprise and internet levels, organizations must consistently deliver trustworthy outcomes.