package io.github.adbmlkit.helper;

import android.app.Instrumentation;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Matrix;
import android.graphics.Point;
import android.graphics.Rect;
import android.os.Bundle;
import android.os.Looper;
import android.os.SystemClock;
import android.system.ErrnoException;
import android.system.Os;

import com.google.android.gms.tasks.Tasks;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions;
import com.google.mlkit.vision.text.devanagari.DevanagariTextRecognizerOptions;
import com.google.mlkit.vision.text.japanese.JapaneseTextRecognizerOptions;
import com.google.mlkit.vision.text.korean.KoreanTextRecognizerOptions;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import org.json.JSONTokener;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/** Self-instrumentation file RPC. No Activity, external storage, or network required. */
public final class OcrInstrumentation extends Instrumentation {
    private Bundle arguments;

    @Override public void onCreate(Bundle arguments) {
        super.onCreate(arguments);
        this.arguments = arguments == null ? new Bundle() : new Bundle(arguments);
        start(); // Android invokes onStart on the instrumentation thread, not the UI thread.
    }

    @Override public void onStart() {
        String id = arguments.getString("request_id");
        File directory = null;
        JSONObject result;
        try {
            if (Looper.myLooper() == Looper.getMainLooper()) {
                throw new IllegalStateException("OCR cannot run on the main thread");
            }
            if (!OcrRequest.validId(id)) {
                throw new Failure("INVALID_REQUEST", "request_id must be 32 lowercase hexadecimal characters");
            }
            directory = requestDirectory(id);
            // Wait for application/provider startup. ML Kit's merged init provider initializes
            // the SDK in the target process, including when launched by self-instrumentation.
            waitForIdleSync();
            result = recognize(readRequest(directory, id), directory);
        } catch (Failure error) {
            result = errorResult(id, error.code, error.getMessage());
        } catch (OutOfMemoryError error) {
            result = errorResult(id, "INTERNAL_ERROR", "Insufficient memory to complete OCR");
        } catch (Exception | LinkageError error) {
            result = errorResult(id, "INTERNAL_ERROR", safeMessage(error));
            if (error instanceof InterruptedException) Thread.currentThread().interrupt();
        }

        Bundle status = new Bundle();
        boolean published = false;
        if (directory != null) {
            try {
                writeResult(directory, result);
                published = true;
                status.putString("result_file", "files/requests/" + id + "/result.json");
            } catch (IOException error) {
                result = errorResult(id, "INTERNAL_ERROR", "Cannot publish result.json: " + safeMessage(error));
            }
        }
        // An invalid ID or an unwritable directory has no safe result path. Always expose
        // the error envelope in instrumentation status so a host can diagnose transport errors.
        boolean ok = published && result.optBoolean("ok", false);
        status.putBoolean("ok", ok);
        if (!ok) status.putString("response", result.toString());
        finish(ok ? 0 : -1, status);
    }

    private File requestDirectory(String id) throws IOException, Failure {
        File root = getTargetContext().getFilesDir().getCanonicalFile();
        File requests = checkedChild(root, "requests");
        File directory = checkedChild(requests, id);
        if (!directory.isDirectory() && !directory.mkdirs()) {
            throw new IOException("Cannot create private request directory");
        }
        return directory;
    }

    private static File checkedChild(File parent, String name) throws IOException, Failure {
        File child = new File(parent, name);
        if (!child.getCanonicalFile().equals(child.getAbsoluteFile())) {
            throw new Failure("INVALID_REQUEST", "Symbolic links and path aliases are not allowed");
        }
        return child;
    }

