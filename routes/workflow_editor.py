"""
Visual workflow editor with declarative schema support.
Provides drag-and-drop workflow building and YAML/JSON automation schemas.
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
import time
import json
import yaml
import uuid
from dataclasses import dataclass, asdict
from enum import Enum
from utils.auth import verify_key
from utils.safety import safety_check, log_action

router = APIRouter()

class NodeType(Enum):
    INPUT = "input"
    ACTION = "action"
    CONDITION = "condition"
    LOOP = "loop"
    PARALLEL = "parallel"
    OUTPUT = "output"
    TRIGGER = "trigger"
    DELAY = "delay"

class ConnectionType(Enum):
    SEQUENCE = "sequence"
    CONDITION_TRUE = "condition_true"
    CONDITION_FALSE = "condition_false"
    ERROR = "error"
    SUCCESS = "success"

@dataclass
class WorkflowNode:
    id: str
    type: NodeType
    name: str
    description: str
    position: Dict[str, float]  # x, y coordinates
    properties: Dict[str, Any]
    inputs: List[str]  # Input connection points
    outputs: List[str]  # Output connection points
    validation_rules: Dict[str, Any]
    execution_config: Dict[str, Any]

@dataclass
class WorkflowConnection:
    id: str
    source_node: str
    source_output: str
    target_node: str
    target_input: str
    connection_type: ConnectionType
    condition: Optional[str] = None
    properties: Dict[str, Any] = None

@dataclass
class WorkflowSchema:
    schema_id: str
    name: str
    description: str
    version: str
    nodes: List[WorkflowNode]
    connections: List[WorkflowConnection]
    variables: Dict[str, Any]
    triggers: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    created_at: float

class WorkflowEditorRequest(BaseModel):
    action: str  # "create", "edit", "validate", "preview", "export"
    workflow_id: Optional[str] = None
    schema_format: Optional[str] = "yaml"  # "yaml", "json"
    workflow_data: Optional[Dict[str, Any]] = None
    export_format: Optional[str] = "schema"  # "schema", "executable", "visual"
    validation_level: Optional[str] = "strict"  # "basic", "strict", "runtime"
    dry_run: Optional[bool] = False

class DeclarativeSchemaRequest(BaseModel):
    action: str  # "parse", "generate", "convert", "validate"
    schema_content: Optional[str] = None
    schema_format: str = "yaml"  # "yaml", "json"
    target_format: Optional[str] = None
    include_metadata: Optional[bool] = True
    validation_rules: Optional[Dict[str, Any]] = None

class VisualEditorRequest(BaseModel):
    action: str  # "load_canvas", "save_canvas", "add_node", "connect_nodes", "validate_flow"
    canvas_id: Optional[str] = None
    canvas_data: Optional[Dict[str, Any]] = None
    node_data: Optional[Dict[str, Any]] = None
    connection_data: Optional[Dict[str, Any]] = None
    editor_config: Optional[Dict[str, Any]] = None

# Workflow storage
_workflow_schemas = {}
_visual_canvases = {}
_node_templates = {}

class WorkflowSchemaValidator:
    """Validates workflow schemas for correctness and safety"""
    
    def __init__(self):
        self.validation_rules = {
            "required_fields": ["name", "version", "nodes"],
            "node_types": [t.value for t in NodeType],
            "connection_types": [t.value for t in ConnectionType],
            "max_nodes": 1000,
            "max_connections": 2000,
            "max_depth": 50
        }
    
    def validate_schema(self, schema: WorkflowSchema, level: str = "strict") -> Dict[str, Any]:
        """Validate workflow schema"""
        errors = []
        warnings = []
        
        # Basic validation
        if not schema.name:
            errors.append("Workflow name is required")
        
        if not schema.nodes:
            errors.append("At least one node is required")
        
        if len(schema.nodes) > self.validation_rules["max_nodes"]:
            errors.append(f"Too many nodes (max: {self.validation_rules['max_nodes']})")
        
        # Node validation
        node_ids = set()
        for node in schema.nodes:
            if node.id in node_ids:
                errors.append(f"Duplicate node ID: {node.id}")
            node_ids.add(node.id)
            
            if node.type.value not in self.validation_rules["node_types"]:
                errors.append(f"Invalid node type: {node.type.value}")
        
        # Connection validation
        if len(schema.connections) > self.validation_rules["max_connections"]:
            errors.append(f"Too many connections (max: {self.validation_rules['max_connections']})")
        
        for conn in schema.connections:
            if conn.source_node not in node_ids:
                errors.append(f"Connection references non-existent source node: {conn.source_node}")
            if conn.target_node not in node_ids:
                errors.append(f"Connection references non-existent target node: {conn.target_node}")
        
        # Strict validation
        if level == "strict":
            # Check for cycles
            if self._has_cycles(schema):
                warnings.append("Workflow contains cycles - may cause infinite loops")
            
            # Check for unreachable nodes
            unreachable = self._find_unreachable_nodes(schema)
            if unreachable:
                warnings.append(f"Unreachable nodes found: {', '.join(unreachable)}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "validation_level": level,
            "node_count": len(schema.nodes),
            "connection_count": len(schema.connections)
        }
    
    def _has_cycles(self, schema: WorkflowSchema) -> bool:
        """Check for cycles in workflow graph"""
        # Build adjacency list
        graph = {node.id: [] for node in schema.nodes}
        for conn in schema.connections:
            graph[conn.source_node].append(conn.target_node)
        
        # DFS cycle detection
        visited = set()
        rec_stack = set()
        
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node_id in graph:
            if node_id not in visited:
                if dfs(node_id):
                    return True
        
        return False
    
    def _find_unreachable_nodes(self, schema: WorkflowSchema) -> List[str]:
        """Find nodes that are not reachable from trigger nodes"""
        if not schema.nodes:
            return []
        
        # Find trigger/start nodes
        trigger_nodes = [node.id for node in schema.nodes if node.type == NodeType.TRIGGER]
        if not trigger_nodes:
            # If no trigger nodes, assume first node is start
            trigger_nodes = [schema.nodes[0].id]
        
        # Build graph
        graph = {node.id: [] for node in schema.nodes}
        for conn in schema.connections:
            graph[conn.source_node].append(conn.target_node)
        
        # BFS from trigger nodes
        reachable = set()
        queue = trigger_nodes.copy()
        
        while queue:
            current = queue.pop(0)
            if current in reachable:
                continue
            reachable.add(current)
            queue.extend(graph.get(current, []))
        
        # Find unreachable nodes
        all_nodes = set(node.id for node in schema.nodes)
        unreachable = list(all_nodes - reachable)
        
        return unreachable

class DeclarativeSchemaProcessor:
    """Processes declarative workflow schemas in YAML/JSON"""
    
    def __init__(self):
        self.schema_templates = {
            "basic_automation": {
                "name": "Basic Automation Template",
                "version": "1.0",
                "description": "Simple automation workflow template",
                "triggers": [{"type": "manual", "name": "start"}],
                "steps": [
                    {"name": "step1", "action": "screen_capture", "params": {}},
                    {"name": "step2", "action": "input_click", "params": {"x": 100, "y": 100}}
                ],
                "error_handling": {"on_error": "stop", "retry_count": 3}
            },
            "web_automation": {
                "name": "Web Automation Template",
                "version": "1.0",
                "description": "Web browser automation template",
                "triggers": [{"type": "schedule", "cron": "0 9 * * *"}],
                "steps": [
                    {"name": "navigate", "action": "web_navigate", "params": {"url": "https://example.com"}},
                    {"name": "fill_form", "action": "web_fill", "params": {"selector": "#form", "data": {}}},
                    {"name": "submit", "action": "web_click", "params": {"selector": "button[type=submit]"}}
                ],
                "variables": {"base_url": "https://example.com", "timeout": 30}
            }
        }
    
    def parse_schema(self, content: str, format: str) -> Dict[str, Any]:
        """Parse schema from YAML or JSON"""
        try:
            if format.lower() == "yaml":
                return yaml.safe_load(content)
            elif format.lower() == "json":
                return json.loads(content)
            else:
                raise ValueError(f"Unsupported format: {format}")
        except Exception as e:
            raise ValueError(f"Failed to parse {format}: {str(e)}")
    
    def generate_schema(self, workflow: WorkflowSchema, format: str, include_metadata: bool = True) -> str:
        """Generate schema string from workflow object"""
        schema_dict = {
            "name": workflow.name,
            "description": workflow.description,
            "version": workflow.version,
            "variables": workflow.variables,
            "triggers": workflow.triggers,
            "steps": []
        }
        
        # Convert nodes to steps
        for node in workflow.nodes:
            step = {
                "id": node.id,
                "name": node.name,
                "type": node.type.value,
                "description": node.description,
                "properties": node.properties,
                "execution_config": node.execution_config
            }
            schema_dict["steps"].append(step)
        
        # Add connections
        if workflow.connections:
            schema_dict["connections"] = [
                {
                    "from": conn.source_node,
                    "to": conn.target_node,
                    "type": conn.connection_type.value,
                    "condition": conn.condition
                }
                for conn in workflow.connections
            ]
        
        if include_metadata:
            schema_dict["metadata"] = workflow.metadata
            schema_dict["created_at"] = workflow.created_at
        
        # Export in requested format
        if format.lower() == "yaml":
            return yaml.dump(schema_dict, default_flow_style=False, indent=2)
        elif format.lower() == "json":
            return json.dumps(schema_dict, indent=2)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def convert_format(self, content: str, from_format: str, to_format: str) -> str:
        """Convert between YAML and JSON formats"""
        # Parse from source format
        data = self.parse_schema(content, from_format)
        
        # Export to target format
        if to_format.lower() == "yaml":
            return yaml.dump(data, default_flow_style=False, indent=2)
        elif to_format.lower() == "json":
            return json.dumps(data, indent=2)
        else:
            raise ValueError(f"Unsupported target format: {to_format}")

# Global instances
_schema_validator = WorkflowSchemaValidator()
_schema_processor = DeclarativeSchemaProcessor()

def _initialize_node_templates():
    """Initialize node templates for visual editor"""
    global _node_templates
    
    _node_templates = {
        "input": {
            "name": "Input Node",
            "description": "Captures user input or external data",
            "properties": {"input_type": "text", "required": True},
            "inputs": [],
            "outputs": ["data"],
            "icon": "input",
            "category": "data"
        },
        "action": {
            "name": "Action Node",
            "description": "Performs an automation action",
            "properties": {"action_type": "click", "target": "", "parameters": {}},
            "inputs": ["trigger"],
            "outputs": ["success", "error"],
            "icon": "play",
            "category": "automation"
        },
        "condition": {
            "name": "Condition Node",
            "description": "Evaluates a condition and branches execution",
            "properties": {"condition": "", "operator": "equals", "value": ""},
            "inputs": ["data"],
            "outputs": ["true", "false"],
            "icon": "decision",
            "category": "logic"
        },
        "loop": {
            "name": "Loop Node",
            "description": "Repeats actions for a collection or count",
            "properties": {"loop_type": "count", "count": 1, "collection": ""},
            "inputs": ["items"],
            "outputs": ["iteration", "complete"],
            "icon": "repeat",
            "category": "control"
        },
        "delay": {
            "name": "Delay Node",
            "description": "Waits for a specified duration",
            "properties": {"duration": 1000, "unit": "milliseconds"},
            "inputs": ["trigger"],
            "outputs": ["complete"],
            "icon": "clock",
            "category": "utility"
        }
    }

_initialize_node_templates()

@router.post("/", dependencies=[Depends(verify_key)])
def workflow_editor(req: WorkflowEditorRequest, response: Response):
    """
    Visual workflow editor with drag-and-drop interface.
    Create, edit, and validate automation workflows visually.
    """
    start_time = time.time()
    
    # Safety check
    safety_result = safety_check("/workflow_editor", req.action, req.dict(), req.dry_run)
    if not safety_result["safe"]:
        return {"errors": [{"code": "SAFETY_VIOLATION", "message": safety_result["message"]}]}
    
    result = {
        "action": req.action,
        "workflow_id": req.workflow_id,
        "schema_format": req.schema_format,
        "validation_level": req.validation_level,
        "dry_run": req.dry_run,
        "safety_check": safety_result
    }
    
    if req.dry_run:
        result["status"] = f"would_{req.action}"
        log_action("/workflow_editor", req.action, req.dict(), result, dry_run=True)
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    try:
        if req.action == "create":
            # Create new workflow
            workflow_id = req.workflow_id or f"workflow_{uuid.uuid4().hex[:8]}"
            
            # Create basic workflow structure
            workflow = WorkflowSchema(
                schema_id=workflow_id,
                name=req.workflow_data.get("name", "New Workflow") if req.workflow_data else "New Workflow",
                description=req.workflow_data.get("description", "") if req.workflow_data else "",
                version="1.0",
                nodes=[],
                connections=[],
                variables={},
                triggers=[{"type": "manual", "name": "start"}],
                metadata={"created_by": "workflow_editor", "editor_version": "2.0"},
                created_at=time.time()
            )
            
            _workflow_schemas[workflow_id] = workflow
            
            result.update({
                "status": "workflow_created",
                "workflow_id": workflow_id,
                "workflow_info": {
                    "name": workflow.name,
                    "version": workflow.version,
                    "node_count": len(workflow.nodes),
                    "connection_count": len(workflow.connections)
                }
            })
            
        elif req.action == "edit":
            if not req.workflow_id or req.workflow_id not in _workflow_schemas:
                return {"errors": [{"code": "WORKFLOW_NOT_FOUND", "message": f"Workflow {req.workflow_id} not found"}]}
            
            workflow = _workflow_schemas[req.workflow_id]
            
            # Apply edits from workflow_data
            if req.workflow_data:
                if "name" in req.workflow_data:
                    workflow.name = req.workflow_data["name"]
                if "description" in req.workflow_data:
                    workflow.description = req.workflow_data["description"]
                if "variables" in req.workflow_data:
                    workflow.variables.update(req.workflow_data["variables"])
            
            result.update({
                "status": "workflow_updated",
                "workflow_id": req.workflow_id,
                "changes_applied": list(req.workflow_data.keys()) if req.workflow_data else []
            })
            
        elif req.action == "validate":
            if not req.workflow_id or req.workflow_id not in _workflow_schemas:
                return {"errors": [{"code": "WORKFLOW_NOT_FOUND", "message": f"Workflow {req.workflow_id} not found"}]}
            
            workflow = _workflow_schemas[req.workflow_id]
            validation_result = _schema_validator.validate_schema(workflow, req.validation_level)
            
            result.update({
                "status": "validation_complete",
                "validation_result": validation_result
            })
            
        elif req.action == "export":
            if not req.workflow_id or req.workflow_id not in _workflow_schemas:
                return {"errors": [{"code": "WORKFLOW_NOT_FOUND", "message": f"Workflow {req.workflow_id} not found"}]}
            
            workflow = _workflow_schemas[req.workflow_id]
            
            if req.export_format == "schema":
                schema_content = _schema_processor.generate_schema(workflow, req.schema_format, True)
                result.update({
                    "status": "schema_exported",
                    "schema_content": schema_content,
                    "format": req.schema_format
                })
            elif req.export_format == "executable":
                # Generate executable automation script
                executable_script = {
                    "workflow_id": workflow.schema_id,
                    "execution_plan": [
                        {
                            "step": i + 1,
                            "node_id": node.id,
                            "action": node.properties.get("action_type", "unknown"),
                            "parameters": node.properties
                        }
                        for i, node in enumerate(workflow.nodes)
                    ],
                    "execution_metadata": {
                        "total_steps": len(workflow.nodes),
                        "estimated_duration": sum(
                            node.execution_config.get("estimated_duration", 1.0) 
                            for node in workflow.nodes
                        )
                    }
                }
                
                result.update({
                    "status": "executable_generated",
                    "executable_script": executable_script
                })
        
        log_action("/workflow_editor", req.action, req.dict(), result, dry_run=False)
        
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return {"errors": [{"code": "WORKFLOW_EDITOR_ERROR", "message": str(e)}]}

@router.post("/schema", dependencies=[Depends(verify_key)])
def declarative_schema(req: DeclarativeSchemaRequest, response: Response):
    """
    Declarative schema processing for YAML/JSON automation definitions.
    Parse, generate, convert, and validate automation schemas.
    """
    start_time = time.time()
    
    # Safety check
    safety_result = safety_check("/workflow_editor", req.action, req.dict())
    if not safety_result["safe"]:
        return {"errors": [{"code": "SAFETY_VIOLATION", "message": safety_result["message"]}]}
    
    result = {
        "action": req.action,
        "schema_format": req.schema_format,
        "target_format": req.target_format,
        "include_metadata": req.include_metadata,
        "safety_check": safety_result
    }
    
    try:
        if req.action == "parse":
            if not req.schema_content:
                return {"errors": [{"code": "MISSING_CONTENT", "message": "schema_content required for parse action"}]}
            
            parsed_data = _schema_processor.parse_schema(req.schema_content, req.schema_format)
            
            result.update({
                "status": "schema_parsed",
                "parsed_data": parsed_data,
                "validation": {
                    "has_name": "name" in parsed_data,
                    "has_steps": "steps" in parsed_data,
                    "step_count": len(parsed_data.get("steps", [])),
                    "has_triggers": "triggers" in parsed_data
                }
            })
            
        elif req.action == "generate":
            # Generate schema from template
            template_name = req.validation_rules.get("template", "basic_automation") if req.validation_rules else "basic_automation"
            
            if template_name in _schema_processor.schema_templates:
                template_data = _schema_processor.schema_templates[template_name].copy()
                
                # Customize template based on validation_rules
                if req.validation_rules:
                    if "name" in req.validation_rules:
                        template_data["name"] = req.validation_rules["name"]
                    if "description" in req.validation_rules:
                        template_data["description"] = req.validation_rules["description"]
                
                # Generate schema string
                if req.schema_format.lower() == "yaml":
                    schema_content = yaml.dump(template_data, default_flow_style=False, indent=2)
                else:
                    schema_content = json.dumps(template_data, indent=2)
                
                result.update({
                    "status": "schema_generated",
                    "schema_content": schema_content,
                    "template_used": template_name,
                    "format": req.schema_format
                })
            else:
                return {"errors": [{"code": "TEMPLATE_NOT_FOUND", "message": f"Template {template_name} not found"}]}
                
        elif req.action == "convert":
            if not req.schema_content or not req.target_format:
                return {"errors": [{"code": "MISSING_PARAMETERS", "message": "schema_content and target_format required"}]}
            
            converted_content = _schema_processor.convert_format(
                req.schema_content, req.schema_format, req.target_format
            )
            
            result.update({
                "status": "schema_converted",
                "converted_content": converted_content,
                "from_format": req.schema_format,
                "to_format": req.target_format
            })
            
        elif req.action == "validate":
            if not req.schema_content:
                return {"errors": [{"code": "MISSING_CONTENT", "message": "schema_content required for validation"}]}
            
            # Parse and validate schema
            try:
                parsed_data = _schema_processor.parse_schema(req.schema_content, req.schema_format)
                
                validation_errors = []
                validation_warnings = []
                
                # Basic validation
                if "name" not in parsed_data:
                    validation_errors.append("Missing required field: name")
                if "steps" not in parsed_data or not parsed_data["steps"]:
                    validation_errors.append("At least one step is required")
                
                # Step validation
                for i, step in enumerate(parsed_data.get("steps", [])):
                    if "name" not in step:
                        validation_errors.append(f"Step {i+1}: Missing name")
                    if "action" not in step:
                        validation_errors.append(f"Step {i+1}: Missing action")
                
                # Trigger validation
                triggers = parsed_data.get("triggers", [])
                if not triggers:
                    validation_warnings.append("No triggers defined - workflow may not be executable")
                
                result.update({
                    "status": "validation_complete",
                    "valid": len(validation_errors) == 0,
                    "validation_result": {
                        "errors": validation_errors,
                        "warnings": validation_warnings,
                        "step_count": len(parsed_data.get("steps", [])),
                        "trigger_count": len(triggers),
                        "has_variables": "variables" in parsed_data
                    }
                })
                
            except Exception as e:
                result.update({
                    "status": "validation_failed",
                    "valid": False,
                    "parse_error": str(e)
                })
        
        log_action("/workflow_editor", req.action, req.dict(), result)
        
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return {"errors": [{"code": "SCHEMA_PROCESSING_ERROR", "message": str(e)}]}

@router.post("/visual", dependencies=[Depends(verify_key)])
def visual_editor(req: VisualEditorRequest, response: Response):
    """
    Visual drag-and-drop workflow editor interface.
    Manage canvas, nodes, and connections for visual workflow building.
    """
    start_time = time.time()
    
    # Safety check
    safety_result = safety_check("/workflow_editor", req.action, req.dict())
    if not safety_result["safe"]:
        return {"errors": [{"code": "SAFETY_VIOLATION", "message": safety_result["message"]}]}
    
    result = {
        "action": req.action,
        "canvas_id": req.canvas_id,
        "safety_check": safety_result
    }
    
    try:
        if req.action == "load_canvas":
            canvas_id = req.canvas_id or f"canvas_{uuid.uuid4().hex[:8]}"
            
            if canvas_id in _visual_canvases:
                canvas_data = _visual_canvases[canvas_id]
            else:
                # Create new canvas
                canvas_data = {
                    "canvas_id": canvas_id,
                    "nodes": [],
                    "connections": [],
                    "canvas_properties": {
                        "width": 1200,
                        "height": 800,
                        "zoom": 1.0,
                        "grid_enabled": True,
                        "snap_to_grid": True
                    },
                    "created_at": time.time(),
                    "modified_at": time.time()
                }
                _visual_canvases[canvas_id] = canvas_data
            
            result.update({
                "status": "canvas_loaded",
                "canvas_data": canvas_data,
                "node_templates": _node_templates,
                "editor_config": {
                    "drag_enabled": True,
                    "connect_enabled": True,
                    "validation_enabled": True,
                    "auto_save": True
                }
            })
            
        elif req.action == "save_canvas":
            if not req.canvas_id or not req.canvas_data:
                return {"errors": [{"code": "MISSING_PARAMETERS", "message": "canvas_id and canvas_data required"}]}
            
            canvas_data = req.canvas_data.copy()
            canvas_data["modified_at"] = time.time()
            _visual_canvases[req.canvas_id] = canvas_data
            
            result.update({
                "status": "canvas_saved",
                "canvas_id": req.canvas_id,
                "node_count": len(canvas_data.get("nodes", [])),
                "connection_count": len(canvas_data.get("connections", []))
            })
            
        elif req.action == "add_node":
            if not req.canvas_id or not req.node_data:
                return {"errors": [{"code": "MISSING_PARAMETERS", "message": "canvas_id and node_data required"}]}
            
            if req.canvas_id not in _visual_canvases:
                return {"errors": [{"code": "CANVAS_NOT_FOUND", "message": f"Canvas {req.canvas_id} not found"}]}
            
            canvas = _visual_canvases[req.canvas_id]
            
            # Create new node
            node_id = req.node_data.get("id") or f"node_{uuid.uuid4().hex[:8]}"
            node_type = req.node_data.get("type", "action")
            
            if node_type in _node_templates:
                template = _node_templates[node_type]
                new_node = {
                    "id": node_id,
                    "type": node_type,
                    "name": req.node_data.get("name", template["name"]),
                    "description": req.node_data.get("description", template["description"]),
                    "position": req.node_data.get("position", {"x": 100, "y": 100}),
                    "properties": req.node_data.get("properties", template["properties"].copy()),
                    "inputs": template["inputs"].copy(),
                    "outputs": template["outputs"].copy(),
                    "created_at": time.time()
                }
                
                canvas["nodes"].append(new_node)
                canvas["modified_at"] = time.time()
                
                result.update({
                    "status": "node_added",
                    "node": new_node,
                    "canvas_id": req.canvas_id
                })
            else:
                return {"errors": [{"code": "INVALID_NODE_TYPE", "message": f"Node type {node_type} not supported"}]}
                
        elif req.action == "connect_nodes":
            if not req.canvas_id or not req.connection_data:
                return {"errors": [{"code": "MISSING_PARAMETERS", "message": "canvas_id and connection_data required"}]}
            
            if req.canvas_id not in _visual_canvases:
                return {"errors": [{"code": "CANVAS_NOT_FOUND", "message": f"Canvas {req.canvas_id} not found"}]}
            
            canvas = _visual_canvases[req.canvas_id]
            
            # Create new connection
            connection = {
                "id": f"conn_{uuid.uuid4().hex[:8]}",
                "source_node": req.connection_data["source_node"],
                "source_output": req.connection_data.get("source_output", "output"),
                "target_node": req.connection_data["target_node"],
                "target_input": req.connection_data.get("target_input", "input"),
                "connection_type": req.connection_data.get("type", "sequence"),
                "created_at": time.time()
            }
            
            canvas["connections"].append(connection)
            canvas["modified_at"] = time.time()
            
            result.update({
                "status": "nodes_connected",
                "connection": connection,
                "canvas_id": req.canvas_id
            })
            
        elif req.action == "validate_flow":
            if not req.canvas_id:
                return {"errors": [{"code": "MISSING_CANVAS_ID", "message": "canvas_id required"}]}
            
            if req.canvas_id not in _visual_canvases:
                return {"errors": [{"code": "CANVAS_NOT_FOUND", "message": f"Canvas {req.canvas_id} not found"}]}
            
            canvas = _visual_canvases[req.canvas_id]
            
            # Validate workflow logic
            validation_errors = []
            validation_warnings = []
            
            nodes = canvas.get("nodes", [])
            connections = canvas.get("connections", [])
            
            if not nodes:
                validation_errors.append("No nodes in workflow")
            
            # Check for disconnected nodes
            connected_nodes = set()
            for conn in connections:
                connected_nodes.add(conn["source_node"])
                connected_nodes.add(conn["target_node"])
            
            disconnected = [node["id"] for node in nodes if node["id"] not in connected_nodes and len(nodes) > 1]
            if disconnected:
                validation_warnings.append(f"Disconnected nodes: {', '.join(disconnected)}")
            
            # Check for invalid connections
            node_ids = set(node["id"] for node in nodes)
            for conn in connections:
                if conn["source_node"] not in node_ids:
                    validation_errors.append(f"Connection references non-existent source: {conn['source_node']}")
                if conn["target_node"] not in node_ids:
                    validation_errors.append(f"Connection references non-existent target: {conn['target_node']}")
            
            result.update({
                "status": "flow_validated",
                "validation_result": {
                    "valid": len(validation_errors) == 0,
                    "errors": validation_errors,
                    "warnings": validation_warnings,
                    "node_count": len(nodes),
                    "connection_count": len(connections),
                    "disconnected_nodes": len(disconnected)
                }
            })
        
        log_action("/workflow_editor", req.action, req.dict(), result)
        
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return {"errors": [{"code": "VISUAL_EDITOR_ERROR", "message": str(e)}]}

@router.get("/templates", dependencies=[Depends(verify_key)])
def get_workflow_templates():
    """Get available workflow templates and node types"""
    
    return {
        "result": {
            "node_templates": _node_templates,
            "workflow_templates": _schema_processor.schema_templates,
            "supported_formats": ["yaml", "json"],
            "validation_levels": ["basic", "strict", "runtime"],
            "node_categories": {
                "data": ["input", "output", "variable"],
                "automation": ["action", "api_call", "file_operation"],
                "logic": ["condition", "switch", "merge"],
                "control": ["loop", "parallel", "sequence"],
                "utility": ["delay", "log", "notification"]
            },
            "connection_types": [t.value for t in ConnectionType]
        },
        "timestamp": int(time.time() * 1000)
    }

@router.get("/capabilities", dependencies=[Depends(verify_key)])
def get_workflow_editor_capabilities():
    """Get workflow editor capabilities and features"""
    capabilities = {
        "visual_editor": {
            "drag_and_drop": True,
            "node_library": True,
            "connection_management": True,
            "canvas_operations": True,
            "real_time_validation": True,
            "auto_save": True,
            "grid_snapping": True,
            "zoom_pan": True
        },
        "declarative_schemas": {
            "yaml_support": True,
            "json_support": True,
            "schema_validation": True,
            "format_conversion": True,
            "template_generation": True,
            "import_export": True
        },
        "workflow_features": {
            "multi_step_workflows": True,
            "conditional_logic": True,
            "loops_iteration": True,
            "parallel_execution": True,
            "error_handling": True,
            "variable_management": True,
            "trigger_system": True
        },
        "validation": {
            "syntax_validation": True,
            "logic_validation": True,
            "dependency_checking": True,
            "cycle_detection": True,
            "reachability_analysis": True,
            "performance_analysis": False  # Future enhancement
        },
        "supported_node_types": list(_node_templates.keys()),
        "max_limits": {
            "nodes_per_workflow": 1000,
            "connections_per_workflow": 2000,
            "workflow_depth": 50,
            "concurrent_canvases": 100
        }
    }
    
    return {
        "result": capabilities,
        "timestamp": int(time.time() * 1000)
    }