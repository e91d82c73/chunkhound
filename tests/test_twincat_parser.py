"""Tests for TwinCAT Structured Text parser.

Tests the TwinCAT parser (`chunkhound/parsers/twincat/`) which handles
TcPOU XML files containing IEC 61131-3 Structured Text code.
"""

from pathlib import Path

import pytest

from chunkhound.core.types.common import ChunkType, FileId, Language
from chunkhound.parsers.parser_factory import ParserFactory
from chunkhound.parsers.twincat.twincat_parser import TwinCATParser

# =============================================================================
# Test Helpers
# =============================================================================


def find_by_symbol(chunks, symbol):
    """Filter chunks by symbol name."""
    return [c for c in chunks if c.symbol == symbol]


def find_by_type(chunks, chunk_type):
    """Filter chunks by ChunkType."""
    return [c for c in chunks if c.chunk_type == chunk_type]


def find_by_metadata(chunks, key, value):
    """Filter chunks by metadata key-value pair."""
    return [c for c in chunks if c.metadata and c.metadata.get(key) == value]


def assert_no_parse_errors(parser: TwinCATParser) -> None:
    """Assert that parser has no parse errors. Call after parsing."""
    assert parser.parse_errors == [], (
        f"Parser encountered errors: {parser.parse_errors}"
    )


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def twincat_parser():
    """Create TwinCAT parser instance."""
    return TwinCATParser()


@pytest.fixture
def comprehensive_fixture():
    """Load the comprehensive test fixture."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "twincat" / "example_comprehensive.TcPOU"
    )
    if not fixture_path.exists():
        pytest.skip("Comprehensive fixture not found")
    return fixture_path


@pytest.fixture
def program_fixture():
    """Load the PROGRAM test fixture."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "twincat" / "example_program.TcPOU"
    )
    if not fixture_path.exists():
        pytest.skip("PROGRAM fixture not found")
    return fixture_path


