"""Public operation dispatch."""
from .inputs import validate
from . import state, dashboard, scheduler


def dispatch(request):
    operation = request["operation"]
    args = request.get("args", {})
    if operation == "help":
        from .api_help import describe
        return describe(**args)
    if operation == "validate":
        return validate(**args)
    if operation == "initialize":
        args = dict(args)
        owner = args.pop("owner")
        parallel_request = args.pop("parallel_request", None)
        isolation = args.pop("isolation", False)
        mode = args.pop("mode", "parallel")
        result = state.initialize(validate(**args), owner, parallel_request, isolation, mode)
        directory = result["basis"]["change_root"] + "/execution"
        dashboard.render(directory)
        return state.inspect(directory, view="full")
    if operation == "read":
        return state.inspect(**args)
    if operation == "audit":
        return state.audit(**args)
    if operation == "read_object":
        return state.read_object(**args)
    if operation == "resolve_agent":
        from .subagents import resolve
        args = dict(args)
        current = state.read(args.pop("directory"))
        return resolve(current, **args)
    if operation == "available":
        return scheduler.available(state.read(args["directory"]))
    if operation == "event":
        result = state.apply(**args)
        from .state_objects import StateObjects
        result = StateObjects(args["directory"]).pack(result, root=True)
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
