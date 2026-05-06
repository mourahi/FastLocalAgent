import inspect
from langgraph.prebuilt import create_react_agent
print(inspect.signature(create_react_agent))
print(create_react_agent.__doc__)
