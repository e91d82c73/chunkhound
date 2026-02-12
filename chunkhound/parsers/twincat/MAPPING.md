# TwinCAT/IEC 61131-3 to ChunkHound Mapping

## Overview

This document maps TwinCAT Structured Text (IEC 61131-3) concepts to ChunkHound's ChunkType system, using **hardware/PLC engineering terminology** rather than software-centric terms where they differ.

---

## Existing ChunkType Enum (from `chunkhound/core/types/common.py:30-77`)

```python
class ChunkType(Enum):
    # Code structure types
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    INTERFACE = "interface"
    STRUCT = "struct"
    ENUM = "enum"
    NAMESPACE = "namespace"
    CONSTRUCTOR = "constructor"
    PROPERTY = "property"
    FIELD = "field"
    TYPE_ALIAS = "type_alias"
    CLOSURE = "closure"
    TRAIT = "trait"
    SCRIPT = "script"
    OBJECT = "object"
    COMPANION_OBJECT = "companion_object"
    DATA_CLASS = "data_class"
    EXTENSION_FUNCTION = "extension_function"
    VARIABLE = "variable"
    TYPE = "type"
    MACRO = "macro"
    COMMENT = "comment"
    DOCSTRING = "docstring"
    # ... documentation types ...
    TABLE = "table"
    KEY_VALUE = "key_value"
    ARRAY = "array"
    BLOCK = "block"
    UNKNOWN = "unknown"
```

---

## New Chunk Types Recommended for PLC/Industrial Automation

After analysis, **3 new ChunkTypes are recommended** to better represent hardware engineering concepts that don't map cleanly to software terms:

| New ChunkType | Value | Rationale |
|---------------|-------|-----------|
| `FUNCTION_BLOCK` | `"function_block"` | Core IEC 61131-3 concept - stateful, instantiable, with I/O. More meaningful to PLC engineers than "class" |
| `PROGRAM` | `"program"` | PLC entry point/cyclic task. Different from software "function" - represents a real-time cyclic execution unit |
| `ACTION` | `"action"` | Named callable within a FB/PROGRAM. Not exactly a "method" - can be called with qualifiers (R, S, N, P, etc.) |

### Why Not Just Use Existing Types?

| Concept | Software Mapping | Why New Type Is Better |
|---------|------------------|------------------------|
| **FUNCTION_BLOCK** | CLASS | FB has VAR_INPUT/VAR_OUTPUT semantics, I/O binding, cycle execution - none of which "class" conveys. Every PLC engineer knows "FB" but may not think "class". |
| **PROGRAM** | FUNCTION | A PROGRAM runs cyclically in a task, can have I/O bindings, and is the execution entry point. "Function" implies stateless, returns value - neither applies to PROGRAM. |
| **ACTION** | METHOD | ACTIONs have IEC-specific qualifier semantics (R=Reset, S=Set, N=Non-stored, P=Pulse, etc.) and can belong to steps in SFC. "Method" doesn't capture this. |

---

## Complete TwinCAT to ChunkType Mapping

### Tier 1: Program Organization Units (POUs)

| IEC 61131-3 Concept | Hardware Term | ChunkType | `metadata["kind"]` | Description |
|---------------------|---------------|-----------|-------------------|-------------|
| **PROGRAM** | Program | `PROGRAM` (new) | `"program"` | Cyclic execution unit bound to a task. Entry point for PLC logic. |
| **FUNCTION_BLOCK** | Function Block (FB) | `FUNCTION_BLOCK` (new) | `"function_block"` | Stateful, instantiable block with inputs/outputs. Core building block. |
| **FUNCTION** | Function (FC) | `FUNCTION` | `"function"` | Stateless callable, returns a value. No instance data. |
| **METHOD** | Method | `METHOD` | `"method"` | Member function within an FB. TwinCAT 3 OOP extension. |
| **PROPERTY** | Property | `PROPERTY` | `"property"` | GET/SET accessor in FB. TwinCAT 3 OOP extension. |
| **ACTION** | Action | `ACTION` (new) | `"action"` | Named code block in FB/PROGRAM, callable with qualifiers. |
| **TRANSITION** | Transition | `FUNCTION` | `"transition"` | SFC transition condition - evaluates to BOOL. |

### Tier 2: Data Types

