import inspect
from typing import Dict, Callable, Any, List, Optional, Type, Set
from pydantic import BaseModel

class ToolNode(BaseModel):
    name: str
    func: Callable
    description: str
    schema_type: Optional[Type[BaseModel]]
    dependencies: Set[str] = set()
    tags: List[str] = []

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

    def get_definitions(self, minimalist: bool = False) -> str:
        """
        Returns tool definitions. Minimalist mode saves tokens.
        """
        defs = "AVAILABLE TOOLS:\n"
        for name, node in self.tools.items():
            if minimalist:
                defs += f"- {name}: {node.description.split('.')[0]}\n"
            else:
                schema_info = f" Args: {node.schema_type.model_json_schema()}" if node.schema_type else ""
                defs += f"- {name}: {node.description}{schema_info}\n"
        return defs

    def get_tool_summary(self, name: str, full: bool = False) -> str:
        """Returns a string description of the tool, optionally with full schema."""
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
        """Simple topological sort for tool dependencies."""
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
