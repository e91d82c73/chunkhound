"""TwinCAT Structured Text parser for ChunkHound.

Architecture: Custom Orchestration (like Svelte/Vue)
- Uses Lark for parsing (not tree-sitter)
- Directly processes lark.Tree and lark.Token objects (no AST transformation)
- Handles multi-section XML files (declaration + implementation)
- Adjusts line numbers from CDATA-relative to XML-absolute
"""

import re
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
    MethodContent,
    POUContent,
    PropertyContent,
    SourceLocation,
    TcPOUExtractor,
)
from chunkhound.parsers.universal_engine import UniversalChunk, UniversalConcept
from chunkhound.parsers.universal_parser import CASTConfig

# Regex patterns for comment extraction
# Block comments: (* ... *)
BLOCK_COMMENT_RE = re.compile(r"\(\*[\s\S]*?\*\)")
# Line comments: // ...
LINE_COMMENT_RE = re.compile(r"//[^\n]*")

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

    # =========================================================================
    # UniversalChunk Extraction (for UniversalParser integration)
    # =========================================================================

    def extract_universal_chunks(
        self,
        content: str,
        file_path: Path | None = None,
    ) -> list[UniversalChunk]:
        """Extract UniversalChunk objects from TcPOU content.

        This method produces UniversalChunk objects that can flow through
        the UniversalParser's cAST pipeline for deduplication, comment
        merging, and greedy merge optimization.

        Args:
            content: TcPOU XML content string
            file_path: Optional path to the source file

        Returns:
            List of UniversalChunk objects
        """
        pou_content = self._extractor.extract_string(content)
        return self._process_pou_content_to_universal(pou_content, file_path)

    def _process_pou_content_to_universal(
        self,
        content: POUContent,
        file_path: Path | None,
    ) -> list[UniversalChunk]:
        """Process extracted POU content into UniversalChunk objects."""
        self._parse_errors = []  # Clear errors at start of each parse
        chunks: list[UniversalChunk] = []

        # 1. Create main POU chunk (the whole PROGRAM/FUNCTION_BLOCK/FUNCTION)
        pou_chunk = self._create_pou_universal_chunk(content, file_path)
        if pou_chunk:
            chunks.append(pou_chunk)

        # 2. Parse declaration section → extract variable chunks
        if content.declaration and content.declaration.strip():
            try:
                decl_tree = self.decl_parser.parse(content.declaration)
                var_chunks = self._extract_var_universal_chunks_from_tree(
                    decl_tree, content, file_path
                )
                chunks.extend(var_chunks)
            except LarkError as e:
                error_msg = f"Declaration parse error in {content.name}: {e}"
                logger.error(error_msg)
                self._parse_errors.append(error_msg)

        # 3. Parse implementation for control flow blocks (all POU types)
        if content.implementation and content.implementation.strip():
            block_chunks = self._extract_block_universal_chunks_from_implementation(
                content.implementation,
                content.implementation_location,
                content.name,
                content.pou_type.upper(),
                file_path,
            )
            chunks.extend(block_chunks)

        # 4. Extract comments from declaration and implementation
        decl_base_line = (
            content.declaration_location.line if content.declaration_location else 1
        )
        impl_base_line = (
            content.implementation_location.line
            if content.implementation_location
            else decl_base_line
        )

        if content.declaration and content.declaration.strip():
            comment_chunks = self._extract_comment_universal_chunks(
                content.declaration,
                file_path,
                content.name,
                content.pou_type.upper(),
                decl_base_line,
            )
            chunks.extend(comment_chunks)

        if content.implementation and content.implementation.strip():
            comment_chunks = self._extract_comment_universal_chunks(
                content.implementation,
                file_path,
                content.name,
                content.pou_type.upper(),
                impl_base_line,
            )
            chunks.extend(comment_chunks)

        # 5. Parse actions → create action chunks
        for action in content.actions:
            action_chunks = self._extract_action_universal_chunks(
                action, content, file_path
            )
            chunks.extend(action_chunks)

        # 6. Parse methods → create method chunks
        for method in content.methods:
            method_chunks = self._extract_method_universal_chunks(
                method, content, file_path
            )
            chunks.extend(method_chunks)

        # 7. Parse properties → create property chunks
        for prop in content.properties:
            property_chunks = self._extract_property_universal_chunks(
                prop, content, file_path
            )
            chunks.extend(property_chunks)

        return chunks

    def _map_chunk_type_to_concept(self, chunk_type: ChunkType) -> UniversalConcept:
        """Map TwinCAT ChunkType to UniversalConcept.

        Mapping:
        - PROGRAM, FUNCTION_BLOCK, FUNCTION → DEFINITION
        - METHOD, ACTION, PROPERTY → DEFINITION
        - VARIABLE, FIELD → DEFINITION
        - BLOCK (control flow) → BLOCK
        - COMMENT → COMMENT
        """
        if chunk_type in (
            ChunkType.PROGRAM,
            ChunkType.FUNCTION_BLOCK,
            ChunkType.FUNCTION,
            ChunkType.METHOD,
            ChunkType.ACTION,
            ChunkType.PROPERTY,
            ChunkType.VARIABLE,
            ChunkType.FIELD,
        ):
            return UniversalConcept.DEFINITION
        elif chunk_type == ChunkType.BLOCK:
            return UniversalConcept.BLOCK
        elif chunk_type == ChunkType.COMMENT:
            return UniversalConcept.COMMENT
        else:
            return UniversalConcept.DEFINITION  # Default for unknown types

    def _create_universal_chunk(
        self,
        chunk_type: ChunkType,
        name: str,
        content: str,
        start_line: int,
        end_line: int,
        metadata: dict[str, Any],
        language_node_type: str,
    ) -> UniversalChunk:
        """Create UniversalChunk from TwinCAT extraction data.

        Args:
            chunk_type: The TwinCAT ChunkType
            name: Symbol name for the chunk
            content: Code content
            start_line: Starting line number (1-based)
            end_line: Ending line number (1-based)
            metadata: Additional metadata dict
            language_node_type: Original node type (using "lark_{rule}" format)

        Returns:
            UniversalChunk instance
        """
        # Store original ChunkType name for accurate reverse mapping
        enriched_metadata = {
            **metadata,
            "chunk_type_hint": chunk_type.name.lower(),
        }

        return UniversalChunk(
            concept=self._map_chunk_type_to_concept(chunk_type),
            name=name,
            content=content,
            start_line=start_line,
            end_line=end_line,
            metadata=enriched_metadata,
            language_node_type=language_node_type,
        )

    def _create_pou_universal_chunk(
        self,
        content: POUContent,
        file_path: Path | None,
    ) -> UniversalChunk | None:
        """Create UniversalChunk for the main POU."""
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

        metadata = {
            "kind": pou_type.lower(),
            "pou_type": pou_type,
            "pou_name": content.name,
            "pou_id": content.id,
        }

        return self._create_universal_chunk(
            chunk_type=chunk_type,
            name=content.name,
            content=combined_code,
            start_line=start_line,
            end_line=end_line,
            metadata=metadata,
            language_node_type="lark_pou",
        )

    def _extract_var_universal_chunks_from_tree(
        self,
        tree: Tree,
        content: POUContent,
        file_path: Path | None,
        declaration_location: SourceLocation | None = None,
        action_name: str | None = None,
        method_name: str | None = None,
    ) -> list[UniversalChunk]:
        """Walk Lark tree and extract variable UniversalChunks from VAR blocks."""
        chunks: list[UniversalChunk] = []

        # Use provided location or fall back to POU declaration location
        location = declaration_location or content.declaration_location

        # Find all var_block nodes
        var_blocks = self._find_nodes(tree, "var_block")

        for var_block in var_blocks:
            # Extract var class from var_block_start
            var_class = "local"  # default
            retain = False
            persistent = False
            constant = False

            for child in var_block.children:
                if isinstance(child, Tree):
                    if child.data == "var_block_start":
                        for token in child.children:
                            if isinstance(token, Token):
                                var_class = VAR_BLOCK_MAP.get(
                                    token.type, token.value.lower()
                                )
                                break
                    elif child.data == "var_qualifier":
                        for token in child.children:
                            if isinstance(token, Token):
                                if token.type == "RETAIN":
                                    retain = True
                                elif token.type == "PERSISTENT":
                                    persistent = True
                                elif token.type == "CONSTANT":
                                    constant = True
                    elif child.data == "var_declaration":
                        var_chunks = self._extract_var_decl_universal_chunk(
                            child,
                            content,
                            file_path,
                            var_class,
                            retain,
                            persistent,
                            constant,
                            location,
                            action_name,
                            method_name,
                        )
                        chunks.extend(var_chunks)

        return chunks

    def _extract_var_decl_universal_chunk(
        self,
        var_decl: Tree,
        content: POUContent,
        file_path: Path | None,
        var_class: str,
        retain: bool,
        persistent: bool,
        constant: bool,
        declaration_location: SourceLocation | None = None,
        action_name: str | None = None,
        method_name: str | None = None,
    ) -> list[UniversalChunk]:
        """Extract UniversalChunk(s) from a var_declaration node."""
        chunks: list[UniversalChunk] = []

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
                    var_names.append(str(child))
            elif isinstance(child, Tree):
                if child.data == "hw_location":
                    hw_addr_token = self._get_token_value(child, "HW_ADDRESS")
                    if hw_addr_token:
                        hw_address = hw_addr_token
                elif child.data == "type_spec":
                    data_type = self._extract_type_spec(child)

        # Reconstruct the declaration code
        code = ", ".join(var_names)
        if hw_address:
            code += f" AT {hw_address}"
        code += f" : {data_type or 'UNKNOWN'};"

        # Determine ChunkType and kind based on variable scope
        if var_class in ("global", "external"):
            chunk_type = ChunkType.VARIABLE
            kind = "variable"
        else:
            chunk_type = ChunkType.FIELD
            kind = "field"

        # Build metadata
        metadata: dict[str, Any] = {
            "kind": kind,
            "pou_type": content.pou_type,
            "pou_name": content.name,
            "var_class": var_class,
            "data_type": data_type,
            "hw_address": hw_address,
            "retain": retain,
            "persistent": persistent,
            "constant": constant,
        }
        if action_name:
            metadata["action_name"] = action_name
        if method_name:
            metadata["method_name"] = method_name

        # Create a chunk for each variable name
        for var_name in var_names:
            fqn = self._build_fqn(content.name, var_name, method_name, action_name)
            chunk = self._create_universal_chunk(
                chunk_type=chunk_type,
                name=fqn,
                content=code,
                start_line=adjusted_line,
                end_line=adjusted_line,
                metadata=metadata.copy(),
                language_node_type="lark_var_declaration",
            )
            chunks.append(chunk)

        return chunks

    def _extract_action_universal_chunks(
        self,
        action: ActionContent,
        content: POUContent,
        file_path: Path | None,
    ) -> list[UniversalChunk]:
        """Create UniversalChunks for an action."""
        chunks: list[UniversalChunk] = []

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

        # Use action's declaration location for start_line
        start_line = 1
        if action.declaration_location:
            start_line = action.declaration_location.line
        elif action.implementation_location:
            start_line = action.implementation_location.line

        end_line = start_line + action_code.count("\n")

        # Create the main ACTION chunk
        metadata = {
            "kind": "action",
            "pou_type": content.pou_type,
            "pou_name": content.name,
            "action_id": action.id,
        }

        chunk = self._create_universal_chunk(
            chunk_type=ChunkType.ACTION,
            name=f"{content.name}.{action.name}",
            content=action_code,
            start_line=start_line,
            end_line=end_line,
            metadata=metadata,
            language_node_type="lark_action",
        )
        chunks.append(chunk)

        # Parse action declaration for variables
        if action.declaration and action.declaration.strip():
            try:
                decl_tree = self.decl_parser.parse(action.declaration)
                var_chunks = self._extract_var_universal_chunks_from_tree(
                    decl_tree,
                    content,
                    file_path,
                    declaration_location=action.declaration_location,
                    action_name=action.name,
                )
                chunks.extend(var_chunks)
            except LarkError as e:
                error_msg = f"Action '{action.name}' declaration parse error: {e}"
                logger.error(error_msg)
                self._parse_errors.append(error_msg)

        # Parse action implementation for control flow blocks
        if action.implementation and action.implementation.strip():
            block_chunks = self._extract_block_universal_chunks_from_implementation(
                action.implementation,
                action.implementation_location,
                content.name,
                content.pou_type.upper(),
                file_path,
                action_name=action.name,
            )
            chunks.extend(block_chunks)

        # Extract comments
        if action.declaration and action.declaration.strip():
            decl_base = (
                action.declaration_location.line
                if action.declaration_location
                else 1
            )
            comment_chunks = self._extract_comment_universal_chunks(
                action.declaration,
                file_path,
                content.name,
                content.pou_type.upper(),
                decl_base,
                action_name=action.name,
            )
            chunks.extend(comment_chunks)

        if action.implementation and action.implementation.strip():
            impl_base = (
                action.implementation_location.line
                if action.implementation_location
                else 1
            )
            comment_chunks = self._extract_comment_universal_chunks(
                action.implementation,
                file_path,
                content.name,
                content.pou_type.upper(),
                impl_base,
                action_name=action.name,
            )
            chunks.extend(comment_chunks)

        return chunks

    def _extract_method_universal_chunks(
        self,
        method: MethodContent,
        content: POUContent,
        file_path: Path | None,
    ) -> list[UniversalChunk]:
        """Create UniversalChunks for a method."""
        chunks: list[UniversalChunk] = []

        # Combine method declaration and implementation
        method_code = method.declaration
        if method.implementation and method.implementation.strip():
            if method_code:
                method_code += "\n\n"
            method_code += method.implementation

        if not method_code.strip():
            return chunks

        # Use method's declaration location for start_line
        start_line = 1
        if method.declaration_location:
            start_line = method.declaration_location.line
        elif method.implementation_location:
            start_line = method.implementation_location.line

        end_line = start_line + method_code.count("\n")

        # Create the main METHOD chunk
        metadata = {
            "kind": "method",
            "pou_type": content.pou_type,
            "pou_name": content.name,
            "method_id": method.id,
        }

        chunk = self._create_universal_chunk(
            chunk_type=ChunkType.METHOD,
            name=f"{content.name}.{method.name}",
            content=method_code,
            start_line=start_line,
            end_line=end_line,
            metadata=metadata,
            language_node_type="lark_method",
        )
        chunks.append(chunk)

        # Parse method declaration for variables
        if method.declaration and method.declaration.strip():
            try:
                decl_tree = self.decl_parser.parse(method.declaration)
                var_chunks = self._extract_var_universal_chunks_from_tree(
                    decl_tree,
                    content,
                    file_path,
                    declaration_location=method.declaration_location,
                    method_name=method.name,
                )
                chunks.extend(var_chunks)
            except LarkError as e:
                error_msg = f"Method '{method.name}' declaration parse error: {e}"
                logger.error(error_msg)
                self._parse_errors.append(error_msg)

        # Parse method implementation for control flow blocks
        if method.implementation and method.implementation.strip():
            block_chunks = self._extract_block_universal_chunks_from_implementation(
                method.implementation,
                method.implementation_location,
                content.name,
                content.pou_type.upper(),
                file_path,
                method_name=method.name,
            )
            chunks.extend(block_chunks)

        # Extract comments
        if method.declaration and method.declaration.strip():
            decl_base = (
                method.declaration_location.line
                if method.declaration_location
                else 1
            )
            comment_chunks = self._extract_comment_universal_chunks(
                method.declaration,
                file_path,
                content.name,
                content.pou_type.upper(),
                decl_base,
                method_name=method.name,
            )
            chunks.extend(comment_chunks)

        if method.implementation and method.implementation.strip():
            impl_base = (
                method.implementation_location.line
                if method.implementation_location
                else 1
            )
            comment_chunks = self._extract_comment_universal_chunks(
                method.implementation,
                file_path,
                content.name,
                content.pou_type.upper(),
                impl_base,
                method_name=method.name,
            )
            chunks.extend(comment_chunks)

        return chunks

    def _extract_property_universal_chunks(
        self,
        prop: PropertyContent,
        content: POUContent,
        file_path: Path | None,
    ) -> list[UniversalChunk]:
        """Create UniversalChunks for a property."""
        chunks: list[UniversalChunk] = []

        # Combine property declaration and accessor implementations
        property_code = prop.declaration

        if prop.get and prop.get.implementation and prop.get.implementation.strip():
            if property_code:
                property_code += "\n\n// GET\n"
            property_code += prop.get.implementation

        if prop.set and prop.set.implementation and prop.set.implementation.strip():
            if property_code:
                property_code += "\n\n// SET\n"
            property_code += prop.set.implementation

        if not property_code.strip():
            return chunks

        # Calculate start_line from property declaration location
        start_line = 1
        if prop.declaration_location:
            start_line = prop.declaration_location.line
        end_line = start_line + property_code.count("\n")

        # Create the main PROPERTY chunk
        metadata = {
            "kind": "property",
            "pou_type": content.pou_type,
            "pou_name": content.name,
            "property_id": prop.id,
            "has_get": prop.get is not None,
            "has_set": prop.set is not None,
        }

        chunk = self._create_universal_chunk(
            chunk_type=ChunkType.PROPERTY,
            name=f"{content.name}.{prop.name}",
            content=property_code,
            start_line=start_line,
            end_line=end_line,
            metadata=metadata,
            language_node_type="lark_property",
        )
        chunks.append(chunk)

        return chunks

    def _extract_block_universal_chunks_from_implementation(
        self,
        implementation: str,
        implementation_location: SourceLocation | None,
        pou_name: str,
        pou_type: str,
        file_path: Path | None,
        action_name: str | None = None,
        method_name: str | None = None,
    ) -> list[UniversalChunk]:
        """Extract control flow blocks as UniversalChunks."""
        chunks: list[UniversalChunk] = []

        try:
            tree = self.impl_parser.parse(implementation)
        except LarkError as e:
            if method_name:
                context = f"method '{method_name}'"
            elif action_name:
                context = f"action '{action_name}'"
            else:
                context = f"FUNCTION '{pou_name}'"
            error_msg = f"Implementation parse error in {context}: {e}"
            logger.error(error_msg)
            self._parse_errors.append(error_msg)
            return chunks

        # Find all control flow statement nodes
        statement_nodes = self._find_statement_nodes(tree)

        for node in statement_nodes:
            chunk = self._create_block_universal_chunk(
                node,
                implementation,
                implementation_location,
                pou_name,
                pou_type,
                file_path,
                action_name,
                method_name,
            )
            if chunk:
                chunks.append(chunk)

        return chunks

    def _create_block_universal_chunk(
        self,
        node: Tree,
        implementation: str,
        implementation_location: SourceLocation | None,
        pou_name: str,
        pou_type: str,
        file_path: Path | None,
        action_name: str | None,
        method_name: str | None = None,
    ) -> UniversalChunk | None:
        """Create UniversalChunk for a control flow block."""
        # Get line numbers from node metadata
        if not hasattr(node, "meta") or node.meta is None:
            return None

        start_line = node.meta.line
        end_line = node.meta.end_line or start_line

        # Reconstruct code from implementation using line numbers
        code = self._reconstruct_code_from_lines(implementation, start_line, end_line)

        # Adjust line numbers to XML-absolute
        adjusted_start = self._adjust_line_number(start_line, implementation_location)
        adjusted_end = self._adjust_line_number(end_line, implementation_location)

        # Determine kind from statement type
        kind = self._STATEMENT_KIND_MAP.get(node.data, "block")

        # Build FQN
        symbol = self._build_fqn(
            pou_name, f"{kind}_{adjusted_start}", method_name, action_name
        )

        # Build metadata
        metadata: dict[str, Any] = {
            "kind": kind,
            "pou_type": pou_type,
            "pou_name": pou_name,
        }
        if action_name:
            metadata["action_name"] = action_name
        if method_name:
            metadata["method_name"] = method_name

        return self._create_universal_chunk(
            chunk_type=ChunkType.BLOCK,
            name=symbol,
            content=code,
            start_line=adjusted_start,
            end_line=adjusted_end,
            metadata=metadata,
            language_node_type=f"lark_{node.data}",
        )

    def _extract_comment_universal_chunks(
        self,
        source: str,
        file_path: Path | None,
        pou_name: str,
        pou_type: str,
        base_line: int,
        method_name: str | None = None,
        action_name: str | None = None,
    ) -> list[UniversalChunk]:
        """Extract comments as UniversalChunks."""
        chunks: list[UniversalChunk] = []

        # Block comments: (* ... *)
        for match in BLOCK_COMMENT_RE.finditer(source):
            line = source[: match.start()].count("\n") + base_line
            chunk = self._create_comment_universal_chunk(
                content=match.group(),
                line=line,
                file_path=file_path,
                pou_name=pou_name,
                pou_type=pou_type,
                comment_type="block",
                method_name=method_name,
                action_name=action_name,
            )
            chunks.append(chunk)

        # Line comments: // ...
        for match in LINE_COMMENT_RE.finditer(source):
            line = source[: match.start()].count("\n") + base_line
            chunk = self._create_comment_universal_chunk(
                content=match.group(),
                line=line,
                file_path=file_path,
                pou_name=pou_name,
                pou_type=pou_type,
                comment_type="line",
                method_name=method_name,
                action_name=action_name,
            )
            chunks.append(chunk)

        return chunks

    def _create_comment_universal_chunk(
        self,
        content: str,
        line: int,
        file_path: Path | None,
        pou_name: str,
        pou_type: str,
        comment_type: str,
        method_name: str | None = None,
        action_name: str | None = None,
    ) -> UniversalChunk:
        """Create a comment UniversalChunk."""
        # Build FQN
        element_name = f"comment_line_{line}"
        fqn = self._build_fqn(pou_name, element_name, method_name, action_name)

        # Calculate end line for multi-line block comments
        end_line = line + content.count("\n")

        # Clean comment text (strip markers)
        cleaned_text = self._clean_st_comment(content)

        # Build metadata
        metadata: dict[str, Any] = {
            "kind": "comment",
            "comment_type": comment_type,
            "pou_name": pou_name,
            "pou_type": pou_type,
            "cleaned_text": cleaned_text,
        }
        if method_name:
            metadata["method_name"] = method_name
        if action_name:
            metadata["action_name"] = action_name

        return self._create_universal_chunk(
            chunk_type=ChunkType.COMMENT,
            name=fqn,
            content=content,
            start_line=line,
            end_line=end_line,
            metadata=metadata,
            language_node_type="lark_comment",
        )

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

        # 3. Parse implementation for control flow blocks (all POU types)
        if content.implementation and content.implementation.strip():
            block_chunks = self._extract_blocks_from_implementation(
                content.implementation,
                content.implementation_location,
                content.name,
                content.pou_type.upper(),
                file_path,
                file_id,
            )
            chunks.extend(block_chunks)

        # 4. Extract comments from declaration and implementation
        decl_base_line = (
            content.declaration_location.line if content.declaration_location else 1
        )
        impl_base_line = (
            content.implementation_location.line
            if content.implementation_location
            else decl_base_line
        )

        if content.declaration and content.declaration.strip():
            comment_chunks = self._extract_comment_chunks(
                content.declaration,
                file_path,
                file_id,
                content.name,
                content.pou_type.upper(),
                decl_base_line,
            )
            chunks.extend(comment_chunks)

        if content.implementation and content.implementation.strip():
            comment_chunks = self._extract_comment_chunks(
                content.implementation,
                file_path,
                file_id,
                content.name,
                content.pou_type.upper(),
                impl_base_line,
            )
            chunks.extend(comment_chunks)

        # 5. Parse actions → create action chunks
        for action in content.actions:
            action_chunks = self._extract_action_chunks(
                action, content, file_path, file_id
            )
            chunks.extend(action_chunks)

        # 6. Parse methods → create method chunks
        for method in content.methods:
            method_chunks = self._extract_method_chunks(
                method, content, file_path, file_id
            )
            chunks.extend(method_chunks)

        # 7. Parse properties → create property chunks
        for prop in content.properties:
            property_chunks = self._extract_property_chunks(
                prop, content, file_path, file_id
            )
            chunks.extend(property_chunks)

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
        method_name: str | None = None,
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
            method_name: If extracting from a method, the method name for metadata
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
            constant = False

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
                        # Check for RETAIN/PERSISTENT/CONSTANT qualifiers
                        for token in child.children:
                            if isinstance(token, Token):
                                if token.type == "RETAIN":
                                    retain = True
                                elif token.type == "PERSISTENT":
                                    persistent = True
                                elif token.type == "CONSTANT":
                                    constant = True
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
                            constant,
                            location,
                            action_name,
                            method_name,
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
        constant: bool,
        declaration_location: SourceLocation | None = None,
        action_name: str | None = None,
        method_name: str | None = None,
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

        # Build metadata - include action_name/method_name if in that context
        metadata: dict[str, Any] = {
            "kind": kind,
            "pou_type": content.pou_type,
            "pou_name": content.name,
            "var_class": var_class,
            "data_type": data_type,
            "hw_address": hw_address,
            "retain": retain,
            "persistent": persistent,
            "constant": constant,
        }
        if action_name:
            metadata["action_name"] = action_name
        if method_name:
            metadata["method_name"] = method_name

        # Create a chunk for each variable name
        for var_name in var_names:
            fqn = self._build_fqn(content.name, var_name, method_name, action_name)
            chunk = Chunk(
                symbol=fqn,
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
            symbol=f"{content.name}.{action.name}",
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

        # Parse action implementation for control flow blocks
        if action.implementation and action.implementation.strip():
            block_chunks = self._extract_blocks_from_implementation(
                action.implementation,
                action.implementation_location,
                content.name,
                content.pou_type.upper(),
                file_path,
                file_id,
                action_name=action.name,
            )
            chunks.extend(block_chunks)

        # Extract comments from action declaration and implementation
        if action.declaration and action.declaration.strip():
            decl_base = (
                action.declaration_location.line
                if action.declaration_location
                else 1
            )
            comment_chunks = self._extract_comment_chunks(
                action.declaration,
                file_path,
                file_id,
                content.name,
                content.pou_type.upper(),
                decl_base,
                action_name=action.name,
            )
            chunks.extend(comment_chunks)

        if action.implementation and action.implementation.strip():
            impl_base = (
                action.implementation_location.line
                if action.implementation_location
                else 1
            )
            comment_chunks = self._extract_comment_chunks(
                action.implementation,
                file_path,
                file_id,
                content.name,
                content.pou_type.upper(),
                impl_base,
                action_name=action.name,
            )
            chunks.extend(comment_chunks)

        return chunks

    def _extract_method_chunks(
        self,
        method: MethodContent,
        content: POUContent,
        file_path: Path | None,
        file_id: FileId | None,
    ) -> list[Chunk]:
        """Create chunks for a method.

        Creates:
        1. A METHOD chunk containing the combined declaration + implementation
        2. FIELD chunks for variables declared in the method
        3. BLOCK chunks for control flow statements in the method
        """
        chunks: list[Chunk] = []

        # Combine method declaration and implementation
        method_code = method.declaration
        if method.implementation and method.implementation.strip():
            if method_code:
                method_code += "\n\n"
            method_code += method.implementation

        if not method_code.strip():
            return chunks

        # Use method's declaration location for start_line
        start_line = 1
        if method.declaration_location:
            start_line = method.declaration_location.line
        elif method.implementation_location:
            start_line = method.implementation_location.line

        end_line = start_line + method_code.count("\n")

        # Create the main METHOD chunk
        chunk = Chunk(
            symbol=f"{content.name}.{method.name}",
            start_line=LineNumber(start_line),
            end_line=LineNumber(end_line),
            code=method_code,
            chunk_type=ChunkType.METHOD,
            file_id=file_id or FileId(0),
            language=Language.TWINCAT,
            file_path=FilePath(str(file_path)) if file_path else None,
            metadata={
                "kind": "method",
                "pou_type": content.pou_type,
                "pou_name": content.name,
                "method_id": method.id,
            },
        )
        chunks.append(chunk)

        # Parse method declaration for variables
        if method.declaration and method.declaration.strip():
            try:
                decl_tree = self.decl_parser.parse(method.declaration)
                var_chunks = self._extract_variable_chunks_from_tree(
                    decl_tree,
                    content,
                    file_path,
                    file_id,
                    declaration_location=method.declaration_location,
                    method_name=method.name,
                )
                chunks.extend(var_chunks)
            except LarkError as e:
                error_msg = f"Method '{method.name}' declaration parse error: {e}"
                logger.error(error_msg)
                self._parse_errors.append(error_msg)

        # Parse method implementation for control flow blocks
        if method.implementation and method.implementation.strip():
            block_chunks = self._extract_blocks_from_implementation(
                method.implementation,
                method.implementation_location,
                content.name,
                content.pou_type.upper(),
                file_path,
                file_id,
                method_name=method.name,
            )
            chunks.extend(block_chunks)

        # Extract comments from method declaration and implementation
        if method.declaration and method.declaration.strip():
            decl_base = (
                method.declaration_location.line
                if method.declaration_location
                else 1
            )
            comment_chunks = self._extract_comment_chunks(
                method.declaration,
                file_path,
                file_id,
                content.name,
                content.pou_type.upper(),
                decl_base,
                method_name=method.name,
            )
            chunks.extend(comment_chunks)

        if method.implementation and method.implementation.strip():
            impl_base = (
                method.implementation_location.line
                if method.implementation_location
                else 1
            )
            comment_chunks = self._extract_comment_chunks(
                method.implementation,
                file_path,
                file_id,
                content.name,
                content.pou_type.upper(),
                impl_base,
                method_name=method.name,
            )
            chunks.extend(comment_chunks)

        return chunks

    def _extract_property_chunks(
        self,
        prop: PropertyContent,
        content: POUContent,
        file_path: Path | None,
        file_id: FileId | None,
    ) -> list[Chunk]:
        """Create chunks for a property.

        Creates:
        1. A PROPERTY chunk containing declaration + GET/SET implementations
        """
        chunks: list[Chunk] = []

        # Combine property declaration and accessor implementations
        property_code = prop.declaration

        if prop.get and prop.get.implementation and prop.get.implementation.strip():
            if property_code:
                property_code += "\n\n// GET\n"
            property_code += prop.get.implementation

        if prop.set and prop.set.implementation and prop.set.implementation.strip():
            if property_code:
                property_code += "\n\n// SET\n"
            property_code += prop.set.implementation

        if not property_code.strip():
            return chunks

        # Calculate start_line from property declaration location
        start_line = 1
        if prop.declaration_location:
            start_line = prop.declaration_location.line
        end_line = start_line + property_code.count("\n")

        # Create the main PROPERTY chunk
        chunk = Chunk(
            symbol=f"{content.name}.{prop.name}",
            start_line=LineNumber(start_line),
            end_line=LineNumber(end_line),
            code=property_code,
            chunk_type=ChunkType.PROPERTY,
            file_id=file_id or FileId(0),
            language=Language.TWINCAT,
            file_path=FilePath(str(file_path)) if file_path else None,
            metadata={
                "kind": "property",
                "pou_type": content.pou_type,
                "pou_name": content.name,
                "property_id": prop.id,
                "has_get": prop.get is not None,
                "has_set": prop.set is not None,
            },
        )
        chunks.append(chunk)

        return chunks

    def _adjust_line_number(
        self, line: int, location: SourceLocation | None
    ) -> int:
        """Adjust line number from CDATA-relative to XML-absolute."""
        if location is None:
            return line
        return line + (location.line - 1)

    @staticmethod
    def _build_fqn(
        pou_name: str,
        element_name: str,
        method_name: str | None = None,
        action_name: str | None = None,
    ) -> str:
        """Build a fully qualified name for a chunk symbol.

        FQN hierarchy: POUName[.MethodName|.ActionName].ElementName
        """
        if method_name:
            return f"{pou_name}.{method_name}.{element_name}"
        elif action_name:
            return f"{pou_name}.{action_name}.{element_name}"
        return f"{pou_name}.{element_name}"

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

    # =========================================================================
    # Implementation Block Extraction (Tier 4 - Control Flow Blocks)
    # =========================================================================

    # Statement type to metadata kind mapping
    _STATEMENT_KIND_MAP = {
        "if_stmt": "if_block",
        "case_stmt": "case_block",
        "for_stmt": "for_loop",
        "while_stmt": "while_loop",
        "repeat_stmt": "repeat_loop",
    }

    def _extract_blocks_from_implementation(
        self,
        implementation: str,
        implementation_location: SourceLocation | None,
        pou_name: str,
        pou_type: str,
        file_path: Path | None,
        file_id: FileId | None,
        action_name: str | None = None,
        method_name: str | None = None,
    ) -> list[Chunk]:
        """Parse implementation code and extract control flow blocks as BLOCK chunks.

        Args:
            implementation: Raw ST code from CDATA
            implementation_location: XML position for line adjustment
            pou_name: Parent POU name
            pou_type: POU type (FUNCTION, FUNCTION_BLOCK, PROGRAM)
            file_path: Path to source file
            file_id: Database file ID
            action_name: If parsing action implementation, the action name
            method_name: If parsing method implementation, the method name

        Returns:
            List of BLOCK chunks for control flow statements
            (IF, CASE, FOR, WHILE, REPEAT)
        """
        chunks: list[Chunk] = []

        try:
            tree = self.impl_parser.parse(implementation)
        except LarkError as e:
            if method_name:
                context = f"method '{method_name}'"
            elif action_name:
                context = f"action '{action_name}'"
            else:
                context = f"FUNCTION '{pou_name}'"
            error_msg = f"Implementation parse error in {context}: {e}"
            logger.error(error_msg)
            self._parse_errors.append(error_msg)
            return chunks

        # Find all control flow statement nodes
        statement_nodes = self._find_statement_nodes(tree)

        for node in statement_nodes:
            chunk = self._create_block_chunk(
                node,
                implementation,
                implementation_location,
                pou_name,
                pou_type,
                file_path,
                file_id,
                action_name,
                method_name,
            )
            if chunk:
                chunks.append(chunk)

        return chunks

    def _find_statement_nodes(self, tree: Tree) -> list[Tree]:
        """Recursively find all control flow statement nodes in parse tree.

        Finds: if_stmt, case_stmt, for_stmt, while_stmt, repeat_stmt
        """
        results: list[Tree] = []

        if isinstance(tree, Tree):
            if tree.data in self._STATEMENT_KIND_MAP:
                results.append(tree)
            # Recurse into children to find nested statements
            for child in tree.children:
                if isinstance(child, Tree):
                    results.extend(self._find_statement_nodes(child))

        return results

    def _create_block_chunk(
        self,
        node: Tree,
        implementation: str,
        implementation_location: SourceLocation | None,
        pou_name: str,
        pou_type: str,
        file_path: Path | None,
        file_id: FileId | None,
        action_name: str | None,
        method_name: str | None = None,
    ) -> Chunk | None:
        """Create BLOCK chunk from a control flow statement node.

        Args:
            node: Lark Tree node for a control flow statement
            implementation: Full implementation source code
            implementation_location: XML position for line adjustment
            pou_name: Parent POU name
            pou_type: POU type (FUNCTION, FUNCTION_BLOCK, PROGRAM)
            file_path: Path to source file
            file_id: Database file ID
            action_name: Optional action name for action blocks
            method_name: Optional method name for method blocks

        Returns:
            BLOCK chunk or None if unable to create
        """
        # Get line numbers from node metadata
        if not hasattr(node, "meta") or node.meta is None:
            return None

        start_line = node.meta.line
        end_line = node.meta.end_line or start_line

        # Reconstruct code from the implementation using line numbers
        code = self._reconstruct_code_from_lines(implementation, start_line, end_line)

        # Adjust line numbers to XML-absolute
        adjusted_start = self._adjust_line_number(start_line, implementation_location)
        adjusted_end = self._adjust_line_number(end_line, implementation_location)

        # Determine kind from statement type
        kind = self._STATEMENT_KIND_MAP.get(node.data, "block")

        # Build FQN: POUName[.MethodName|.ActionName].{kind}_{line}
        symbol = self._build_fqn(
            pou_name, f"{kind}_{adjusted_start}", method_name, action_name
        )

        # Build metadata
        metadata: dict[str, Any] = {
            "kind": kind,
            "pou_type": pou_type,
            "pou_name": pou_name,
        }
        if action_name:
            metadata["action_name"] = action_name
        if method_name:
            metadata["method_name"] = method_name

        return Chunk(
            symbol=symbol,
            start_line=LineNumber(adjusted_start),
            end_line=LineNumber(adjusted_end),
            code=code,
            chunk_type=ChunkType.BLOCK,
            file_id=file_id or FileId(0),
            language=Language.TWINCAT,
            file_path=FilePath(str(file_path)) if file_path else None,
            metadata=metadata,
        )

    def _reconstruct_code_from_lines(
        self, source: str, start_line: int, end_line: int
    ) -> str:
        """Extract code substring using line numbers.

        Args:
            source: Full source code string
            start_line: 1-based start line number
            end_line: 1-based end line number (inclusive)

        Returns:
            Code substring spanning the specified lines
        """
        lines = source.splitlines()

        # Convert to 0-based indices
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)

        return "\n".join(lines[start_idx:end_idx])

    # =========================================================================
    # Comment Extraction (Tier 5 - Comments as Searchable Chunks)
    # =========================================================================

    def _extract_comment_chunks(
        self,
        source: str,
        file_path: Path | None,
        file_id: FileId | None,
        pou_name: str,
        pou_type: str,
        base_line: int,
        method_name: str | None = None,
        action_name: str | None = None,
    ) -> list[Chunk]:
        """Extract comment chunks from ST source code.

        Uses regex to find block comments (* *) and line comments (//)
        since Lark ignores them during parsing.

        Args:
            source: ST source code to scan for comments
            file_path: Path to source file
            file_id: Database file ID
            pou_name: Parent POU name
            pou_type: POU type (FUNCTION, FUNCTION_BLOCK, PROGRAM)
            base_line: Line offset for XML-absolute positioning
            method_name: If extracting from method body, the method name
            action_name: If extracting from action body, the action name

        Returns:
            List of COMMENT chunks
        """
        chunks: list[Chunk] = []

        # Block comments: (* ... *)
        for match in BLOCK_COMMENT_RE.finditer(source):
            line = source[: match.start()].count("\n") + base_line
            chunk = self._create_comment_chunk(
                content=match.group(),
                line=line,
                file_path=file_path,
                file_id=file_id,
                pou_name=pou_name,
                pou_type=pou_type,
                comment_type="block",
                method_name=method_name,
                action_name=action_name,
            )
            chunks.append(chunk)

        # Line comments: // ...
        for match in LINE_COMMENT_RE.finditer(source):
            line = source[: match.start()].count("\n") + base_line
            chunk = self._create_comment_chunk(
                content=match.group(),
                line=line,
                file_path=file_path,
                file_id=file_id,
                pou_name=pou_name,
                pou_type=pou_type,
                comment_type="line",
                method_name=method_name,
                action_name=action_name,
            )
            chunks.append(chunk)

        return chunks

    def _create_comment_chunk(
        self,
        content: str,
        line: int,
        file_path: Path | None,
        file_id: FileId | None,
        pou_name: str,
        pou_type: str,
        comment_type: str,
        method_name: str | None = None,
        action_name: str | None = None,
    ) -> Chunk:
        """Create a comment chunk.

        Args:
            content: Raw comment text including markers
            line: XML-absolute line number
            file_path: Path to source file
            file_id: Database file ID
            pou_name: Parent POU name
            pou_type: POU type (FUNCTION, FUNCTION_BLOCK, PROGRAM)
            comment_type: "block" or "line"
            method_name: If in method context, the method name
            action_name: If in action context, the action name

        Returns:
            COMMENT chunk
        """
        # Build FQN: POUName[.MethodName|.ActionName].comment_line_N
        element_name = f"comment_line_{line}"
        fqn = self._build_fqn(pou_name, element_name, method_name, action_name)

        # Calculate end line for multi-line block comments
        end_line = line + content.count("\n")

        # Clean comment text (strip markers)
        cleaned_text = self._clean_st_comment(content)

        # Build metadata
        metadata: dict[str, Any] = {
            "kind": "comment",
            "comment_type": comment_type,
            "pou_name": pou_name,
            "pou_type": pou_type,
            "cleaned_text": cleaned_text,
        }
        if method_name:
            metadata["method_name"] = method_name
        if action_name:
            metadata["action_name"] = action_name

        return Chunk(
            symbol=fqn,
            start_line=LineNumber(line),
            end_line=LineNumber(end_line),
            code=content,
            chunk_type=ChunkType.COMMENT,
            file_id=file_id or FileId(0),
            language=Language.TWINCAT,
            file_path=FilePath(str(file_path)) if file_path else None,
            metadata=metadata,
        )

    def _clean_st_comment(self, text: str) -> str:
        """Strip ST comment markers (* *) and //.

        Args:
            text: Raw comment text with markers

        Returns:
            Cleaned comment text without markers
        """
        cleaned = text.strip()
        if cleaned.startswith("(*") and cleaned.endswith("*)"):
            cleaned = cleaned[2:-2].strip()
        elif cleaned.startswith("//"):
            cleaned = cleaned[2:].strip()
        return cleaned