| IEC 61131-3 Concept | Hardware Term | ChunkType | `metadata["kind"]` | Description |
|---------------------|---------------|-----------|-------------------|-------------|
| **TYPE...STRUCT...END_TYPE** | Structure Type | `STRUCT` | `"struct"` | User-defined data structure (ST_MotorData, ST_Recipe). |
| **TYPE...ENUM...END_TYPE** | Enumeration | `ENUM` | `"enum"` | Enumerated type (E_State, E_MotorCommand). |
| **TYPE alias END_TYPE** | Type Alias | `TYPE_ALIAS` | `"type_alias"` | Type synonym (T_Position : LREAL). |
| **INTERFACE** | Interface | `INTERFACE` | `"interface"` | IEC 61131-3 Ed.3 interface (I_Runnable, I_Axis). |

### Tier 3: Variable Declarations

| IEC 61131-3 Concept | Hardware Term | ChunkType | `metadata["kind"]` | `metadata["var_class"]` |
|---------------------|---------------|-----------|-------------------|------------------------|
| **VAR_INPUT** | Input | `FIELD` | `"field"` | `"input"` |
| **VAR_OUTPUT** | Output | `FIELD` | `"field"` | `"output"` |
| **VAR_IN_OUT** | In/Out (Reference) | `FIELD` | `"field"` | `"in_out"` |
| **VAR** | Local Variable | `FIELD` | `"field"` | `"local"` |
| **VAR_TEMP** | Temp Variable | `FIELD` | `"field"` | `"temp"` |
| **VAR_STAT** | Static Variable | `FIELD` | `"field"` | `"static"` |
| **VAR_GLOBAL** | Global Variable | `VARIABLE` | `"variable"` | `"global"` |
| **VAR_EXTERNAL** | External Reference | `VARIABLE` | `"variable"` | `"external"` |
| **CONSTANT** | Constant | `VARIABLE` | `"constant"` | `"constant"` |

### Tier 4: Control Flow (Optional Extraction)

| IEC 61131-3 Concept | Hardware Term | ChunkType | `metadata["kind"]` |
|---------------------|---------------|-----------|-------------------|
| **IF...END_IF** | Conditional | `BLOCK` | `"if_block"` |
| **CASE...END_CASE** | Case/Switch | `BLOCK` | `"case_block"` |
| **FOR...END_FOR** | For Loop | `BLOCK` | `"for_loop"` |
| **WHILE...END_WHILE** | While Loop | `BLOCK` | `"while_loop"` |
| **REPEAT...END_REPEAT** | Repeat Loop | `BLOCK` | `"repeat_loop"` |

### Tier 5: SFC (Sequential Function Chart)

| IEC 61131-3 Concept | Hardware Term | ChunkType | `metadata["kind"]` |
|---------------------|---------------|-----------|-------------------|
| **SFC Step** | Step | `BLOCK` | `"sfc_step"` |
| **SFC Initial Step** | Initial Step | `BLOCK` | `"sfc_initial_step"` |
| **SFC Action Association** | Step Action | `BLOCK` | `"sfc_action_association"` |
| **SFC Transition** | Transition | `FUNCTION` | `"transition"` |

### Tier 6: Metadata and Comments

| IEC 61131-3 Concept | Hardware Term | ChunkType | `metadata["kind"]` |
|---------------------|---------------|-----------|-------------------|
| **{attribute 'xxx'}** | Pragma/Attribute | `MACRO` | `"attribute"` |
| **(* comment *)** | Block Comment | `COMMENT` | `"block_comment"` |
| **// comment** | Line Comment | `COMMENT` | `"line_comment"` |

---

## Proposed ChunkType Enum Additions

Add to `chunkhound/core/types/common.py`:

```python
class ChunkType(Enum):
    # ... existing types ...

    # PLC/Industrial Automation types (IEC 61131-3)
    PROGRAM = "program"              # PLC program - cyclic execution unit
    FUNCTION_BLOCK = "function_block"  # FB - stateful instantiable block with I/O
    ACTION = "action"                # Named action block in FB/PROGRAM
```

Update `is_code` property to include new types:

```python
@property
def is_code(self) -> bool:
    return self in {
        # ... existing types ...
        ChunkType.PROGRAM,
        ChunkType.FUNCTION_BLOCK,
        ChunkType.ACTION,
    }
```

---

## Kind-to-ChunkType Resolution

Update `chunkhound/parsers/universal_parser.py` kind mapping (around line 1234):

```python
kind_map = {
    # ... existing mappings ...

    # PLC/IEC 61131-3 additions
    "program": ChunkType.PROGRAM,
    "function_block": ChunkType.FUNCTION_BLOCK,
    "action": ChunkType.ACTION,
    "transition": ChunkType.FUNCTION,
    "sfc_step": ChunkType.BLOCK,
    "sfc_initial_step": ChunkType.BLOCK,
}
```

