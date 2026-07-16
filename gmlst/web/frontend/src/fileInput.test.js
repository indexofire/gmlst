import test from "node:test";
import assert from "node:assert/strict";

import { MAX_FILE_SIZE, readFileWithSizeCheck, parseSessionPayload } from "./fileInput.js";

test("MAX_FILE_SIZE is 64 MiB", () => {
  assert.equal(MAX_FILE_SIZE, 64 * 1024 * 1024);
});

test("readFileWithSizeCheck returns text for small files", async () => {
  const fakeFile = { size: 100, name: "test.tsv", text: () => Promise.resolve("hello") };
  const result = await readFileWithSizeCheck(fakeFile);
  assert.equal(result, "hello");
});

test("readFileWithSizeCheck rejects files exceeding limit", async () => {
  const fakeFile = {
    size: MAX_FILE_SIZE + 1,
    name: "big.tsv",
    text: () => Promise.resolve("x"),
  };
  await assert.rejects(
    () => readFileWithSizeCheck(fakeFile),
    /too large/,
  );
});

test("parseSessionPayload parses valid JSON object", () => {
  const result = parseSessionPayload('{"a": 1}');
  assert.deepEqual(result, { a: 1 });
});

test("parseSessionPayload rejects non-object JSON", () => {
  assert.throws(() => parseSessionPayload('"hello"'), /JSON object/);
  assert.throws(() => parseSessionPayload("42"), /JSON object/);
  assert.throws(() => parseSessionPayload("null"), /JSON object/);
});

test("parseSessionPayload rejects invalid JSON", () => {
  assert.throws(() => parseSessionPayload("not json"), SyntaxError);
});
