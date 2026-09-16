from datetime import datetime


class HealthMonitorAgent:
    def __init__(self):
        self.step_timings = {}
        print("[Health Monitor] Initialized")

    def record_step(self, agent_name, duration_ms, success=True):
        stats = self.step_timings.setdefault(agent_name, {"calls": 0, "errors": 0, "total_ms": 0.0, "last_ms": 0.0})
        stats["calls"] += 1
        if not success:
            stats["errors"] += 1
        stats["total_ms"] += duration_ms
        stats["last_ms"] = duration_ms

    def get_status(self, agents=None):
        try:
            status = {"timestamp": datetime.now().isoformat(), "agents": []}
            agents = agents or {}
            for name, agent in agents.items():
                agent_status = agent.get_status() if hasattr(agent, "get_status") else {}
                timing = self.step_timings.get(name, {"calls": 0, "errors": 0, "total_ms": 0.0, "last_ms": 0.0})
                avg_ms = round(timing["total_ms"] / timing["calls"], 1) if timing["calls"] else 0
                status["agents"].append({
                    "agent_name": agent_status.get("agent_name", name),
                    "status": agent_status.get("status", "Online"),
                    "health": "Healthy" if timing["errors"] == 0 else "Degraded",
                    "response_time_ms": avg_ms,
                    "tasks_completed": agent_status.get("tasks_completed", timing["calls"]),
                    "errors": agent_status.get("errors", timing["errors"]),
                })
            status["system_status"] = "Operational"
            status["all_agents_healthy"] = all(a["errors"] == 0 for a in status["agents"]) if status["agents"] else True
            return status
        except Exception as e:
            return {"error": str(e)}
