import asyncio
from app.core.agent import get_agent

async def inspect():
    agent = get_agent()
    print('Agent loaded', agent)
    try:
        async for event in agent.astream_events({'messages': [('human', 'Bonjour')]}, version='v2', config={'configurable': {'thread_id': 'inspect_test'}}):
            print('EVENT', type(event), event)
            break
    except Exception as e:
        print('ERR', e)

asyncio.run(inspect())
