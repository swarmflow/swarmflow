from ..postgres_engine.postgres_engine import PostgresEngine
from ..config import Config
from openai import OpenAI, AsyncOpenAI
import json
from sse_starlette.sse import EventSourceResponse
import os

class AIEngine:
    '''
    An AI engine to run the AI Architect and Deploy AI Agents.
    '''
    def __init__(self):
        self.oai_api_key = Config().OPEN_AI_KEY
        self.assistant = self.create_workflow_assistant()
        self.pg_engine = PostgresEngine()

    def create_workflow_assistant(self):
        # Initialize the OpenAI client
        client = OpenAI(api_key=self.oai_api_key)
        
        # Load the function definitions and prompt
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        with open(os.path.join(current_dir, 'assets', 'functions.json'), 'r') as f:
            functions = json.load(f)
        
        with open(os.path.join(current_dir, 'assets', 'prompt.txt'), 'r') as f:
            instructions = f.read()
        
        # Check if the assistant already exists
        assistants = client.beta.assistants.list()
        existing_assistant = None
        
        for assistant in assistants.data:
            if assistant.name == "swarmflow_workflow_assistant":
                existing_assistant = assistant
                break
        
        if existing_assistant:
            print(f"Assistant already exists with ID: {existing_assistant.id}")
            return existing_assistant.id
        
        # Create new assistant if it doesn't exist
        assistant = client.beta.assistants.create(
            name="swarmflow_workflow_assistant",
            description="Assistant that builds database infrastructure for AI agent workflows",
            model="gpt-4o",
            tools=functions,
            instructions=instructions
        )
        
        print(f"Created new assistant with ID: {assistant.id}")
        return assistant.id

    
    def call_architect(self, msg):
        '''
        Architect to Configure Supabase and Generate PKL Files.
        '''
        class StreamMemory:
            def __init__(self):
                self.full_msg = ""
                self.employees = ""
                self.employees_text=""
        client = OpenAI(api_key=self.oai_api_key)
        async_client = AsyncOpenAI(api_key=self.oai_api_key)
        memory = StreamMemory()
        thread = client.beta.threads.create()
        async def handle_stream(stream, memory):
            query = ""
            id = ""
            name = ""
            async for response in stream:
                # print(response.event)
                if response.event == "thread.message.delta":
                    memory.full_msg += response.data.delta.content[0].text.value.replace('*','')
                    yield f"{response.data.delta.content[0].text.value.replace('*','')}"
                if response.event == "thread.run.step.delta":
                    if response.data.delta.step_details.type == "tool_calls":
                        for tool_call in response.data.delta.step_details.tool_calls:
                            if tool_call.type == "function":
                                if tool_call.function.arguments:
                                    query += tool_call.function.arguments
                                    print('query', query)
                                if tool_call.id:
                                    id = tool_call.id
                                    print('id', id)
                                if tool_call.function.name:
                                    name = tool_call.function.name
                                    print('name', name)
                                # stream_tools = None
                                if id and name and "}" in query:
                                    try:
                                        if name == "search_employees":
                                            print("Searching for employees...")
                                            args = json.loads(query)
                                            employees, text = search_employees(args['query'], limit=args["limit"], tenant_id= tenant_id)
                                            memory.employees_text = text
                                            memory.employees = json.loads(employees)
                                            yield f"search_response: {employees}\n\n"
                                        else:
                                            print("Unknown tool call:", name)
                                        stream_tools = async_client.beta.threads.runs.submit_tool_outputs_stream(
                                            thread_id= thread.thread_id,
                                            run_id= stream.current_run.id,
                                            tool_outputs=[
                                                {
                                                "tool_call_id": id,
                                                "output": "Search was successful, information is being shown " + memory.employees_text
                                                }
                                            ])
                                    except Exception as e:
                                        print("Error:", e)
                                        stream_tools = async_client.beta.threads.runs.submit_tool_outputs_stream(
                                            thread_id= thread.thread_id,
                                            run_id= stream.current_run.id,
                                            tool_outputs=[
                                                {
                                                "tool_call_id": id,
                                                "output": "Search was unsuccessful, information is not being shown " + str(e)
                                                }
                                            ])
                                    async with stream_tools as st:
                                        async for event in handle_stream(st,memory):
                                            yield event
        async def event_generator():

            client.beta.threads.messages.create(
                thread_id=thread.thread_id,
                role="user",
                content=msg
            )

            async with async_client.beta.threads.runs.stream(
                thread_id=thread.id,
                assistant_id=self.assistant,
                # event_handler=ChatEventHandler()
            ) as stream:
                async for event in handle_stream(stream,memory):
                    yield event
                # async for text in stream.text_deltas:
                #     yield f"data: {text}\n\n"
                # db = SessionLocal()
                index = 0
                try:
                    index = memory.full_msg.index("{")
                except ValueError:
                    index = len(memory.full_msg)
                memory.full_msg = memory.full_msg[:index]
                # client.beta.threads.messages.create(
                #     thread_id=session.thread_id,
                #     role="assistant",
                #     content=f"These are the people the search came back with for context: {memory.employees_text}"
                # )
                yield {
                    "event": "done",
                    "data": ""
                }
        return EventSourceResponse(event_generator())