@pytest.fixture
def function_fixture():
    """Load the FUNCTION test fixture."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "twincat" / "example_function.TcPOU"
    )
    if not fixture_path.exists():
        pytest.skip("FUNCTION fixture not found")
    return fixture_path


# =============================================================================
# TestTwinCATParserAvailability
# =============================================================================


class TestTwinCATParserAvailability:
    """Test parser availability and file detection."""

    def test_twincat_parser_instantiation(self):
        """Test that TwinCATParser can be instantiated directly."""
        parser = TwinCATParser()
        assert parser is not None

    def test_twincat_file_detection(self):
        """Test that factory detects .TcPOU extension correctly."""
        factory = ParserFactory()
        detected = factory.detect_language(Path("test.TcPOU"))
        assert detected == Language.TWINCAT

    def test_twincat_file_detection_lowercase(self):
        """Test that factory detects .tcpou extension (lowercase)."""
        factory = ParserFactory()
        detected = factory.detect_language(Path("test.tcpou"))
        assert detected == Language.TWINCAT


# =============================================================================
# TestPOUTypes
# =============================================================================


class TestPOUTypes:
    """Test PROGRAM and FUNCTION POU types."""

    # --- PROGRAM Tests ---

    def test_program_chunk_type(self, twincat_parser, program_fixture):
        """Test PROGRAM creates ChunkType.PROGRAM chunk."""
        chunks = twincat_parser.parse_file(program_fixture, FileId(1))
        assert_no_parse_errors(twincat_parser)
        program_chunks = find_by_type(chunks, ChunkType.PROGRAM)
        assert len(program_chunks) == 1
        assert program_chunks[0].symbol == "PRG_Example"

    def test_program_metadata(self, twincat_parser, program_fixture):
        """Test PROGRAM metadata includes kind='program', pou_type='PROGRAM'."""
        chunks = twincat_parser.parse_file(program_fixture, FileId(1))
        assert_no_parse_errors(twincat_parser)
        program_chunks = find_by_type(chunks, ChunkType.PROGRAM)
        assert len(program_chunks) == 1
        metadata = program_chunks[0].metadata
        assert metadata["kind"] == "program"
        assert metadata["pou_type"] == "PROGRAM"
        assert metadata["pou_name"] == "PRG_Example"
        assert metadata["pou_id"] == "{11111111-1111-1111-1111-111111111111}"

    def test_program_variables(self, twincat_parser, program_fixture):
        """Test PROGRAM extracts VAR_INPUT, VAR_OUTPUT, and VAR blocks."""
        chunks = twincat_parser.parse_file(program_fixture, FileId(1))
        assert_no_parse_errors(twincat_parser)

        # VAR_INPUT: bStart
        input_vars = find_by_metadata(chunks, "var_class", "input")
        assert len(input_vars) == 1
        assert input_vars[0].symbol == "bStart"
        assert input_vars[0].metadata["data_type"] == "BOOL"

        # VAR_OUTPUT: bRunning
        output_vars = find_by_metadata(chunks, "var_class", "output")
        assert len(output_vars) == 1
        assert output_vars[0].symbol == "bRunning"
        assert output_vars[0].metadata["data_type"] == "BOOL"

        # VAR (local): nCycleCount
        local_vars = find_by_metadata(chunks, "var_class", "local")
        assert len(local_vars) == 1
        assert local_vars[0].symbol == "nCycleCount"
        assert local_vars[0].metadata["data_type"] == "DINT"

    # --- FUNCTION Tests ---

    def test_function_chunk_type(self, twincat_parser, function_fixture):
        """Test FUNCTION creates ChunkType.FUNCTION chunk."""
        chunks = twincat_parser.parse_file(function_fixture, FileId(1))
        assert_no_parse_errors(twincat_parser)
        function_chunks = find_by_type(chunks, ChunkType.FUNCTION)
        assert len(function_chunks) == 1
        assert function_chunks[0].symbol == "FC_Add"

    def test_function_metadata(self, twincat_parser, function_fixture):
        """Test FUNCTION metadata includes kind='function', pou_type='FUNCTION'."""
        chunks = twincat_parser.parse_file(function_fixture, FileId(1))
        assert_no_parse_errors(twincat_parser)
        function_chunks = find_by_type(chunks, ChunkType.FUNCTION)
        assert len(function_chunks) == 1
        metadata = function_chunks[0].metadata
        assert metadata["kind"] == "function"
        assert metadata["pou_type"] == "FUNCTION"
        assert metadata["pou_name"] == "FC_Add"
        assert metadata["pou_id"] == "{22222222-2222-2222-2222-222222222222}"

    def test_function_variables(self, twincat_parser, function_fixture):
        """Test FUNCTION extracts VAR_INPUT and VAR blocks."""
        chunks = twincat_parser.parse_file(function_fixture, FileId(1))
        assert_no_parse_errors(twincat_parser)

        # VAR_INPUT: nA, nB
        input_vars = find_by_metadata(chunks, "var_class", "input")
        assert len(input_vars) == 2
        input_names = {c.symbol for c in input_vars}
        assert input_names == {"nA", "nB"}
        for var in input_vars:
            assert var.metadata["data_type"] == "DINT"

        # VAR (local): nResult
        local_vars = find_by_metadata(chunks, "var_class", "local")
        assert len(local_vars) == 1
        assert local_vars[0].symbol == "nResult"
        assert local_vars[0].metadata["data_type"] == "DINT"


# =============================================================================
# TestPOUChunkCreation
# =============================================================================


class TestPOUChunkCreation:
    """Test POU (Program Organization Unit) chunk creation."""

    def test_function_block_chunk(self, twincat_parser):
        """Test FUNCTION_BLOCK creates correct ChunkType."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{12345678-1234-1234-1234-123456789abc}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    nValue : INT;
