import json
import uuid


def build_envelope(task: str, result: dict | None = None, error: dict | None = None) -> dict:
    payload: dict[str, object] = {
        "request_id": str(uuid.uuid4()),
        "service": "ears",
        "task": task,
        "provider": None,
        "model": None,
        "usage": None,
    }
    if error is not None:
        payload["error"] = error
    elif result is not None:
        payload["result"] = result
    return payload


async def send_envelope(websocket, task: str, result: dict | None = None, error: dict | None = None) -> None:
    await websocket.send(json.dumps(build_envelope(task, result=result, error=error)))
