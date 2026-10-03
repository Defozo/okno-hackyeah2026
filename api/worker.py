"""Bounded isolated jobs. No late persistence; killed jobs cannot save anything."""
import asyncio
import multiprocessing as mp
import os
import time
from fastapi import HTTPException
from api.settings import settings

_slots = asyncio.Semaphore(settings.solver_workers)


def _solve_child(connection, scenario, budget):
    try:
        if os.name != 'nt':
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (1536 * 1024**2, 1536 * 1024**2))
        from api.solver import solve_scenario
        result = solve_scenario(scenario, budget_seconds=budget)
        connection.send(('ok', result))
    except Exception:
        connection.send(('error', None))
    finally:
        connection.close()


async def run_solver(scenario: dict):
    if _slots.locked():
        raise HTTPException(429, 'Obliczenia są zajęte. Spróbuj ponownie.', headers={'Retry-After': '3'})
    async with _slots:
        started = time.monotonic()
        from api.transit import hydrate_scenario_routes
        hydrated = await hydrate_scenario_routes(scenario, budget_seconds=max(.1, settings.solver_budget - 2))
        if not hydrated['complete']:
            return {'status': 'UNKNOWN', 'data_status': 'needs_input', 'alternatives': [], 'conflicts': [],
                    'baseline': {'status': 'UNKNOWN', 'schedule': [], 'conflicts': []},
                    'data_gaps': hydrated['issues'], 'routing': {k: v for k, v in hydrated.items() if k != 'scenario'},
                    'message': 'Nie sprawdzono całej domeny tras. Nie można potwierdzić planu.',
                    'checked_period': {'start': scenario.get('start_date'), 'end': scenario.get('end_date')}}
        normalized = hydrated['scenario']
        remaining = max(.01, settings.solver_budget - (time.monotonic() - started) - 1)
        ctx = mp.get_context('spawn')
        receive, send = ctx.Pipe(duplex=False)
        process = ctx.Process(target=_solve_child, args=(send, normalized, remaining), daemon=True)
        process.start()
        send.close()
        deadline = started + settings.solver_budget
        try:
            while time.monotonic() < deadline:
                if receive.poll():
                    status, result = receive.recv()
                    if status != 'ok':
                        raise HTTPException(503, 'Nie udało się zakończyć obliczeń. Dane formularza są zachowane.')
                    result['routing'] = {k: v for k, v in hydrated.items() if k != 'scenario'}
                    if hydrated['active']:
                        result['route_snapshot'] = normalized['travel_legs']
                    result['total_elapsed_ms'] = round((time.monotonic() - started) * 1000)
                    return result
                if not process.is_alive():
                    raise HTTPException(503, 'Proces obliczeń został przerwany. Spróbuj ponownie.')
                await asyncio.sleep(0.025)
            return {'status': 'UNKNOWN', 'data_status': 'complete', 'alternatives': [], 'conflicts': [],
                    'data_gaps': [], 'message': 'Upłynął limit całej analizy. To nie oznacza braku rozwiązania.',
                    'checked_period': {'start': scenario.get('start_date'), 'end': scenario.get('end_date')}}
        finally:
            if process.is_alive():
                process.terminate()
            process.join(timeout=1)
            receive.close()
