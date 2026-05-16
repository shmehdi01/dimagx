from tree_sitter_languages import get_parser, get_language

def print_ast(code, lang_name):
    try:
        parser = get_parser(lang_name)
        tree = parser.parse(bytes(code, "utf8"))
        print(f"AST for {lang_name}:")
        print(tree.root_node.sexp())
    except Exception as e:
        print(f"Error for {lang_name}: {e}")

python_code = """
@app.get("/users")
def get_users():
    pass
"""

print_ast(python_code, "python")

react_code = "const MyComponent = () => { return <div>Hello</div>; };"
print_ast(react_code, "javascript")
