import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from IPython.display import display, Markdown
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
#from langgraph.prebuilt.agents.react.agent import ReactAgent
from langchain.agents import create_agent

from langchain_mcp_adapters.client import MultiServerMCPClient
#from langchain_azure_ai.chat_models import AzureAIChatCompletionsModel
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("OPEN_API_KEY")

 #model = ChatGroq(model="llama-3.3-70b-versatile",temperature=0.5)
#model = ChatOllama(model="llama3.2:1b",temperature=0.0,max_new_tokens=500)
# This line of code is initializing a ChatOpenAI model with specific parameters. Here's a breakdown of
# each parameter:
model = ChatOpenAI(model="gpt-4",api_key=api_key,temperature=0.0,max_retries=3)
server_params = StdioServerParameters(
    command="python",
    # Make sure to update to the full absolute path to your math_server.py file
    args=["math_server.py"],
)
async def run_app(user_question):
    
    client = MultiServerMCPClient({
    "math": {
        "command": "python",
        # Make sure to update to the full absolute path to your math_server.py file
        "args": ["math_server.py"],
        "transport": "stdio",
    }
})

    async with client.session("math") as session:
        tools = await load_mcp_tools(session)
        # Load tools from the MCP client
        agent = create_agent(model, tools)
        agent_response = await agent.ainvoke({"messages": user_question})
        print(agent_response['messages'][-1].content)
        
        return agent_response['messages'][-1].content
if __name__ == "__main__":
    #user_question = "what is the weather in california?"
    user_question = "what's (3 + 5) x 12?"
    #user_question = "what's the weather in seattle?"
    #user_question = "what's the weather in NYC?"
    response = asyncio.run(run_app(user_question=user_question))
    print(response)
        
        
        
        
        



# # Stream the response chunks
        # async for chunk in agent.astream({"messages": user_question}):
        #     # Extract the message content from the AddableUpdatesDict structure
        #     if 'agent' in chunk and 'messages' in chunk['agent']:
        #         for message in chunk['agent']['messages']:
        #             if isinstance(message, AIMessage):
        #                 # Handle different content formats
        #                 if isinstance(message.content, list):
        #                     # For structured content with text and tool use
        #                     for item in message.content:
        #                         if isinstance(item, dict) and 'text' in item:
        #                             print(f"**AI**: {item['text']}")
        #                 else:
        #                     # For simple text content
        #                     print(f"**AI**: {message.content}")
                            
        #     elif 'tools' in chunk and 'messages' in chunk['tools']:
        #         for message in chunk['tools']['messages']:
        #             if hasattr(message, 'name') and hasattr(message, 'content'):
        #                 # Display tool response
        #                 print(f"**Tool ({message.name})**: {message.content}")     
