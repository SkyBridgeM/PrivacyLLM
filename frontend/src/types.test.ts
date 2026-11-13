import { expect, test } from "vitest";
import { cpLength, cpSlice, utf16ToCodePoint, overlap } from "./types";
test("code point boundaries survive emoji, supplementary CJK and combining characters", () => {
  const text = "😀𠮷e\u0301张敏";
  expect(cpLength(text)).toBe(6);
  expect(cpSlice(text, 4, 6)).toBe("张敏");
  expect(utf16ToCodePoint(text, text.indexOf("张"))).toBe(4);
});
test("adjacent ranges do not overlap", () => {
  expect(overlap({ start: 0, end: 2 }, { start: 2, end: 4 })).toBe(false);
  expect(overlap({ start: 0, end: 3 }, { start: 2, end: 4 })).toBe(true);
});
