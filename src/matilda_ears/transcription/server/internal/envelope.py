import json
import uuid
from typing import Optional


def build_envelope(task: str, result: Optional[dict] = None, error: Optional[dict] = None) -> dict:
    payload = {
        "request_id": str(uuid.uuid4()),
        "service": "ears",
        "task": task,
    }
    if error is not None:
        payload["error"] = error
    elif result is not None:
        payload["result"] = result
    return payload


async def send_envelope(websocket, task: str, result: Optional[dict] = None, error: Optional[dict] = None) -> None:
    await websocket.send(json.dumps(build_envelope(task, result=result, error=error)))