    private static OcrRequest readRequest(File directory, String id) throws Failure {
        try {
            File file = checkedChild(directory, "request.json");
            if (!file.isFile() || file.length() > OcrRequest.MAX_REQUEST_BYTES) {
                throw new IllegalArgumentException("request.json must exist and be at most 16384 bytes");
            }
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (FileInputStream input = new FileInputStream(file)) {
                byte[] buffer = new byte[4096];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    if (bytes.size() + count > OcrRequest.MAX_REQUEST_BYTES) {
                        throw new IllegalArgumentException("request.json exceeds 16384 bytes");
                    }
                    bytes.write(buffer, 0, count);
                }
            }
            String json = StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(bytes.toByteArray())).toString();
            JSONTokener parser = new JSONTokener(json);
            Object value = parser.nextValue();
            if (!(value instanceof JSONObject) || parser.nextClean() != 0) {
                throw new IllegalArgumentException("request.json must contain one JSON object");
            }
            return OcrRequest.parse((JSONObject) value, id);
        } catch (IOException | JSONException | IllegalArgumentException error) {
            throw new Failure("INVALID_REQUEST", safeMessage(error));
        }
    }

    private JSONObject recognize(OcrRequest request, File directory) throws Exception {
        long decodeStart = SystemClock.elapsedRealtimeNanos();
        File input = checkedChild(directory, "input.png");
        if (!input.isFile() || input.length() == 0) {
            throw new Failure("DECODE_FAILED", "Missing or empty input.png");
        }
        if (input.length() > OcrRequest.MAX_INPUT_BYTES) {
            throw new Failure("INVALID_REQUEST", "input.png exceeds 32 MiB");
        }
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(input.getAbsolutePath(), bounds);
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) {
            throw new Failure("DECODE_FAILED", "Cannot read image dimensions");
        }
        try {
            request.validateDimensions(bounds.outWidth, bounds.outHeight);
        } catch (IllegalArgumentException error) {
            throw new Failure("INVALID_REQUEST", safeMessage(error));
        }
        // Reject, never silently downsample. Allow heap room for source, transformed bitmap,
        // and ML Kit/native buffers. This deliberately may refuse a legal-size image on a
        // low-memory runtime rather than attempt an allocation known to be unsafe.
        long pixels = (long) bounds.outWidth * bounds.outHeight;
        long transformedPixels = request.roi == null ? pixels
                : (long) (request.roi[2] - request.roi[0]) * (request.roi[3] - request.roi[1]);
        long estimatedBytes = pixels * 4 + transformedPixels * 8 + 32L * 1024 * 1024;
        Runtime runtime = Runtime.getRuntime();
        long available = runtime.maxMemory() - (runtime.totalMemory() - runtime.freeMemory());
        if (estimatedBytes > available) {
            throw new Failure("DECODE_FAILED", "Image exceeds available decode/OCR memory budget");
        }
        Bitmap bitmap;
        try {
            BitmapFactory.Options options = new BitmapFactory.Options();
            options.inPreferredConfig = Bitmap.Config.ARGB_8888;
            options.inSampleSize = 1;
            options.inScaled = false;
            bitmap = BitmapFactory.decodeFile(input.getAbsolutePath(), options);
            if (bitmap == null) throw new Failure("DECODE_FAILED", "Cannot decode input.png");
            if (bitmap.getWidth() != bounds.outWidth || bitmap.getHeight() != bounds.outHeight) {
                bitmap.recycle();
                throw new Failure("DECODE_FAILED", "Image changed during decoding");
            }
            if (request.roi != null || request.rotation != 0) {
                int[] roi = request.roi == null
                        ? new int[]{0, 0, bounds.outWidth, bounds.outHeight} : request.roi;
                Matrix matrix = new Matrix();
                matrix.postRotate(request.rotation);
                Bitmap transformed = Bitmap.createBitmap(bitmap, roi[0], roi[1],
                        roi[2] - roi[0], roi[3] - roi[1], matrix, false);
                if (transformed != bitmap) bitmap.recycle();
                bitmap = transformed;
            }
        } catch (OutOfMemoryError error) {
            throw new Failure("DECODE_FAILED", "Insufficient memory to decode/transform image");
        } catch (IllegalArgumentException error) {
            throw new Failure("DECODE_FAILED", safeMessage(error));
        }
        double decodeMs = elapsedMs(decodeStart);
        long initStart = SystemClock.elapsedRealtimeNanos();
        TextRecognizer recognizer = null;
        Text text;
        JSONArray runs = new JSONArray();
        double initMs;
        try {
            InputImage image = InputImage.fromBitmap(bitmap, 0);
            recognizer = recognizer(request.script);
            initMs = elapsedMs(initStart);
            text = null;
            for (int i = 0; i < request.runs; i++) {
                long runStart = SystemClock.elapsedRealtimeNanos();
                text = Tasks.await(recognizer.process(image), 30, TimeUnit.SECONDS);
                runs.put(elapsedMs(runStart));
            }
        } catch (TimeoutException error) {
            throw new Failure("TIMEOUT", "OCR run exceeded 30 seconds");
        } catch (ExecutionException | RuntimeException error) {
            throw new Failure("OCR_FAILED", safeMessage(error));
        } finally {
            if (recognizer != null) recognizer.close();
            // Do not recycle this bitmap: an asynchronously timed-out task may still use it.
        }
        if (text == null) throw new Failure("OCR_FAILED", "Recognizer returned no result");
        JSONObject image = new JSONObject()
                .put("source_width", bounds.outWidth).put("source_height", bounds.outHeight)
                .put("width", bitmap.getWidth()).put("height", bitmap.getHeight())
                .put("rotation", request.rotation)
                .put("roi", request.roi == null ? JSONObject.NULL : new JSONArray(request.roi));
        JSONObject timing = new JSONObject().put("decode_ms", decodeMs)
                .put("init_ms", initMs).put("runs_ms", runs);
        return envelope(request.id, true).put("text", text.getText()).put("script", request.script)
                .put("image", image).put("timing", timing).put("blocks", blocks(text));
    }

    private static TextRecognizer recognizer(String script) {
        switch (script) {
            case "chinese": return TextRecognition.getClient(new ChineseTextRecognizerOptions.Builder().build());
            case "devanagari": return TextRecognition.getClient(new DevanagariTextRecognizerOptions.Builder().build());
            case "japanese": return TextRecognition.getClient(new JapaneseTextRecognizerOptions.Builder().build());
            case "korean": return TextRecognition.getClient(new KoreanTextRecognizerOptions.Builder().build());
            case "latin": return TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
            default: throw new IllegalArgumentException("Unsupported script");
        }
    }

    private static JSONArray blocks(Text text) throws JSONException {
        JSONArray blocks = new JSONArray();
        for (Text.TextBlock block : text.getTextBlocks()) {
            JSONObject blockJson = node(block.getText(), block.getBoundingBox(),
                    block.getCornerPoints(), block.getRecognizedLanguage());
            JSONArray lines = new JSONArray();
            for (Text.Line line : block.getLines()) {
                JSONObject lineJson = node(line.getText(), line.getBoundingBox(),
                        line.getCornerPoints(), line.getRecognizedLanguage())
                        .put("confidence", confidence(line.getConfidence()));
                JSONArray elements = new JSONArray();
                for (Text.Element element : line.getElements()) {
                    elements.put(node(element.getText(), element.getBoundingBox(),
                            element.getCornerPoints(), element.getRecognizedLanguage())
                            .put("confidence", confidence(element.getConfidence())));
                }
                lines.put(lineJson.put("elements", elements));
            }
            blocks.put(blockJson.put("lines", lines));
        }
        return blocks;
    }

    private static JSONObject node(String text, Rect bounds, Point[] points, String language)
            throws JSONException {
        JSONArray corners = new JSONArray();
        if (points != null) {
            for (Point point : points) corners.put(new JSONArray(new int[]{point.x, point.y}));
        }
        return new JSONObject().put("text", text)
                .put("bounds", bounds == null ? JSONObject.NULL
                        : new JSONArray(new int[]{bounds.left, bounds.top, bounds.right, bounds.bottom}))
                .put("corner_points", corners).put("recognized_language", language);
    }

    private static Object confidence(float value) {
        // Bundled 16.0.1 exposes real primitive-float confidence for lines and elements.
        return Float.isNaN(value) || Float.isInfinite(value) || value < 0 || value > 1
                ? JSONObject.NULL : value;
    }

    private static double elapsedMs(long start) {
        return (SystemClock.elapsedRealtimeNanos() - start) / 1_000_000.0;
    }

    private static JSONObject envelope(String id, boolean ok) throws JSONException {
        return new JSONObject().put("schema_version", 1)
                .put("id", id == null ? JSONObject.NULL : id).put("ok", ok);
    }

    private static JSONObject errorResult(String id, String code, String message) {
        try {
            return envelope(id, false).put("error",
                    new JSONObject().put("code", code).put("message", message));
        } catch (JSONException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private static String safeMessage(Throwable error) {
        String message = error.getMessage();
        return message == null || message.isEmpty() ? error.getClass().getSimpleName() : message;
    }

    private static void writeResult(File directory, JSONObject result) throws IOException {
        File temporary = File.createTempFile("result-", ".tmp", directory);
        try {
            try (FileOutputStream stream = new FileOutputStream(temporary)) {
                stream.write(result.toString().getBytes(StandardCharsets.UTF_8));
                stream.getFD().sync();
            }
            try {
                Os.rename(temporary.getAbsolutePath(), new File(directory, "result.json").getAbsolutePath());
            } catch (ErrnoException error) {
                throw new IOException("Atomic result rename failed", error);
            }
        } finally {
            if (temporary.exists() && !temporary.delete()) temporary.deleteOnExit();
        }
    }

    private static final class Failure extends Exception {
        final String code;
        Failure(String code, String message) {
            super(message);
            this.code = code;
        }
    }
}
