import asyncio
from app.core.agent import get_agent

async def inspect():
    agent = get_agent()
    print('Agent loaded', agent)
    try:
        async for event in agent.astream_events({'messages': [('human', 'Bonjour')]}, version='v2', config={'configurable': {'thread_id': 'inspect_test'}}):
            print('EVENT', event['event'], event['name'], event['data'] if 'data' in event else event)
            if event['event'] == 'on_chain_end' and event['name'] == 'agent':
                break
    except Exception as e:
        print('ERR', e)

asyncio.run(inspect())
