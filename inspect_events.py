import asyncio
from app.core.agent import get_agent

async def inspect():
    agent = get_agent()
    count = 0
    async for event in agent.astream_events({'messages': [('human', 'Bonjour')]}, version='v2', config={'configurable': {'thread_id': 'inspect_test'}}):
        kind = event.get('event')
        data = event.get('data')
        print('EVENT', count, kind)
        if kind == 'on_chain_stream':
            chunk = data.get('chunk', {})
            print('  chunk type', type(chunk), 'repr=', repr(chunk))
            if hasattr(chunk, 'messages'):
                print('  messages', chunk.messages)
        elif kind in ('on_chat_model_stream', 'on_chat_model_end', 'on_chain_end'):
            print('  data repr=', repr(data))
        else:
            print('  data keys', list(data.keys()) if isinstance(data, dict) else type(data))
        count += 1
        if count >= 50:
            break

asyncio.run(inspect())