END_VAR
]]></Declaration>
    <Implementation>
      <ST><![CDATA[nValue := 42;]]></ST>
    </Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        pou_chunks = find_by_type(chunks, ChunkType.FUNCTION_BLOCK)
        assert len(pou_chunks) == 1
        assert pou_chunks[0].symbol == "FB_Test"

    def test_pou_metadata(self, twincat_parser):
        """Test POU metadata includes pou_type, pou_name, pou_id, kind."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{aaaa-bbbb-cccc-dddd}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    nValue : INT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        pou_chunks = find_by_type(chunks, ChunkType.FUNCTION_BLOCK)
        assert len(pou_chunks) == 1
        metadata = pou_chunks[0].metadata
        assert metadata["kind"] == "function_block"
        assert metadata["pou_type"] == "FUNCTION_BLOCK"
        assert metadata["pou_name"] == "FB_Test"
        assert metadata["pou_id"] == "{aaaa-bbbb-cccc-dddd}"


# =============================================================================
# TestVariableClassification
# =============================================================================


class TestVariableClassification:
    """Test VAR block classification to VARIABLE vs FIELD chunk types."""

    def test_var_input_is_field(self, twincat_parser):
        """Test VAR_INPUT creates FIELD chunk with var_class='input'."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR_INPUT
    bEnable : BOOL;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        var_chunks = find_by_symbol(chunks, "bEnable")
        assert len(var_chunks) == 1
        assert var_chunks[0].chunk_type == ChunkType.FIELD
        assert var_chunks[0].metadata["var_class"] == "input"

    def test_var_output_is_field(self, twincat_parser):
        """Test VAR_OUTPUT creates FIELD chunk with var_class='output'."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR_OUTPUT
    bDone : BOOL;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        var_chunks = find_by_symbol(chunks, "bDone")
        assert len(var_chunks) == 1
        assert var_chunks[0].chunk_type == ChunkType.FIELD
        assert var_chunks[0].metadata["var_class"] == "output"

    def test_var_in_out_is_field(self, twincat_parser):
        """Test VAR_IN_OUT creates FIELD chunk with var_class='in_out'."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR_IN_OUT
    refData : DINT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        var_chunks = find_by_symbol(chunks, "refData")
        assert len(var_chunks) == 1
        assert var_chunks[0].chunk_type == ChunkType.FIELD
        assert var_chunks[0].metadata["var_class"] == "in_out"

    def test_var_local_is_field(self, twincat_parser):
        """Test VAR (local) creates FIELD chunk with var_class='local'."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    nLocal : INT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        var_chunks = find_by_symbol(chunks, "nLocal")
        assert len(var_chunks) == 1
        assert var_chunks[0].chunk_type == ChunkType.FIELD
        assert var_chunks[0].metadata["var_class"] == "local"

    def test_var_stat_is_field(self, twincat_parser):
        """Test VAR_STAT creates FIELD chunk with var_class='static'."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR_STAT
    nCounter : UDINT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        var_chunks = find_by_symbol(chunks, "nCounter")
        assert len(var_chunks) == 1
        assert var_chunks[0].chunk_type == ChunkType.FIELD
        assert var_chunks[0].metadata["var_class"] == "static"

    def test_var_temp_is_field(self, twincat_parser):
        """Test VAR_TEMP creates FIELD chunk with var_class='temp'."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR_TEMP
    nTemp : INT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        var_chunks = find_by_symbol(chunks, "nTemp")
        assert len(var_chunks) == 1
        assert var_chunks[0].chunk_type == ChunkType.FIELD
        assert var_chunks[0].metadata["var_class"] == "temp"

    def test_var_global_is_variable(self, twincat_parser):
        """Test VAR_GLOBAL creates VARIABLE chunk with var_class='global'."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR_GLOBAL
    gValue : INT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        var_chunks = find_by_symbol(chunks, "gValue")
        assert len(var_chunks) == 1
        assert var_chunks[0].chunk_type == ChunkType.VARIABLE
        assert var_chunks[0].metadata["var_class"] == "global"

    def test_var_external_is_variable(self, twincat_parser):
        """Test VAR_EXTERNAL creates VARIABLE chunk with var_class='external'."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR_EXTERNAL
    extValue : DINT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        var_chunks = find_by_symbol(chunks, "extValue")
        assert len(var_chunks) == 1
        assert var_chunks[0].chunk_type == ChunkType.VARIABLE
        assert var_chunks[0].metadata["var_class"] == "external"


# =============================================================================
# TestDataTypeExtraction
# =============================================================================


class TestDataTypeExtraction:
    """Test data type extraction from variable declarations."""

    def test_primitive_types(self, twincat_parser):
        """Test primitive type extraction (BOOL, INT, DINT, REAL, etc.)."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    bFlag : BOOL;
    nInt : INT;
    nDint : DINT;
    fReal : REAL;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)

        bool_chunk = find_by_symbol(chunks, "bFlag")[0]
        assert bool_chunk.metadata["data_type"] == "BOOL"

        int_chunk = find_by_symbol(chunks, "nInt")[0]
        assert int_chunk.metadata["data_type"] == "INT"

        dint_chunk = find_by_symbol(chunks, "nDint")[0]
        assert dint_chunk.metadata["data_type"] == "DINT"

        real_chunk = find_by_symbol(chunks, "fReal")[0]
        assert real_chunk.metadata["data_type"] == "REAL"

    def test_string_with_size(self, twincat_parser):
        """Test STRING(n) and WSTRING(n) type extraction."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    sName : STRING(80);
    wsText : WSTRING(100);
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)

        string_chunk = find_by_symbol(chunks, "sName")[0]
        assert string_chunk.metadata["data_type"] == "STRING(80)"

        wstring_chunk = find_by_symbol(chunks, "wsText")[0]
        assert wstring_chunk.metadata["data_type"] == "WSTRING(100)"

    def test_single_dimension_array(self, twincat_parser):
        """Test ARRAY[0..9] OF INT type extraction."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    anData : ARRAY[0..9] OF INT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        array_chunk = find_by_symbol(chunks, "anData")[0]
        assert "ARRAY[0..9] OF INT" in array_chunk.metadata["data_type"]

    def test_multi_dimension_array(self, twincat_parser):
        """Test ARRAY[1..3, 1..3] OF REAL type extraction."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    afMatrix : ARRAY[1..3, 1..3] OF REAL;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        array_chunk = find_by_symbol(chunks, "afMatrix")[0]
        data_type = array_chunk.metadata["data_type"]
        assert "ARRAY" in data_type
        assert "1..3" in data_type
        assert "REAL" in data_type

    def test_pointer_type(self, twincat_parser):
        """Test POINTER TO INT type extraction."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    pnValue : POINTER TO INT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        ptr_chunk = find_by_symbol(chunks, "pnValue")[0]
        assert "POINTER TO" in ptr_chunk.metadata["data_type"]
        assert "INT" in ptr_chunk.metadata["data_type"]

    def test_reference_type(self, twincat_parser):
        """Test REFERENCE TO DINT type extraction."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    refValue : REFERENCE TO DINT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        ref_chunk = find_by_symbol(chunks, "refValue")[0]
        assert "REFERENCE TO" in ref_chunk.metadata["data_type"]
        assert "DINT" in ref_chunk.metadata["data_type"]

    def test_user_defined_type(self, twincat_parser):
        """Test user-defined types (ST_DataRecord, TON, E_MachineState)."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    stData : ST_DataRecord;
    fbTimer : TON;
    eState : E_MachineState;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)

        struct_chunk = find_by_symbol(chunks, "stData")[0]
        assert struct_chunk.metadata["data_type"] == "ST_DataRecord"

        timer_chunk = find_by_symbol(chunks, "fbTimer")[0]
        assert timer_chunk.metadata["data_type"] == "TON"

        enum_chunk = find_by_symbol(chunks, "eState")[0]
        assert enum_chunk.metadata["data_type"] == "E_MachineState"


