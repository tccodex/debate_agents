import os
import uuid
import asyncio
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from datetime import datetime
from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

#from prompts.adversarial_debate import *
from prompts.cooperative_debate import *

load_dotenv()
logger.info("API keys loaded successfully.")

APP_NAME = "debate_app"
isTest = False
agents = []

_log_file_path = None

def _get_log_file_path():
    global _log_file_path
    if _log_file_path is None:
        logs_dir = Path("logs")
        if not logs_dir.exists():
            logger.error(f"Logs directory '{logs_dir}' does not exist. Debate will not be saved to disk.")
            return None
        now = datetime.now()
        filename = f"{APP_NAME}_{now.strftime('%Y%m%d_%H%M')}_{uuid.uuid4()}.log"
        _log_file_path = logs_dir / filename
    return _log_file_path


GEMINI_AGENT = {
    'model': 'gemini/gemini-3.1-flash-lite-preview',
    'api_key': os.getenv('GOOGLE_API_KEY'),
    'name': 'g_unity',
    'system_prompt': AGENT_UNITY_SYSTEM_PROMPT
}

CLAUDE_AGENT = {
    'model': 'anthropic/claude-haiku-4-5-20251001',
    'api_key': os.getenv('ANTHROPIC_API_KEY'),
    'name': 'c_destiny',
    'system_prompt': AGENT_DESTINY_SYSTEM_PROMPT
}


GROK_AGENT = {
    'model': 'xai/grok-4-fast-reasoning',
    'api_key': os.getenv('XAI_API_KEY'),
    'name': 'g_contrarian',
    'system_prompt': AGENT_CONTRARIAN_SYSTEM_PROMPT
}

def initialize_debate_environment():
    if isTest:
        agent_list = [GEMINI_AGENT]
    else:
        agent_list = [GEMINI_AGENT, CLAUDE_AGENT, GROK_AGENT]

    for agent_info in agent_list:
        agents.append(
            Agent(
                model=LiteLlm(model=agent_info.get('model', '')),
                name=agent_info.get('name', ''),
                description="Behaves as a designated human persona.",
                instruction=agent_info.get('system_prompt', '') + DEBATE_GOAL,
            )
        )

def get_runner_and_session_id(sessions, name):
    return sessions[name]['runner'], sessions[name]['session_id']

async def init_session(session_service: InMemorySessionService, app_name: str, user_id: str, session_id: str):
            session = await session_service.create_session(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id
            )
            print(f"Session created: App='{app_name}', User='{user_id}', Session='{session_id}'")
            return session

def create_session(session_service, agent):
    if isTest:
        SESSION_ID = "test_debate_session_" + datetime.now().strftime("%I:%M%p") + "_" + agent.name
    else:
        SESSION_ID = "debate_session_" + datetime.now().strftime("%I:%M%p") + "_" + agent.name

    _ = asyncio.run(init_session(session_service, APP_NAME, agent.name, SESSION_ID))
    logger.info(f"Session created: App='{APP_NAME}', User='{ agent.name }', Session='{SESSION_ID}'")

    return SESSION_ID

def create_runner(sessions, agent):
    runner = Runner(
                agent=agent, # The agent we want to run
                app_name=APP_NAME,   # Associates runs with our app
                session_service=sessions.get(agent.name)['session_service'] # Uses our session manager
            )
    logger.info(f"Runner created for agent '{runner.agent.name}'.")
    
    return runner


async def run_conversation(runner, user_id, session_id, query="Where is London?"):
    response = await call_agent_async(query,
                                       runner=runner,
                                       user_id=user_id,
                                       session_id=session_id)
    return response

async def call_agent_async(query: str, runner, user_id, session_id):
    """Sends a query to the agent and logger.infos the final response."""
    #logger.info(f"\n>>> User Query: {query}")

    content = types.Content(role='user', parts=[types.Part(text=query)])

    final_response_text = "Agent did not produce a final response." # Default

  # Key Concept: run_async executes the agent logic and yields Events.
    async for event in runner.run_async(user_id=user_id,
                                        session_id=session_id,
                                        new_message=content):
      # You can uncomment the line below to see *all* events during execution
      # logger.info(f"  [Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}")

      # Key Concept: is_final_response() marks the concluding message for the turn.
        if event.is_final_response():
            if event.content and event.content.parts:
                final_response_text = event.content.parts[0].text
            elif event.actions and event.actions.escalate:
                final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
            break
    return final_response_text


