export function textValue(value) {
  return String(value ?? "").trim();
}

export function nullableTextValue(value) {
  const text = textValue(value);
  return text || null;
}
