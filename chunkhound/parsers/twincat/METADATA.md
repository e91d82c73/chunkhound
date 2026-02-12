# TcPOU XML Metadata Extraction Specification

## Overview

This specification defines all metadata fields available in TcPOU XML files that exist **outside** CDATA sections. These fields should be extracted and made available for downstream processing.

---

## 1. General TcPOU Metadata

| Element | Attribute | Type | Description | Example |
|---------|-----------|------|-------------|---------|
| `<?xml ?>` | `version` | string | XML version | `"1.0"` |
| `<?xml ?>` | `encoding` | string | Character encoding | `"utf-8"` |
| `<TcPlcObject>` | `Version` | string | TcPlcObject schema version | `"1.1.0.1"` |
| `<TcPlcObject>` | `ProductVersion` | string | TwinCAT product version | `"3.1.4020.3"`, `"3.1.4018.10"` |
| `<POU>` | `Name` | string | POU identifier name | `"FB_MotorController"`, `"PRG_Main"` |
| `<POU>` | `Id` | GUID | Unique identifier for POU | `"{a1b2c3d4-e5f6-7890-abcd-ef1234567890}"` |
| `<POU>` | `SpecialFunc` | string | Special function designation | `"None"` |

**Evidence:**
```xml
<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1" ProductVersion="3.1.4020.3">
  <POU Name="FB_MotorController" Id="{a1b2c3d4-e5f6-7890-abcd-ef1234567890}" SpecialFunc="None">
```

---

## 2. Declaration Metadata

| Element | Attribute | Type | Description | Example |
|---------|-----------|------|-------------|---------|
| `<Declaration>` | *(none)* | — | Container only - no attributes | N/A |

**Structure:** The `<Declaration>` element is a container with no attributes. Contains a CDATA section with ST declaration code.

**Evidence:**
```xml
    <Declaration><![CDATA[FUNCTION_BLOCK FB_MotorController
VAR_INPUT
	bEnable   : BOOL;
END_VAR
]]></Declaration>
```

**Note:** POU type (PROGRAM, FUNCTION_BLOCK, FUNCTION) must be derived from parsing the CDATA content.

---

## 3. Implementation Metadata

| Element | Attribute | Type | Description | Example |
|---------|-----------|------|-------------|---------|
| `<Implementation>` | *(none)* | — | Container only - no attributes | N/A |
| `<ST>` | *(none)* | — | Structured Text container - no attributes | N/A |
| `<NWL>` | *(complex)* | — | Network List (FBD/Ladder) - nested XML structure | See below |

**Structure:** The `<Implementation>` element contains either:
1. `<ST>` — Structured Text implementation (CDATA with ST code)
2. `<NWL>` — Network List (graphical programming - FBD/Ladder)

**ST Evidence:**
```xml
    <Implementation>
      <ST><![CDATA[tRunTimer(IN := bEnable, PT := tMaxTime);
]]></ST>
    </Implementation>
```

**NWL Structure:**
```xml
<Implementation>
  <NWL>
    <XmlArchive>
      <Data>
        <o xml:space="preserve" t="NWLImplementationObject">
          <v n="NetworkListComment">""</v>
          <v n="DefaultViewMode">"Fbd"</v>
          <l2 n="NetworkList" cet="Network">
            ...
          </l2>
        </o>
      </Data>
    </XmlArchive>
  </NWL>
</Implementation>
```

---

## 4. Method Metadata

### 4.1 General Method Metadata

| Element | Attribute | Type | Description | Example |
|---------|-----------|------|-------------|---------|
| `<Method>` | `Name` | string | Method name | `"Start"`, `"GetStatus"` |
| `<Method>` | `Id` | GUID | Unique identifier for method | `"{12345678-abcd-ef01-2345-6789abcdef01}"` |

### 4.2 Method Declaration Metadata

| Element | Attribute | Type | Description |
|---------|-----------|------|-------------|
| `<Declaration>` | *(none)* | — | Container for method signature and local variables (CDATA) |

### 4.3 Method Implementation Metadata

| Element | Attribute | Type | Description |
|---------|-----------|------|-------------|
| `<Implementation>` | *(none)* | — | Container only |
| `<ST>` | *(none)* | — | Method body (CDATA) |

