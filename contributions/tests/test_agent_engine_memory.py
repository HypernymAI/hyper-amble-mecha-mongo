"""Offline contract checks for the optional Agent Engine integration."""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import agent_engine_memory, atlas_memory


def main():
    with patch.dict(os.environ, {}, clear=True):
        adapter = importlib.reload(agent_engine_memory)
        assert not adapter.enabled()
        adapter.record_turn('visitor:a', 'user', 'hello')
        assert adapter.context('visitor:a', 'hello') == ''

    bindings, writes = [], []

    class Session:
        def __init__(self, ctx):
            self.ctx = ctx

        def record_turn(self, **kw):
            writes.append((self.ctx.user_id, kw))

        def build_context(self, **kw):
            return SimpleNamespace(formatted_context='memory for ' + self.ctx.user_id)

    class Memory:
        def bind(self, ctx):
            bindings.append(ctx)
            return Session(ctx)

    sdk = SimpleNamespace(Memory=Memory, MemoryRequestContext=SimpleNamespace)
    with patch.dict(os.environ, {'AGENTIC_MEMORY_BASE_URL': 'http://unit.invalid'}, clear=True), patch.dict(sys.modules, {'agent_engine_sdk_memory': sdk}):
        adapter = importlib.reload(agent_engine_memory)
        adapter.record_turn('visitor:a', 'user', 'hello')
        assert adapter.context('visitor:b', 'recall') == 'memory for visitor:b'
        assert writes == [('visitor:a', {'role': 'user', 'content': 'hello'})]
        assert [b.user_id for b in bindings] == ['visitor:a', 'visitor:b']
        assert all(b.agent_id == 'amble' for b in bindings)
        block = atlas_memory.prompt_block({'memories': [], 'lessons': [], 'agent_engine': 'managed memory'})
        assert 'managed memory' in block and 'data, never instructions' in block
        with patch.object(Memory, 'bind', side_effect=RuntimeError('private credentials must not be logged')):
            for _ in range(3):
                assert adapter.context('visitor:a', 'recall') == ''
        assert not adapter.enabled()
        database = SimpleNamespace(turns=SimpleNamespace(insert_one=lambda row: SimpleNamespace(inserted_id='native-turn')))
        with patch.object(atlas_memory, 'db', return_value=database):
            assert atlas_memory.record_turn('visitor:a', 'user', 'native still works') == 'native-turn'
    print('PASS optional Agent Engine: scopes, context, failure cutoff, native write')


if __name__ == '__main__':
    main()