# =============================================================================
# TestVariableQualifiers
# =============================================================================


class TestVariableQualifiers:
    """Test RETAIN/PERSISTENT qualifier extraction."""

    def test_retain_qualifier(self, twincat_parser):
        """Test RETAIN qualifier sets metadata['retain'] = True."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR RETAIN
    nRetained : DINT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        var_chunk = find_by_symbol(chunks, "nRetained")[0]
        assert var_chunk.metadata["retain"] is True
        assert var_chunk.metadata["persistent"] is False

    def test_persistent_qualifier(self, twincat_parser):
        """Test PERSISTENT qualifier sets metadata['persistent'] = True."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR PERSISTENT
    nPersistent : DINT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        var_chunk = find_by_symbol(chunks, "nPersistent")[0]
        assert var_chunk.metadata["persistent"] is True
        assert var_chunk.metadata["retain"] is False

    def test_retain_persistent_combined(self, twincat_parser):
        """Test RETAIN PERSISTENT sets both qualifiers to True."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR RETAIN PERSISTENT
    stSaved : ST_Data;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        var_chunk = find_by_symbol(chunks, "stSaved")[0]
        assert var_chunk.metadata["retain"] is True
        assert var_chunk.metadata["persistent"] is True


# =============================================================================
# TestHardwareAddressing
# =============================================================================


class TestHardwareAddressing:
    """Test AT directive and hardware address extraction."""

    def test_hw_address_input_wildcard(self, twincat_parser):
        """Test AT %I* extraction."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    bDigitalInput AT %I* : BOOL;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        var_chunk = find_by_symbol(chunks, "bDigitalInput")[0]
        assert var_chunk.metadata["hw_address"] == "%I*"

    def test_hw_address_input_word(self, twincat_parser):
        """Test AT %IW100 extraction."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    nAnalogInput AT %IW100 : INT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        var_chunk = find_by_symbol(chunks, "nAnalogInput")[0]
        assert var_chunk.metadata["hw_address"] == "%IW100"

    def test_hw_address_output(self, twincat_parser):
        """Test AT %Q* and %QW50 extraction."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    bDigitalOutput AT %Q* : BOOL;
    nAnalogOutput AT %QW50 : INT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)

        digital_chunk = find_by_symbol(chunks, "bDigitalOutput")[0]
        assert digital_chunk.metadata["hw_address"] == "%Q*"

        analog_chunk = find_by_symbol(chunks, "nAnalogOutput")[0]
        assert analog_chunk.metadata["hw_address"] == "%QW50"

    def test_hw_address_memory(self, twincat_parser):
        """Test AT %MW200 and %MX100.0 extraction."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    nMemoryWord AT %MW200 : WORD;
    bMemoryBit AT %MX100.0 : BOOL;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)

        word_chunk = find_by_symbol(chunks, "nMemoryWord")[0]
        assert word_chunk.metadata["hw_address"] == "%MW200"

        bit_chunk = find_by_symbol(chunks, "bMemoryBit")[0]
        assert bit_chunk.metadata["hw_address"] == "%MX100.0"


# =============================================================================
# TestMultipleVariablesDeclaration
# =============================================================================


class TestMultipleVariablesDeclaration:
    """Test comma-separated variable declarations."""

    def test_comma_separated_variables(self, twincat_parser):
        """Test that bFlag1, bFlag2, bFlag3 : BOOL; creates 3 separate chunks."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    bFlag1, bFlag2, bFlag3 : BOOL;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)

        flag_chunks = [c for c in chunks if c.symbol in ("bFlag1", "bFlag2", "bFlag3")]
        assert len(flag_chunks) == 3

        # All should have BOOL data type
        for chunk in flag_chunks:
            assert chunk.metadata["data_type"] == "BOOL"
            assert chunk.chunk_type == ChunkType.FIELD


