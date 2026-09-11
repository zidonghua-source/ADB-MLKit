package io.github.adbmlkit.helper;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;

import static org.junit.Assert.*;

public class OcrRequestTest {
    private static final String ID = "0123456789abcdef0123456789abcdef";

    private JSONObject valid() throws Exception {
        return new JSONObject().put("schema_version", 1).put("id", ID).put("runs", 1)
                .put("source", new JSONObject().put("type", "private")
                        .put("path", "files/requests/" + ID + "/input.png"));
    }

    private void rejected(JSONObject json) {
        assertThrows(Exception.class, () -> OcrRequest.parse(json, ID));
    }

    @Test public void defaultsAndNullRoi() throws Exception {
        OcrRequest request = OcrRequest.parse(valid(), ID);
        assertEquals("latin", request.script);
        assertEquals(0, request.rotation);
        assertEquals(1, request.runs);
        assertNull(request.roi);
        assertNull(OcrRequest.parse(valid().put("roi", JSONObject.NULL), ID).roi);
    }

    @Test public void allScriptsRotationsAndRunEndpoints() throws Exception {
        for (String script : new String[]{"latin", "chinese", "devanagari", "japanese", "korean"}) {
            for (int rotation : new int[]{0, 90, 180, 270}) {
                for (int runs : new int[]{1, 30}) {
                    OcrRequest request = OcrRequest.parse(valid().put("script", script)
                            .put("rotation", rotation).put("runs", runs), ID);
                    assertEquals(script, request.script);
                    assertEquals(rotation, request.rotation);
                    assertEquals(runs, request.runs);
                }
            }
        }
    }

    @Test public void idsMustBeCanonicalUuidHex() throws Exception {
        assertTrue(OcrRequest.validId(ID));
        for (String id : new String[]{null, "", "../outside", ID.toUpperCase(), ID + "0",
                "01234567-89ab-cdef-0123-456789abcdef"}) {
            assertFalse(OcrRequest.validId(id));
            assertThrows(Exception.class, () -> OcrRequest.parse(valid(), id));
        }
        rejected(valid().put("id", "ffffffffffffffffffffffffffffffff"));
        rejected(valid().put("id", JSONObject.NULL));
    }

    @Test public void strictScriptAndNumericTypes() throws Exception {
        for (Object value : new Object[]{"Latin", "unknown", "", 1, JSONObject.NULL}) {
            rejected(valid().put("script", value));
        }
        for (Object value : new Object[]{0, 31, -1, "1", 1.5, 1.0, true, JSONObject.NULL, Long.MAX_VALUE}) {
            rejected(valid().put("runs", value));
        }
        JSONObject missingRuns = valid();
        missingRuns.remove("runs");
        rejected(missingRuns);
        for (Object value : new Object[]{45, -90, 360, "90", 90.0, JSONObject.NULL}) {
            rejected(valid().put("rotation", value));
        }
        for (Object value : new Object[]{0, 2, "1", true, 1.0, JSONObject.NULL}) {
            rejected(valid().put("schema_version", value));
        }
    }

    @Test public void sourceOnlyNamesOwnPrivateInput() throws Exception {
        for (String path : new String[]{"/sdcard/input.png", "/data/local/tmp/input.png",
                "files/requests/ffffffffffffffffffffffffffffffff/input.png",
                "files/requests/" + ID + "/../input.png",
                "files/requests/" + ID + "/other.png"}) {
            JSONObject json = valid();
            json.getJSONObject("source").put("path", path);
            rejected(json);
        }
        JSONObject json = valid();
        json.getJSONObject("source").put("type", "external");
        rejected(json);
        rejected(valid().put("source", "private"));
    }

    @Test public void roiShapeTypesAndEdges() throws Exception {
        for (Object value : new Object[]{"0,0,1,1", new JSONArray(new int[]{0, 0, 1}),
                new JSONArray(new int[]{0, 0, 1, 1, 2}), new JSONArray(new int[]{-1, 0, 1, 1}),
                new JSONArray(new int[]{0, 0, 0, 1}), new JSONArray(new int[]{0, 2, 1, 1}),
                new JSONArray().put(0).put(0).put("1").put(1)}) {
            rejected(valid().put("roi", value));
        }
        OcrRequest request = OcrRequest.parse(valid().put("roi", new JSONArray(new int[]{0, 1, 10, 20})), ID);
        request.validateDimensions(10, 20);
        assertArrayEquals(new int[]{0, 1, 10, 20}, request.roi);
        assertThrows(IllegalArgumentException.class, () -> request.validateDimensions(9, 20));
        assertThrows(IllegalArgumentException.class, () -> request.validateDimensions(10, 19));
    }

    @Test public void dimensionLimitsDoNotOverflow() throws Exception {
        OcrRequest request = OcrRequest.parse(valid(), ID);
        request.validateDimensions(8000, 4000);
        request.validateDimensions(16384, 1);
        for (int[] size : new int[][]{{0, 1}, {1, -1}, {8000, 4001}, {16385, 1},
                {1, 16385}, {Integer.MAX_VALUE, Integer.MAX_VALUE}}) {
            assertThrows(IllegalArgumentException.class, () -> request.validateDimensions(size[0], size[1]));
        }
    }

    @Test public void unknownFieldsAreForwardCompatible() throws Exception {
        assertEquals(ID, OcrRequest.parse(valid().put("future_field", true), ID).id);
    }
}
