# TwinCAT 3 Structured Text Operator Precedence

Source: [Beckhoff InfoSys - Operators](https://infosys.beckhoff.com/content/1033/tc3_plc_intro/2528237963.html)

## Precedence Table (Strongest to Weakest)

| Precedence | Operators | Description |
|------------|-----------|-------------|
| 1 (Highest) | `()` | Parentheses (explicit grouping) |
| 2 | Function calls | All operators with syntax `<Operator>()` |
| 3 | `EXPT` | Exponentiation |
| 4 | `-` (unary), `NOT` | Negation, Bitwise/Boolean complement |
| 5 | `*`, `/`, `MOD` | Multiplication, Division, Modulo |
| 6 | `+`, `-` (binary) | Addition, Subtraction |
| 7 | `<`, `>`, `<=`, `>=` | Comparison operators |
| 8 | `=`, `<>` | Equality, Inequality |
| 9 | `AND`, `AND_THEN` | Boolean/Bitwise AND |
| 10 (Lowest) | `XOR`, `OR`, `OR_ELSE` | Boolean/Bitwise XOR, OR |

## Associativity

Operators with the same precedence level are evaluated **left to right**.

## Short-Circuit Evaluation

- `AND_THEN`: Right operand is only evaluated if the left operand is TRUE
- `OR_ELSE`: Right operand is only evaluated if the left operand is FALSE

## Examples

```st
// Exponentiation binds tighter than unary minus
-2 EXPT 2    // Evaluates as -(2^2) = -4, not (-2)^2 = 4

// Multiplication before addition
2 + 3 * 4    // Evaluates as 2 + (3*4) = 14

// Comparison before equality
a < b = c < d    // Evaluates as (a < b) = (c < d)

// AND before OR
a OR b AND c     // Evaluates as a OR (b AND c)
```
