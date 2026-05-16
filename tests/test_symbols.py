from pathlib import Path
import os
from dimagx.symbols import extract_entities

def test_extraction():
    # Create dummy files for testing
    flutter_code = """
    class CounterCubit extends Cubit<int> {
      CounterCubit() : super(0);
      void increment() => emit(state + 1);
    }
    """
    
    react_code = """
    const MyComponent = () => {
      return <div>Hello</div>;
    };
    """
    
    python_code = """
    @app.get("/users")
    def get_users():
        return []
    """
    
    Path("test_flutter.dart").write_text(flutter_code)
    Path("test_react.jsx").write_text(react_code)
    Path("test_fastapi.py").write_text(python_code)
    
    try:
        print("Testing Flutter extraction...")
        flutter = extract_entities(Path("test_flutter.dart"))
        assert any(e['name'] == 'CounterCubit' for e in flutter)
        
        print("Testing React extraction...")
        react = extract_entities(Path("test_react.jsx"))
        assert any(e['name'] == 'MyComponent' for e in react)
        
        print("Testing FastAPI extraction...")
        python = extract_entities(Path("test_fastapi.py"))
        assert any(e['kind'] == 'route' for e in python)
        
        print("✅ All entity extraction tests passed!")
    finally:
        # Cleanup
        if os.path.exists("test_flutter.dart"): os.remove("test_flutter.dart")
        if os.path.exists("test_react.jsx"): os.remove("test_react.jsx")
        if os.path.exists("test_fastapi.py"): os.remove("test_fastapi.py")

if __name__ == "__main__":
    test_extraction()
