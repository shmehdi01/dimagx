"""
DimagX Symbols
Extracts functions, classes and methods using Tree-sitter.
"""

from pathlib import Path
from typing import List, Dict, Optional
import re
import tree_sitter_languages
from tree_sitter import Parser, Language

# Map file extensions to tree-sitter language names
LANG_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".dart": "dart",
}

ENTITY_REGEX = {
    ".dart": [
        (r"class\s+(\w+Cubit)\s+extends\s+Cubit", "cubit", "Flutter"),
        (r"class\s+(\w+Bloc)\s+extends\s+Bloc", "bloc", "Flutter"),
        (r"class\s+(\w+Provider)\s+extends\s+", "provider", "Flutter"),
        (r"class\s+(\w+Page)\s+extends\s+", "page", "Flutter"),
    ],
    ".jsx": [
        (r"(?:const|let|var)\s+([A-Z]\w+)\s*=\s*(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>", "component", "React"),
        (r"function\s+([A-Z]\w+)\s*\(", "component", "React"),
        (r"(?:const|let|var)\s+(use[A-Z]\w+)\s*=", "hook", "React"),
    ],
    ".js": [
        (r"(?:const|let|var)\s+([A-Z]\w+)\s*=\s*(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>", "component", "React"),
        (r"function\s+([A-Z]\w+)\s*\(", "component", "React"),
        (r"(?:const|let|var)\s+(use[A-Z]\w+)\s*=", "hook", "React"),
    ]
}

ENTITY_QUERIES = {
    "python": """
        (decorated_definition
            (decorator (call function: (attribute object: (identifier) attribute: (identifier) @method)))
            (#match? @method "^(get|post|put|delete|patch)$")
        ) @entity
    """,
    "javascript": """
        (function_declaration name: (identifier) @name (#match? @name "^[A-Z]")) @entity
        (variable_declarator name: (identifier) @name value: (arrow_function) (#match? @name "^[A-Z]")) @entity
        (variable_declarator name: (identifier) @name value: (function) (#match? @name "^[A-Z]")) @entity
        (variable_declarator name: (identifier) @name (#match? @name "^use[A-Z]")) @entity
    """,
    "tsx": """
        (function_declaration name: (identifier) @name (#match? @name "^[A-Z]")) @entity
        (variable_declarator name: (identifier) @name value: (arrow_function) (#match? @name "^[A-Z]")) @entity
        (variable_declarator name: (identifier) @name value: (function) (#match? @name "^[A-Z]")) @entity
        (variable_declarator name: (identifier) @name (#match? @name "^use[A-Z]")) @entity
    """
}

def extract_entities(path: Path) -> List[Dict]:
    """Extract framework-specific entities using Tree-sitter or Regex."""
    ext = path.suffix
    try:
        code = path.read_text()
    except Exception:
        return []
    
    entities = []

    # Try Regex first for certain languages (like Flutter where TS might fail)
    if ext in ENTITY_REGEX:
        lines = code.splitlines()
        for pattern, kind, framework in ENTITY_REGEX[ext]:
            for i, line in enumerate(lines):
                match = re.search(pattern, line)
                if match:
                    entities.append({
                        "name": match.group(1),
                        "kind": kind,
                        "framework": framework,
                        "line": i + 1
                    })
        return entities

    # Then Tree-sitter
    lang_name = LANG_MAP.get(ext)
    if not lang_name or lang_name not in ENTITY_QUERIES:
        return []

    try:
        lang = tree_sitter_languages.get_language(lang_name)
        parser = get_parser(ext)
        if not parser:
            return []
            
        query = lang.query(ENTITY_QUERIES[lang_name])
        code_bytes = code.encode("utf-8")
        tree = parser.parse(code_bytes)
        captures = query.captures(tree.root_node)

        for node, tag in captures:
            if tag == "entity":
                # Find name in captures or node children
                name = "unknown"
                
                # Heuristics for details
                framework = "Unknown"
                kind = "entity"
                
                if lang_name in ["javascript", "tsx"]:
                    framework = "React"
                    # Find the first identifier
                    for descendant in _get_all_descendants(node):
                        if descendant.type == "identifier":
                            name = code_bytes[descendant.start_byte:descendant.end_byte].decode("utf-8")
                            if name[0].isupper():
                                kind = "component"
                                break
                            elif name.startswith("use"):
                                kind = "hook"
                                break
                
                elif lang_name == "python":
                    framework = "FastAPI"
                    kind = "route"
                    # Find the route string in the decorator
                    for descendant in _get_all_descendants(node):
                        if descendant.type == "string":
                            raw = code_bytes[descendant.start_byte:descendant.end_byte].decode("utf-8")
                            name = raw.strip("\"'")
                            break

                entities.append({
                    "name": name,
                    "kind": kind,
                    "framework": framework,
                    "line": node.start_point[0] + 1
                })
    except Exception:
        pass

    return entities

def _get_all_descendants(node):
    for child in node.children:
        yield child
        yield from _get_all_descendants(child)

def get_parser(ext: str) -> Optional[Parser]:
    lang_name = LANG_MAP.get(ext)
    if not lang_name:
        return None
    try:
        lang = tree_sitter_languages.get_language(lang_name)
        parser = Parser()
        parser.set_language(lang)
        return parser
    except Exception:
        return None

def extract_symbols(path: Path) -> List[Dict]:
    """Extract classes and functions from a source file."""
    ext = path.suffix
    parser = get_parser(ext)
    if not parser:
        return []

    try:
        code = path.read_bytes()
        tree = parser.parse(code)
        root = tree.root_node
        
        symbols = []
        
        # Simple recursive traversal for functions and classes
        def traverse(node):
            if node.type in ["function_definition", "class_definition", "method_definition", "function_declaration", "class_declaration"]:
                # Try to find the name identifier
                name = ""
                for child in node.children:
                    if child.type in ["identifier", "type_identifier"]:
                        name = code[child.start_byte:child.end_byte].decode("utf-8")
                        break
                
                if name:
                    symbols.append({
                        "name": name,
                        "type": "class" if "class" in node.type else "function",
                        "start_line": node.start_point[0] + 1,
                        "end_line": node.end_point[0] + 1,
                    })
            
            for child in node.children:
                traverse(child)
        
        traverse(root)
        return symbols
    except Exception:
        return []
