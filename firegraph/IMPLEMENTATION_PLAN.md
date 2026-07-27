# Firegraph Implementation Plan

## Goal
Link all code components (class, method, param) relationally so that when a component uses another, they are logically linked. Provide a main workflow that accepts text or file path, analyzes, visualizes, and saves locally.

## Changes Applied (Clean, Non-Breaking)

### 1. StructInspector Extensions (`graph_creator.py`)

- **CLASS nodes**: Added in `visit_ClassDef`. Creates `CLASS` node and `MODULE -> CLASS` edge.
- **CLASS -> METHOD**: When processing a method inside a class, add `CLASS -> METHOD` edge.
- **CLASS -> CLASS_VAR**: In `visit_Assign`, add `CLASS -> CLASS_VAR` edge.
- **Fixed `process_method_params`**: Return param block moved outside the `for` loop (was incorrectly inside).

### 2. UsageLinker (`_UsageLinker` in `graph_creator.py`)

Second-pass visitor that runs after StructInspector:

- **METHOD -> METHOD** (`calls`): When method A calls method B (resolved from AST `Call` nodes).
- **PARAM -> METHOD** (`passes_to`): When a param is passed as argument to another method.

Resolves callees from graph (module-level functions, `self.method`, `ClassName.method`).

### 3. Visualization (`graph/visual.py`)

- **`ds=False`**: Direct format for code structure graphs. Uses `G.nodes` and `G.edges` directly (no `graph_item` filter).
- **`ds=True`**: Keeps existing datastore format for backward compatibility.

### 4. Main Workflow (`run_firegraph.py`)

- **Input**: File path or code string (`--text`).
- **Flow**: Load content -> StructInspector -> UsageLinker -> save JSON -> create_g_visual (ds=False) -> save HTML.
- **Output**: `output/graph.json`, `output/graph.html`.

### 5. Logging

- All `print` calls use `file=sys.stderr` for workflow progress and errors.

## Usage

```bash
# Analyze a file
python run_firegraph.py path/to/module.py

# Analyze inline code
python run_firegraph.py --text "def foo(): return bar()"

# Custom output dir
python run_firegraph.py module.py -o my_output
```

## Edge Types (Summary)

| rel          | src     | trgt     | Meaning                    |
|-------------|---------|----------|----------------------------|
| has_class   | MODULE  | CLASS    | Module contains class       |
| has_method  | MODULE  | METHOD   | Module contains method      |
| has_method  | CLASS   | METHOD   | Class contains method      |
| has_var     | CLASS   | CLASS_VAR| Class contains variable     |
| requires_param | METHOD | PARAM    | Method requires param       |
| returns_param  | METHOD | PARAM    | Method returns param        |
| calls       | METHOD  | METHOD   | Method calls another        |
| passes_to   | PARAM   | METHOD   | Param passed to method      |
