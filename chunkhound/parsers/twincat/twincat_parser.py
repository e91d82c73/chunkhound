"""TwinCAT Structured Text parser for ChunkHound.

Architecture: Custom Orchestration (like Svelte/Vue)
- Uses Lark for parsing (not tree-sitter)
- Directly processes lark.Tree and lark.Token objects (no AST transformation)
- Handles multi-section XML files (declaration + implementation)
- Adjusts line numbers from CDATA-relative to XML-absolute
"""

from pathlib import Path
from typing import Any

from lark import Lark, Token, Tree
from lark.exceptions import LarkError
from loguru import logger

from chunkhound.core.models.chunk import Chunk
from chunkhound.core.types.common import (
    ChunkType,
    FileId,
    FilePath,
    Language,
    LineNumber,
)
from chunkhound.parsers.twincat.xml_extractor import (
    ActionContent,
    POUContent,
    SourceLocation,
    TcPOUExtractor,
)
from chunkhound.parsers.universal_parser import CASTConfig

# Map VAR block keywords to semantic variable classes
VAR_BLOCK_MAP = {
    "VAR_INPUT": "input",
    "VAR_OUTPUT": "output",
    "VAR_IN_OUT": "in_out",
    "VAR_GLOBAL": "global",
    "VAR_EXTERNAL": "external",
    "VAR_TEMP": "temp",
    "VAR_STAT": "static",
    "VAR": "local",
}