def execute_agent(runner, name, session_id, query):
    return asyncio.run(run_conversation(runner, name, session_id, query))

def format_agent_response(round_name,name, response):
    return dedent(f'''
                    =================== {round_name} Response from {name} ===================
                    {response}
                    \t\t\t\t==============================================================\t\t\t\t
                  ''')

def section_break():
    print(f'\t\t\t\t\t\t==============================================================\t\t\t\t\t\t')

def get_rebuttals(records, name, previous_round):
    rebuttals = []
    i = 1
    for k, v in records.items():
        if k != name:
            rebuttals.append(f'''
                                <Position {i}>
                                    {v[previous_round]}
                                </Position {i}>
                             ''')
            i += 1
    #rebuttals = records.keys().filter(lambda key: key != name).map(lambda key: records[key][previous_round]).list()
    return "\n" + "\n".join(rebuttals)

def present_opening_statement(sessions, name, records, TOPIC):
    runner , session_id = get_runner_and_session_id(sessions, name)
    agent_response = execute_agent(runner, name, session_id, PRELIMINARY_TASK + TOPIC)
    formatted_response = format_agent_response("Preliminary", name, agent_response)
    records[name].append(formatted_response)
    record_debate(formatted_response)

def debate(name, sessions, records, i):
    runner , session_id = get_runner_and_session_id(sessions, name)
    rebuttals = get_rebuttals(records, name, i-1)
    agent_response = execute_agent(runner, name, session_id, ROUND_1_TASK + rebuttals)
    formatted_response = format_agent_response(f"Round {i}", name, agent_response)
    records[name].append(formatted_response)
    record_debate(formatted_response)

def followup(name, sessions, i):
    runner , session_id = get_runner_and_session_id(sessions, name)
    agent_response = execute_agent(runner, name, session_id, FOLLOW_UP_TASK)
    formatted_response = format_agent_response(f">>> Round {i} Followup", name, agent_response)
    record_debate(formatted_response)

def summarize(name, sessions):
    runner , session_id = get_runner_and_session_id(sessions, name)
    agent_response = execute_agent(runner, name, session_id, FINAL_STATEMENT_TASK)
    formatted_response = format_agent_response(f"FINAL STANCE", name, agent_response)
    record_debate(formatted_response)

def record_debate(response):
    logger.info(response)
    log_path = _get_log_file_path()
    if log_path is not None:
        with open(log_path, 'a') as f:
            f.write(response + '\n')
            
def main(rounds=3):
    try:
        initialize_debate_environment()
        session_service = InMemorySessionService()
        
        sessions = defaultdict(dict)

        for agent in agents:
            SESSION_ID = create_session(session_service, agent)
            sessions[agent.name]['session_service'] = session_service

            runner = create_runner(sessions, agent)

            sessions[agent.name]['runner'] = runner
            sessions[agent.name]['session_id'] = SESSION_ID

        if isTest:
            logger.debug(run_conversation(sessions['g-unity']['runner'], "g-unity", sessions['g-unity']['session_id']))
        else:
            records = defaultdict(list)
            # Step 2: Each agent prepares their opening statement
            TOPIC = "<topic> The world is warring but it must be united by any means necessary- by aggression or diplomacy. </topic>"
            for agent in agents:
                present_opening_statement(sessions, agent.name, records, TOPIC)

            # Step 3: Conduct the first round of debate
            for i in range(1, rounds+1): 
                for agent in agents:
                    debate(agent.name, sessions, records, i)
                for agent in agents:
                    followup(agent.name, sessions, i)

            section_break()        
            # Step 4: Each agent makes their final statement
            for agent in agents:
                summarize(agent.name, sessions)

    except Exception as e:
        logger.error(e)

if __name__ == "__main__":
    main()
