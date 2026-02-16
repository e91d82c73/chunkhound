## TwinCAT FQN Hierarchy Design

### Hierarchy Levels (Root to Leaf)

```
[Namespace] → [POU Name] → [Member Name] → [Nested Element]
```

---

### 1. Program Organization Units (POUs)

| Concept | FQN Pattern | Example |
|---------|-------------|---------|
| **PROGRAM** | `Namespace.ProgramName` | `Motion.Main` |
| **FUNCTION_BLOCK** | `Namespace.FBName` | `Drives.FB_Motor` |
| **FUNCTION** | `Namespace.FunctionName` | `Utils.FC_Clamp` |

**Hierarchy:** `Namespace` (optional) → `POU Name`

---

### 2. Variables (Declaration Section)

| Concept | FQN Pattern | Example |
|---------|-------------|---------|
| **VAR_INPUT** | `POUName.varName` | `FB_Motor.bEnable` |
| **VAR_OUTPUT** | `POUName.varName` | `FB_Motor.bRunning` |
| **VAR** | `POUName.varName` | `FB_Motor.nCounter` |
| **VAR_IN_OUT** | `POUName.varName` | `FB_Motor.refData` |
| **VAR_GLOBAL** | `GVL_Name.varName` | `GVL_Alarms.bSystemFault` |

**Hierarchy:** `Namespace` → `POU Name` → `Variable Name`

---

### 3. Methods (Inside FUNCTION_BLOCK)

| Concept | FQN Pattern | Example |
|---------|-------------|---------|
| **METHOD** | `FBName.MethodName` | `FB_Motor.Start` |
| **Method VAR_INPUT** | `FBName.MethodName.varName` | `FB_Motor.Start.rTargetSpeed` |

**Hierarchy:** `Namespace` → `FB Name` → `Method Name` → `Variable Name`

---

### 4. Properties (Inside FUNCTION_BLOCK)

| Concept | FQN Pattern | Example |
|---------|-------------|---------|
| **PROPERTY** | `FBName.PropertyName` | `FB_Motor.Speed` |
| **PROPERTY GET** | `FBName.PropertyName.GET` | `FB_Motor.Speed.GET` |
| **PROPERTY SET** | `FBName.PropertyName.SET` | `FB_Motor.Speed.SET` |

**Hierarchy:** `Namespace` → `FB Name` → `Property Name` → `Accessor`

---

### 5. Actions (Inside POUs)

| Concept | FQN Pattern | Example |
|---------|-------------|---------|
| **ACTION** | `POUName.ActionName` | `FB_Motor.ActReset` |

**Hierarchy:** `Namespace` → `POU Name` → `Action Name`

---

### 6. User-Defined Types (DUTs)

| Concept | FQN Pattern | Example |
|---------|-------------|---------|
| **STRUCT** | `Namespace.StructName` | `Types.ST_MotorData` |
| **Struct Field** | `StructName.fieldName` | `ST_MotorData.rSpeed` |
| **ENUM** | `Namespace.EnumName` | `Types.E_MotorState` |
| **Enum Value** | `EnumName.valueName` | `E_MotorState.Running` |
| **UNION** | `Namespace.UnionName` | `Types.U_DataWord` |
| **ALIAS** | `Namespace.AliasName` | `Types.T_Speed` |

**Hierarchy:** `Namespace` → `Type Name` → `Member Name`

---

### 7. Interfaces

| Concept | FQN Pattern | Example |
|---------|-------------|---------|
| **INTERFACE** | `Namespace.InterfaceName` | `Contracts.I_Drive` |
| **Interface Method** | `InterfaceName.MethodName` | `I_Drive.Start` |
| **Interface Property** | `InterfaceName.PropertyName` | `I_Drive.IsRunning` |

**Hierarchy:** `Namespace` → `Interface Name` → `Member Name`

---

### 8. Global Variable Lists (GVLs)

| Concept | FQN Pattern | Example |
|---------|-------------|---------|
| **GVL** | `Namespace.GVLName` | `Globals.GVL_System` |
| **GVL Variable** | `GVLName.varName` | `GVL_System.bEmergencyStop` |

**Hierarchy:** `Namespace` → `GVL Name` → `Variable Name`

---

### 9. Control Flow Blocks (Implementation)

| Concept | FQN Pattern | Example |
|---------|-------------|---------|
| **POU Block** | `POUName.{kind}_{line}` | `FC_Test.if_block_42` |
| **Action Block** | `POUName.ActionName.{kind}_{line}` | `FB_Motor.Reset.for_loop_15` |
| **Method Block** | `POUName.MethodName.{kind}_{line}` | `FB_Motor.Start.case_block_28` |

**Hierarchy:** `Namespace` → `POU Name` → [`Method Name` | `Action Name`] → `Block Kind_Line`

---

## Summary Table: FQN Hierarchy Depth

| Concept | Max Depth | Separator | Example FQN |
|---------|-----------|-----------|-------------|
| POU | 2 | `.` | `Motion.FB_Axis` |
| POU Variable | 3 | `.` | `Motion.FB_Axis.bEnabled` |
| Method | 3 | `.` | `FB_Axis.MoveAbsolute` |
| Method Variable | 4 | `.` | `FB_Axis.MoveAbsolute.rPosition` |
| Property | 3 | `.` | `FB_Axis.Position` |
| Property Accessor | 4 | `.` | `FB_Axis.Position.GET` |
| Action | 3 | `.` | `FB_Axis.ActHome` |
| Struct | 2 | `.` | `Types.ST_AxisData` |
| Struct Field | 3 | `.` | `Types.ST_AxisData.rVelocity` |
| Enum | 2 | `.` | `Types.E_AxisState` |
| Enum Value | 3 | `.` | `Types.E_AxisState.Moving` |
| Interface | 2 | `.` | `Contracts.I_Axis` |
| Interface Method | 3 | `.` | `Contracts.I_Axis.Home` |
| GVL Variable | 3 | `.` | `Globals.GVL_IO.bSensor1` |
| POU Block | 3 | `.` | `FC_Test.if_block_42` |
| Action Block | 4 | `.` | `FB_Motor.Reset.for_loop_15` |
| Method Block | 4 | `.` | `FB_Motor.Start.case_block_28` |

---

## Recommended Metadata Keys for Parser

Based on patterns in existing ChunkHound parsers, the TwinCAT parser should populate `metadata`:

```python
metadata = {
    "parent_name": "FB_Motor",           # Containing POU/Type
    "namespace": "Drives",               # TwinCAT namespace
    "pou_type": "FUNCTION_BLOCK",        # PROGRAM/FUNCTION_BLOCK/FUNCTION
    "var_section": "VAR_INPUT",          # For variables
    "kind": "method",                    # method/property/action/variable
}
```