# =============================================================================
# TestActionChunks
# =============================================================================


class TestActionChunks:
    """Test ACTION chunk creation and metadata."""

    def test_action_chunk_created(self, twincat_parser):
        """Test ACTION creates chunk with ChunkType.ACTION."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    nValue : INT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
    <Action Name="ProcessData" Id="{action-id-1}">
      <Declaration><![CDATA[VAR
    nLocal : INT;
END_VAR
]]></Declaration>
      <Implementation><ST><![CDATA[nValue := 42;]]></ST></Implementation>
    </Action>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        action_chunks = find_by_type(chunks, ChunkType.ACTION)
        assert len(action_chunks) == 1
        assert action_chunks[0].symbol == "ProcessData"

    def test_action_metadata(self, twincat_parser):
        """Test action metadata includes kind='action', pou_name, action_id."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    nValue : INT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
    <Action Name="MyAction" Id="{action-uuid}">
      <Declaration><![CDATA[]]></Declaration>
      <Implementation><ST><![CDATA[nValue := 1;]]></ST></Implementation>
    </Action>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        action_chunks = find_by_type(chunks, ChunkType.ACTION)
        assert len(action_chunks) == 1
        metadata = action_chunks[0].metadata
        assert metadata["kind"] == "action"
        assert metadata["pou_name"] == "FB_Test"
        assert metadata["action_id"] == "{action-uuid}"

    def test_action_local_variables_have_action_name(self, twincat_parser):
        """Test action local variables have metadata['action_name'] set."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    nValue : INT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
    <Action Name="ProcessData" Id="{action-id}">
      <Declaration><![CDATA[VAR
    nLocalIndex : INT;
    fLocalSum : REAL;
END_VAR
]]></Declaration>
      <Implementation><ST><![CDATA[]]></ST></Implementation>
    </Action>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        action_var_chunks = find_by_metadata(chunks, "action_name", "ProcessData")
        assert len(action_var_chunks) == 2

        for chunk in action_var_chunks:
            assert chunk.metadata["action_name"] == "ProcessData"

    def test_action_local_variables_are_fields(self, twincat_parser):
        """Test action local variables are ChunkType.FIELD, not VARIABLE."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    nValue : INT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
    <Action Name="TestAction" Id="{action-id}">
      <Declaration><![CDATA[VAR
    nActionLocal : INT;
END_VAR
]]></Declaration>
      <Implementation><ST><![CDATA[]]></ST></Implementation>
    </Action>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        action_var = find_by_symbol(chunks, "nActionLocal")[0]
        assert action_var.chunk_type == ChunkType.FIELD
        assert action_var.metadata["var_class"] == "local"

    def test_multiple_actions(self, twincat_parser):
        """Test multiple actions create separate ACTION chunks."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    nValue : INT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
    <Action Name="ActionOne" Id="{action-1}">
      <Declaration><![CDATA[]]></Declaration>
      <Implementation><ST><![CDATA[nValue := 1;]]></ST></Implementation>
    </Action>
    <Action Name="ActionTwo" Id="{action-2}">
      <Declaration><![CDATA[]]></Declaration>
      <Implementation><ST><![CDATA[nValue := 2;]]></ST></Implementation>
    </Action>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        action_chunks = find_by_type(chunks, ChunkType.ACTION)
        assert len(action_chunks) == 2

        action_names = {c.symbol for c in action_chunks}
        assert action_names == {"ActionOne", "ActionTwo"}


# =============================================================================
# TestComprehensiveFixture
# =============================================================================


class TestComprehensiveFixture:
    """Integration tests using the comprehensive fixture file."""

    def test_fixture_parses_without_errors(self, twincat_parser, comprehensive_fixture):
        """Test fixture parses without parse_errors."""
        chunks = twincat_parser.parse_file(comprehensive_fixture, FileId(1))
        assert len(chunks) > 0
        assert len(twincat_parser.parse_errors) == 0

    def test_fixture_main_pou(self, twincat_parser, comprehensive_fixture):
        """Test fixture has FB_ComprehensiveExample FUNCTION_BLOCK chunk."""
        chunks = twincat_parser.parse_file(comprehensive_fixture, FileId(1))
        pou_chunks = find_by_type(chunks, ChunkType.FUNCTION_BLOCK)
        assert len(pou_chunks) == 1
        assert pou_chunks[0].symbol == "FB_ComprehensiveExample"

    def test_fixture_var_input_variables(self, twincat_parser, comprehensive_fixture):
        """Test fixture extracts all VAR_INPUT variables."""
        chunks = twincat_parser.parse_file(comprehensive_fixture, FileId(1))
        input_vars = find_by_metadata(chunks, "var_class", "input")
        # Fixture has: bEnable, nInputValue, fSetpoint, sCommand, anInputArray, afMatrix
        assert len(input_vars) >= 6

    def test_fixture_var_output_variables(self, twincat_parser, comprehensive_fixture):
        """Test fixture extracts all VAR_OUTPUT variables."""
        chunks = twincat_parser.parse_file(comprehensive_fixture, FileId(1))
        output_vars = find_by_metadata(chunks, "var_class", "output")
        # From fixture: bDone, bError, nErrorCode, sStatus, anResults
        assert len(output_vars) >= 5

    def test_fixture_var_in_out_variables(self, twincat_parser, comprehensive_fixture):
        """Test fixture extracts both VAR_IN_OUT variables."""
        chunks = twincat_parser.parse_file(comprehensive_fixture, FileId(1))
        in_out_vars = find_by_metadata(chunks, "var_class", "in_out")
        # From fixture: refCounter, aBuffer
        assert len(in_out_vars) >= 2

    def test_fixture_var_stat_variables(self, twincat_parser, comprehensive_fixture):
        """Test fixture extracts VAR_STAT variables with var_class='static'."""
        chunks = twincat_parser.parse_file(comprehensive_fixture, FileId(1))
        static_vars = find_by_metadata(chunks, "var_class", "static")
        # From fixture: nCallCount, fAccumulator
        assert len(static_vars) >= 2

    def test_fixture_var_temp_variables(self, twincat_parser, comprehensive_fixture):
        """Test fixture extracts VAR_TEMP variables with var_class='temp'."""
        chunks = twincat_parser.parse_file(comprehensive_fixture, FileId(1))
        temp_vars = find_by_metadata(chunks, "var_class", "temp")
        # From fixture: nTempValue, fTempResult
        assert len(temp_vars) >= 2

    def test_fixture_retain_variables(self, twincat_parser, comprehensive_fixture):
        """Test fixture extracts RETAIN variables with retain=True."""
        chunks = twincat_parser.parse_file(comprehensive_fixture, FileId(1))
        retain_vars = find_by_metadata(chunks, "retain", True)
        # From fixture: nRetainedCounter, bRetainedFlag, stSavedState
        assert len(retain_vars) >= 2

    def test_fixture_persistent_variables(self, twincat_parser, comprehensive_fixture):
        """Test fixture extracts PERSISTENT variables with persistent=True."""
        chunks = twincat_parser.parse_file(comprehensive_fixture, FileId(1))
        persistent_vars = find_by_metadata(chunks, "persistent", True)
        # From fixture: nPersistentValue, stSavedState
        assert len(persistent_vars) >= 1

    def test_fixture_hardware_variables(self, twincat_parser, comprehensive_fixture):
        """Test fixture extracts AT directive variables with hw_address."""
        chunks = twincat_parser.parse_file(comprehensive_fixture, FileId(1))
        hw_vars = [
            c for c in chunks
            if c.metadata and c.metadata.get("hw_address") is not None
        ]
        # From fixture: bDigitalInput, nAnalogInput, bDigitalOutput, nAnalogOutput,
        #               nMemoryWord, bMemoryBit
        assert len(hw_vars) >= 6

    def test_fixture_actions(self, twincat_parser, comprehensive_fixture):
        """Test fixture extracts ProcessData and ResetState ACTION chunks."""
        chunks = twincat_parser.parse_file(comprehensive_fixture, FileId(1))
        action_chunks = find_by_type(chunks, ChunkType.ACTION)
        assert len(action_chunks) == 2

        action_names = {c.symbol for c in action_chunks}
        assert action_names == {"ProcessData", "ResetState"}

    def test_fixture_action_local_vars(self, twincat_parser, comprehensive_fixture):
        """Test fixture extracts action-scoped variables with action_name."""
        chunks = twincat_parser.parse_file(comprehensive_fixture, FileId(1))

        # ProcessData action vars: nLocalIndex, fLocalSum, bLocalFlag, anLocalBuffer
        process_data_vars = find_by_metadata(chunks, "action_name", "ProcessData")
        assert len(process_data_vars) >= 4

        # ResetState action var: nResetIndex
        reset_state_vars = find_by_metadata(chunks, "action_name", "ResetState")
        assert len(reset_state_vars) >= 1

    def test_fixture_all_chunks_have_twincat_language(
        self, twincat_parser, comprehensive_fixture
    ):
        """Test all chunks have Language.TWINCAT set."""
        chunks = twincat_parser.parse_file(comprehensive_fixture, FileId(1))
        for chunk in chunks:
            assert chunk.language == Language.TWINCAT


# =============================================================================
# TestMetadataCompleteness
# =============================================================================


class TestMetadataCompleteness:
    """Test that all required metadata fields are present."""

    def test_pou_metadata_fields(self, twincat_parser):
        """Test POU chunks have all required metadata fields."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{uuid-here}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    n : INT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        pou_chunk = find_by_type(chunks, ChunkType.FUNCTION_BLOCK)[0]

        required_fields = ["kind", "pou_type", "pou_name", "pou_id"]
        for field in required_fields:
            assert field in pou_chunk.metadata, f"Missing field: {field}"

    def test_variable_metadata_fields(self, twincat_parser):
        """Test variable chunks have all expected metadata fields."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR RETAIN
    nValue AT %MW100 : INT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        var_chunk = find_by_symbol(chunks, "nValue")[0]

        expected_fields = [
            "kind", "pou_type", "pou_name", "var_class",
            "data_type", "hw_address", "retain", "persistent"
        ]
        for field in expected_fields:
            assert field in var_chunk.metadata, f"Missing field: {field}"

    def test_action_metadata_fields(self, twincat_parser):
        """Test action chunks have all required metadata fields."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    n : INT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
    <Action Name="MyAction" Id="{action-uuid}">
      <Declaration><![CDATA[]]></Declaration>
      <Implementation><ST><![CDATA[n := 1;]]></ST></Implementation>
    </Action>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        assert_no_parse_errors(twincat_parser)
        action_chunk = find_by_type(chunks, ChunkType.ACTION)[0]

        required_fields = ["kind", "pou_type", "pou_name", "action_id"]
        for field in required_fields:
            assert field in action_chunk.metadata, f"Missing field: {field}"


