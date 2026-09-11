package io.github.adbmlkit.helper;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/** Version-one wire validation, independent of Android for local JVM tests. */
final class OcrRequest {
    static final long MAX_INPUT_BYTES = 32L * 1024 * 1024;
    static final long MAX_PIXELS = 32_000_000L;
    static final int MAX_DIMENSION = 16_384;
    static final int MAX_REQUEST_BYTES = 16 * 1024;

    final String id;
    final String script;
    final int rotation;
    final int runs;
    final int[] roi;

    private OcrRequest(String id, String script, int rotation, int runs, int[] roi) {
        this.id = id;
        this.script = script;
        this.rotation = rotation;
        this.runs = runs;
        this.roi = roi;
    }

    static boolean validId(String id) {
        return id != null && id.matches("[0-9a-f]{32}");
    }

    static OcrRequest parse(JSONObject json, String expectedId) throws JSONException {
        require(validId(expectedId), "request_id must be 32 lowercase hexadecimal characters");
        require(integer(json.get("schema_version"), "schema_version") == 1,
                "schema_version must be 1");
        require(expectedId.equals(json.get("id")), "id must match request_id");
        Object scriptValue = json.has("script") ? json.get("script") : "latin";
        require(scriptValue instanceof String, "script must be a string");
        String script = (String) scriptValue;
        require(script.equals("latin") || script.equals("chinese")
                || script.equals("devanagari") || script.equals("japanese")
                || script.equals("korean"), "unsupported script");
        JSONObject source = json.getJSONObject("source");
        require("private".equals(source.get("type")), "source.type must be private");
        require(("files/requests/" + expectedId + "/input.png").equals(source.get("path")),
                "source.path must name this request's private input.png");
        int rotation = json.has("rotation") ? integer(json.get("rotation"), "rotation") : 0;
        require(rotation == 0 || rotation == 90 || rotation == 180 || rotation == 270,
                "rotation must be 0, 90, 180, or 270");
        int runs = integer(json.get("runs"), "runs");
        require(runs >= 1 && runs <= 30, "runs must be from 1 to 30");
        int[] roi = null;
        if (json.has("roi") && !json.isNull("roi")) {
            JSONArray values = json.getJSONArray("roi");
            require(values.length() == 4, "roi must contain exactly four integers");
            roi = new int[4];
            for (int i = 0; i < 4; i++) roi[i] = integer(values.get(i), "roi");
            require(roi[0] >= 0 && roi[1] >= 0 && roi[2] > roi[0] && roi[3] > roi[1],
                    "roi must be a nonempty rectangle with nonnegative origin");
        }
        return new OcrRequest(expectedId, script, rotation, runs, roi);
    }

    void validateDimensions(int width, int height) {
        require(width > 0 && height > 0, "image dimensions must be positive");
        require(width <= MAX_DIMENSION && height <= MAX_DIMENSION
                && (long) width * height <= MAX_PIXELS,
                "image exceeds 16384 pixels per side or 32000000 pixels total");
        if (roi != null) {
            require(roi[2] <= width && roi[3] <= height, "roi must be inside the source image");
        }
    }

    private static int integer(Object value, String name) {
        require(value instanceof Integer || value instanceof Long, name + " must be an integer");
        long number = ((Number) value).longValue();
        require(number >= Integer.MIN_VALUE && number <= Integer.MAX_VALUE,
                name + " is outside integer range");
        return (int) number;
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new IllegalArgumentException(message);
    }
}
