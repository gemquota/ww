import inspect
import asyncio
from typing import Dict, Callable, Any, List, Optional, Type, Set
from pydantic import BaseModel

class ToolNode(BaseModel):
    name: str
    func: Callable
    description: str
    schema_type: Optional[Type[BaseModel]]
    dependencies: Set[str] = set()
    tags: List[str] = []

class CircularDependencyError(ValueError):
    """Raised when tool dependencies form a cycle."""
    pass


class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, ToolNode] = {}

    def register(self, name: str, func: Callable, description: str, schema: Optional[Type[BaseModel]] = None, dependencies: Set[str] = None, tags: List[str] = None):
        self.tools[name] = ToolNode(
            name=name,
            func=func,
            description=description,
            schema_type=schema,
            dependencies=dependencies or set(),
            tags=tags or []
        )

    def unregister(self, name: str):
        """Remove a tool by name."""
        if name in self.tools:
            del self.tools[name]

    def clear_by_tag(self, tag: str):
        """Remove all tools that have the specified tag."""
        to_remove = [name for name, node in self.tools.items() if tag in node.tags]
        for name in to_remove:
            del self.tools[name]

    def get_definitions(self, minimalist: bool = False) -> str:
        defs = "AVAILABLE TOOLS:\n"
        for name, node in self.tools.items():
            if minimalist:
                defs += f"- {name}: {node.description.split('.')[0]}\n"
            else:
                schema_info = f" Args: {node.schema_type.model_json_schema()}" if node.schema_type else ""
                defs += f"- {name}: {node.description}{schema_info}\n"
        return defs

    def get_tool_summary(self, name: str, full: bool = False) -> str:
        if name not in self.tools:
            return f"- {name}: Not found."
        node = self.tools[name]
        if not full:
            summary = node.description.split('.')[0] + "."
            return f"- {name}: {summary}"
        schema_info = f" Args: {node.schema_type.model_json_schema()}" if node.schema_type else ""
        return f"- {name}: {node.description}{schema_info}"

    async def execute(self, name: str, args: Dict[str, Any]) -> str:
        if name not in self.tools:
            return f"ERROR: Tool '{name}' not found."
        try:
            func = self.tools[name].func
            if inspect.iscoroutinefunction(func):
                return await func(**args)
            return func(**args)
        except Exception as e:
            return f"TOOL ERROR ({name}): {e}"

    def resolve_dag(self, target_tool: str) -> List[str]:
        """Resolve the dependency chain for a tool via DFS.
        
        Returns a linearized list of tool names in dependency order.
        Note: Prefer get_dag_levels() for parallel execution scheduling.
        """
        if target_tool not in self.tools:
            return []
        order = []
        visited = set()
        def visit(name):
            if name in visited:
                return
            visited.add(name)
            for dep in self.tools[name].dependencies:
                visit(dep)
            order.append(name)
        visit(target_tool)
        return order

    def get_dag_levels(self, target_tool: str) -> List[List[str]]:
        """Return DAG levels for parallel execution: each level contains
        independent tools that can run concurrently.
        
        Handles disconnected subgraphs by assigning depth 0 to tools
        with no inbound dependencies that aren't in the main chain."""
        from collections import deque
        
        order = self.resolve_dag(target_tool)
        if not order:
            return []
        
        # Build dependency graph for all nodes in the resolved order
        in_degree = {}
        dep_map = {}
        for name in order:
            dep_map[name] = set()
            in_degree[name] = 0
        
        for name in order:
            node = self.tools.get(name)
            if node and node.dependencies:
                for d in node.dependencies:
                    if d in dep_map:
                        dep_map[d].add(name)
                        in_degree[name] = in_degree.get(name, 0) + 1
        
        # Topological sort with Kahn's algorithm for correct level assignment
        levels = []
        queue = deque([n for n in order if in_degree.get(n, 0) == 0])
        visited = set(queue)
        
        while queue:
            current_level = []
            for _ in range(len(queue)):
                n = queue.popleft()
                current_level.append(n)
                for successor in dep_map.get(n, set()):
                    in_degree[successor] -= 1
                    if in_degree[successor] == 0 and successor not in visited:
                        visited.add(successor)
                        queue.append(successor)
            if current_level:
                levels.append(current_level)
        
        # Detect remaining nodes — means circular dependency
        remaining = set(order) - visited
        if remaining:
            raise CircularDependencyError(
                f"Circular dependency detected among: {remaining}"
            )
        
        return levels

    async def execute_dag(self, target_tool: str, root_args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and its dependencies respecting DAG order.
        Tools at the same DAG level run in parallel via asyncio.gather."""
        levels = self.get_dag_levels(target_tool)
        if not levels:
            return {"error": f"Tool '{target_tool}' not found"}
        results = {}
        for level in levels:
            coros = []
            for name in level:
                # Gather args from dependency results
                args = {}
                if name == target_tool:
                    args = root_args
                node = self.tools[name]
                for dep in node.dependencies:
                    if dep in results:
                        dep_out = results[dep]
                        if isinstance(dep_out, str):
                            args["dependency_output"] = dep_out
                coros.append(self.execute(name, args))
            level_results = await asyncio.gather(*coros)
            for name, result in zip(level, level_results):
                results[name] = result
        return results

    def get_tools_by_tag(self, tag: str) -> List[str]:
        """Return all tool names with the given tag."""
        return [name for name, node in self.tools.items() if tag in node.tags]
