"""Public operation dispatch."""
from .inputs import validate
from . import state, dashboard, scheduler


def dispatch(request):
    operation = request["operation"]
    args = request.get("args", {})
    if operation == "validate":
        return validate(**args)
    if operation == "initialize":
        args = dict(args)
        owner = args.pop("owner")
        parallel_request = args.pop("parallel_request", None)
        isolation = args.pop("isolation", False)
        result = state.initialize(validate(**args), owner, parallel_request, isolation)
        dashboard.render(result["basis"]["change_root"] + "/execution")
        return result
    if operation == "read":
        return state.read(**args)
    if operation == "available":
        return scheduler.available(state.read(args["directory"]))
    if operation == "event":
        result = state.apply(**args)
        try:
            view = dashboard.render(args["directory"])
        except (OSError, ValueError) as exc:
            return {"event_result": result, "view_error": str(exc), "recovery": "Run dashboard; do not repeat Git operations"}
        return {"event_result": result, "view": view}
    if operation == "dashboard":
        return dashboard.render(**args)
    if operation == "recover_lock":
        return state.recover_lock(**args)
    if operation in {"serve", "stop_server"}:
        from . import server
        return server.serve(**args) if operation == "serve" else server.stop(**args)
    raise ValueError(f"Unsupported operation: {operation}")