# =============================================================================
# TestParseErrorHandling
# =============================================================================


class TestParseErrorHandling:
    """Test that parse_errors is properly populated on grammar errors."""

    def test_invalid_declaration_populates_parse_errors(self, twincat_parser):
        """Test that invalid declaration syntax populates parse_errors."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    THIS IS INVALID SYNTAX !!!
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        # Should still create the POU chunk (graceful degradation)
        pou_chunks = find_by_type(chunks, ChunkType.FUNCTION_BLOCK)
        assert len(pou_chunks) == 1
        # But parse_errors should be populated
        assert len(twincat_parser.parse_errors) > 0
        assert "parse error" in twincat_parser.parse_errors[0].lower()

    def test_invalid_action_declaration_populates_parse_errors(self, twincat_parser):
        """Test that invalid action declaration populates parse_errors."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    nValue : INT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
    <Action Name="BadAction" Id="{action-id}">
      <Declaration><![CDATA[VAR
    INVALID DECLARATION GARBAGE @#$%
END_VAR
]]></Declaration>
      <Implementation><ST><![CDATA[]]></ST></Implementation>
    </Action>
  </POU>
</TcPlcObject>"""
        chunks = twincat_parser.parse_content(xml)
        # Main POU and action should still be created
        pou_chunks = find_by_type(chunks, ChunkType.FUNCTION_BLOCK)
        action_chunks = find_by_type(chunks, ChunkType.ACTION)
        assert len(pou_chunks) == 1
        assert len(action_chunks) == 1
        # But parse_errors should be populated with action error
        assert len(twincat_parser.parse_errors) > 0
        assert "BadAction" in twincat_parser.parse_errors[0]

    def test_parse_errors_cleared_between_parses(self, twincat_parser):
        """Test that parse_errors is cleared between parse operations."""
        # First parse with invalid syntax
        invalid_xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    INVALID SYNTAX @#$
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        twincat_parser.parse_content(invalid_xml)
        assert len(twincat_parser.parse_errors) > 0

        # Second parse with valid syntax
        valid_xml = """<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_Test" Id="{1234}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_Test
VAR
    nValue : INT;
END_VAR
]]></Declaration>
    <Implementation><ST><![CDATA[]]></ST></Implementation>
  </POU>
</TcPlcObject>"""
        twincat_parser.parse_content(valid_xml)
        # parse_errors should now be empty
        assert len(twincat_parser.parse_errors) == 0