---

## Metadata Schema for TwinCAT Chunks

Each extracted chunk should include rich metadata for searchability:

```python
{
    # Required
    "kind": str,              # Semantic type (see mappings above)

    # POU-specific
    "pou_type": str,          # Original: "PROGRAM", "FUNCTION_BLOCK", "FUNCTION"
    "extends": str | None,    # Parent FB for inheritance
    "implements": list[str],  # Implemented interfaces

    # Variable-specific
    "var_class": str,         # "input", "output", "in_out", "local", "temp", "static", "global"
    "data_type": str,         # "BOOL", "INT", "REAL", "ST_MotorData", etc.
    "initial_value": str | None,  # ":= 0", ":= FALSE", etc.
    "hw_address": str | None, # "%IX0.0", "%QW100", etc.
    "retain": bool,           # RETAIN qualifier
    "persistent": bool,       # PERSISTENT qualifier
    "constant": bool,         # CONSTANT qualifier

    # OOP-specific
    "visibility": str,        # "PUBLIC", "PRIVATE", "PROTECTED"
    "abstract": bool,         # ABSTRACT modifier
    "final": bool,            # FINAL modifier

    # SFC-specific
    "action_qualifier": str,  # "N", "R", "S", "P", "D", "L", etc.
}
```

---

## Hardware Engineer Search Patterns

The mapping should support natural searches by PLC engineers:

| Search Query | Expected Results |
|--------------|------------------|
| `"FB_Motor"` | FUNCTION_BLOCK definitions |
| `"VAR_INPUT"` | Input fields across all FBs |
| `"PROGRAM Main"` | Main program entry point |
| `"E_State"` | Enum types |
| `"ST_Recipe"` | Struct types |
| `"%QW100"` | Output word at address 100 |
| `"TON"` or `"timer"` | Timer instances |
| `"PERSISTENT"` | Retained variables |

---

## File Format Handling

### TcPOU (TwinCAT POU files)

```xml
<TcPlcObject>
  <POU Name="FB_Motor" SpecialFunc="None">
    <Declaration><!-- ST declarations --></Declaration>
    <Implementation><ST><!-- ST code --></ST></Implementation>
  </POU>
</TcPlcObject>
```

**Extraction strategy:**
1. Parse XML to get POU name, type, attributes
2. Extract Declaration CDATA → parse with `declarations.lark`
3. Extract Implementation/ST CDATA → parse with `implementation.lark`

### TcGVL (Global Variable Lists)

```xml
<TcPlcObject>
  <GVL Name="GVL_Main">
    <Declaration><!-- VAR_GLOBAL block --></Declaration>
  </GVL>
</TcPlcObject>
```

### TcDUT (Data Unit Types)

```xml
<TcPlcObject>
  <DUT Name="ST_Motor">
    <Declaration><!-- TYPE...END_TYPE --></Declaration>
  </DUT>
</TcPlcObject>
```

---

## Summary: Key Decisions

| Decision | Rationale |
|----------|-----------|
| **Add PROGRAM ChunkType** | Cyclic execution unit is fundamentally different from stateless function |
| **Add FUNCTION_BLOCK ChunkType** | Core IEC concept, not semantically equivalent to "class" |
| **Add ACTION ChunkType** | Has qualifier semantics not captured by "method" |
| **Keep STRUCT for types** | Maps well - both represent data-only structures |
| **Use FIELD for VAR_* in POUs** | Variables declared inside a POU are member fields |
| **Use VARIABLE for VAR_GLOBAL** | Standalone global, not a member of anything |
| **Use BLOCK for SFC steps** | Steps are scoped code regions |
| **Store var_class in metadata** | Preserves input/output/in_out distinction for searching |

---

## Language Enum Addition

Add to `chunkhound/core/types/common.py`:

```python
class Language(Enum):
    # ... existing languages ...
    STRUCTURED_TEXT = "structured_text"  # IEC 61131-3 Structured Text
    TWINCAT = "twincat"                  # TwinCAT POU files (XML + ST)
```

File extension mappings:
- `.st` → STRUCTURED_TEXT (raw ST files)
- `.TcPOU` → TWINCAT (TwinCAT POU)
- `.TcGVL` → TWINCAT (Global Variable List)
- `.TcDUT` → TWINCAT (Data Unit Type)