**Evidence:**
```xml
    <Method Name="Start" Id="{12345678-abcd-ef01-2345-6789abcdef01}">
      <Declaration><![CDATA[METHOD Start : BOOL
VAR_INPUT
	nChannel : UINT := 1;
END_VAR
VAR
	sCommand : STRING := 'RUN';
END_VAR]]></Declaration>
      <Implementation>
        <ST><![CDATA[IF GVL.OutputBuffer[nChannel].bReady = FALSE THEN
	GVL.OutputBuffer[nChannel].sData := sCommand;
END_IF]]></ST>
      </Implementation>
    </Method>
```

---

## 5. Action Metadata

### 5.1 General Action Metadata

| Element | Attribute | Type | Description | Example |
|---------|-----------|------|-------------|---------|
| `<Action>` | `Name` | string | Action name | `"ACT_ScaleOutput"` |
| `<Action>` | `Id` | GUID | Unique identifier for action | `"{fedcba98-7654-3210-fedc-ba9876543210}"` |

### 5.2 Action Declaration Metadata

| Element | Attribute | Type | Description |
|---------|-----------|------|-------------|
| `<Declaration>` | *(none)* | — | Optional container for action-local variables (CDATA) |

**Note:** Actions rarely have Declaration sections. The XML schema supports them, but they are uncommon in practice.

### 5.3 Action Implementation Metadata

| Element | Attribute | Type | Description |
|---------|-----------|------|-------------|
| `<Implementation>` | *(none)* | — | Container only |
| `<ST>` | *(none)* | — | Structured Text (CDATA) |
| `<NWL>` | *(complex)* | — | Network List with nested structure |

**Evidence:**
```xml
    <Action Name="ACT_ScaleOutput" Id="{fedcba98-7654-3210-fedc-ba9876543210}">
      <Implementation>
        <ST><![CDATA[
	rScaledValue := nRawInput * 10000 / 32768;
	rApproxValue := nRawInputB * 10000 / 32768;
]]></ST>
      </Implementation>
    </Action>
```

---

## 6. Complete XML Structure Reference

```
TcPOU File
├── <?xml version="1.0" encoding="utf-8"?>
└── <TcPlcObject Version="..." ProductVersion="...">
    └── <POU Name="..." Id="{...}" SpecialFunc="...">
        ├── <Declaration><![CDATA[...]]></Declaration>
        ├── <Implementation>
        │   └── <ST><![CDATA[...]]></ST>          (or <NWL>...</NWL>)
        ├── <Method Name="..." Id="{...}">        (0..N methods)
        │   ├── <Declaration><![CDATA[...]]></Declaration>
        │   └── <Implementation>
        │       └── <ST><![CDATA[...]]></ST>
        └── <Action Name="..." Id="{...}">        (0..N actions)
            ├── <Declaration><![CDATA[...]]></Declaration>  (optional)
            └── <Implementation>
                └── <ST><![CDATA[...]]></ST>      (or <NWL>...</NWL>)
```

---

## 7. Metadata Extraction Requirements

### Required Fields

| Scope | Field | Priority |
|-------|-------|----------|
| TcPOU | TcPlcObject Version | High |
| TcPOU | TcPlcObject ProductVersion | High |
| TcPOU | POU Name | Critical |
| TcPOU | POU Id | Critical |
| TcPOU | POU SpecialFunc | Medium |
| Method | Name | Critical |
| Method | Id | Critical |
| Method | Declaration content | Critical |
| Method | Declaration location | High |
| Method | Implementation content | Critical |
| Method | Implementation location | High |
| Action | Name | Critical |
| Action | Id | Critical |
| Action | Declaration content | High |
| Action | Declaration location | High |
| Action | Implementation content | Critical |
| Action | Implementation location | High |

### Location Tracking

For each CDATA section, track:
- `line` — 1-indexed line number where content starts
- `column` — 1-indexed column where content starts
- `pos` — 0-indexed character offset in the XML file

### Implementation Type Detection

The implementation should detect and report:
- `ST` — Structured Text (parseable)
- `NWL` — Network List/FBD (not parseable as ST)
