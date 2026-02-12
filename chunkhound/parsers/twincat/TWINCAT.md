# TcPOU File Format and Its Relationship to Structured Text

## What is TcPOU?

**TcPOU** (TwinCAT POU) is an XML-based file format used by **Beckhoff TwinCAT** (a PLC development environment) to store Program Organization Units (POUs). POUs are the fundamental building blocks of IEC 61131-3 compliant PLC programs.

## File Structure

A TcPOU file is an XML document with this general structure:

```xml
<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Example" Id="{guid}" SpecialFunc="None">
    <Declaration><![CDATA[
      FUNCTION_BLOCK FB_Example
      VAR_INPUT
          bStart : BOOL;
      END_VAR
      VAR_OUTPUT
          bDone : BOOL;
      END_VAR
      VAR
          nCounter : INT;
      END_VAR
    ]]></Declaration>
    <Implementation>
      <ST><![CDATA[
        IF bStart THEN
            nCounter := nCounter + 1;
            IF nCounter >= 100 THEN
                bDone := TRUE;
            END_IF
        END_IF
      ]]></ST>
    </Implementation>
  </POU>
</TcPlcObject>
```

## Key Components

| Element | Purpose |
|---------|---------|
| `<TcPlcObject>` | Root element with version info |
| `<POU>` | Contains the POU definition (Name, Id, SpecialFunc attributes) |
| `<Declaration>` | Variable declarations in IEC 61131-3 syntax |
| `<Implementation>` | The actual code logic |
| `<ST>` | Structured Text code (inside `<Implementation>`) |
| `<Action>` | Sub-routine within a POU (optional, can have multiple) |
| `<![CDATA[...]]>` | Wraps ST code to preserve special characters |

## Actions

**Actions** are sub-routines within a POU (PROGRAM or FUNCTION_BLOCK) that encapsulate reusable logic. They can have their own local variables and can access all variables from the parent POU.

### Action XML Structure

Actions appear as child elements of `<POU>`, after the main Declaration and Implementation:

```xml
<POU Name="FB_Motor" Id="{guid}" SpecialFunc="None">
  <Declaration><![CDATA[
    FUNCTION_BLOCK FB_Motor
    VAR
        bRunning : BOOL;
    END_VAR
  ]]></Declaration>
  <Implementation>
    <ST><![CDATA[
      // Main implementation
    ]]></ST>
  </Implementation>

  <!-- Actions follow the main implementation -->
  <Action Name="Start" Id="{guid}">
    <Implementation>
      <ST><![CDATA[
        bRunning := TRUE;
      ]]></ST>
    </Implementation>
  </Action>

  <Action Name="Stop" Id="{guid}">
    <Declaration><![CDATA[
      VAR
        nDelay : INT := 100;
      END_VAR
    ]]></Declaration>
    <Implementation>
      <ST><![CDATA[
        // Action with local variable
        bRunning := FALSE;
      ]]></ST>
    </Implementation>
  </Action>
</POU>
```

### Action Characteristics

| Aspect | Description |
|--------|-------------|
| **Declaration** | Optional - actions may have no local variables |
| **Implementation** | Required - must contain `<ST>` (or other language) |
| **Variable Access** | Can access all parent POU variables |
| **Declaration Content** | Only VAR blocks (no POU header like `FUNCTION_BLOCK`) |
| **Scope** | Local variables exist only during action execution |

### Calling Actions in ST Code

Actions are called using the action name directly within the parent POU:

```iecst
// Inside FB_Motor implementation
IF bEnable THEN
    Start();      // Calls the Start action
ELSE
    Stop();       // Calls the Stop action
END_IF
```

From outside the function block instance:

```iecst
// Calling action on an instance
fbMotor1.Start();
fbMotor1.Stop();
```

## POU Types

The `<POU>` element can represent:

1. **PROGRAM** - Main executable unit
2. **FUNCTION_BLOCK** - Reusable block with state (instance data)
3. **FUNCTION** - Stateless, returns a value

## Relationship to Structured Text (ST)

**Structured Text** is one of five IEC 61131-3 programming languages:

| Language | Type | Description |
|----------|------|-------------|
| **ST** (Structured Text) | Textual | Pascal-like high-level language |
| **IL** (Instruction List) | Textual | Assembly-like (deprecated in IEC 61131-3 Ed.3) |
| **LD** (Ladder Diagram) | Graphical | Relay logic representation |
| **FBD** (Function Block Diagram) | Graphical | Data flow diagrams |
| **SFC** (Sequential Function Chart) | Graphical | State machine representation |

### How ST Fits in TcPOU

The `<Implementation>` section can contain different language elements:

```xml
<!-- Structured Text -->
<Implementation>
  <ST><![CDATA[ ... ST code ... ]]></ST>
</Implementation>

<!-- Ladder Diagram (stored as XML) -->
<Implementation>
  <LD> ... ladder XML ... </LD>
</Implementation>

<!-- Function Block Diagram -->
<Implementation>
  <FBD> ... FBD XML ... </FBD>
</Implementation>
```

## Structured Text Syntax Highlights

ST code inside TcPOU files follows IEC 61131-3 syntax:

```iecst
// Variable declarations (in <Declaration>)
FUNCTION_BLOCK FB_Motor
VAR_INPUT
    bEnable : BOOL;
    rSpeed  : REAL;
END_VAR
VAR_OUTPUT
    bRunning : BOOL;
    bFault   : BOOL;
END_VAR
VAR
    tonDelay : TON;  // Timer instance
END_VAR

// Implementation (in <ST>)
tonDelay(IN := bEnable, PT := T#2S);

IF tonDelay.Q THEN
    bRunning := TRUE;

    CASE nState OF
        0: (* Idle *)
            IF rSpeed > 0.0 THEN
                nState := 1;
            END_IF
        1: (* Running *)
            // Motor control logic
        2: (* Stopping *)
            bRunning := FALSE;
    END_CASE
END_IF
```

## Key ST Language Features

- **Control structures**: `IF/THEN/ELSE`, `CASE`, `FOR`, `WHILE`, `REPEAT`
- **Data types**: `BOOL`, `INT`, `REAL`, `STRING`, `TIME`, `ARRAY`, `STRUCT`
- **Operators**: `:=` (assignment), `AND`, `OR`, `NOT`, `+`, `-`, `*`, `/`, `MOD`
- **Comments**: `(* block *)` or `// line`
- **Timers/Counters**: `TON`, `TOF`, `CTU`, `CTD` (standard function blocks)

## Why This Format?

1. **IDE Integration** - TwinCAT XAE (Visual Studio-based) reads/writes these files
2. **Version Control** - XML is text-based, enabling diff/merge in Git
3. **Portability** - Standardized format across TwinCAT projects
4. **Mixed Languages** - Same file structure regardless of implementation language

## Summary

TcPOU is a **container format** that wraps IEC 61131-3 code. Structured Text is the **most common language** stored within it, appearing inside `<ST>` tags wrapped in CDATA sections. The XML structure separates metadata (name, GUID) from declarations (variables) and implementation (logic), making it both machine-readable and human-editable.