class TwinCATParser:
    """Parser for TwinCAT TcPOU files.

    Directly processes Lark parse trees (Tree/Token objects) without
    AST transformation to extract semantic chunks.
    """

    def __init__(self, cast_config: CASTConfig | None = None) -> None:
        self._grammar_dir = Path(__file__).parent
        self._decl_parser: Lark | None = None
        self._impl_parser: Lark | None = None
        self._extractor = TcPOUExtractor()
        self.cast_config = cast_config or CASTConfig()
        self._parse_errors: list[str] = []

    @property
    def parse_errors(self) -> list[str]:
        """Errors from the most recent parse operation. Cleared on each parse."""
        return self._parse_errors

    @property
    def decl_parser(self) -> Lark:
        """Lazy-load declaration parser."""
        if self._decl_parser is None:
            grammar_path = self._grammar_dir / "declarations.lark"
            self._decl_parser = Lark.open(
                str(grammar_path),
                parser="lalr",
                propagate_positions=True,
            )
        return self._decl_parser

    @property
    def impl_parser(self) -> Lark:
        """Lazy-load implementation parser.

        Note: Not currently used - implementation code is extracted as raw text.
        Reserved for future use when full ST implementation parsing is added.
        """
        if self._impl_parser is None:
            grammar_path = self._grammar_dir / "implementation.lark"
            self._impl_parser = Lark.open(
                str(grammar_path),
                parser="lalr",
                propagate_positions=True,
            )
        return self._impl_parser

    def parse_file(self, file_path: Path, file_id: FileId) -> list[Chunk]:
        """Parse TcPOU file and return ChunkHound Chunk objects."""
        content = self._extractor.extract_file(file_path)
        return self._process_pou_content(content, file_path, file_id)

    def parse_content(
        self,
        content: str,
        file_path: Path | None = None,
        file_id: FileId | None = None,
    ) -> list[Chunk]:
        """Parse TcPOU XML string."""
        pou_content = self._extractor.extract_string(content)
        return self._process_pou_content(pou_content, file_path, file_id)

    def _process_pou_content(
        self,
        content: POUContent,
        file_path: Path | None,
        file_id: FileId | None,
    ) -> list[Chunk]:
        """Process extracted POU content into chunks."""
        self._parse_errors = []  # Clear errors at start of each parse
        chunks: list[Chunk] = []

        # 1. Create main POU chunk (the whole PROGRAM/FUNCTION_BLOCK/FUNCTION)
        pou_chunk = self._create_pou_chunk(content, file_path, file_id)
        if pou_chunk:
            chunks.append(pou_chunk)

        # 2. Parse declaration section → extract variable chunks
        if content.declaration and content.declaration.strip():
            try:
                decl_tree = self.decl_parser.parse(content.declaration)
                var_chunks = self._extract_variable_chunks_from_tree(
                    decl_tree, content, file_path, file_id
                )
                chunks.extend(var_chunks)
            except LarkError as e:
                error_msg = f"Declaration parse error in {content.name}: {e}"
                logger.error(error_msg)
                self._parse_errors.append(error_msg)

        # 3. Parse actions → create action chunks
        for action in content.actions:
            action_chunks = self._extract_action_chunks(
                action, content, file_path, file_id
            )
            chunks.extend(action_chunks)

        return chunks

    def _create_pou_chunk(
        self,
        content: POUContent,
        file_path: Path | None,
        file_id: FileId | None,
    ) -> Chunk | None:
        """Create chunk for the main POU (PROGRAM/FUNCTION_BLOCK/FUNCTION)."""
        # Combine declaration + implementation as the POU code
        combined_code = content.declaration
        if content.implementation and content.implementation.strip():
            combined_code += "\n\n" + content.implementation

        if not combined_code.strip():
            return None

        # Use XML locations for accurate line numbers
        start_line = 1
        if content.declaration_location:
            start_line = content.declaration_location.line

        # Calculate end line from the combined content
        end_line = start_line + combined_code.count("\n")

        # Map POU type to ChunkType
        pou_type = content.pou_type.upper()
        if pou_type == "PROGRAM":
            chunk_type = ChunkType.PROGRAM
        elif pou_type == "FUNCTION_BLOCK":
            chunk_type = ChunkType.FUNCTION_BLOCK
        elif pou_type == "FUNCTION":
            chunk_type = ChunkType.FUNCTION
        else:
            chunk_type = ChunkType.BLOCK

        return Chunk(
            symbol=content.name,
            start_line=LineNumber(start_line),
            end_line=LineNumber(end_line),
            code=combined_code,
            chunk_type=chunk_type,
            file_id=file_id or FileId(0),
            language=Language.TWINCAT,
            file_path=FilePath(str(file_path)) if file_path else None,
            metadata={
                "kind": pou_type.lower(),
                "pou_type": pou_type,
                "pou_name": content.name,
                "pou_id": content.id,
            },
        )

    def _extract_variable_chunks_from_tree(
        self,
        tree: Tree,
        content: POUContent,
        file_path: Path | None,
        file_id: FileId | None,
        declaration_location: SourceLocation | None = None,
        action_name: str | None = None,
    ) -> list[Chunk]:
        """Walk Lark tree and extract VARIABLE chunks from VAR blocks.

        Directly traverses tree.children looking for:
        - tree.data == "var_block" → extract block type and variables
        - tree.data == "var_declaration" → extract variable name, type, metadata

        Args:
            tree: Lark parse tree of the declaration
            content: Parent POU content (for pou_type, pou_name metadata)
            file_path: Path to source file
            file_id: Database file ID
            declaration_location: Location of declaration in XML. Defaults to
                content.declaration_location if not provided.
            action_name: If extracting from an action, the action name for metadata
        """
        chunks: list[Chunk] = []

        # Use provided location or fall back to POU declaration location
        location = declaration_location or content.declaration_location

        # Find all var_block nodes
        var_blocks = self._find_nodes(tree, "var_block")

        for var_block in var_blocks:
            # Extract var class from var_block_start
            var_class = "local"  # default
            retain = False
            persistent = False

            for child in var_block.children:
                if isinstance(child, Tree):
                    if child.data == "var_block_start":
                        # Get the token that indicates the var type
                        for token in child.children:
                            if isinstance(token, Token):
                                var_class = VAR_BLOCK_MAP.get(
                                    token.type, token.value.lower()
                                )
                                break
                    elif child.data == "var_qualifier":
                        # Check for RETAIN/PERSISTENT qualifiers
                        for token in child.children:
                            if isinstance(token, Token):
                                if token.type == "RETAIN":
                                    retain = True
                                elif token.type == "PERSISTENT":
                                    persistent = True
                    elif child.data == "var_declaration":
                        # Extract variable info
                        var_chunks = self._extract_var_declaration_chunk(
                            child,
                            content,
                            file_path,
                            file_id,
                            var_class,
                            retain,
                            persistent,
                            location,
                            action_name,
                        )
                        chunks.extend(var_chunks)

        return chunks

    def _extract_var_declaration_chunk(
        self,
        var_decl: Tree,
        content: POUContent,
        file_path: Path | None,
        file_id: FileId | None,
        var_class: str,
        retain: bool,
        persistent: bool,
        declaration_location: SourceLocation | None = None,
        action_name: str | None = None,
    ) -> list[Chunk]:
        """Extract chunk(s) from a var_declaration node.

        A single var_declaration can declare multiple variables:
        bFlag1, bFlag2, bFlag3 : BOOL;
        """
        chunks: list[Chunk] = []

        # Collect variable names (IDENTIFIERs before the colon)
        var_names: list[str] = []
        data_type: str | None = None
        hw_address: str | None = None

        # Get line number from node metadata
        line = var_decl.meta.line if hasattr(var_decl, "meta") and var_decl.meta else 1

        # Use provided location or fall back to POU declaration location
        location = declaration_location or content.declaration_location

        # Adjust line number to XML position
        adjusted_line = self._adjust_line_number(line, location)

        for child in var_decl.children:
            if isinstance(child, Token):
                if child.type == "IDENTIFIER" and data_type is None:
                    # This is a variable name
                    var_names.append(str(child))
            elif isinstance(child, Tree):
                if child.data == "hw_location":
                    # Extract hardware address
                    hw_addr_token = self._get_token_value(child, "HW_ADDRESS")
                    if hw_addr_token:
                        hw_address = hw_addr_token
                elif child.data == "type_spec":
                    # Extract data type
                    data_type = self._extract_type_spec(child)

        # Reconstruct the declaration code
        code = ", ".join(var_names)
        if hw_address:
            code += f" AT {hw_address}"
        code += f" : {data_type or 'UNKNOWN'};"

        # Determine ChunkType and kind based on variable scope (per MAPPING.md)
        # - VAR_GLOBAL, VAR_EXTERNAL → VARIABLE (standalone globals)
        # - All others (input, output, in_out, local, temp, static) → FIELD (members)
        if var_class in ("global", "external"):
            chunk_type = ChunkType.VARIABLE
            kind = "variable"
        else:
            chunk_type = ChunkType.FIELD
            kind = "field"

        # Build metadata - include action_name if this is an action variable
        metadata: dict[str, Any] = {
            "kind": kind,
            "pou_type": content.pou_type,
            "pou_name": content.name,
            "var_class": var_class,
            "data_type": data_type,
            "hw_address": hw_address,
            "retain": retain,
            "persistent": persistent,
        }
        if action_name:
            metadata["action_name"] = action_name

        # Create a chunk for each variable name
        for var_name in var_names:
            chunk = Chunk(
                symbol=var_name,
                start_line=LineNumber(adjusted_line),
                end_line=LineNumber(adjusted_line),
                code=code,
                chunk_type=chunk_type,
                file_id=file_id or FileId(0),
                language=Language.TWINCAT,
                file_path=FilePath(str(file_path)) if file_path else None,
                metadata=metadata.copy(),
            )
            chunks.append(chunk)

        return chunks

    def _extract_type_spec(self, type_spec: Tree) -> str:
        """Extract type specification as a string."""
        parts: list[str] = []

        for child in type_spec.children:
            if isinstance(child, Token):
                parts.append(str(child))
            elif isinstance(child, Tree):
                if child.data == "primitive_type":
                    # Get the token from primitive_type
                    for token in child.children:
                        if isinstance(token, Token):
                            parts.append(str(token))
                elif child.data == "string_type_with_size":
                    # STRING(80) or WSTRING[100]
                    parts.append(self._extract_string_type(child))
                elif child.data == "array_type":
                    parts.append(self._extract_array_type(child))
                elif child.data == "pointer_type":
                    parts.append(f"POINTER TO {self._extract_type_spec(child)}")
                elif child.data == "reference_type":
                    parts.append(f"REFERENCE TO {self._extract_type_spec(child)}")
                elif child.data == "user_type":
                    # User-defined type is just an IDENTIFIER
                    for token in child.children:
                        if isinstance(token, Token) and token.type == "IDENTIFIER":
                            parts.append(str(token))
                elif child.data == "type_spec":
                    # Nested type spec (for POINTER TO, REFERENCE TO)
                    parts.append(self._extract_type_spec(child))

        return " ".join(parts) if parts else "UNKNOWN"

    def _extract_string_type(self, string_type: Tree) -> str:
        """Extract STRING(n) or WSTRING[n] type."""
        type_name = "STRING"
        size: str | None = None

        for child in string_type.children:
            if isinstance(child, Token):
                if child.type == "STRING_TYPE":
                    type_name = "STRING"
                elif child.type == "WSTRING":
                    type_name = "WSTRING"
                elif child.type == "INTEGER":
                    size = str(child)

        if size:
            return f"{type_name}({size})"
        return type_name

    def _extract_array_type(self, array_type: Tree) -> str:
        """Extract ARRAY[...] OF type."""
        ranges: list[str] = []
        element_type = "UNKNOWN"

        for child in array_type.children:
            if isinstance(child, Tree):
                if child.data == "array_range":
                    ranges.append(self._extract_array_range(child))
                elif child.data == "type_spec":
                    element_type = self._extract_type_spec(child)

        return f"ARRAY[{', '.join(ranges)}] OF {element_type}"

    def _extract_array_range(self, array_range: Tree) -> str:
        """Extract array range like 0..9 or 1..MAX_SIZE."""
        bounds: list[str] = []

        for child in array_range.children:
            if isinstance(child, Tree):
                if child.data == "array_bound":
                    bounds.append(self._extract_array_bound(child))
                elif child.data == "integer_value":
                    bounds.append(self._extract_integer_value(child))
            elif isinstance(child, Token):
                if child.type == "IDENTIFIER":
                    bounds.append(str(child))

        return "..".join(bounds)

    def _extract_array_bound(self, bound: Tree) -> str:
        """Extract a single array bound."""
        for child in bound.children:
            if isinstance(child, Token):
                if child.type == "IDENTIFIER":
                    return str(child)
            elif isinstance(child, Tree):
                if child.data == "integer_value":
                    return self._extract_integer_value(child)

        return "0"

    def _extract_integer_value(self, int_val: Tree) -> str:
        """Extract integer value (may include sign)."""
        parts: list[str] = []

        for child in int_val.children:
            if isinstance(child, Token):
                parts.append(str(child))

        return "".join(parts)

    def _extract_action_chunks(
        self,
        action: ActionContent,
        content: POUContent,
        file_path: Path | None,
        file_id: FileId | None,
    ) -> list[Chunk]:
        """Create chunks for an action.

        Creates:
        1. An ACTION chunk containing the combined declaration + implementation
        2. VARIABLE chunks for any variables declared in the action
        """
        chunks: list[Chunk] = []

        # Combine action declaration and implementation
        action_code = ""
        if action.declaration:
            action_code = action.declaration

        if action.implementation and action.implementation.strip():
            if action_code:
                action_code += "\n\n"
            action_code += action.implementation

        if not action_code.strip():
            return chunks

        # Use action's declaration location for start_line if available,
        # since code includes both declaration and implementation
        start_line = 1
        if action.declaration_location:
            start_line = action.declaration_location.line
        elif action.implementation_location:
            start_line = action.implementation_location.line

        end_line = start_line + action_code.count("\n")

        # Create the main ACTION chunk
        chunk = Chunk(
            symbol=action.name,
            start_line=LineNumber(start_line),
            end_line=LineNumber(end_line),
            code=action_code,
            chunk_type=ChunkType.ACTION,
            file_id=file_id or FileId(0),
            language=Language.TWINCAT,
            file_path=FilePath(str(file_path)) if file_path else None,
            metadata={
                "kind": "action",
                "pou_type": content.pou_type,
                "pou_name": content.name,
                "action_id": action.id,
            },
        )
        chunks.append(chunk)

        # Parse action declaration for variables
        if action.declaration and action.declaration.strip():
            try:
                decl_tree = self.decl_parser.parse(action.declaration)
                var_chunks = self._extract_variable_chunks_from_tree(
                    decl_tree,
                    content,
                    file_path,
                    file_id,
                    declaration_location=action.declaration_location,
                    action_name=action.name,
                )
                chunks.extend(var_chunks)
            except LarkError as e:
                error_msg = f"Action '{action.name}' declaration parse error: {e}"
                logger.error(error_msg)
                self._parse_errors.append(error_msg)

        return chunks

    def _adjust_line_number(
        self, line: int, location: SourceLocation | None
    ) -> int:
        """Adjust line number from CDATA-relative to XML-absolute."""
        if location is None:
            return line
        return line + (location.line - 1)

    def _find_nodes(self, tree: Tree, rule_name: str) -> list[Tree]:
        """Recursively find all nodes with given rule name."""
        results: list[Tree] = []
        if isinstance(tree, Tree):
            if tree.data == rule_name:
                results.append(tree)
            for child in tree.children:
                if isinstance(child, Tree):
                    results.extend(self._find_nodes(child, rule_name))
        return results

    def _get_token_value(self, tree: Tree, token_type: str) -> str | None:
        """Find first token of given type in tree's children."""
        for child in tree.children:
            if isinstance(child, Token) and child.type == token_type:
                return str(child)
        return None
