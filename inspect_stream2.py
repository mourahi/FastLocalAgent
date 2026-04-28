import asyncio
from app.core.agent import get_agent

async def inspect():
    agent = get_agent()
    print('Agent loaded', agent)
    try:
        count = 0
        async for event in agent.astream_events({'messages': [('human', 'Bonjour')]}, version='v2', config={'configurable': {'thread_id': 'inspect_test'}}):
            print('EVENT', count, type(event), event)
            count += 1
            if count >= 20:
                break
    except Exception as e:
        print('ERR', e)

asyncio.run(inspect())
